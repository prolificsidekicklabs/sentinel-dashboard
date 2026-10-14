from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_core.manifest import ManifestError, PluginType, load_manifest

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins"
SAMPLE_MANIFEST = PLUGIN_ROOT / "moving-average" / "sentinel_manifest.yaml"
STRATEGY_MANIFEST = PLUGIN_ROOT / "rsi-macd-candidate" / "sentinel_manifest.yaml"


def test_example_manifest_parses_into_typed_metadata() -> None:
    manifest = load_manifest(SAMPLE_MANIFEST)

    assert manifest.plugin_id == "moving-average"
    assert manifest.plugin_api_version == "1.0"
    assert manifest.plugin_type is PluginType.INDICATOR
    assert manifest.permissions == ()
    assert manifest.deterministic is True


def test_candidate_strategy_manifest_uses_the_strategy_category_without_permissions() -> None:
    manifest = load_manifest(STRATEGY_MANIFEST)

    assert manifest.plugin_id == "rsi-macd-candidate"
    assert manifest.plugin_type is PluginType.STRATEGY
    assert manifest.permissions == ()
    assert manifest.deterministic is True


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sentinel_manifest.yaml"
    manifest_path.write_text(
        "manifest_version: '1.0'\nplugin_id: first\nplugin_id: second\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="invalid or unsafe YAML"):
        load_manifest(manifest_path)


def test_unknown_manifest_fields_are_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sentinel_manifest.yaml"
    manifest_path.write_text(
        "manifest_version: '1.0'\n"
        "plugin_api_version: '1.0'\n"
        "plugin_id: sample\n"
        "name: Sample\n"
        "version: 1.0.0\n"
        "plugin_type: indicator\n"
        "entrypoint: plugin:SamplePlugin\n"
        "permissions: []\n"
        "deterministic: true\n"
        "description: A test plugin.\n"
        "unexpected: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="schema validation failed"):
        load_manifest(manifest_path)


def test_unsafe_yaml_tags_are_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "sentinel_manifest.yaml"
    manifest_path.write_text("!!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8")

    with pytest.raises(ManifestError, match="invalid or unsafe YAML"):
        load_manifest(manifest_path)
