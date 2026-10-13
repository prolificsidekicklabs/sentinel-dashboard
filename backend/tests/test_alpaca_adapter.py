from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from sentinel_core.adapters.alpaca import (
    AlpacaMarketDataAdapter,
    AlpacaNotConfigured,
    AlpacaReadOnlyBrokerAdapter,
    AlpacaSettings,
)
from sentinel_core.adapters.ports import DataQuality, MarketDataQuery

FIXED_NOW = datetime(2026, 10, 11, 20, 0, tzinfo=UTC)


def _settings(**overrides: object) -> AlpacaSettings:
    values: dict[str, object] = {
        "key_id": SecretStr("test-key-id"),
        "secret_key": SecretStr("test-secret"),
    }
    values.update(overrides)
    return AlpacaSettings(**values)  # type: ignore[arg-type]


class BarsHandler:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.params.get("page_token"):
            response = {
                "bars": {
                    "AAPL": [
                        {
                            "t": "2026-10-02T14:30:00Z",
                            "o": 12.0,
                            "h": 13.0,
                            "l": 11.0,
                            "c": 12.5,
                            "v": 200,
                        }
                    ]
                },
                "currency": "USD",
                "next_page_token": None,
            }
        else:
            response = {
                "bars": {
                    "AAPL": [
                        {
                            "t": "2026-10-01T14:30:00Z",
                            "o": 10.0,
                            "h": 11.0,
                            "l": 9.0,
                            "c": 10.125,
                            "v": 100,
                        }
                    ]
                },
                "currency": "USD",
                "next_page_token": "next-page-token",
            }
        return httpx.Response(200, json=response)


def test_alpaca_bars_paginate_and_normalize_prices_to_decimal() -> None:
    handler = BarsHandler()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AlpacaMarketDataAdapter(_settings(), http_client=client, clock=lambda: FIXED_NOW)
    query = MarketDataQuery(
        instrument_id="AAPL",
        timeframe="1Day",
        start=FIXED_NOW - timedelta(days=20),
        end=FIXED_NOW,
    )

    snapshot = asyncio.run(adapter.get_bars(query))
    asyncio.run(client.aclose())

    assert len(snapshot.bars) == 2
    assert snapshot.quality is DataQuality.VALID
    assert snapshot.source_id == "alpaca:iex"
    assert snapshot.bars[0].close == Decimal("10.125")
    assert snapshot.bars[0].observed_at < snapshot.bars[1].observed_at
    assert handler.requests[0].url.path == "/v2/stocks/bars"
    assert handler.requests[0].url.params["feed"] == "iex"
    assert handler.requests[1].url.params["page_token"] == "next-page-token"
    assert handler.requests[0].headers["APCA-API-KEY-ID"] == "test-key-id"
    assert handler.requests[0].headers["APCA-API-SECRET-KEY"] == "test-secret"


def test_alpaca_credentials_are_required_from_server_environment() -> None:
    with pytest.raises(AlpacaNotConfigured):
        AlpacaSettings.from_environment({})


def test_direct_alpaca_settings_enforce_safe_bounds() -> None:
    with pytest.raises(ValueError, match="stock feed"):
        _settings(stock_feed="unapproved")
    with pytest.raises(ValueError, match="timeout"):
        _settings(timeout_seconds=float("nan"))
    with pytest.raises(ValueError, match="page/bar limits"):
        _settings(max_pages=101)


def test_market_data_symbol_and_timeframe_are_validated() -> None:
    adapter = AlpacaMarketDataAdapter(_settings(), clock=lambda: FIXED_NOW)
    query = MarketDataQuery(
        instrument_id="AAPL?symbols=MSFT",
        timeframe="1Day",
        start=FIXED_NOW - timedelta(days=1),
        end=FIXED_NOW,
    )

    with pytest.raises(ValueError, match="ticker"):
        asyncio.run(adapter.get_bars(query))


def test_paper_account_and_positions_are_read_only() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v2/account":
            return httpx.Response(
                200,
                json={
                    "id": "account-1",
                    "currency": "USD",
                    "equity": "1000.25",
                    "cash": "800.25",
                    "buying_power": "1600.50",
                },
            )
        if request.url.path == "/v2/positions":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "AAPL",
                        "qty": "2",
                        "avg_entry_price": "90.00",
                        "current_price": "100.00",
                        "market_value": "200.00",
                        "unrealized_pl": "20.00",
                    }
                ],
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AlpacaReadOnlyBrokerAdapter(_settings(), http_client=client, clock=lambda: FIXED_NOW)
    account = asyncio.run(adapter.get_account())
    positions = asyncio.run(adapter.get_positions())
    asyncio.run(client.aclose())

    assert adapter.base_url == "https://paper-api.alpaca.markets"
    assert account.equity == Decimal("1000.25")
    assert positions[0].market_value == Decimal("200.00")
    assert [request.url.path for request in requests] == ["/v2/account", "/v2/positions"]
    assert all(request.method == "GET" for request in requests)
    assert not hasattr(adapter, "submit_order")


def test_live_account_reads_require_explicit_setting() -> None:
    settings = _settings(trading_base_url="https://api.alpaca.markets")

    with pytest.raises(ValueError, match="official Alpaca API host"):
        AlpacaReadOnlyBrokerAdapter(settings)

    enabled_settings = _settings(
        trading_base_url="https://api.alpaca.markets", allow_live_reads=True
    )
    adapter = AlpacaReadOnlyBrokerAdapter(enabled_settings)

    assert adapter.base_url == "https://api.alpaca.markets"
