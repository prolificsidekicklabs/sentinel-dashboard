"""Explicitly paper-only Alpaca order submission and reconciliation adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from sentinel_core.adapters.alpaca import AlpacaError, AlpacaSettings, _validate_alpaca_base_url
from sentinel_core.adapters.ports import OrderType, RiskApprovedOrder

PAPER_TRADING_BASE_URL = "https://paper-api.alpaca.markets"
_SUPPORTED_POLICY = ("sentinel-paper-risk", "1.0.0")
_ORDER_STATUSES = frozenset(
    {
        "new",
        "accepted",
        "pending_new",
        "partially_filled",
        "filled",
        "done_for_day",
        "canceled",
        "expired",
        "replaced",
        "rejected",
        "pending_cancel",
        "pending_replace",
        "accepted_for_bidding",
        "stopped",
        "suspended",
        "calculated",
    }
)


class RiskAuthorizationRejected(AlpacaError):
    """Raised before network I/O when the server approval is invalid or expired."""


class AlpacaPaperExecutionAdapter:
    """Submit only short-lived orders approved by Sentinel's fixed paper risk policy."""

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
        # Deliberately ignore configured trading URLs; this adapter has no live host path.
        self.base_url = _validate_alpaca_base_url(
            PAPER_TRADING_BASE_URL, allowed_hosts={"paper-api.alpaca.markets"}
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        headers = {
            "APCA-API-KEY-ID": self.settings.key_id.get_secret_value(),
            "APCA-API-SECRET-KEY": self.settings.secret_key.get_secret_value(),
            "Accept": "application/json",
        }
        try:
            if self.http_client is not None:
                response = await self.http_client.request(
                    method,
                    f"{self.base_url}{path}",
                    params=params,
                    json=body,
                    headers=headers,
                    timeout=self.settings.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                    response = await client.request(
                        method,
                        f"{self.base_url}{path}",
                        params=params,
                        json=body,
                        headers=headers,
                    )
            if method == "GET" and response.status_code == 404:
                return None
            response.raise_for_status()
            if len(response.content) > 1_000_000:
                raise AlpacaError("paper broker response exceeds its size limit")
            parsed = json.loads(response.content)
            if not isinstance(parsed, dict):
                raise AlpacaError("paper broker response did not match its schema")
            return parsed
        except httpx.HTTPStatusError as exc:
            # Do not retain provider response bodies, which could contain account details.
            raise AlpacaError(
                f"paper broker request returned HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError:
            raise AlpacaError("paper broker request failed") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AlpacaError("paper broker returned invalid JSON") from None

    @staticmethod
    def _normalize_order(data: dict[str, Any]) -> dict[str, str]:
        required = ("id", "client_order_id", "status", "symbol", "qty", "side", "type")
        if any(not isinstance(data.get(key), str) or not data[key] for key in required):
            raise AlpacaError("paper broker order response failed normalized validation")
        if data["status"] not in _ORDER_STATUSES:
            raise AlpacaError("paper broker returned an unsupported order status")
        return {key: data[key] for key in required}

    async def submit_order(self, order: RiskApprovedOrder) -> dict[str, str]:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("adapter clock must return an aware timestamp")
        evaluation = order.evaluation
        if not evaluation.allowed or evaluation.expires_at.astimezone(UTC) <= now.astimezone(UTC):
            raise RiskAuthorizationRejected("risk evaluation is denied or expired")
        if (evaluation.policy_id, evaluation.policy_version) != _SUPPORTED_POLICY:
            raise RiskAuthorizationRejected(
                "paper broker accepts only the configured Sentinel risk policy"
            )
        intent = order.intent
        if intent.order_type is not OrderType.MARKET or intent.quantity <= 0:
            raise RiskAuthorizationRejected(
                "paper broker accepts only positive-quantity market orders"
            )
        data = await self._request(
            "POST",
            "/v2/orders",
            body={
                "symbol": intent.instrument_id.upper(),
                "qty": str(intent.quantity),
                "side": intent.side.value,
                "type": "market",
                "time_in_force": "day",
                "client_order_id": intent.client_order_id,
            },
        )
        if data is None:
            raise AlpacaError("paper broker returned no order record")
        normalized = self._normalize_order(data)
        if (
            normalized["client_order_id"] != intent.client_order_id
            or normalized["symbol"].upper() != intent.instrument_id.upper()
            or normalized["side"] != intent.side.value
            or normalized["type"] != "market"
        ):
            raise AlpacaError("paper broker acknowledged a mismatched order")
        return normalized

    async def get_order_by_client_id(self, client_order_id: str) -> dict[str, str] | None:
        data = await self._request(
            "GET",
            "/v2/orders:by_client_order_id",
            params={"client_order_id": client_order_id},
        )
        return self._normalize_order(data) if data is not None else None


__all__ = [
    "AlpacaPaperExecutionAdapter",
    "PAPER_TRADING_BASE_URL",
    "RiskAuthorizationRejected",
]
