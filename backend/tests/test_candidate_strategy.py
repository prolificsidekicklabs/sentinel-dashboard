from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from sentinel_core.adapters.ports import DataQuality, MarketSnapshot, OHLCVBar
from sentinel_core.candidate_strategy import (
    CandidateClass,
    CandidateRiskGate,
    CandidateSignal,
    TechnicalIndicatorValues,
)

NOW = datetime(2026, 10, 11, 20, 0, tzinfo=UTC)


def _market(*, quality: DataQuality = DataQuality.VALID, days_old: int = 1) -> MarketSnapshot:
    latest = NOW - timedelta(days=days_old)
    bars = tuple(
        OHLCVBar(
            instrument_id="SPY",
            observed_at=latest - timedelta(days=199 - index),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.00"),
            volume=Decimal("1000"),
            currency="USD",
            source_id="alpaca:iex",
        )
        for index in range(200)
    )
    return MarketSnapshot(
        instrument_id="SPY",
        timeframe="1Day",
        source_id="alpaca:iex",
        observed_at=latest,
        received_at=NOW,
        quality=quality,
        bars=bars,
    )


def _signal(market: MarketSnapshot, candidate: CandidateClass) -> CandidateSignal:
    return CandidateSignal(
        instrument_id="SPY",
        timeframe="1Day",
        as_of=market.observed_at,
        bar_count=len(market.bars),
        candidate=candidate,
        reason_codes=["test_candidate"],
        indicators=TechnicalIndicatorValues(
            rsi_14=55.0,
            macd=1.2,
            macd_signal=1.0,
            macd_histogram=0.2,
            ema_50=110.0,
            ema_100=105.0,
            ema_200=100.0,
            last_close=112.0,
        ),
    )


def test_candidate_can_only_pass_to_human_review_not_execution() -> None:
    market = _market()
    signal = _signal(market, CandidateClass.BULLISH)

    review = CandidateRiskGate().evaluate(signal, market, evaluated_at=NOW)

    assert review.disposition == "review_required"
    assert review.eligible_for_human_review is True
    assert review.execution_enabled is False
    assert "human_review_required" in review.reason_codes
    assert "position_sizing_not_evaluated" in review.unassessed_risks
    assert "account_exposure_not_evaluated" in review.unassessed_risks


def test_no_candidate_does_not_enter_human_review_or_execution() -> None:
    market = _market()
    signal = _signal(market, CandidateClass.NONE)

    review = CandidateRiskGate().evaluate(signal, market, evaluated_at=NOW)

    assert review.disposition == "no_candidate"
    assert review.eligible_for_human_review is False
    assert review.execution_enabled is False


@pytest.mark.parametrize(
    ("quality", "days_old", "expected_reason"),
    [
        (DataQuality.STALE, 1, "market_data_quality_not_valid"),
        (DataQuality.VALID, 8, "market_observation_stale"),
    ],
)
def test_invalid_quality_or_stale_observations_are_blocked(
    quality: DataQuality, days_old: int, expected_reason: str
) -> None:
    market = _market(quality=quality, days_old=days_old)
    signal = _signal(market, CandidateClass.BULLISH)

    review = CandidateRiskGate().evaluate(signal, market, evaluated_at=NOW)

    assert review.disposition == "blocked"
    assert review.eligible_for_human_review is False
    assert review.execution_enabled is False
    assert expected_reason in review.reason_codes


def test_signal_instrument_or_bar_count_mismatch_is_blocked() -> None:
    market = _market()
    signal = _signal(market, CandidateClass.BULLISH).model_copy(update={"instrument_id": "QQQ"})

    review = CandidateRiskGate().evaluate(signal, market, evaluated_at=NOW)

    assert review.disposition == "blocked"
    assert "instrument_mismatch" in review.reason_codes


def test_history_below_minimum_is_blocked() -> None:
    full_market = _market()
    short_market = replace(full_market, bars=full_market.bars[:-1])
    signal = _signal(full_market, CandidateClass.BULLISH)

    review = CandidateRiskGate().evaluate(signal, short_market, evaluated_at=NOW)

    assert review.disposition == "blocked"
    assert "insufficient_history" in review.reason_codes
    assert "bar_count_mismatch" in review.reason_codes


def test_signal_contract_rejects_any_execution_enabled_value() -> None:
    market = _market()
    payload = _signal(market, CandidateClass.BULLISH).model_dump(mode="json")
    payload["execution_enabled"] = True

    with pytest.raises(ValidationError):
        CandidateSignal.model_validate(payload)


def test_gate_requires_timezone_aware_evaluation_time() -> None:
    market = _market()
    signal = _signal(market, CandidateClass.BULLISH)

    with pytest.raises(ValueError, match="timezone"):
        CandidateRiskGate().evaluate(
            signal,
            market,
            evaluated_at=datetime(2026, 10, 11, 20, 0),
        )
