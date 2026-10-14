"""Subprocess entry point for one trusted, local plugin invocation."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from sentinel_core.contracts import PluginContext, PluginResult

MAX_REQUEST_BYTES = 256 * 1024


def _apply_resource_limits(
    cpu_seconds: int, memory_limit_bytes: int, max_output_bytes: int
) -> None:
    """Best-effort POSIX limits; process separation is not a hostile-code sandbox."""
    if os.name != "posix":
        return
    try:
        import resource

        limits = (
            (resource.RLIMIT_CPU, cpu_seconds),
            (resource.RLIMIT_AS, memory_limit_bytes),
            (resource.RLIMIT_FSIZE, max_output_bytes),
            (resource.RLIMIT_NOFILE, 64),
        )
        for resource_id, requested in limits:
            _, hard_limit = resource.getrlimit(resource_id)
            effective = (
                min(requested, hard_limit) if hard_limit != resource.RLIM_INFINITY else requested
            )
            resource.setrlimit(resource_id, (effective, effective))
    except (ImportError, OSError, ValueError):
        # The outer wall-clock timeout and output cap still apply if POSIX limits are unavailable.
        return


def _load_plugin(plugin_file: Path, class_name: str) -> Any:
    """Load exactly one validated Python file without adding its folder to sys.path."""
    resolved_file = plugin_file.resolve(strict=True)
    if not resolved_file.is_file() or resolved_file.suffix != ".py":
        raise ValueError("plugin entrypoint is not a Python source file")
    module_name = f"sentinel_local_plugin_{resolved_file.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, resolved_file)
    if spec is None or spec.loader is None:
        raise ValueError("plugin module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plugin_class = getattr(module, class_name, None)
    if plugin_class is None or not isinstance(plugin_class, type):
        raise ValueError("plugin class is missing")
    return plugin_class()


async def _execute(request: dict[str, Any]) -> PluginResult:
    plugin = _load_plugin(Path(request["plugin_file"]), request["class_name"])
    context = PluginContext.create(
        plugin_id=request["plugin_id"],
        plugin_version=request["plugin_version"],
        plugin_api_version=request["plugin_api_version"],
        seed=request["seed"],
        input_data=request["input"],
        market_context=request.get("market_context"),
    )
    result = await plugin.run(context)
    if not isinstance(result, PluginResult):
        result = PluginResult.model_validate(result)
    return result


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        sys.stdout.write('{"ok":false,"error":"request_too_large"}')
        return 2

    try:
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        _apply_resource_limits(
            int(request["cpu_seconds"]),
            int(request["memory_limit_bytes"]),
            int(request["max_output_bytes"]),
        )
        # Keep the worker's stdout reserved for the one-line JSON protocol.
        with contextlib.redirect_stdout(sys.stderr):
            result = asyncio.run(_execute(request))
        response = {"ok": True, "result": result.model_dump(mode="json")}
        encoded = json.dumps(response, allow_nan=False, sort_keys=True, separators=(",", ":"))
        sys.stdout.write(encoded)
        sys.stdout.flush()
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stdout.write('{"ok":false,"error":"plugin_execution_failed"}')
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
