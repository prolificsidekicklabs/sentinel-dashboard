"""Offline deterministic checks for the repository's reviewed plugin fixtures."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sentinel_core.adapters.ports import DataQuality, MarketSnapshot, OHLCVBar
from sentinel_core.candidate_strategy import CandidateRiskGate, CandidateSignal
from sentinel_core.contracts import (
    PLUGIN_API_VERSION,
    PluginMarketBarV1,
    PluginMarketContextV1,
    PluginRunRequest,
)
from sentinel_core.manifest import PluginType
from sentinel_core.runtime import PluginRuntime

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins"
FIXED_NOW = datetime(2026, 10, 11, 20, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Stable summary of one offline plugin contract/determinism check."""

    plugin_id: str
    plugin_version: str
    plugin_api_version: str
    output_sha256: str
    deterministic: bool
    candidate_disposition: str | None = None


def _candidate_fixture() -> tuple[PluginRunRequest, MarketSnapshot]:
    """Build a deterministic synthetic daily-bar snapshot without network access."""
    prices = [
        100.0 + 0.03 * index + 0.3 * math.sin(2 * math.pi * index / 4 + 2.2) for index in range(240)
    ]
    observed_at = FIXED_NOW - timedelta(days=1)
    domain_bars: list[OHLCVBar] = []
    plugin_bars: list[PluginMarketBarV1] = []
    for index, price in enumerate(prices):
        timestamp = observed_at - timedelta(days=len(prices) - index - 1)
        close = Decimal(str(price))
        opening = close
        high = close + Decimal("1")
        low = close - Decimal("1")
        domain_bars.append(
            OHLCVBar(
                instrument_id="SPY",
                observed_at=timestamp,
                open=opening,
                high=high,
                low=low,
                close=close,
                volume=Decimal("1000"),
                currency="USD",
                source_id="offline:fixture",
            )
        )
        plugin_bars.append(
            PluginMarketBarV1(
                instrument_id="SPY",
                observed_at=timestamp,
                open=opening,
                high=high,
                low=low,
                close=close,
                volume=Decimal("1000"),
                currency="USD",
                source_id="offline:fixture",
            )
        )

    market = MarketSnapshot(
        instrument_id="SPY",
        timeframe="1Day",
        source_id="offline:fixture",
        observed_at=observed_at,
        received_at=FIXED_NOW,
        quality=DataQuality.VALID,
        bars=tuple(domain_bars),
    )
    plugin_context = PluginMarketContextV1(
        plugin_api_version=PLUGIN_API_VERSION,
        instrument_id="SPY",
        timeframe="1Day",
        source_id="offline:fixture",
        quality="valid",
        observed_at=observed_at,
        received_at=FIXED_NOW,
        bars=tuple(plugin_bars),
    )
    return (
        PluginRunRequest(
            plugin_api_version=PLUGIN_API_VERSION,
            seed=0,
            input={},
            market_context=plugin_context,
        ),
        market,
    )


def _fixture_for(plugin_id: str) -> tuple[PluginRunRequest, MarketSnapshot | None]:
    if plugin_id == "moving-average":
        return (
            PluginRunRequest(
                plugin_api_version=PLUGIN_API_VERSION,
                seed=7,
                input={"instrument": "OFFLINE", "prices": [9, 10, 11, 12], "window": 3},
            ),
            None,
        )
    if plugin_id == "rsi-macd-candidate":
        return _candidate_fixture()
    raise ValueError(f"offline validation fixture is not defined for plugin {plugin_id!r}")


async def validate_builtin_plugins(plugin_root: Path = PLUGIN_ROOT) -> tuple[ValidationResult, ...]:
    """Run each fixture twice and require stable, typed, research-only output."""
    runtime = PluginRuntime(plugin_root)
    manifests = runtime.list_plugins()
    if not manifests:
        raise ValueError("no plugin manifests were discovered for offline validation")

    results: list[ValidationResult] = []
    for manifest in manifests:
        request, market = _fixture_for(manifest.plugin_id)
        if manifest.plugin_api_version != PLUGIN_API_VERSION:
            raise ValueError(f"plugin {manifest.plugin_id!r} uses an unsupported API version")
        if not manifest.deterministic:
            raise ValueError(f"plugin {manifest.plugin_id!r} is not declared deterministic")

        first = await runtime.run(manifest.plugin_id, request)
        second = await runtime.run(manifest.plugin_id, request)
        if first.output_sha256 != second.output_sha256:
            raise ValueError(f"plugin {manifest.plugin_id!r} produced non-deterministic output")

        disposition: str | None = None
        if manifest.plugin_type is PluginType.STRATEGY:
            if market is None:
                raise ValueError("strategy fixtures require an independent market snapshot")
            raw_signal: Any = first.result.output.get("signal")
            signal = CandidateSignal.model_validate(raw_signal)
            if signal.execution_enabled is not False:
                raise ValueError("candidate strategy output must keep execution disabled")
            review = CandidateRiskGate().evaluate(signal, market, evaluated_at=FIXED_NOW)
            if review.execution_enabled is not False:
                raise ValueError("candidate review output must keep execution disabled")
            disposition = review.disposition
        elif market is not None:
            raise ValueError("non-strategy fixture unexpectedly supplied a market snapshot")

        results.append(
            ValidationResult(
                plugin_id=manifest.plugin_id,
                plugin_version=manifest.version,
                plugin_api_version=manifest.plugin_api_version,
                output_sha256=first.output_sha256,
                deterministic=True,
                candidate_disposition=disposition,
            )
        )
    return tuple(results)


def main() -> int:
    """Run the offline fixture suite as ``python -m sentinel_core.validation_harness``."""
    report = asyncio.run(validate_builtin_plugins())
    print(json.dumps([asdict(result) for result in report], sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
