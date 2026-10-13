from __future__ import annotations

import asyncio

import pytest

import sentinel_core.oci_sandbox as sandbox_module
from sentinel_core.contracts import PluginRunRequest
from sentinel_core.manifest import PluginPermission
from sentinel_core.oci_sandbox import OCISandboxRunner, SandboxUnavailable
from sentinel_core.runtime import PluginRuntime, PluginSandboxUnavailable


def test_untrusted_runtime_requires_digest_pinned_image_and_gvisor(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(sandbox_module.shutil, "which", lambda _: "/usr/bin/docker")
    runner = OCISandboxRunner(image="plugin-runtime:latest")
    with pytest.raises(SandboxUnavailable, match="pinned by digest"):
        runner.command(tmp_path, "sentinel-plugin-abc")
    monkeypatch.setenv("SENTINEL_OCI_PROFILE", "default")
    runner = OCISandboxRunner(image="plugin-runtime@sha256:" + "a" * 64)
    with pytest.raises(SandboxUnavailable, match="not configured"):
        runner.command(tmp_path, "sentinel-plugin-abc")


def test_oci_command_is_read_only_networkless_unprivileged_and_resource_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(sandbox_module.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setenv("SENTINEL_OCI_PROFILE", "runsc")
    runner = OCISandboxRunner(image="plugin-runtime@sha256:" + "b" * 64)
    command = runner.command(tmp_path, "sentinel-plugin-test")
    joined = " ".join(command)
    for required in (
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--runtime=runsc",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=32",
        "--user=65532:65532",
        "readonly",
    ):
        assert required in joined


def test_untrusted_plugin_never_falls_back_to_local_worker(tmp_path) -> None:
    plugin_dir = tmp_path / "untrusted-example"
    plugin_dir.mkdir()
    (plugin_dir / "sentinel_manifest.yaml").write_text(
        """manifest_version: '1.0'
plugin_id: untrusted-example
name: Untrusted example
version: 1.0.0
plugin_type: indicator
entrypoint: plugin:ExamplePlugin
trust_level: untrusted
permissions: []
deterministic: true
description: Test plugin
""",
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text("class ExamplePlugin: pass\n", encoding="utf-8")
    runtime = PluginRuntime(tmp_path)
    with pytest.raises(PluginSandboxUnavailable):
        asyncio.run(runtime.run("untrusted-example", PluginRunRequest(seed=1, input={})))


def test_repository_reviewed_plugins_continue_using_bounded_local_runtime() -> None:
    runtime = PluginRuntime(
        __import__("pathlib").Path(__file__).parents[1] / "plugins",
        granted_permissions=frozenset(PluginPermission),
    )
    result = asyncio.run(
        runtime.run(
            "moving-average",
            PluginRunRequest(
                seed=3, input={"instrument": "DEMO", "prices": [1, 2, 3], "window": 2}
            ),
        )
    )
    assert result.result.output["simple_moving_average"] == 2.5
