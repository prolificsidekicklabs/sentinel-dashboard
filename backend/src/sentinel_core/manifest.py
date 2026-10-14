"""Safe loading and validation for Sentinel plugin manifests."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

MAX_MANIFEST_BYTES = 64 * 1024
_PLUGIN_ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
_ENTRYPOINT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:[A-Z][A-Za-z0-9_]*$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class PluginType(StrEnum):
    """Supported plugin categories in the versioned local manifest contract."""

    AGENT = "agent"
    ENGINE = "engine"
    INDICATOR = "indicator"
    STRATEGY = "strategy"
    RISK_MODEL = "risk_model"
    SCREENER = "screener"
    DATA_CONNECTOR = "data_connector"
    MCP_BRIDGE = "mcp_bridge"


class PluginPermission(StrEnum):
    """Capability names; none are granted by default in this foundation."""

    MARKET_DATA_READ = "market_data.read"
    NETWORK_EGRESS = "network.egress"


class PluginManifest(BaseModel):
    """Machine-readable, versioned metadata for one local plugin."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: str = Field(pattern=r"^1\.0$")
    plugin_api_version: Literal["1.0"]
    plugin_id: str = Field(min_length=3, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=5, max_length=80)
    plugin_type: PluginType
    entrypoint: str = Field(min_length=3, max_length=100)
    trust_level: Literal["repository-reviewed", "untrusted"] = "repository-reviewed"
    permissions: tuple[PluginPermission, ...] = ()
    deterministic: bool
    description: str = Field(min_length=1, max_length=500)

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        if not _PLUGIN_ID_RE.fullmatch(value):
            raise ValueError("plugin_id must use lowercase letters, digits, dots, or hyphens")
        return value

    @field_validator("version")
    @classmethod
    def valid_semver(cls, value: str) -> str:
        if not _SEMVER_RE.fullmatch(value):
            raise ValueError("version must be a semantic version")
        return value

    @field_validator("entrypoint")
    @classmethod
    def valid_entrypoint(cls, value: str) -> str:
        if not _ENTRYPOINT_RE.fullmatch(value):
            raise ValueError("entrypoint must use the form module:PluginClass")
        return value

    @field_validator("permissions")
    @classmethod
    def unique_permissions(
        cls, value: tuple[PluginPermission, ...]
    ) -> tuple[PluginPermission, ...]:
        if len(set(value)) != len(value):
            raise ValueError("permissions must not contain duplicates")
        return value


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


class ManifestError(ValueError):
    """Raised when a manifest cannot be safely read or validated."""


def load_manifest(path: Path) -> PluginManifest:
    """Read one bounded YAML file using safe parsing and strict schema validation."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ManifestError("manifest could not be read") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ManifestError(f"manifest exceeds the {MAX_MANIFEST_BYTES}-byte limit")

    try:
        data = yaml.load(raw, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ManifestError("manifest contains invalid or unsafe YAML") from exc
    if not isinstance(data, dict) or any(not isinstance(key, str) for key in data):
        raise ManifestError("manifest root must be a mapping with string keys")

    try:
        return PluginManifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestError(f"manifest schema validation failed: {exc}") from exc
