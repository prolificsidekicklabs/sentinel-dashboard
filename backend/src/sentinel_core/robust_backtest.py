"""Dependency-light chronological walk-forward evaluation for research only.

The engine fixes strategy parameters before evaluation, uses only completed-bar
signals and next-bar opens, resets each test fold to flat, and never emits orders.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sentinel_core.adapters.ports import DataQuality, MarketSnapshot, OHLCVBar

ENGINE_VERSION = "walk-forward-sma-1.0.0"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    fast_period: int = 10
    slow_period: int = 30
    starting_capital: Decimal = Decimal("10000")
    allocation_pct: Decimal = Decimal("0.95")
    commission_bps: Decimal = Decimal("1")
    half_spread_bps: Decimal = Decimal("2")
    slippage_bps: Decimal = Decimal("3")
    folds: int = 5

    def __post_init__(self) -> None:
        if self.fast_period < 2 or self.slow_period <= self.fast_period:
            raise ValueError("SMA periods must satisfy 2 <= fast < slow")
        if not Decimal("0") < self.starting_capital <= Decimal("100000000"):
            raise ValueError("starting capital is outside the allowed range")
        if not Decimal("0") < self.allocation_pct <= Decimal("1"):
            raise ValueError("allocation percentage must be in (0, 1]")
        for name in ("commission_bps", "half_spread_bps", "slippage_bps"):
            value = getattr(self, name)
            if not Decimal("0") <= value <= Decimal("1000"):
                raise ValueError(f"{name} must be between 0 and 1,000 basis points")
        if not 2 <= self.folds <= 10:
            raise ValueError("fold count must be between 2 and 10")


def _bar_payload(bar: OHLCVBar) -> dict[str, str | None]:
    return {
        "instrument_id": bar.instrument_id,
        "observed_at": bar.observed_at.astimezone(UTC).isoformat(),
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": str(bar.volume) if bar.volume is not None else None,
        "currency": bar.currency,
        "source_id": bar.source_id,
    }


def dataset_sha256(bars: tuple[OHLCVBar, ...]) -> str:
    canonical = json.dumps(
        [_bar_payload(bar) for bar in bars], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sma(values: list[Decimal], end: int, period: int) -> Decimal | None:
    if end + 1 < period:
        return None
    return sum(values[end - period + 1 : end + 1], Decimal("0")) / Decimal(period)


def _check_market(market: MarketSnapshot, now: datetime) -> None:
    if market.quality is not DataQuality.VALID:
        raise ValueError("market data quality must be valid")
    if market.timeframe not in {"1Day", "1D"} or not market.source_id.startswith("alpaca:"):
        raise ValueError("backtest requires daily bars from the configured Alpaca provider")
    if len(market.bars) < 30:
        raise ValueError("at least 30 daily bars are required for walk-forward evaluation")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("evaluation time must include a timezone")
    if market.received_at > now + timedelta(minutes=2):
        raise ValueError("market data receipt timestamp is in the future")
    if (now - market.received_at.astimezone(UTC)).total_seconds() > 300:
        raise ValueError("market data snapshot is too old to start a backtest")
    last = market.bars[-1]
    if last.observed_at != market.observed_at or last.source_id != market.source_id:
        raise ValueError("market snapshot provenance does not match its latest bar")
    observation_age = now.astimezone(UTC) - last.observed_at.astimezone(UTC)
    if observation_age < -timedelta(minutes=2) or observation_age > timedelta(days=7):
        raise ValueError("latest market observation is too far in the past or future")
    if any(
        bar.instrument_id != market.instrument_id
        or bar.source_id != market.source_id
        or bar.currency != "USD"
        for bar in market.bars
    ):
        raise ValueError("market bars contain mixed instruments, sources, or currencies")
    if list(bar.observed_at for bar in market.bars) != sorted(
        set(bar.observed_at for bar in market.bars)
    ):
        raise ValueError("market bars must be strictly chronological")


def _run_segment(
    bars: tuple[OHLCVBar, ...],
    *,
    start: int,
    end: int,
    warmup_start: int,
    config: BacktestConfig,
    cost_multiplier: Decimal,
) -> dict[str, Any]:
    closes = [bar.close for bar in bars]
    cash = config.starting_capital
    quantity = Decimal("0")
    entry_costs = Decimal("0")
    trade_pnls: list[Decimal] = []
    costs_paid = Decimal("0")
    curve: list[Decimal] = []
    benchmark_cash = config.starting_capital
    benchmark_qty = Decimal("0")
    benchmark_curve: list[Decimal] = []
    fee_rate = config.commission_bps * cost_multiplier / Decimal("10000")
    adverse_rate = (
        (config.half_spread_bps + config.slippage_bps) * cost_multiplier / Decimal("10000")
    )
    if adverse_rate >= Decimal("1"):
        raise ValueError("stressed transaction costs make fill assumptions invalid")

    for i in range(start, end):
        bar = bars[i]
        prior = i - 1
        if prior >= 0 and i > warmup_start:
            fast_prev = _sma(closes, prior - 1, config.fast_period)
            slow_prev = _sma(closes, prior - 1, config.slow_period)
            fast_now = _sma(closes, prior, config.fast_period)
            slow_now = _sma(closes, prior, config.slow_period)
            if (
                fast_prev is not None
                and slow_prev is not None
                and fast_now is not None
                and slow_now is not None
            ):
                enter = fast_prev <= slow_prev and fast_now > slow_now
                exit_ = fast_prev >= slow_prev and fast_now < slow_now
                if enter and quantity == 0:
                    fill = bar.open * (Decimal("1") + adverse_rate)
                    budget = cash * config.allocation_pct
                    new_quantity = budget / (fill * (Decimal("1") + fee_rate))
                    commission = new_quantity * fill * fee_rate
                    outflow = new_quantity * fill + commission
                    cash -= outflow
                    costs_paid += commission + new_quantity * bar.open * adverse_rate
                    quantity = new_quantity
                    entry_costs = outflow
                elif exit_ and quantity > 0:
                    fill = bar.open * (Decimal("1") - adverse_rate)
                    commission = quantity * fill * fee_rate
                    proceeds = quantity * fill - commission
                    trade_pnls.append(proceeds - entry_costs)
                    costs_paid += commission + quantity * bar.open * adverse_rate
                    cash += proceeds
                    quantity = Decimal("0")

        if i == start:
            benchmark_fill = bar.open * (Decimal("1") + adverse_rate)
            benchmark_budget = benchmark_cash * config.allocation_pct
            benchmark_qty = benchmark_budget / (benchmark_fill * (Decimal("1") + fee_rate))
            benchmark_cost = benchmark_qty * benchmark_fill * fee_rate
            benchmark_cash -= benchmark_qty * benchmark_fill + benchmark_cost
        curve.append(cash + quantity * bar.close)
        benchmark_curve.append(benchmark_cash + benchmark_qty * bar.close)

    # Remaining holdings are valued at the last close with an adverse-cost liquidation estimate.
    if quantity > 0:
        last = bars[end - 1]
        fill = last.close * (Decimal("1") - adverse_rate)
        commission = quantity * fill * fee_rate
        proceeds = quantity * fill - commission
        trade_pnls.append(proceeds - entry_costs)
        costs_paid += commission + quantity * last.close * adverse_rate
        cash += proceeds
        curve[-1] = cash
    if not curve or not benchmark_curve:
        raise ValueError("test fold contains no bars")

    def metrics(values: list[Decimal], pnls: list[Decimal] | None = None) -> dict[str, Any]:
        starting = config.starting_capital
        final = values[-1]
        running_max = starting
        max_drawdown = Decimal("0")
        for value in values:
            running_max = max(running_max, value)
            if running_max > 0:
                max_drawdown = max(max_drawdown, (running_max - value) / running_max)
        daily_returns = [
            float(values[index] / values[index - 1] - 1)
            for index in range(1, len(values))
            if values[index - 1] > 0
        ]
        mean = sum(daily_returns) / len(daily_returns) if daily_returns else 0.0
        variance = (
            sum((value - mean) ** 2 for value in daily_returns) / (len(daily_returns) - 1)
            if len(daily_returns) > 1
            else 0.0
        )
        volatility = math.sqrt(variance * 252)
        sharpe = mean / math.sqrt(variance) * math.sqrt(252) if variance > 0 else None
        elapsed_days = max(
            (bars[end - 1].observed_at - bars[start].observed_at).total_seconds() / 86400, 1
        )
        cagr = (
            float((final / starting) ** (Decimal("365.25") / Decimal(str(elapsed_days))) - 1)
            if final > 0
            else None
        )
        return {
            "starting_equity": str(starting),
            "ending_equity": str(final.quantize(Decimal("0.01"))),
            "total_return_pct": float((final / starting - 1) * 100),
            "cagr_pct": cagr * 100 if cagr is not None else None,
            "annualized_volatility_pct": volatility * 100,
            "sharpe_zero_risk_free": sharpe,
            "max_drawdown_pct": float(max_drawdown * 100),
            "closed_trades": len(pnls or []),
            "win_rate_pct": (sum(1 for pnl in (pnls or []) if pnl > 0) / len(pnls) * 100)
            if pnls
            else None,
        }

    return {
        "start_date": bars[start].observed_at.astimezone(UTC).date().isoformat(),
        "end_date": bars[end - 1].observed_at.astimezone(UTC).date().isoformat(),
        "bar_count": end - start,
        "strategy": metrics(curve, trade_pnls),
        "buy_and_hold": metrics(benchmark_curve),
        "modeled_costs": str(costs_paid.quantize(Decimal("0.01"))),
        "cost_multiplier": str(cost_multiplier),
    }


def run_walk_forward_backtest(
    market: MarketSnapshot,
    config: BacktestConfig,
    *,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Run fixed-parameter rolling folds and deterministic cost stress scenarios."""
    now = evaluated_at or datetime.now(UTC)
    _check_market(market, now)
    bars = market.bars
    minimum_test_bars = max(5, config.slow_period // 2)
    available = len(bars) - config.slow_period
    fold_size = available // config.folds
    if fold_size < minimum_test_bars:
        raise ValueError("history is too short for the requested walk-forward folds and warm-up")

    folds: list[dict[str, Any]] = []
    first_test_start = config.slow_period
    for fold_index in range(config.folds):
        start = first_test_start + fold_index * fold_size
        end = len(bars) if fold_index == config.folds - 1 else min(len(bars), start + fold_size)
        if end - start < minimum_test_bars:
            raise ValueError("walk-forward fold is too short")
        folds.append(
            _run_segment(
                bars,
                start=start,
                end=end,
                warmup_start=max(0, start - config.slow_period - 2),
                config=config,
                cost_multiplier=Decimal("1"),
            )
        )

    stress = [
        {
            "cost_multiplier": multiplier,
            "folds": [
                _run_segment(
                    bars,
                    start=first_test_start + index * fold_size,
                    end=len(bars)
                    if index == config.folds - 1
                    else min(len(bars), first_test_start + (index + 1) * fold_size),
                    warmup_start=max(
                        0, first_test_start + index * fold_size - config.slow_period - 2
                    ),
                    config=config,
                    cost_multiplier=Decimal(multiplier),
                )
                for index in range(config.folds)
            ],
        }
        for multiplier in ("1", "2", "3")
    ]
    parameters = {
        "fast_period": config.fast_period,
        "slow_period": config.slow_period,
        "starting_capital": str(config.starting_capital),
        "allocation_pct": str(config.allocation_pct),
        "commission_bps_per_side": str(config.commission_bps),
        "half_spread_bps_per_side": str(config.half_spread_bps),
        "slippage_bps_per_side": str(config.slippage_bps),
        "folds": config.folds,
    }
    record: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "strategy_id": "sma-crossover-long-only",
        "instrument_id": market.instrument_id,
        "source_id": market.source_id,
        "timeframe": market.timeframe,
        "dataset_sha256": dataset_sha256(bars),
        "input_bar_count": len(bars),
        "input_start": bars[0].observed_at.astimezone(UTC).isoformat(),
        "input_end": bars[-1].observed_at.astimezone(UTC).isoformat(),
        "parameters": parameters,
        "folds": folds,
        "cost_sensitivity": stress,
        "execution_enabled": False,
        "limitations": [
            "fixed user-selected parameters; no parameter fitting or multiple-testing correction",
            "next-bar-open fills are estimates, not executable fills",
            "no corporate actions, dividends, taxes, halts, partial fills, market impact, "
            "or venue lot rules",
            "no statistical significance test; results do not establish a strategy edge",
        ],
    }
    canonical = json.dumps(record, allow_nan=False, sort_keys=True, separators=(",", ":"))
    record["run_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return record


__all__ = ["BacktestConfig", "ENGINE_VERSION", "dataset_sha256", "run_walk_forward_backtest"]
