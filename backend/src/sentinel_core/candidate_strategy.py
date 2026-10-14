"""Typed, non-executing technical candidates and an independent review-only gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinel_core.adapters.ports import DataQuality, MarketSnapshot


class CandidateClass(StrEnum):
    """Directional research labels; these are not broker actions or recommendations."""

    BULLISH = "bullish_candidate"
    BEARISH = "bearish_candidate"
    NONE = "no_candidate"


class TechnicalIndicatorValues(BaseModel):
    """Finite, normalized indicator values produced by the deterministic plugin."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    rsi_14: float = Field(ge=0, le=100)
    macd: float
    macd_signal: float
    macd_histogram: float
    ema_50: float = Field(gt=0)
    ema_100: float = Field(gt=0)
    ema_200: float = Field(gt=0)
    last_close: float = Field(gt=0)


class CandidateSignal(BaseModel):
    """Versioned plugin output. Its execution flag is structurally fixed to false."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    plugin_id: Literal["rsi-macd-candidate"] = "rsi-macd-candidate"
    plugin_version: Literal["0.1.0"] = "0.1.0"
    instrument_id: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9.\-]+$")
    timeframe: Literal["1Day"]
    as_of: datetime
    bar_count: int = Field(ge=0, le=1000)
    candidate: CandidateClass
    reason_codes: tuple[str, ...] = ()
    indicators: TechnicalIndicatorValues | None = None
    execution_enabled: Literal[False] = False

    @field_validator("as_of")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value.astimezone(UTC)


class CandidateReview(BaseModel):
    """Independent, research-only gate result; never an order authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    policy_id: Literal["candidate-review-gate"] = "candidate-review-gate"
    policy_version: Literal["0.1.0"] = "0.1.0"
    disposition: Literal["blocked", "no_candidate", "review_required"]
    eligible_for_human_review: bool
    execution_enabled: Literal[False] = False
    evaluated_at: datetime
    reason_codes: tuple[str, ...]
    unassessed_risks: tuple[str, ...] = Field(
        default=(
            "account_exposure_not_evaluated",
            "position_sizing_not_evaluated",
            "stop_loss_and_drawdown_not_evaluated",
            "broker_execution_not_enabled",
        )
    )

    @field_validator("evaluated_at")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must include a timezone")
        return value.astimezone(UTC)


class CandidateRiskGate:
    """Fail-closed data and contract gate before any candidate reaches human review.

    This is deliberately not a position-risk model: it has no account, order, size,
    or execution input. Passing means only that the candidate is eligible for human
    review; execution remains disabled in every result.
    """

    policy_id = "candidate-review-gate"
    policy_version = "0.1.0"
    minimum_bars = 200
    maximum_observation_age = timedelta(days=7)
    maximum_receive_age = timedelta(minutes=15)
    future_clock_skew = timedelta(minutes=2)

    def evaluate(
        self,
        signal: CandidateSignal,
        market: MarketSnapshot,
        *,
        evaluated_at: datetime,
    ) -> CandidateReview:
        """Return blocked, no-candidate, or human-review-required without execution."""
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must include a timezone")
        now = evaluated_at.astimezone(UTC)
        blockers: list[str] = []
        checks: list[str] = []
        bar_count = len(market.bars)

        if market.quality is not DataQuality.VALID:
            blockers.append("market_data_quality_not_valid")
        else:
            checks.append("market_data_quality_valid")
        if market.instrument_id != signal.instrument_id:
            blockers.append("instrument_mismatch")
        if market.timeframe != signal.timeframe or market.timeframe != "1Day":
            blockers.append("timeframe_mismatch")
        if signal.bar_count != bar_count:
            blockers.append("bar_count_mismatch")
        if bar_count < self.minimum_bars:
            blockers.append("insufficient_history")
        else:
            checks.append("minimum_history_met")
        if signal.as_of != market.observed_at:
            blockers.append("observation_timestamp_mismatch")
        if not market.bars or market.bars[-1].observed_at != market.observed_at:
            blockers.append("latest_bar_timestamp_mismatch")
        if any(bar.source_id != market.source_id for bar in market.bars):
            blockers.append("market_source_mismatch")
        if bar_count >= self.minimum_bars and signal.indicators is None:
            blockers.append("indicator_output_missing")

        observation_age = now - market.observed_at.astimezone(UTC)
        if observation_age < -self.future_clock_skew:
            blockers.append("market_observation_in_future")
        elif observation_age > self.maximum_observation_age:
            blockers.append("market_observation_stale")
        elif bar_count:
            checks.append("market_observation_within_age_limit")

        receive_age = now - market.received_at.astimezone(UTC)
        if receive_age < -self.future_clock_skew:
            blockers.append("market_receive_timestamp_in_future")
        elif receive_age > self.maximum_receive_age:
            blockers.append("market_snapshot_stale")
        else:
            checks.append("market_snapshot_recently_received")

        if blockers:
            disposition: Literal["blocked", "no_candidate", "review_required"] = "blocked"
            eligible = False
            reasons = list(dict.fromkeys(blockers))
        elif signal.candidate is CandidateClass.NONE:
            disposition = "no_candidate"
            eligible = False
            reasons = checks + list(signal.reason_codes) + ["no_candidate_conditions_met"]
        else:
            disposition = "review_required"
            eligible = True
            reasons = checks + list(signal.reason_codes) + ["human_review_required"]

        return CandidateReview(
            disposition=disposition,
            eligible_for_human_review=eligible,
            evaluated_at=now,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )
