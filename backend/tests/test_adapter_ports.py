from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from sentinel_core.adapters.ports import (
    DataQuality,
    MarketDataQuery,
    MarketSnapshot,
    OHLCVBar,
    OrderIntent,
    OrderSide,
    OrderType,
    RiskApprovedOrder,
    RiskEvaluation,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _bar(timestamp: datetime = NOW) -> OHLCVBar:
    return OHLCVBar(
        instrument_id="DEMO",
        observed_at=timestamp,
        open=Decimal("10.00"),
        high=Decimal("11.00"),
        low=Decimal("9.00"),
        close=Decimal("10.50"),
        volume=Decimal("100"),
        currency="USD",
        source_id="test-source",
    )


def test_market_snapshot_keeps_provenance_and_data_quality() -> None:
    snapshot = MarketSnapshot(
        instrument_id="DEMO",
        timeframe="1d",
        source_id="test-source",
        observed_at=NOW,
        received_at=NOW + timedelta(seconds=1),
        quality=DataQuality.VALID,
        bars=(_bar(),),
    )

    assert snapshot.quality is DataQuality.VALID
    assert snapshot.bars[0].close == Decimal("10.50")


def test_financial_bar_rejects_float_values() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        OHLCVBar(
            instrument_id="DEMO",
            observed_at=NOW,
            open=10.0,  # type: ignore[arg-type]
            high=11.0,  # type: ignore[arg-type]
            low=9.0,  # type: ignore[arg-type]
            close=10.5,  # type: ignore[arg-type]
            volume=None,
            currency="USD",
            source_id="test-source",
        )


def test_market_query_requires_timezone_and_ordered_range() -> None:
    with pytest.raises(ValueError, match="timezone"):
        MarketDataQuery(
            instrument_id="DEMO",
            timeframe="1d",
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 2),
        )


def test_rejected_policy_cannot_create_a_risk_approved_order() -> None:
    intent = OrderIntent(
        client_order_id="order-1",
        instrument_id="DEMO",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        order_type=OrderType.MARKET,
    )
    evaluation = RiskEvaluation(
        allowed=False,
        evaluation_id="risk-1",
        policy_id="default",
        policy_version="1",
        evaluated_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        reasons=("limit exceeded",),
    )

    with pytest.raises(ValueError, match="rejected"):
        RiskApprovedOrder(
            intent=intent,
            evaluation=evaluation,
            idempotency_key="idem-1",
            approved_by="user-1",
        )
