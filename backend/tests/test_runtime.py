from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from sentinel_core.contracts import PluginRunRequest
from sentinel_core.runtime import (
    PluginInputTooLarge,
    PluginPermissionDenied,
    PluginRuntime,
    PluginTimeout,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BUILTIN_PLUGINS = BACKEND_ROOT / "plugins"


def test_local_plugin_runs_in_separate_process_with_stable_digest() -> None:
    runtime = PluginRuntime(BUILTIN_PLUGINS)
    request = PluginRunRequest(
        seed=7,
        input={"instrument": "DEMO", "prices": [9.0, 10.0, 11.0, 12.0], "window": 3},
    )

    first = asyncio.run(runtime.run("moving-average", request))
    second = asyncio.run(runtime.run("moving-average", request))

    assert first.worker_pid != os.getpid()
    assert second.worker_pid != os.getpid()
    assert first.output_sha256 == second.output_sha256
    assert first.result.output["simple_moving_average"] == 11.0
    assert first.result.output["instrument"] == "DEMO"


def _write_plugin(plugin_root: Path, *, permission: str = "", source: str | None = None) -> None:
    plugin_dir = plugin_root / "seeded-test"
    plugin_dir.mkdir(parents=True)
    permissions = f"[{permission}]" if permission else "[]"
    (plugin_dir / "sentinel_manifest.yaml").write_text(
        "manifest_version: '1.0'\n"
        "plugin_id: seeded-test\n"
        "name: Seeded test plugin\n"
        "version: 0.1.0\n"
        "plugin_type: indicator\n"
        "entrypoint: plugin:SeededPlugin\n"
        f"permissions: {permissions}\n"
        "deterministic: true\n"
        "description: A runtime test fixture.\n",
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(
        source
        or "from sentinel_core.contracts import PluginContext, PluginResult\n"
        "class SeededPlugin:\n"
        "    async def run(self, context: PluginContext) -> PluginResult:\n"
        "        return PluginResult(output={'draw': context.rng.random()})\n",
        encoding="utf-8",
    )


def test_explicit_seed_reproduces_random_values_and_changes_with_seed(tmp_path: Path) -> None:
    _write_plugin(tmp_path)
    runtime = PluginRuntime(tmp_path)

    first = asyncio.run(runtime.run("seeded-test", PluginRunRequest(seed=123, input={})))
    repeated = asyncio.run(runtime.run("seeded-test", PluginRunRequest(seed=123, input={})))
    other_seed = asyncio.run(runtime.run("seeded-test", PluginRunRequest(seed=124, input={})))

    assert first.output_sha256 == repeated.output_sha256
    assert first.output_sha256 != other_seed.output_sha256


def test_plugin_permission_is_denied_by_default(tmp_path: Path) -> None:
    _write_plugin(tmp_path, permission="network.egress")
    runtime = PluginRuntime(tmp_path)

    with pytest.raises(PluginPermissionDenied):
        asyncio.run(runtime.run("seeded-test", PluginRunRequest(seed=1, input={})))


def test_serialized_input_limit_is_enforced(tmp_path: Path) -> None:
    runtime = PluginRuntime(BUILTIN_PLUGINS, max_input_bytes=80)
    request = PluginRunRequest(seed=1, input={"large": "x" * 200})

    with pytest.raises(PluginInputTooLarge):
        asyncio.run(runtime.run("moving-average", request))


def test_plugin_wall_clock_timeout_kills_worker(tmp_path: Path) -> None:
    _write_plugin(
        tmp_path,
        source=(
            "import asyncio\n"
            "from sentinel_core.contracts import PluginContext, PluginResult\n"
            "class SeededPlugin:\n"
            "    async def run(self, context: PluginContext) -> PluginResult:\n"
            "        await asyncio.sleep(5)\n"
            "        return PluginResult(output={})\n"
        ),
    )
    runtime = PluginRuntime(tmp_path, timeout_seconds=0.25, cpu_seconds=2)

    with pytest.raises(PluginTimeout):
        asyncio.run(runtime.run("seeded-test", PluginRunRequest(seed=1, input={})))
