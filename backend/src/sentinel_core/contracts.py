"""Typed contracts shared by the service, runtime, and local plugins."""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_SEED = 2**32 - 1


class PluginRunRequest(BaseModel):
    """JSON request supplied to one deterministic plugin execution."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(strict=True, ge=0, le=MAX_SEED)
    input: dict[str, Any]

    @field_validator("input")
    @classmethod
    def input_must_be_finite_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("input must contain only finite JSON-compatible values") from exc
        return value


class PluginResult(BaseModel):
    """Structured plugin output; values must serialize to finite JSON."""

    model_config = ConfigDict(extra="forbid")

    output: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("output")
    @classmethod
    def output_must_be_finite_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("output must contain only finite JSON-compatible values") from exc
        return value


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Per-run inputs and deterministic randomness; no implicit service clients."""

    plugin_id: str
    plugin_version: str
    seed: int
    input_data: Mapping[str, Any]
    rng: random.Random

    @classmethod
    def create(
        cls,
        *,
        plugin_id: str,
        plugin_version: str,
        seed: int,
        input_data: Mapping[str, Any],
    ) -> PluginContext:
        """Construct a fresh random generator for each run using the explicit seed."""
        return cls(
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            seed=seed,
            input_data=input_data,
            rng=random.Random(seed),
        )


class SentinelPlugin(Protocol):
    """Minimal asynchronous interface implemented by a reviewed local plugin."""

    async def run(self, context: PluginContext) -> PluginResult:
        """Execute one bounded analysis using only the supplied run context."""
        ...
