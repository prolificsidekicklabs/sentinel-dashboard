"""Provider-neutral ports and precise domain records for integrations.

Read-only provider adapters may implement these ports; no risk policy or live-order
execution implementation is enabled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class DataQuality(StrEnum):
    """Quality state that adapters must preserve rather than silently upgrade."""

    VALID = "valid"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


class OrderSide(StrEnum):
    """Normalized order side independent of any broker API vocabulary."""

    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Initial normalized order types; provider-specific types need explicit review."""

    MARKET = "market"
    LIMIT = "limit"


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")


def _require_decimal(value: Decimal, label: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"{label} must be a finite Decimal")
    if positive and value <= 0:
        raise ValueError(f"{label} must be greater than zero")


@dataclass(frozen=True, slots=True)
class MarketDataQuery:
    """Time-bounded historical data query passed to a market-data adapter."""

    instrument_id: str
    timeframe: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or not self.timeframe.strip():
            raise ValueError("instrument_id and timeframe are required")
        _require_aware(self.start, "start")
        _require_aware(self.end, "end")
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """Normalized market bar with decimal prices and explicit provenance."""

    instrument_id: str
    observed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    currency: str
    source_id: str

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        if (
            not self.instrument_id.strip()
            or not self.currency.strip()
            or not self.source_id.strip()
        ):
            raise ValueError("instrument_id, currency, and source_id are required")
        for name in ("open", "high", "low", "close"):
            _require_decimal(getattr(self, name), name, positive=True)
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC values are inconsistent")
        if self.high < self.low:
            raise ValueError("high must not be below low")
        if self.volume is not None:
            _require_decimal(self.volume, "volume")
            if self.volume < 0:
                raise ValueError("volume cannot be negative")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Provenance-bearing adapter output consumed by model-independent logic."""

    instrument_id: str
    timeframe: str
    source_id: str
    observed_at: datetime
    received_at: datetime
    quality: DataQuality
    bars: tuple[OHLCVBar, ...]

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        _require_aware(self.received_at, "received_at")
        if not self.instrument_id.strip() or not self.source_id.strip():
            raise ValueError("instrument_id and source_id are required")
        if any(bar.instrument_id != self.instrument_id for bar in self.bars):
            raise ValueError("all bars must match the snapshot instrument")
        timestamps = [bar.observed_at for bar in self.bars]
        if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
            raise ValueError("bars must be strictly chronological")


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Minimal account view; never contains API credentials."""

    account_ref: str
    currency: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    observed_at: datetime
    account_status: str = "unknown"

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        if not self.account_status.strip():
            raise ValueError("account status is required")
        for name in ("equity", "cash", "buying_power"):
            _require_decimal(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Normalized read-only position record with decimal monetary fields."""

    instrument_id: str
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or not self.currency.strip():
            raise ValueError("instrument_id and currency are required")
        _require_decimal(self.quantity, "quantity")
        for name in ("average_entry_price", "current_price", "market_value"):
            _require_decimal(getattr(self, name), name)
        _require_decimal(self.unrealized_pl, "unrealized_pl")


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Normalized proposal only; it is not authorization to trade."""

    client_order_id: str
    instrument_id: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType
    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id.strip() or not self.instrument_id.strip():
            raise ValueError("client_order_id and instrument_id are required")
        _require_decimal(self.quantity, "quantity", positive=True)
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit orders require a limit_price")
            _require_decimal(self.limit_price, "limit_price", positive=True)
        elif self.limit_price is not None:
            raise ValueError("market orders must not carry a limit_price")


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    """Server-side policy result required before any broker order adapter call."""

    allowed: bool
    evaluation_id: str
    policy_id: str
    policy_version: str
    evaluated_at: datetime
    expires_at: datetime
    reasons: tuple[str, ...]
    unassessed_risks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_aware(self.evaluated_at, "evaluated_at")
        _require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.evaluated_at:
            raise ValueError("risk evaluation expiry must follow its evaluation time")
        if (
            not self.evaluation_id.strip()
            or not self.policy_id.strip()
            or not self.policy_version.strip()
        ):
            raise ValueError("risk evaluation identifiers are required")


@dataclass(frozen=True, slots=True)
class RiskApprovedOrder:
    """Order carrying an explicit server-side risk evaluation and idempotency key."""

    intent: OrderIntent
    evaluation: RiskEvaluation
    idempotency_key: str
    approved_by: str

    def __post_init__(self) -> None:
        if not self.evaluation.allowed:
            raise ValueError("a rejected risk evaluation cannot authorize an order")
        if not self.idempotency_key.strip() or not self.approved_by.strip():
            raise ValueError("idempotency_key and approved_by are required")


class MarketDataAdapter(Protocol):
    """Asynchronous port for normalized, provenance-bearing market observations."""

    async def get_bars(self, query: MarketDataQuery) -> MarketSnapshot:
        """Fetch bars while preserving source, timestamps, and data-quality state."""
        ...


class RiskEvaluator(Protocol):
    """Model-independent risk-policy port; language-model output is not authorization."""

    async def evaluate(
        self,
        order: OrderIntent,
        account: AccountSnapshot,
        market: MarketSnapshot,
    ) -> RiskEvaluation:
        """Evaluate deterministic policy and return a versioned result."""
        ...


class BrokerReadAdapter(Protocol):
    """Read-only asynchronous broker port; it cannot submit or cancel orders."""

    async def get_account(self) -> AccountSnapshot:
        """Read a normalized account snapshot without exposing credentials."""
        ...

    async def get_positions(self) -> tuple[PositionSnapshot, ...]:
        """Read normalized positions without exposing credentials."""
        ...


class BrokerAdapter(BrokerReadAdapter, Protocol):
    """Future execution port; order submission requires a risk-approved envelope."""

    async def submit_order(self, order: RiskApprovedOrder) -> str:
        """Submit an idempotent order only after explicit server-side risk approval."""
        ...


__all__ = [
    "AccountSnapshot",
    "BrokerAdapter",
    "BrokerReadAdapter",
    "DataQuality",
    "MarketDataAdapter",
    "MarketDataQuery",
    "MarketSnapshot",
    "OHLCVBar",
    "OrderIntent",
    "OrderSide",
    "OrderType",
    "PositionSnapshot",
    "RiskApprovedOrder",
    "RiskEvaluation",
    "RiskEvaluator",
]
