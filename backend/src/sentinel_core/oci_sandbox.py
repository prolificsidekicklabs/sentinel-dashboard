"""Fail-closed gVisor OCI sandbox runner for third-party Python plugins.

The trusted-local subprocess runner is not an adversarial security boundary. Untrusted
code runs only when an operator has built a reviewed, digest-pinned worker image and
configured rootless Docker with gVisor (runsc).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    """Raised when an isolated OCI runtime cannot safely be started or completed."""


class OCISandboxRunner:
    """Run a worker in an unprivileged, network-isolated gVisor container."""

    def __init__(
        self,
        *,
        image: str | None = None,
        runtime: str | None = None,
        memory_limit: str = "512m",
        cpu_limit: str = "1",
        pids_limit: int = 32,
        timeout_seconds: float = 5.0,
        max_output_bytes: int = 512 * 1024,
    ) -> None:
        self.image = (image or os.environ.get("SENTINEL_PLUGIN_SANDBOX_IMAGE", "")).strip()
        requested = runtime or os.environ.get("SENTINEL_OCI_RUNTIME", "docker")
        self.runtime = shutil.which(requested) or ""
        self.profile = os.environ.get("SENTINEL_OCI_PROFILE", "runsc").strip()
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        if (
            self.timeout_seconds <= 0
            or self.max_output_bytes < 1
            or self.pids_limit < 1
            or not re.fullmatch(r"[1-9][0-9]*[mMgG]", self.memory_limit)
            or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", self.cpu_limit)
        ):
            raise ValueError("OCI sandbox resource limits are invalid")

    def command(self, plugin_dir: Path, container_name: str) -> list[str]:
        if not self.image or not self.runtime or self.profile != "runsc":
            raise SandboxUnavailable("untrusted plugin sandbox runtime is not configured")
        if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", self.image):
            raise SandboxUnavailable("untrusted plugin sandbox image must be pinned by digest")
        resolved = plugin_dir.resolve(strict=True)
        if not resolved.is_dir():
            raise SandboxUnavailable("plugin source directory is invalid")
        return [
            self.runtime,
            "run",
            "--rm",
            "--interactive",
            f"--name={container_name}",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--runtime=runsc",
            f"--memory={self.memory_limit}",
            f"--cpus={self.cpu_limit}",
            f"--pids-limit={self.pids_limit}",
            "--user=65532:65532",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m",
            "--mount",
            f"type=bind,src={resolved},dst=/plugin,readonly",
            self.image,
            "python",
            "-m",
            "sentinel_core.worker",
        ]

    async def _remove_container(self, container_name: str) -> None:
        try:
            cleanup = await asyncio.create_subprocess_exec(
                self.runtime,
                "rm",
                "--force",
                container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(cleanup.wait(), timeout=3)
        except (OSError, TimeoutError):
            return

    async def run(self, plugin_dir: Path, payload: bytes, *, seed: int) -> tuple[bytes, int, int]:
        container_name = f"sentinel-plugin-{secrets.token_hex(12)}"
        worker_request = json.loads(payload)
        if not isinstance(worker_request, dict) or not isinstance(
            worker_request.get("plugin_file"), str
        ):
            raise SandboxUnavailable("plugin worker request is invalid")
        worker_request["plugin_file"] = f"/plugin/{Path(worker_request['plugin_file']).name}"
        encoded = json.dumps(
            worker_request, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        argv = self.command(plugin_dir, container_name)
        env = {"PATH": os.defpath, "PYTHONHASHSEED": str(seed), "PYTHONIOENCODING": "utf-8"}
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd="/tmp",
                env=env,
            )
        except (OSError, ValueError) as exc:
            raise SandboxUnavailable("isolated plugin container could not be started") from exc
        if process.stdout is None:
            raise SandboxUnavailable("isolated plugin output channel is unavailable")
        process_id = process.pid
        output = bytearray()

        async def collect_output() -> None:
            assert process.stdout is not None
            while True:
                chunk = await process.stdout.read(
                    min(65_536, self.max_output_bytes + 1 - len(output))
                )
                if not chunk:
                    return
                output.extend(chunk)
                if len(output) > self.max_output_bytes:
                    raise SandboxUnavailable("untrusted plugin output exceeded the sandbox limit")

        collector = asyncio.create_task(collect_output())
        waiter = asyncio.create_task(process.wait())

        async def stop_process() -> None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()

        async def feed_input() -> None:
            if process.stdin is None:
                raise SandboxUnavailable("isolated plugin input channel is unavailable")
            process.stdin.write(encoded)
            await process.stdin.drain()
            process.stdin.close()

        async def run_to_completion() -> None:
            await feed_input()
            await asyncio.gather(collector, waiter)

        try:
            await asyncio.wait_for(run_to_completion(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            await stop_process()
            await self._remove_container(container_name)
            raise SandboxUnavailable("untrusted plugin exceeded the sandbox timeout") from exc
        except SandboxUnavailable:
            await stop_process()
            await self._remove_container(container_name)
            raise
        except OSError as exc:
            await stop_process()
            await self._remove_container(container_name)
            raise SandboxUnavailable("isolated plugin I/O failed") from exc
        except asyncio.CancelledError:
            await stop_process()
            await self._remove_container(container_name)
            raise
        if process.returncode != 0:
            await self._remove_container(container_name)
            raise SandboxUnavailable("isolated plugin container exited unsuccessfully")
        return bytes(output), int(process.returncode or 0), process_id


__all__ = ["OCISandboxRunner", "SandboxUnavailable"]
