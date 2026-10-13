from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from sentinel_core.adapters.ports import DataQuality, MarketSnapshot, OHLCVBar
from sentinel_core.robust_backtest import (
    BacktestConfig,
    _run_segment,
    dataset_sha256,
    run_walk_forward_backtest,
)


def _market(
    count: int = 250, *, source: str = "alpaca:iex", receipt_age: timedelta = timedelta(seconds=1)
) -> MarketSnapshot:
    now = datetime.now(UTC)
    start = now - timedelta(days=count)
    bars: list[OHLCVBar] = []
    for index in range(count):
        close = (
            Decimal("100")
            + Decimal(index) / Decimal("10")
            + (Decimal("4") if index // 15 % 2 else Decimal("-3"))
        )
        open_price = close + Decimal("0.2")
        bars.append(
            OHLCVBar(
                "SPY",
                start + timedelta(days=index),
                open_price,
                max(open_price, close) + Decimal("1"),
                min(open_price, close) - Decimal("1"),
                close,
                Decimal("100000"),
                "USD",
                source,
            )
        )
    return MarketSnapshot(
        "SPY",
        "1Day",
        source,
        bars[-1].observed_at,
        now - receipt_age,
        DataQuality.VALID,
        tuple(bars),
    )


def test_walk_forward_results_are_reproducible_and_use_disjoint_chronological_folds() -> None:
    market = _market()
    config = BacktestConfig(fast_period=3, slow_period=8, folds=5)
    first = run_walk_forward_backtest(market, config)
    second = run_walk_forward_backtest(market, config)

    assert first == second
    assert first["execution_enabled"] is False
    assert len(first["folds"]) == 5
    for previous, current in zip(first["folds"], first["folds"][1:], strict=False):
        assert previous["end_date"] < current["start_date"]
    assert len(first["cost_sensitivity"]) == 3
    assert first["dataset_sha256"] == dataset_sha256(market.bars)
    assert len(first["run_id"]) == 64


def test_higher_cost_scenario_does_not_improve_test_fold_equity() -> None:
    result = run_walk_forward_backtest(
        _market(), BacktestConfig(fast_period=3, slow_period=8, folds=5)
    )
    baseline = result["cost_sensitivity"][0]["folds"]
    stressed = result["cost_sensitivity"][2]["folds"]
    assert all(
        Decimal(stress["strategy"]["ending_equity"]) <= Decimal(base["strategy"]["ending_equity"])
        for base, stress in zip(baseline, stressed, strict=True)
    )


def test_drawdown_includes_loss_from_starting_capital_on_first_test_bar() -> None:
    now = datetime.now(UTC)
    closes = (
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        Decimal("20"),
        Decimal("50"),
    )
    bars = tuple(
        OHLCVBar(
            "SPY",
            now + timedelta(days=index),
            Decimal("100") if index == 4 else close,
            Decimal("101"),
            Decimal("9"),
            close,
            Decimal("1000"),
            "USD",
            "alpaca:iex",
        )
        for index, close in enumerate(closes)
    )
    fold = _run_segment(
        bars,
        start=4,
        end=5,
        warmup_start=0,
        config=BacktestConfig(fast_period=2, slow_period=3, folds=2),
        cost_multiplier=Decimal("1"),
    )
    assert fold["strategy"]["max_drawdown_pct"] > 40


def test_walk_forward_rejects_unverified_stale_or_insufficient_data() -> None:
    with pytest.raises(ValueError, match="daily bars from the configured Alpaca provider"):
        run_walk_forward_backtest(
            _market(source="synthetic:fixture"), BacktestConfig(fast_period=3, slow_period=8)
        )
    with pytest.raises(ValueError, match="too old"):
        run_walk_forward_backtest(
            _market(receipt_age=timedelta(minutes=10)), BacktestConfig(fast_period=3, slow_period=8)
        )
    with pytest.raises(ValueError, match="at least 30"):
        run_walk_forward_backtest(_market(count=20), BacktestConfig(fast_period=3, slow_period=8))
