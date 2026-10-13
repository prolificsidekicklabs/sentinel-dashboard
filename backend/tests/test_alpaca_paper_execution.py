from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from sentinel_core.adapters.alpaca import AlpacaSettings
from sentinel_core.adapters.alpaca_paper_execution import (
    AlpacaPaperExecutionAdapter,
    RiskAuthorizationRejected,
)
from sentinel_core.adapters.ports import (
    OrderIntent,
    OrderSide,
    OrderType,
    RiskApprovedOrder,
    RiskEvaluation,
)

NOW = datetime.now(UTC)


def _settings() -> AlpacaSettings:
    return AlpacaSettings(
        key_id=SecretStr("paper-key"),
        secret_key=SecretStr("paper-secret"),
        trading_base_url="https://api.alpaca.markets",
        allow_live_reads=True,
    )


def _approved(*, expires_at: datetime | None = None) -> RiskApprovedOrder:
    evaluation = RiskEvaluation(
        True,
        "risk-1",
        "sentinel-paper-risk",
        "1.0.0",
        NOW,
        expires_at or NOW + timedelta(seconds=30),
        ("paper_order_within_configured_limits",),
    )
    intent = OrderIntent("sentinel-order-1", "SPY", OrderSide.BUY, Decimal("1"), OrderType.MARKET)
    return RiskApprovedOrder(intent, evaluation, "idem-key-123456", "owner-1")


def test_submission_is_paper_only_and_maps_normalized_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "broker-order-1",
                "client_order_id": "sentinel-order-1",
                "status": "accepted",
                "symbol": "SPY",
                "qty": "1",
                "side": "buy",
                "type": "market",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AlpacaPaperExecutionAdapter(_settings(), http_client=client, clock=lambda: NOW)
    result = asyncio.run(adapter.submit_order(_approved()))
    asyncio.run(client.aclose())

    assert adapter.base_url == "https://paper-api.alpaca.markets"
    assert requests[0].method == "POST"
    assert requests[0].url.host == "paper-api.alpaca.markets"
    assert requests[0].headers["APCA-API-KEY-ID"] == "paper-key"
    assert result["status"] == "accepted"


def test_submission_rejects_expired_risk_approval_before_network_call() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request"))
    )
    adapter = AlpacaPaperExecutionAdapter(
        _settings(), http_client=client, clock=lambda: NOW + timedelta(seconds=10)
    )
    with pytest.raises(RiskAuthorizationRejected, match="expired"):
        asyncio.run(adapter.submit_order(_approved(expires_at=NOW + timedelta(seconds=5))))
    asyncio.run(client.aclose())


def test_reconciliation_looks_up_by_stable_client_order_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/orders:by_client_order_id"
        assert request.url.params["client_order_id"] == "sentinel-order-1"
        return httpx.Response(
            200,
            json={
                "id": "broker-order-1",
                "client_order_id": "sentinel-order-1",
                "status": "filled",
                "symbol": "SPY",
                "qty": "1",
                "side": "buy",
                "type": "market",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AlpacaPaperExecutionAdapter(_settings(), http_client=client)
    order = asyncio.run(adapter.get_order_by_client_id("sentinel-order-1"))
    asyncio.run(client.aclose())
    assert order is not None and order["status"] == "filled"
