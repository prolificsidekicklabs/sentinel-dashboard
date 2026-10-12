"""Pure deterministic RSI/MACD/EMA candidate analysis; no SDK, network, or order APIs."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any, Literal

from sentinel_core.candidate_strategy import (
    CandidateClass,
    CandidateSignal,
    TechnicalIndicatorValues,
)
from sentinel_core.contracts import PluginContext, PluginResult

MINIMUM_BARS = 200
MAXIMUM_BARS = 1000
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
EMA_FAST = 50
EMA_MID = 100
EMA_SLOW = 200
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,20}$")


def _parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _parse_closes(data: Any) -> tuple[str, Literal["1Day"], datetime, list[float]]:
    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    instrument = data.get("instrument_id")
    if not isinstance(instrument, str) or not _SYMBOL_RE.fullmatch(instrument.strip().upper()):
        raise ValueError("instrument_id must be a valid ticker symbol")
    normalized_instrument = instrument.strip().upper()
    if data.get("timeframe") != "1Day":
        raise ValueError("this candidate strategy supports only the 1Day timeframe")
    timeframe: Literal["1Day"] = "1Day"

    bars: Any = data.get("bars")
    if not isinstance(bars, list) or len(bars) > MAXIMUM_BARS:
        raise ValueError(f"bars must be a list with no more than {MAXIMUM_BARS} entries")
    closes: list[float] = []
    timestamps: list[datetime] = []
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bars[{index}] must be an object")
        bar_instrument = bar.get("instrument_id", normalized_instrument)
        if (
            not isinstance(bar_instrument, str)
            or bar_instrument.strip().upper() != normalized_instrument
        ):
            raise ValueError(f"bars[{index}] instrument_id does not match the request")
        timestamp = _parse_timestamp(bar.get("observed_at"), f"bars[{index}].observed_at")
        if timestamps and timestamp <= timestamps[-1]:
            raise ValueError("bars must be strictly chronological and have unique timestamps")
        raw_close = bar.get("close")
        if isinstance(raw_close, bool) or not isinstance(raw_close, (str, int, float)):
            raise ValueError(f"bars[{index}].close must be a finite positive number")
        try:
            close = float(raw_close)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"bars[{index}].close must be a finite positive number") from exc
        if not math.isfinite(close) or close <= 0:
            raise ValueError(f"bars[{index}].close must be a finite positive number")
        timestamps.append(timestamp)
        closes.append(close)

    if timestamps:
        as_of = timestamps[-1]
        supplied_as_of = data.get("observed_at")
        if supplied_as_of is not None and _parse_timestamp(supplied_as_of, "observed_at") != as_of:
            raise ValueError("observed_at must match the latest bar")
    else:
        as_of = _parse_timestamp(data.get("observed_at"), "observed_at")
    return normalized_instrument, timeframe, as_of, closes


def _wilder_rsi(prices: list[float], period: int) -> float | None:
    """Calculate RSI using the initial arithmetic seed and Wilder's recursive smoothing."""
    if period < 1 or len(prices) <= period:
        return None
    deltas = [current - previous for previous, current in zip(prices, prices[1:], strict=False)]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:], strict=True):
        average_gain = ((period - 1) * average_gain + gain) / period
        average_loss = ((period - 1) * average_loss + loss) / period
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0
    return 100.0 - (100.0 / (1.0 + average_gain / average_loss))


def _ema_series(values: list[float], period: int) -> list[float | None]:
    """Return a seeded EMA series aligned to its input, using an initial SMA seed."""
    if period < 1:
        raise ValueError("EMA period must be positive")
    if len(values) < period:
        return [None] * len(values)
    result: list[float | None] = [None] * (period - 1)
    current = sum(values[:period]) / period
    result.append(current)
    alpha = 2.0 / (period + 1.0)
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
        result.append(current)
    return result


def _macd_values(prices: list[float]) -> tuple[float, float, float] | None:
    """Calculate MACD with SMA-seeded fast/slow EMA lines and signal EMA."""
    fast = _ema_series(prices, MACD_FAST)
    slow = _ema_series(prices, MACD_SLOW)
    macd_line = [
        fast_value - slow_value
        for fast_value, slow_value in zip(fast, slow, strict=True)
        if fast_value is not None and slow_value is not None
    ]
    signal_line = _ema_series(macd_line, MACD_SIGNAL)
    if not macd_line or not signal_line or signal_line[-1] is None:
        return None
    macd = macd_line[-1]
    signal = signal_line[-1]
    return macd, signal, macd - signal


def _round(value: float) -> float:
    rounded = round(value, 10)
    if not math.isfinite(rounded):
        raise ValueError("indicator computation returned a non-finite value")
    return rounded


class RsiMacdCandidatePlugin:
    """Emit a directional candidate label without sizing, orders, or provider access."""

    async def run(self, context: PluginContext) -> PluginResult:
        instrument, timeframe, as_of, closes = _parse_closes(context.input_data)
        bar_count = len(closes)
        if bar_count < MINIMUM_BARS:
            signal = CandidateSignal(
                instrument_id=instrument,
                timeframe=timeframe,
                as_of=as_of,
                bar_count=bar_count,
                candidate=CandidateClass.NONE,
                reason_codes=["insufficient_history"],
                indicators=None,
            )
            return PluginResult(output={"signal": signal.model_dump(mode="json")})

        rsi = _wilder_rsi(closes, RSI_PERIOD)
        ema_fast = _ema_series(closes, EMA_FAST)[-1]
        ema_mid = _ema_series(closes, EMA_MID)[-1]
        ema_slow = _ema_series(closes, EMA_SLOW)[-1]
        macd = _macd_values(closes)
        if rsi is None or ema_fast is None or ema_mid is None or ema_slow is None or macd is None:
            raise ValueError("insufficient bars for the configured indicators")
        macd_line, macd_signal, macd_histogram = macd

        if ema_fast > ema_mid > ema_slow and macd_line > macd_signal and rsi < 70.0:
            candidate = CandidateClass.BULLISH
            reasons = ["ema_stack_bullish", "macd_above_signal", "rsi_below_overbought_threshold"]
        elif ema_fast < ema_mid < ema_slow and macd_line < macd_signal and rsi > 30.0:
            candidate = CandidateClass.BEARISH
            reasons = ["ema_stack_bearish", "macd_below_signal", "rsi_above_oversold_threshold"]
        else:
            candidate = CandidateClass.NONE
            reasons = ["indicator_conditions_not_aligned"]

        indicators = TechnicalIndicatorValues(
            rsi_14=_round(rsi),
            macd=_round(macd_line),
            macd_signal=_round(macd_signal),
            macd_histogram=_round(macd_histogram),
            ema_50=_round(ema_fast),
            ema_100=_round(ema_mid),
            ema_200=_round(ema_slow),
            last_close=_round(closes[-1]),
        )
        signal = CandidateSignal(
            instrument_id=instrument,
            timeframe=timeframe,
            as_of=as_of,
            bar_count=bar_count,
            candidate=candidate,
            reason_codes=reasons,
            indicators=indicators,
        )
        return PluginResult(output={"signal": signal.model_dump(mode="json")})
