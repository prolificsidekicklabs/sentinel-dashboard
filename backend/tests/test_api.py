from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi import HTTPException

import sentinel_core.api as api
from sentinel_core.adapters.ports import (
    AccountSnapshot,
    DataQuality,
    MarketDataQuery,
    MarketSnapshot,
    OHLCVBar,
    PositionSnapshot,
)

TEST_API_KEY = "test-only-key-that-is-long-enough-for-256-bit-policy"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}
FIXED_NOW = datetime(2026, 10, 11, 20, 0, tzinfo=UTC)


async def _request(
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=json, headers=headers)


@pytest.fixture(autouse=True)
def _set_test_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    api.app.dependency_overrides.clear()
    monkeypatch.setenv(api.API_KEY_ENV, TEST_API_KEY)
    yield
    api.app.dependency_overrides.clear()


def test_health_route_reports_liveness_without_disclosing_provider_state() -> None:
    response = asyncio.run(_request("GET", "/healthz"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "alpaca" not in response.text.lower()


def test_protected_plugin_routes_require_bearer_authentication() -> None:
    missing = asyncio.run(_request("GET", "/api/v1/plugins"))
    wrong = asyncio.run(
        _request("GET", "/api/v1/plugins", headers={"Authorization": "Bearer wrong"})
    )
    allowed = asyncio.run(_request("GET", "/api/v1/plugins", headers=AUTH_HEADERS))

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()[0]["plugin_id"] == "moving-average"
    assert "plugin_file" not in allowed.json()[0]


def test_api_fails_closed_when_authentication_key_is_missing_or_too_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(api.API_KEY_ENV)
    missing = asyncio.run(_request("GET", "/api/v1/plugins", headers=AUTH_HEADERS))
    monkeypatch.setenv(api.API_KEY_ENV, "short")
    short = asyncio.run(_request("GET", "/api/v1/plugins", headers=AUTH_HEADERS))

    assert missing.status_code == 503
    assert short.status_code == 503
    assert api.API_KEY_ENV not in missing.text


def test_plugin_run_is_authenticated_and_deterministic() -> None:
    payload: dict[str, object] = {
        "seed": 7,
        "input": {"instrument": "DEMO", "prices": [9, 10, 11, 12], "window": 3},
    }
    missing = asyncio.run(_request("POST", "/api/v1/plugins/moving-average/run", json=payload))
    first = asyncio.run(
        _request("POST", "/api/v1/plugins/moving-average/run", json=payload, headers=AUTH_HEADERS)
    )
    second = asyncio.run(
        _request("POST", "/api/v1/plugins/moving-average/run", json=payload, headers=AUTH_HEADERS)
    )

    assert missing.status_code == 401
    assert first.status_code == 200
    assert first.json()["output_sha256"] == second.json()["output_sha256"]
    assert first.json()["result"]["output"]["simple_moving_average"] == 11.0


def test_plugin_run_rejects_unknown_plugins_and_extra_request_fields() -> None:
    unknown = asyncio.run(
        _request(
            "POST",
            "/api/v1/plugins/not-installed/run",
            json={"seed": 1, "input": {}},
            headers=AUTH_HEADERS,
        )
    )
    invalid = asyncio.run(
        _request(
            "POST",
            "/api/v1/plugins/moving-average/run",
            json={"seed": 1, "input": {}, "force": True},
            headers=AUTH_HEADERS,
        )
    )

    assert unknown.status_code == 404
    assert invalid.status_code == 422


def test_strategy_route_runs_candidate_review_and_generic_run_cannot_bypass_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "_make_market_adapter", lambda: _FakeCandidateMarketAdapter())

    missing_auth = asyncio.run(
        _request("GET", "/api/v1/research/strategies/rsi-macd-candidate?symbol=SPY")
    )
    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/research/strategies/rsi-macd-candidate?symbol=SPY",
            headers=AUTH_HEADERS,
        )
    )
    bypass = asyncio.run(
        _request(
            "POST",
            "/api/v1/plugins/rsi-macd-candidate/run",
            json={"seed": 0, "input": {}},
            headers=AUTH_HEADERS,
        )
    )

    assert missing_auth.status_code == 401
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "research-candidate"
    assert body["execution_enabled"] is False
    assert body["signal"]["execution_enabled"] is False
    assert body["signal"]["bar_count"] == 220
    assert body["review"]["disposition"] == "no_candidate"
    assert body["review"]["execution_enabled"] is False
    assert "account" not in body and "positions" not in body
    assert bypass.status_code == 409
    assert "independent research review endpoint" in bypass.json()["detail"]


@pytest.mark.parametrize(
    ("instrument_id", "timeframe"),
    [("QQQ", "1Day"), ("SPY", "1Hour")],
)
def test_strategy_route_rejects_provider_symbol_or_timeframe_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    instrument_id: str,
    timeframe: str,
) -> None:
    monkeypatch.setattr(
        api,
        "_make_market_adapter",
        lambda: _FakeCandidateMarketAdapter(
            instrument_id=instrument_id,
            timeframe=timeframe,
        ),
    )

    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/research/strategies/rsi-macd-candidate?symbol=SPY",
            headers=AUTH_HEADERS,
        )
    )

    assert response.status_code == 502
    assert "unexpected instrument or timeframe" in response.json()["detail"]


class _FakeMarketAdapter:
    async def get_bars(self, query: MarketDataQuery) -> MarketSnapshot:
        assert query.instrument_id == "SPY"
        assert query.timeframe == "1Day"
        bar = OHLCVBar(
            instrument_id="SPY",
            observed_at=FIXED_NOW,
            open=Decimal("451.00"),
            high=Decimal("454.00"),
            low=Decimal("450.00"),
            close=Decimal("452.37"),
            volume=Decimal("1234000"),
            currency="USD",
            source_id="alpaca:iex",
        )
        return MarketSnapshot(
            instrument_id="SPY",
            timeframe="1Day",
            source_id="alpaca:iex",
            observed_at=FIXED_NOW,
            received_at=FIXED_NOW,
            quality=DataQuality.VALID,
            bars=(bar,),
        )


class _FakeCandidateMarketAdapter:
    def __init__(self, *, instrument_id: str = "SPY", timeframe: str = "1Day") -> None:
        self.instrument_id = instrument_id
        self.timeframe = timeframe

    async def get_bars(self, query: MarketDataQuery) -> MarketSnapshot:
        assert query.instrument_id == "SPY"
        assert query.timeframe == "1Day"
        received_at = datetime.now(UTC)
        latest = received_at - timedelta(days=1)
        bars = tuple(
            OHLCVBar(
                instrument_id=self.instrument_id,
                observed_at=latest - timedelta(days=219 - index),
                open=Decimal("100.00") + Decimal(index) / Decimal("10"),
                high=Decimal("101.00") + Decimal(index) / Decimal("10"),
                low=Decimal("99.00") + Decimal(index) / Decimal("10"),
                close=Decimal("100.00") + Decimal(index) / Decimal("10"),
                volume=Decimal("1000"),
                currency="USD",
                source_id="alpaca:iex",
            )
            for index in range(220)
        )
        return MarketSnapshot(
            instrument_id=self.instrument_id,
            timeframe=self.timeframe,
            source_id="alpaca:iex",
            observed_at=latest,
            received_at=received_at,
            quality=DataQuality.VALID,
            bars=bars,
        )


class _FakePaperBroker:
    async def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            account_ref="must-not-be-returned",
            currency="USD",
            equity=Decimal("1000.25"),
            cash=Decimal("800.25"),
            buying_power=Decimal("1600.50"),
            observed_at=FIXED_NOW,
        )

    async def get_positions(self) -> tuple[PositionSnapshot, ...]:
        return (
            PositionSnapshot(
                instrument_id="SPY",
                quantity=Decimal("2"),
                average_entry_price=Decimal("440.00"),
                current_price=Decimal("452.37"),
                market_value=Decimal("904.74"),
                unrealized_pl=Decimal("24.74"),
                currency="USD",
            ),
        )


def test_paper_dashboard_returns_normalized_decimal_strings_and_no_execution_or_account_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "_make_market_adapter", lambda: _FakeMarketAdapter())
    monkeypatch.setattr(api, "_make_paper_broker_adapter", lambda: _FakePaperBroker())
    response = asyncio.run(
        _request("GET", "/api/v1/paper/dashboard?symbol=spy&days=30", headers=AUTH_HEADERS)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "paper-read-only"
    assert body["execution_enabled"] is False
    assert body["market"]["bars"][0]["close"] == "452.37"
    assert body["account"]["paper"] is True
    assert body["account"]["equity"] == "1000.25"
    assert "account_ref" not in body["account"]
    assert body["positions"][0]["instrument_id"] == "SPY"
    assert not any("order" in path.lower() for path in api.app.openapi()["paths"])


def test_paper_dashboard_requires_auth_and_valid_query() -> None:
    missing = asyncio.run(_request("GET", "/api/v1/paper/dashboard"))
    bad_symbol = asyncio.run(
        _request("GET", "/api/v1/paper/dashboard?symbol=SPY%3Fforce%3D1", headers=AUTH_HEADERS)
    )
    bad_days = asyncio.run(
        _request("GET", "/api/v1/paper/dashboard?days=9999", headers=AUTH_HEADERS)
    )

    assert missing.status_code == 401
    assert bad_symbol.status_code == 422
    assert bad_days.status_code == 422


def test_paper_settings_ignore_live_account_opt_ins() -> None:
    settings = api.paper_settings_from_environment(
        {
            "SENTINEL_ALPACA_KEY_ID": "paper-key",
            "SENTINEL_ALPACA_SECRET_KEY": "paper-secret",
            "SENTINEL_ALPACA_TRADING_BASE_URL": "https://api.alpaca.markets",
            "SENTINEL_ALPACA_ALLOW_LIVE_READS": "true",
        }
    )

    assert settings.trading_base_url == api.PAPER_TRADING_BASE_URL
    assert settings.allow_live_reads is False


def test_missing_alpaca_credentials_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_ALPACA_KEY_ID", raising=False)
    monkeypatch.delenv("SENTINEL_ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(HTTPException) as market_error:
        api._make_market_adapter()
    with pytest.raises(HTTPException) as paper_error:
        api._make_paper_broker_adapter()

    assert market_error.value.status_code == 503
    assert paper_error.value.status_code == 503
    assert "key" not in market_error.value.detail.lower()
