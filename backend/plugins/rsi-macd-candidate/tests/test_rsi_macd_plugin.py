from __future__ import annotations

import asyncio
import importlib.util
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from sentinel_core.candidate_strategy import CandidateClass
from sentinel_core.contracts import PluginContext

PLUGIN_PATH = Path(__file__).resolve().parents[1] / "plugin.py"
SPEC = importlib.util.spec_from_file_location("rsi_macd_candidate_plugin", PLUGIN_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _input(prices: list[float], *, timeframe: str = "1Day") -> dict[str, Any]:
    end = datetime(2026, 10, 9, 20, 0, tzinfo=UTC)
    bars = [
        {
            "instrument_id": "SPY",
            "observed_at": (end - timedelta(days=len(prices) - index - 1)).isoformat(),
            "close": str(price),
        }
        for index, price in enumerate(prices)
    ]
    return {
        "instrument_id": "spy",
        "timeframe": timeframe,
        "observed_at": end.isoformat(),
        "bars": bars,
    }


def test_wilder_rsi_uses_recursive_smoothing_not_a_rolling_average() -> None:
    value = MODULE._wilder_rsi([1.0, 2.0, 3.0, 2.0, 1.0], period=3)

    assert value == pytest.approx(44.44444444444444)


def test_flat_series_has_finite_neutral_rsi() -> None:
    assert MODULE._wilder_rsi([100.0] * 201, period=14) == 50.0


def test_short_history_returns_typed_non_executable_no_candidate() -> None:
    context = PluginContext.create(
        plugin_id="rsi-macd-candidate",
        plugin_version="0.1.0",
        seed=0,
        input_data=_input([100.0 + index for index in range(40)]),
    )

    result = asyncio.run(MODULE.RsiMacdCandidatePlugin().run(context))
    signal = result.output["signal"]

    assert signal["candidate"] == CandidateClass.NONE.value
    assert signal["reason_codes"] == ["insufficient_history"]
    assert signal["indicators"] is None
    assert signal["execution_enabled"] is False


def test_indicator_snapshot_is_finite_and_repeatable() -> None:
    prices = [100.0 + index * 0.02 + 1.5 * math.sin(index / 5) for index in range(240)]
    request = _input(prices)
    context = PluginContext.create(
        plugin_id="rsi-macd-candidate",
        plugin_version="0.1.0",
        seed=17,
        input_data=request,
    )
    plugin = MODULE.RsiMacdCandidatePlugin()

    first = asyncio.run(plugin.run(context)).model_dump(mode="json")
    second = asyncio.run(plugin.run(context)).model_dump(mode="json")

    assert first == second
    signal = first["output"]["signal"]
    assert signal["bar_count"] == 240
    assert signal["execution_enabled"] is False
    assert set(signal["indicators"]) == {
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "ema_50",
        "ema_100",
        "ema_200",
        "last_close",
    }
    assert 0 <= signal["indicators"]["rsi_14"] <= 100
    assert signal["candidate"] in {
        "bullish_candidate",
        "bearish_candidate",
        "no_candidate",
    }


def test_uptrend_and_downtrend_can_emit_only_directional_candidate_labels() -> None:
    fixtures = (
        (
            [
                100.0 + 0.03 * index + 0.3 * math.sin(2 * math.pi * index / 4 + 2.2)
                for index in range(240)
            ],
            CandidateClass.BULLISH.value,
        ),
        (
            [
                100.0 - 0.03 * index + 0.3 * math.sin(2 * math.pi * index / 4)
                for index in range(240)
            ],
            CandidateClass.BEARISH.value,
        ),
    )

    for prices, expected_candidate in fixtures:
        context = PluginContext.create(
            plugin_id="rsi-macd-candidate",
            plugin_version="0.1.0",
            seed=0,
            input_data=_input(prices),
        )
        signal = asyncio.run(MODULE.RsiMacdCandidatePlugin().run(context)).output["signal"]

        assert signal["candidate"] == expected_candidate
        assert signal["execution_enabled"] is False


def test_invalid_timeframe_unsorted_bars_and_non_finite_closes_are_rejected() -> None:
    valid = _input([100.0 + index for index in range(10)])
    plugin = MODULE.RsiMacdCandidatePlugin()

    bad_timeframe = {**valid, "timeframe": "1Hour"}
    context = PluginContext.create(
        plugin_id="rsi-macd-candidate",
        plugin_version="0.1.0",
        seed=0,
        input_data=bad_timeframe,
    )
    with pytest.raises(ValueError, match="1Day"):
        asyncio.run(plugin.run(context))

    unsorted = {**valid, "bars": list(reversed(valid["bars"]))}
    context = PluginContext.create(
        plugin_id="rsi-macd-candidate",
        plugin_version="0.1.0",
        seed=0,
        input_data=unsorted,
    )
    with pytest.raises(ValueError, match="chronological"):
        asyncio.run(plugin.run(context))

    non_finite = _input([100.0] * 5)
    non_finite["bars"][2]["close"] = "NaN"
    context = PluginContext.create(
        plugin_id="rsi-macd-candidate",
        plugin_version="0.1.0",
        seed=0,
        input_data=non_finite,
    )
    with pytest.raises(ValueError, match="finite positive"):
        asyncio.run(plugin.run(context))


def test_mismatched_snapshot_timestamp_is_rejected() -> None:
    payload = _input([100.0, 101.0, 102.0])
    payload["observed_at"] = (datetime(2026, 10, 10, tzinfo=UTC)).isoformat()
    context = PluginContext.create(
        plugin_id="rsi-macd-candidate",
        plugin_version="0.1.0",
        seed=0,
        input_data=payload,
    )

    with pytest.raises(ValueError, match="latest bar"):
        asyncio.run(MODULE.RsiMacdCandidatePlugin().run(context))
