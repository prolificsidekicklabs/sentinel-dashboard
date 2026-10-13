"""Local plugin discovery and bounded subprocess execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import signal
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from sentinel_core.contracts import PluginResult, PluginRunRequest
from sentinel_core.manifest import ManifestError, PluginManifest, PluginPermission, load_manifest

_PLUGIN_ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")


class PluginNotFound(RuntimeError):
    """Raised when a requested plugin is not installed in the local registry."""


class PluginPermissionDenied(RuntimeError):
    """Raised when the runtime has not granted a permission declared by a plugin."""


class PluginExecutionError(RuntimeError):
    """Raised when a plugin fails or returns an invalid result."""


class PluginTimeout(PluginExecutionError):
    """Raised when a plugin exceeds the runtime wall-clock limit."""


class PluginInputTooLarge(PluginExecutionError):
    """Raised when the serialized plugin request exceeds its byte limit."""


class PluginOutputTooLarge(PluginExecutionError):
    """Raised when the worker exceeds its bounded output channel."""


@dataclass(frozen=True, slots=True)
class PluginExecution:
    """Validated plugin output plus a deterministic digest and local worker PID."""

    plugin_id: str
    plugin_version: str
    seed: int
    result: PluginResult
    output_sha256: str
    worker_pid: int


class PluginRuntime:
    """Run repository-reviewed plugins in fresh, resource-bounded child processes.

    This provides process separation and best-effort resource limits, not a security
    boundary against malicious code. Only trusted local plugins should be enabled.
    """

    def __init__(
        self,
        plugin_root: Path,
        *,
        granted_permissions: frozenset[PluginPermission] = frozenset(),
        timeout_seconds: float = 5.0,
        cpu_seconds: int = 3,
        memory_limit_bytes: int = 512 * 1024 * 1024,
        max_input_bytes: int = 256 * 1024,
        max_output_bytes: int = 512 * 1024,
        max_concurrent_runs: int = 4,
    ) -> None:
        if timeout_seconds <= 0 or cpu_seconds < 1 or max_concurrent_runs < 1:
            raise ValueError("runtime limits must be positive")
        self.plugin_root = plugin_root.resolve()
        self.granted_permissions = granted_permissions
        self.timeout_seconds = timeout_seconds
        self.cpu_seconds = cpu_seconds
        self.memory_limit_bytes = memory_limit_bytes
        self.max_input_bytes = max_input_bytes
        self.max_output_bytes = max_output_bytes
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)

    def list_plugins(self) -> list[PluginManifest]:
        """Return validated manifests for the local plugin directories."""
        if not self.plugin_root.is_dir():
            return []
        manifests: list[PluginManifest] = []
        for directory in sorted(self.plugin_root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir():
                continue
            resolved_directory = directory.resolve()
            if not resolved_directory.is_relative_to(self.plugin_root):
                raise ManifestError("plugin directory resolves outside the configured root")
            manifest = load_manifest(resolved_directory / "sentinel_manifest.yaml")
            if manifest.plugin_id != directory.name:
                raise ManifestError("plugin_id must match its local directory name")
            manifests.append(manifest)
        return manifests

    def _resolve_plugin(self, plugin_id: str) -> tuple[Path, PluginManifest, Path, str]:
        if not _PLUGIN_ID_RE.fullmatch(plugin_id):
            raise PluginNotFound("plugin is not installed")
        directory = self.plugin_root / plugin_id
        try:
            resolved_directory = directory.resolve(strict=True)
        except OSError as exc:
            raise PluginNotFound("plugin is not installed") from exc
        if (
            not resolved_directory.is_relative_to(self.plugin_root)
            or not resolved_directory.is_dir()
        ):
            raise PluginNotFound("plugin is not installed")

        manifest = load_manifest(resolved_directory / "sentinel_manifest.yaml")
        if manifest.plugin_id != plugin_id or resolved_directory.name != plugin_id:
            raise ManifestError("plugin_id must match its local directory name")
        missing_permissions = set(manifest.permissions) - self.granted_permissions
        if missing_permissions:
            raise PluginPermissionDenied("plugin requests permissions not granted by this runtime")

        module_name, class_name = manifest.entrypoint.split(":", maxsplit=1)
        plugin_file = (resolved_directory / f"{module_name}.py").resolve()
        if not plugin_file.is_relative_to(resolved_directory) or not plugin_file.is_file():
            raise ManifestError("plugin entrypoint file is missing or outside its directory")
        return resolved_directory, manifest, plugin_file, class_name

    async def run(self, plugin_id: str, request: PluginRunRequest) -> PluginExecution:
        """Run one plugin with explicit input and a repeatable random seed."""
        directory, manifest, plugin_file, class_name = self._resolve_plugin(plugin_id)
        del directory  # Only the validated entrypoint path is needed by the worker.

        worker_request = {
            "plugin_id": manifest.plugin_id,
            "plugin_version": manifest.version,
            "plugin_file": str(plugin_file),
            "class_name": class_name,
            "seed": request.seed,
            "input": request.input,
            "cpu_seconds": self.cpu_seconds,
            "memory_limit_bytes": self.memory_limit_bytes,
            "max_output_bytes": self.max_output_bytes,
        }
        try:
            encoded_request = json.dumps(
                worker_request, allow_nan=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise PluginExecutionError("plugin request is not finite JSON") from exc
        if len(encoded_request) > self.max_input_bytes:
            raise PluginInputTooLarge("plugin request exceeds the configured byte limit")

        async with self._semaphore:
            response_bytes, return_code, worker_pid = await self._invoke_worker(
                encoded_request, request.seed
            )

        if len(response_bytes) > self.max_output_bytes:
            raise PluginOutputTooLarge("plugin output exceeds the configured byte limit")
        try:
            response = json.loads(response_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PluginExecutionError("plugin worker returned an invalid response") from exc
        if return_code != 0 or not isinstance(response, dict) or response.get("ok") is not True:
            raise PluginExecutionError("plugin execution failed")

        try:
            result = PluginResult.model_validate(response.get("result"))
            result_json = result.model_dump(mode="json")
            output_payload = {
                "plugin_id": manifest.plugin_id,
                "plugin_version": manifest.version,
                "seed": request.seed,
                "input": request.input,
                "result": result_json,
            }
            canonical = json.dumps(
                output_payload, allow_nan=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        except (ValidationError, TypeError, ValueError) as exc:
            raise PluginExecutionError("plugin returned output outside the JSON contract") from exc

        return PluginExecution(
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            seed=request.seed,
            result=result,
            output_sha256=hashlib.sha256(canonical).hexdigest(),
            worker_pid=worker_pid,
        )

    async def _invoke_worker(self, payload: bytes, seed: int) -> tuple[bytes, int, int]:
        """Invoke the worker with a clean environment and bounded file-backed output."""
        env = {
            "PATH": os.defpath,
            "PYTHONHASHSEED": str(seed),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONNOUSERSITE": "1",
        }
        if os.name == "nt" and "SYSTEMROOT" in os.environ:
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

        with tempfile.TemporaryDirectory(prefix="sentinel-plugin-") as working_directory:
            with tempfile.TemporaryFile(mode="w+b") as stdout_file:
                with tempfile.TemporaryFile(mode="w+b") as stderr_file:
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-m",
                        "sentinel_core.worker",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        cwd=working_directory,
                        env=env,
                        start_new_session=(os.name == "posix"),
                    )
                    try:
                        await asyncio.wait_for(
                            process.communicate(payload), timeout=self.timeout_seconds
                        )
                    except TimeoutError as exc:
                        self._kill_process_tree(process)
                        await process.wait()
                        raise PluginTimeout("plugin exceeded the wall-clock timeout") from exc
                    except asyncio.CancelledError:
                        self._kill_process_tree(process)
                        await process.wait()
                        raise

                    stdout_file.seek(0, os.SEEK_END)
                    output_size = stdout_file.tell()
                    if output_size > self.max_output_bytes:
                        raise PluginOutputTooLarge(
                            "plugin output exceeds the configured byte limit"
                        )
                    stdout_file.seek(0)
                    response_bytes = stdout_file.read(self.max_output_bytes + 1)
                    return response_bytes, int(process.returncode or 0), process.pid

    @staticmethod
    def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
        """Kill the worker process group on POSIX, or the direct process elsewhere."""
        if process.returncode is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
