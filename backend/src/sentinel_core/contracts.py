"""Versioned, read-only contracts shared by the service, runtime, and plugins."""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_SEED = 2**32 - 1
PLUGIN_API_VERSION: Literal["1.0"] = "1.0"
MAX_CONTEXT_BARS = 1000


class PluginRunRequest(BaseModel):
    """JSON request supplied to one deterministic plugin execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin_api_version: Literal["1.0"] = PLUGIN_API_VERSION
    seed: int = Field(strict=True, ge=0, le=MAX_SEED)
    input: dict[str, Any]
    market_context: PluginMarketContextV1 | None = None

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


class PluginMarketBarV1(BaseModel):
    """Immutable, normalized OHLCV bar exposed to plugins by contract version 1.0."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    instrument_id: str = Field(min_length=1, max_length=80)
    observed_at: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(min_length=1, max_length=12)
    source_id: str = Field(min_length=1, max_length=100)

    @field_validator("observed_at")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ohlc_must_be_consistent(self) -> PluginMarketBarV1:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC values are inconsistent")
        if self.high < self.low:
            raise ValueError("high must not be below low")
        return self


class PluginMarketContextV1(BaseModel):
    """Read-only, account-free market snapshot passed across the plugin boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    plugin_api_version: Literal["1.0"] = PLUGIN_API_VERSION
    instrument_id: str = Field(min_length=1, max_length=80)
    timeframe: str = Field(min_length=1, max_length=24)
    source_id: str = Field(min_length=1, max_length=100)
    quality: Literal["valid", "stale", "incomplete", "invalid", "unavailable"]
    observed_at: datetime
    received_at: datetime
    bars: tuple[PluginMarketBarV1, ...] = Field(max_length=MAX_CONTEXT_BARS)

    @field_validator("observed_at", "received_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("market timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def snapshot_must_be_consistent(self) -> PluginMarketContextV1:
        timestamps = tuple(bar.observed_at for bar in self.bars)
        if timestamps != tuple(sorted(timestamps)) or len(set(timestamps)) != len(timestamps):
            raise ValueError("market bars must be strictly chronological")
        if any(bar.instrument_id != self.instrument_id for bar in self.bars):
            raise ValueError("all market bars must match the snapshot instrument")
        if any(bar.source_id != self.source_id for bar in self.bars):
            raise ValueError("all market bars must match the snapshot source")
        if self.bars and self.bars[-1].observed_at != self.observed_at:
            raise ValueError("snapshot observed_at must match the latest bar")
        return self

    @property
    def closes(self) -> tuple[Decimal, ...]:
        """Return immutable close values in chronological order."""
        return tuple(bar.close for bar in self.bars)


def _freeze_json(value: Any) -> Any:
    """Recursively freeze a value already normalized through finite JSON."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Per-run inputs and deterministic randomness; no implicit service clients."""

    plugin_id: str
    plugin_version: str
    plugin_api_version: str
    seed: int
    input_data: Mapping[str, Any]
    rng: random.Random
    market_context: PluginMarketContextV1 | None = None

    @classmethod
    def create(
        cls,
        *,
        plugin_id: str,
        plugin_version: str,
        seed: int,
        input_data: Mapping[str, Any],
        plugin_api_version: str = PLUGIN_API_VERSION,
        market_context: PluginMarketContextV1 | Mapping[str, Any] | None = None,
    ) -> PluginContext:
        """Construct an isolated JSON input snapshot and seeded random generator."""
        try:
            copied_input = json.loads(
                json.dumps(dict(input_data), allow_nan=False, sort_keys=True, separators=(",", ":"))
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "plugin input must contain only finite JSON-compatible values"
            ) from exc
        if not isinstance(copied_input, dict) or any(
            not isinstance(key, str) for key in copied_input
        ):
            raise ValueError("plugin input must be a JSON object with string keys")
        if plugin_api_version != PLUGIN_API_VERSION:
            raise ValueError("unsupported plugin API version")
        if not 0 <= seed <= MAX_SEED:
            raise ValueError("plugin seed is outside the supported range")

        typed_market_context = (
            None if market_context is None else PluginMarketContextV1.model_validate(market_context)
        )
        return cls(
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            plugin_api_version=plugin_api_version,
            seed=seed,
            input_data=cast(Mapping[str, Any], _freeze_json(copied_input)),
            rng=random.Random(seed),
            market_context=typed_market_context,
        )


class SentinelPlugin(Protocol):
    """Minimal asynchronous interface implemented by a reviewed local plugin."""

    async def run(self, context: PluginContext) -> PluginResult:
        """Execute one bounded analysis using only the supplied run context."""
        ...
