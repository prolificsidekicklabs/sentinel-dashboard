from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from sentinel_core.contracts import (
    PLUGIN_API_VERSION,
    PluginContext,
    PluginMarketBarV1,
    PluginMarketContextV1,
    PluginRunRequest,
)


def _market_context() -> PluginMarketContextV1:
    bar = PluginMarketBarV1(
        instrument_id="SPY",
        observed_at=datetime(2026, 10, 11, 20, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1000"),
        currency="USD",
        source_id="fixture:daily",
    )
    return PluginMarketContextV1(
        instrument_id="SPY",
        timeframe="1Day",
        source_id="fixture:daily",
        quality="valid",
        observed_at=bar.observed_at,
        received_at=bar.observed_at,
        bars=(bar,),
    )


def test_plugin_context_defensively_copies_and_deeply_freezes_json_input() -> None:
    source = {"nested": {"values": [1, 2]}}
    context = PluginContext.create(
        plugin_id="test-plugin",
        plugin_version="1.0.0",
        seed=1,
        input_data=source,
    )
    source["nested"]["values"].append(3)

    assert context.plugin_api_version == PLUGIN_API_VERSION
    assert context.input_data["nested"]["values"] == (1, 2)
    with pytest.raises(TypeError):
        context.input_data["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        context.input_data["nested"]["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        context.input_data["nested"]["values"][0] = 9  # type: ignore[index]


def test_market_context_and_bars_are_typed_and_deeply_immutable() -> None:
    market = _market_context()
    context = PluginContext.create(
        plugin_id="test-plugin",
        plugin_version="1.0.0",
        seed=1,
        input_data={},
        market_context=market,
    )

    assert context.market_context is not None
    assert context.market_context.closes == (Decimal("100"),)
    with pytest.raises(ValidationError):
        context.market_context.bars[0].close = Decimal("1")
    with pytest.raises(ValidationError):
        context.market_context.bars = ()
    with pytest.raises(ValidationError):
        PluginMarketContextV1.model_validate({**market.model_dump(), "account": {"equity": "1000"}})


def test_plugin_api_version_is_explicit_and_unknown_versions_are_rejected() -> None:
    request = PluginRunRequest(seed=1, input={})

    assert request.plugin_api_version == PLUGIN_API_VERSION
    with pytest.raises(ValidationError):
        PluginRunRequest(plugin_api_version="2.0", seed=1, input={})
