"""Deterministic server-side risk policy for paper-order requests only."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sentinel_core.adapters.ports import (
    AccountSnapshot,
    DataQuality,
    MarketSnapshot,
    OrderIntent,
    OrderSide,
    PositionSnapshot,
    RiskEvaluation,
)


@dataclass(frozen=True, slots=True)
class PaperRiskPolicy:
    """Conservative fixed limits; no model or client value can override these rules."""

    policy_id: str = "sentinel-paper-risk"
    version: str = "1.0.0"
    max_order_notional: Decimal = Decimal("500")
    max_single_symbol_exposure_pct: Decimal = Decimal("0.10")
    max_gross_exposure_pct: Decimal = Decimal("0.25")
    max_market_age: timedelta = timedelta(minutes=5)
    max_receive_age: timedelta = timedelta(seconds=30)
    max_account_age: timedelta = timedelta(minutes=2)
    allowed_symbols: frozenset[str] = frozenset({"SPY", "QQQ", "IWM", "AAPL", "MSFT"})

    def __post_init__(self) -> None:
        if self.max_order_notional <= 0:
            raise ValueError("max order notional must be positive")
        for name in ("max_single_symbol_exposure_pct", "max_gross_exposure_pct"):
            value = getattr(self, name)
            if not Decimal("0") < value <= Decimal("1"):
                raise ValueError(f"{name} must be in (0, 1]")
        if (
            self.max_market_age <= timedelta(0)
            or self.max_receive_age <= timedelta(0)
            or self.max_account_age <= timedelta(0)
        ):
            raise ValueError("market freshness limits must be positive")


class PaperRiskEvaluator:
    """Require healthy account, allowlisted symbols, fresh bars, and bounded exposure."""

    def __init__(self, policy: PaperRiskPolicy | None = None) -> None:
        self.policy = policy or PaperRiskPolicy()

    def evaluate(
        self,
        order: OrderIntent,
        account: AccountSnapshot,
        positions: tuple[PositionSnapshot, ...],
        market: MarketSnapshot,
        *,
        evaluated_at: datetime | None = None,
    ) -> RiskEvaluation:
        now = evaluated_at or datetime.now(UTC)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("evaluation time must include a timezone")
        now = now.astimezone(UTC)
        expires_at = now + timedelta(seconds=30)
        reasons: list[str] = []
        symbol = order.instrument_id.upper()

        if symbol not in self.policy.allowed_symbols:
            reasons.append("instrument_not_allowlisted")
        if market.quality is not DataQuality.VALID:
            reasons.append("market_data_quality_not_valid")
        if market.instrument_id.upper() != symbol or market.timeframe not in {"1Min", "1T"}:
            reasons.append("market_instrument_or_timeframe_mismatch")
        if not market.source_id.startswith("alpaca:"):
            reasons.append("market_source_not_verified")
        if market.observed_at != (market.bars[-1].observed_at if market.bars else None):
            reasons.append("market_snapshot_latest_timestamp_mismatch")
        if any(bar.currency != "USD" for bar in market.bars) or account.currency != "USD":
            reasons.append("unsupported_risk_currency")
        if not market.bars or market.bars[-1].instrument_id.upper() != symbol:
            reasons.append("latest_market_bar_missing")
        if market.bars:
            latest = market.bars[-1]
            if latest.source_id != market.source_id or latest.observed_at.utcoffset() is None:
                reasons.append("market_bar_provenance_invalid")
            else:
                age = now - latest.observed_at.astimezone(UTC)
                if age < -timedelta(seconds=30):
                    reasons.append("market_observation_in_future")
                elif age > self.policy.max_market_age:
                    reasons.append("market_observation_stale")
        received_age = now - market.received_at.astimezone(UTC)
        if received_age < -timedelta(seconds=30) or received_age > self.policy.max_receive_age:
            reasons.append("market_snapshot_stale")
        account_age = now - account.observed_at.astimezone(UTC)
        if account_age < -timedelta(seconds=30) or account_age > self.policy.max_account_age:
            reasons.append("account_snapshot_stale")
        if account.equity <= 0 or account.buying_power < 0:
            reasons.append("account_values_invalid")
        if account.account_status.strip().lower() != "active":
            reasons.append("account_not_active")
        if any(position.currency != account.currency for position in positions):
            reasons.append("position_currency_mismatch")

        latest_price = market.bars[-1].close if market.bars else Decimal("0")
        notional = order.quantity * latest_price
        if notional <= 0:
            reasons.append("order_notional_invalid")
        if notional > self.policy.max_order_notional:
            reasons.append("order_notional_limit_exceeded")

        symbol_position = next(
            (position for position in positions if position.instrument_id.upper() == symbol), None
        )
        current_quantity = symbol_position.quantity if symbol_position else Decimal("0")
        current_symbol_value = symbol_position.market_value if symbol_position else Decimal("0")
        gross_exposure = sum((abs(position.market_value) for position in positions), Decimal("0"))
        if order.side is OrderSide.BUY:
            if notional > account.buying_power:
                reasons.append("buying_power_exceeded")
            if account.equity > 0:
                if (
                    abs(current_symbol_value) + notional
                    > account.equity * self.policy.max_single_symbol_exposure_pct
                ):
                    reasons.append("single_symbol_exposure_limit_exceeded")
                if gross_exposure + notional > account.equity * self.policy.max_gross_exposure_pct:
                    reasons.append("gross_exposure_limit_exceeded")
        elif order.quantity > current_quantity:
            reasons.append("short_selling_not_allowed")

        allowed = not reasons
        return RiskEvaluation(
            allowed=allowed,
            evaluation_id=secrets.token_hex(16),
            policy_id=self.policy.policy_id,
            policy_version=self.policy.version,
            evaluated_at=now,
            expires_at=expires_at,
            reasons=tuple(reasons if reasons else ["paper_order_within_configured_limits"]),
            unassessed_risks=(
                "intraday_loss_limit_not_assessed_without_intraday_ledger",
                "fills_slippage_and_partial_execution_are_not_predictable",
                "policy_is_paper_only_and_not_validated_for_live_execution",
            ),
        )


__all__ = ["PaperRiskEvaluator", "PaperRiskPolicy"]
