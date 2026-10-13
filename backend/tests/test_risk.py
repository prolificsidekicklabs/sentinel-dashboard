from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sentinel_core.adapters.ports import (
    AccountSnapshot,
    DataQuality,
    MarketSnapshot,
    OHLCVBar,
    OrderIntent,
    OrderSide,
    OrderType,
    PositionSnapshot,
)
from sentinel_core.risk import PaperRiskEvaluator

NOW = datetime(2026, 10, 13, 19, 0, tzinfo=UTC)


def _market(
    *,
    age: timedelta = timedelta(minutes=1),
    quality: DataQuality = DataQuality.VALID,
    symbol: str = "SPY",
    source: str = "alpaca:iex",
) -> MarketSnapshot:
    observed = NOW - age
    bar = OHLCVBar(
        instrument_id=symbol,
        observed_at=observed,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1000"),
        currency="USD",
        source_id=source,
    )
    return MarketSnapshot(symbol, "1Min", source, observed, NOW, quality, (bar,))


def _account() -> AccountSnapshot:
    return AccountSnapshot(
        "paper", "USD", Decimal("10000"), Decimal("5000"), Decimal("5000"), NOW, "ACTIVE"
    )


def _order(
    *, side: OrderSide = OrderSide.BUY, quantity: str = "1", symbol: str = "SPY"
) -> OrderIntent:
    return OrderIntent("client-order-1", symbol, side, Decimal(quantity), OrderType.MARKET)


def test_fresh_allowlisted_order_is_approved_with_explicit_unassessed_risks() -> None:
    evaluation = PaperRiskEvaluator().evaluate(
        _order(), _account(), (), _market(), evaluated_at=NOW
    )
    assert evaluation.allowed is True
    assert evaluation.policy_id == "sentinel-paper-risk"
    assert evaluation.unassessed_risks


def test_risk_gate_blocks_stale_invalid_or_untrusted_market_data() -> None:
    evaluator = PaperRiskEvaluator()
    for snapshot in (
        _market(age=timedelta(minutes=6)),
        _market(quality=DataQuality.INCOMPLETE),
        _market(source="unverified:fixture"),
    ):
        result = evaluator.evaluate(_order(), _account(), (), snapshot, evaluated_at=NOW)
        assert result.allowed is False
        assert result.reasons


def test_risk_gate_rejects_unknown_or_non_active_account_state() -> None:
    account = AccountSnapshot(
        "paper", "USD", Decimal("10000"), Decimal("5000"), Decimal("5000"), NOW, "SUSPENDED"
    )
    result = PaperRiskEvaluator().evaluate(_order(), account, (), _market(), evaluated_at=NOW)
    assert result.allowed is False
    assert "account_not_active" in result.reasons


def test_risk_gate_rejects_currency_mismatches() -> None:
    evaluator = PaperRiskEvaluator()
    usd_market = _market()
    eur_bar = replace(usd_market.bars[0], currency="EUR")
    eur_market = replace(usd_market, bars=(eur_bar,))
    eur_account = replace(_account(), currency="EUR")

    market_result = evaluator.evaluate(_order(), _account(), (), eur_market, evaluated_at=NOW)
    account_result = evaluator.evaluate(_order(), eur_account, (), usd_market, evaluated_at=NOW)
    assert "unsupported_risk_currency" in market_result.reasons
    assert "unsupported_risk_currency" in account_result.reasons


def test_risk_gate_limits_notional_symbols_and_short_sales() -> None:
    evaluator = PaperRiskEvaluator()
    assert (
        "instrument_not_allowlisted"
        in evaluator.evaluate(
            _order(symbol="XYZ"), _account(), (), _market(symbol="XYZ"), evaluated_at=NOW
        ).reasons
    )
    assert (
        "order_notional_limit_exceeded"
        in evaluator.evaluate(
            _order(quantity="6"), _account(), (), _market(), evaluated_at=NOW
        ).reasons
    )
    assert (
        "short_selling_not_allowed"
        in evaluator.evaluate(
            _order(side=OrderSide.SELL, quantity="1"), _account(), (), _market(), evaluated_at=NOW
        ).reasons
    )


def test_risk_gate_accounts_for_existing_symbol_and_gross_exposure() -> None:
    position = PositionSnapshot(
        "SPY", Decimal("10"), Decimal("100"), Decimal("100"), Decimal("1000"), Decimal("0"), "USD"
    )
    result = PaperRiskEvaluator().evaluate(
        _order(quantity="1"), _account(), (position,), _market(), evaluated_at=NOW
    )
    assert result.allowed is False
    assert "single_symbol_exposure_limit_exceeded" in result.reasons
