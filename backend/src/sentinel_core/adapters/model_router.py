"""Model-provider port and OpenAI-compatible HTTP adapter.

This adapter calls configured model gateways for language tasks only. It does not
implement strategy calculations, risk decisions, or trading authorization.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

MAX_MODEL_RESPONSE_BYTES = 2_000_000


class ModelGatewayError(RuntimeError):
    """Raised when a model gateway request fails without exposing secret material."""


class ModelGatewayNotConfigured(ModelGatewayError):
    """Raised when the server-side gateway URL, API key, or model is missing."""


class ChatMessage(BaseModel):
    """One plain-text chat message sent to a configured model gateway."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32_000)


class ModelRequest(BaseModel):
    """Bounded request data for a model task; it contains no trading authority."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class ModelResponse(BaseModel):
    """Normalized text response that callers must treat as untrusted output."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=128_000)
    model: str = Field(max_length=200)
    finish_reason: str | None = Field(default=None, max_length=100)


class ModelAdapter(Protocol):
    """Provider-neutral asynchronous model interface."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete a text-generation request without changing domain state."""
        ...


@dataclass(frozen=True, slots=True)
class ModelGatewaySettings:
    """Server-side connection settings; API keys are masked by SecretStr."""

    base_url: str
    api_key: SecretStr
    model_name: str
    timeout_seconds: float = 30.0
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        if not self.base_url.strip() or not self.api_key.get_secret_value().strip():
            raise ValueError("model gateway URL and API key are required")
        if not self.model_name.strip():
            raise ValueError("model gateway model name is required")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120:
            raise ValueError("model timeout must be finite and between 0 and 120 seconds")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> ModelGatewaySettings:
        """Read gateway credentials from process environment, never from browser input."""
        values = os.environ if environ is None else environ
        base_url = values.get("SENTINEL_MODEL_BASE_URL", "").strip()
        api_key = values.get("SENTINEL_MODEL_API_KEY", "").strip()
        model_name = values.get("SENTINEL_MODEL_NAME", "").strip()
        if not base_url or not api_key or not model_name:
            raise ModelGatewayNotConfigured(
                "set the server-side model base URL, API key, and model name"
            )
        try:
            timeout_seconds = float(values.get("SENTINEL_MODEL_TIMEOUT_SECONDS", "30"))
        except ValueError as exc:
            raise ModelGatewayNotConfigured("model timeout must be a number") from exc
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ModelGatewayNotConfigured("model timeout must be between 0 and 120 seconds")
        allow_insecure_http = (
            values.get("SENTINEL_MODEL_ALLOW_INSECURE_HTTP", "false").lower() == "true"
        )
        return cls(
            base_url=base_url,
            api_key=SecretStr(api_key),
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            allow_insecure_http=allow_insecure_http,
        )


class OpenAICompatibleChatAdapter:
    """Adapter for gateways exposing the OpenAI `/v1/chat/completions` format.

    OmniRoute and 9Router both document this interface. Other compatible gateways
    can use the same adapter; provider selection and model naming are configuration.
    """

    def __init__(
        self,
        settings: ModelGatewaySettings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.http_client = http_client
        self.endpoint = self._validated_endpoint(settings)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> OpenAICompatibleChatAdapter:
        """Build the adapter from server-side environment configuration."""
        return cls(ModelGatewaySettings.from_environment(environ), http_client=http_client)

    @staticmethod
    def _validated_endpoint(settings: ModelGatewaySettings) -> str:
        try:
            url = httpx.URL(settings.base_url)
        except (TypeError, ValueError) as exc:
            raise ValueError("model gateway base URL is invalid") from exc
        if url.scheme not in {"http", "https"} or not url.host:
            raise ValueError("model gateway URL must use HTTP or HTTPS")
        if url.userinfo or url.query or url.fragment:
            raise ValueError("model gateway URL must not contain credentials, query, or fragment")
        if not url.path.rstrip("/").endswith("/v1"):
            raise ValueError(
                "model gateway base URL must include its API version path, usually /v1"
            )
        if url.scheme == "http" and not settings.allow_insecure_http:
            host = url.host.strip("[]").lower()
            is_loopback = host == "localhost"
            try:
                is_loopback = is_loopback or ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
            if not is_loopback:
                raise ValueError("plain HTTP is allowed only for loopback gateways by default")
        return str(url.copy_with(path=url.path.rstrip("/") + "/chat/completions"))

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Call the configured gateway and normalize a single text completion."""
        payload = {
            "model": self.settings.model_name,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key.get_secret_value()}"}

        try:
            if self.http_client is None:
                async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                    response_body = await self._post_bounded(
                        client, payload=payload, headers=headers
                    )
            else:
                response_body = await self._post_bounded(
                    self.http_client, payload=payload, headers=headers
                )
        except httpx.HTTPStatusError as exc:
            raise ModelGatewayError(
                f"model gateway returned HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError:
            raise ModelGatewayError("model gateway request failed") from None

        try:
            data = json.loads(response_body)
            choice = data["choices"][0]
            message = choice["message"]
            content = message["content"]
            model = data.get("model", self.settings.model_name)
            finish_reason = choice.get("finish_reason")
            if not isinstance(content, str) or not isinstance(model, str):
                raise TypeError("invalid response fields")
            if finish_reason is not None and not isinstance(finish_reason, str):
                raise TypeError("invalid finish reason")
            return ModelResponse(content=content, model=model, finish_reason=finish_reason)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelGatewayError(
                "model gateway response did not match the chat contract"
            ) from exc

    async def _post_bounded(
        self,
        client: httpx.AsyncClient,
        *,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> bytes:
        """Apply this adapter's timeout and cap the streamed response before buffering it."""
        chunks: list[bytes] = []
        total_bytes = 0
        async with client.stream(
            "POST",
            self.endpoint,
            json=payload,
            headers=headers,
            timeout=self.settings.timeout_seconds,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                total_bytes += len(chunk)
                if total_bytes > MAX_MODEL_RESPONSE_BYTES:
                    raise ModelGatewayError("model gateway response exceeds the size limit")
                chunks.append(chunk)
        return b"".join(chunks)
