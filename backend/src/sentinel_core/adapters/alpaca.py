"""Read-only Alpaca Trading API and market-data adapters.

The default trading endpoint is paper. No order-submission method is implemented.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import SecretStr

from sentinel_core.adapters.ports import (
    AccountSnapshot,
    DataQuality,
    MarketDataQuery,
    MarketSnapshot,
    OHLCVBar,
    PositionSnapshot,
)


class AlpacaError(RuntimeError):
    """Alpaca request or response failure with credentials and response bodies redacted."""


class AlpacaNotConfigured(AlpacaError):
    """Raised when the server-side Alpaca API keys are not configured."""


@dataclass(frozen=True, slots=True)
class AlpacaSettings:
    """Server-side Alpaca Trading API key pair and bounded read configuration."""

    key_id: SecretStr
    secret_key: SecretStr
    market_data_base_url: str = "https://data.alpaca.markets"
    trading_base_url: str = "https://paper-api.alpaca.markets"
    stock_feed: str = "iex"
    timeout_seconds: float = 20.0
    max_pages: int = 20
    max_bars: int = 20_000
    allow_live_reads: bool = False

    def __post_init__(self) -> None:
        if (
            not self.key_id.get_secret_value().strip()
            or not self.secret_key.get_secret_value().strip()
        ):
            raise ValueError("Alpaca key ID and secret key are required")
        if self.stock_feed not in {"iex", "sip", "boats", "otc"}:
            raise ValueError("stock feed must be iex, sip, boats, or otc")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120:
            raise ValueError("Alpaca timeout must be finite and between 0 and 120 seconds")
        if not 1 <= self.max_pages <= 100 or not 1 <= self.max_bars <= 100_000:
            raise ValueError("Alpaca data page/bar limits are outside safe bounds")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> AlpacaSettings:
        """Read credentials only from the backend process environment."""
        values = os.environ if environ is None else environ
        key_id = values.get("SENTINEL_ALPACA_KEY_ID", "").strip()
        secret_key = values.get("SENTINEL_ALPACA_SECRET_KEY", "").strip()
        if not key_id or not secret_key:
            raise AlpacaNotConfigured(
                "set the server-side Alpaca Trading API key ID and secret key"
            )
        feed = values.get("SENTINEL_ALPACA_STOCK_FEED", "iex").strip().lower()
        if feed not in {"iex", "sip", "boats", "otc"}:
            raise AlpacaNotConfigured("stock feed must be iex, sip, boats, or otc")
        try:
            timeout_seconds = float(values.get("SENTINEL_ALPACA_TIMEOUT_SECONDS", "20"))
            max_pages = int(values.get("SENTINEL_ALPACA_MAX_PAGES", "20"))
            max_bars = int(values.get("SENTINEL_ALPACA_MAX_BARS", "20000"))
        except ValueError as exc:
            raise AlpacaNotConfigured("Alpaca request limits must be numeric") from exc
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise AlpacaNotConfigured("Alpaca timeout must be between 0 and 120 seconds")
        if not 1 <= max_pages <= 100 or not 1 <= max_bars <= 100_000:
            raise AlpacaNotConfigured("Alpaca data page/bar limits are outside safe bounds")
        return cls(
            key_id=SecretStr(key_id),
            secret_key=SecretStr(secret_key),
            market_data_base_url=values.get(
                "SENTINEL_ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"
            ).rstrip("/"),
            trading_base_url=values.get(
                "SENTINEL_ALPACA_TRADING_BASE_URL", "https://paper-api.alpaca.markets"
            ).rstrip("/"),
            stock_feed=feed,
            timeout_seconds=timeout_seconds,
            max_pages=max_pages,
            max_bars=max_bars,
            allow_live_reads=(
                values.get("SENTINEL_ALPACA_ALLOW_LIVE_READS", "false").lower() == "true"
            ),
        )


def _validate_alpaca_base_url(base_url: str, *, allowed_hosts: set[str]) -> str:
    try:
        url = httpx.URL(base_url)
    except (TypeError, ValueError) as exc:
        raise ValueError("Alpaca base URL is invalid") from exc
    if url.scheme != "https" or url.host.lower() not in allowed_hosts:
        raise ValueError("Alpaca URL must use HTTPS and an official Alpaca API host")
    if url.userinfo or url.query or url.fragment or url.path not in {"", "/"}:
        raise ValueError("Alpaca base URL must not contain credentials, path, query, or fragment")
    return str(url.copy_with(path="").copy_with(query=None, fragment=None)).rstrip("/")


def _decode_json(raw: bytes) -> Any:
    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"invalid numeric constant: {value}")

    return json.loads(raw, parse_float=Decimal, parse_constant=reject_nonfinite)


def _as_decimal(value: Any, field: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise AlpacaError(f"Alpaca response has an invalid {field}") from exc
    if not result.is_finite():
        raise AlpacaError(f"Alpaca response has an invalid {field}")
    return result


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise AlpacaError("Alpaca response has an invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlpacaError("Alpaca response has an invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AlpacaError("Alpaca response timestamp must include a timezone")
    return parsed


async def _get_json(
    *,
    client: httpx.AsyncClient | None,
    base_url: str,
    path: str,
    headers: Mapping[str, str],
    params: Mapping[str, str | int] | None,
    timeout_seconds: float,
) -> Any:
    try:
        if client is not None:
            response = await client.get(
                f"{base_url}{path}", params=params, headers=headers, timeout=timeout_seconds
            )
        else:
            async with httpx.AsyncClient(timeout=timeout_seconds) as owned_client:
                response = await owned_client.get(
                    f"{base_url}{path}", params=params, headers=headers
                )
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise AlpacaError("Alpaca response exceeds the configured page-size safety limit")
        return _decode_json(response.content)
    except httpx.HTTPStatusError as exc:
        raise AlpacaError(f"Alpaca request returned HTTP {exc.response.status_code}") from None
    except httpx.HTTPError:
        raise AlpacaError("Alpaca request failed") from None
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise AlpacaError("Alpaca returned invalid JSON") from exc


def _timeframe_is_supported(value: str) -> bool:
    if re.fullmatch(r"(?:[1-9]|[1-5][0-9])(?:Min|T)", value):
        return True
    if re.fullmatch(r"(?:[1-9]|1[0-9]|2[0-3])(?:Hour|H)", value):
        return True
    if value in {"1Day", "1D", "1Week", "1W"}:
        return True
    return value in {
        "1Month",
        "2Month",
        "3Month",
        "4Month",
        "6Month",
        "12Month",
        "1M",
        "2M",
        "3M",
        "4M",
        "6M",
        "12M",
    }


class AlpacaMarketDataAdapter:
    """Fetch bounded historical US-stock OHLCV bars from Alpaca's Market Data API."""

    def __init__(
        self,
        settings: AlpacaSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.http_client = http_client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.base_url = _validate_alpaca_base_url(
            settings.market_data_base_url,
            allowed_hosts={"data.alpaca.markets", "data.sandbox.alpaca.markets"},
        )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> AlpacaMarketDataAdapter:
        return cls(AlpacaSettings.from_environment(environ), http_client=http_client, clock=clock)

    async def get_bars(self, query: MarketDataQuery) -> MarketSnapshot:
        symbol = query.instrument_id.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,20}", symbol):
            raise ValueError("Alpaca stock instrument_id must be a supported ticker symbol")
        if not _timeframe_is_supported(query.timeframe):
            raise ValueError("timeframe is not supported by the Alpaca stock-bars endpoint")
        headers = {
            "APCA-API-KEY-ID": self.settings.key_id.get_secret_value(),
            "APCA-API-SECRET-KEY": self.settings.secret_key.get_secret_value(),
        }
        params: dict[str, str | int] = {
            "symbols": symbol,
            "timeframe": query.timeframe,
            "start": query.start.isoformat().replace("+00:00", "Z"),
            "end": query.end.isoformat().replace("+00:00", "Z"),
            "limit": 1000,
            "sort": "asc",
            "feed": self.settings.stock_feed,
        }
        bars: list[OHLCVBar] = []
        currency = "USD"
        next_page_token: str | None = None
        for page_number in range(self.settings.max_pages):
            if next_page_token is not None:
                params["page_token"] = next_page_token
            data = await _get_json(
                client=self.http_client,
                base_url=self.base_url,
                path="/v2/stocks/bars",
                headers=headers,
                params=params,
                timeout_seconds=self.settings.timeout_seconds,
            )
            if not isinstance(data, dict) or not isinstance(data.get("bars"), dict):
                raise AlpacaError("Alpaca bars response did not match the documented schema")
            response_currency = data.get("currency", "USD")
            if not isinstance(response_currency, str) or not response_currency.strip():
                raise AlpacaError("Alpaca bars response has an invalid currency")
            currency = response_currency
            page_bars = data["bars"].get(symbol, [])
            if not isinstance(page_bars, list):
                raise AlpacaError("Alpaca bars list did not match the documented schema")
            for item in page_bars:
                if not isinstance(item, dict):
                    raise AlpacaError("Alpaca bar did not match the documented schema")
                try:
                    bars.append(
                        OHLCVBar(
                            instrument_id=symbol,
                            observed_at=_parse_timestamp(item["t"]),
                            open=_as_decimal(item["o"], "open"),
                            high=_as_decimal(item["h"], "high"),
                            low=_as_decimal(item["l"], "low"),
                            close=_as_decimal(item["c"], "close"),
                            volume=_as_decimal(item["v"], "volume"),
                            currency=currency,
                            source_id=f"alpaca:{self.settings.stock_feed}",
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise AlpacaError("Alpaca bar failed normalized validation") from exc
                if len(bars) > self.settings.max_bars:
                    raise AlpacaError("Alpaca result exceeds the configured bar limit")
            token = data.get("next_page_token")
            if token is None:
                next_page_token = None
                break
            if not isinstance(token, str) or not token or len(token) > 2048:
                raise AlpacaError("Alpaca pagination token is invalid")
            if page_number == self.settings.max_pages - 1:
                raise AlpacaError("Alpaca result exceeds the configured page limit")
            next_page_token = token
        bars.sort(key=lambda bar: bar.observed_at)
        timestamps = [bar.observed_at for bar in bars]
        if len(timestamps) != len(set(timestamps)):
            raise AlpacaError("Alpaca returned duplicate timestamps for the requested symbol")
        received_at = self.clock()
        observed_at = bars[-1].observed_at if bars else received_at
        return MarketSnapshot(
            instrument_id=symbol,
            timeframe=query.timeframe,
            source_id=f"alpaca:{self.settings.stock_feed}",
            observed_at=observed_at,
            received_at=received_at,
            quality=DataQuality.VALID if bars else DataQuality.UNAVAILABLE,
            bars=tuple(bars),
        )


class AlpacaReadOnlyBrokerAdapter:
    """Read Alpaca account/positions; paper is the default and no order method exists."""

    def __init__(
        self,
        settings: AlpacaSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.http_client = http_client
        self.clock = clock or (lambda: datetime.now(UTC))
        allowed_hosts = {"paper-api.alpaca.markets"}
        if settings.allow_live_reads:
            allowed_hosts.add("api.alpaca.markets")
        self.base_url = _validate_alpaca_base_url(
            settings.trading_base_url, allowed_hosts=allowed_hosts
        )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> AlpacaReadOnlyBrokerAdapter:
        return cls(AlpacaSettings.from_environment(environ), http_client=http_client, clock=clock)

    async def _get(self, path: str) -> Any:
        headers = {
            "APCA-API-KEY-ID": self.settings.key_id.get_secret_value(),
            "APCA-API-SECRET-KEY": self.settings.secret_key.get_secret_value(),
        }
        return await _get_json(
            client=self.http_client,
            base_url=self.base_url,
            path=path,
            headers=headers,
            params=None,
            timeout_seconds=self.settings.timeout_seconds,
        )

    async def get_account(self) -> AccountSnapshot:
        data = await self._get("/v2/account")
        if not isinstance(data, dict):
            raise AlpacaError("Alpaca account response did not match the documented schema")
        try:
            return AccountSnapshot(
                account_ref=str(data["id"]),
                currency=str(data["currency"]),
                equity=_as_decimal(data["equity"], "equity"),
                cash=_as_decimal(data["cash"], "cash"),
                buying_power=_as_decimal(data["buying_power"], "buying_power"),
                observed_at=self.clock(),
                account_status=str(data["status"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AlpacaError("Alpaca account failed normalized validation") from exc

    async def get_positions(self) -> tuple[PositionSnapshot, ...]:
        data = await self._get("/v2/positions")
        if not isinstance(data, list):
            raise AlpacaError("Alpaca positions response did not match the documented schema")
        result: list[PositionSnapshot] = []
        try:
            for item in data:
                if not isinstance(item, dict):
                    raise AlpacaError("Alpaca position did not match the documented schema")
                result.append(
                    PositionSnapshot(
                        instrument_id=str(item["symbol"]),
                        quantity=_as_decimal(item["qty"], "quantity"),
                        average_entry_price=_as_decimal(
                            item["avg_entry_price"], "average entry price"
                        ),
                        current_price=_as_decimal(item["current_price"], "current price"),
                        market_value=_as_decimal(item["market_value"], "market value"),
                        unrealized_pl=_as_decimal(item["unrealized_pl"], "unrealized P&L"),
                        currency="USD",
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise AlpacaError("Alpaca position failed normalized validation") from exc
        return tuple(result)


__all__ = [
    "AlpacaError",
    "AlpacaMarketDataAdapter",
    "AlpacaNotConfigured",
    "AlpacaReadOnlyBrokerAdapter",
    "AlpacaSettings",
]
