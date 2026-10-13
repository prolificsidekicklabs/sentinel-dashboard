from __future__ import annotations

import asyncio
from collections.abc import Mapping

import httpx
import pytest
from pydantic import SecretStr

from sentinel_core.adapters.model_router import (
    MAX_MODEL_RESPONSE_BYTES,
    ModelGatewayError,
    ModelGatewayNotConfigured,
    ModelGatewaySettings,
    ModelRequest,
    OpenAICompatibleChatAdapter,
)


class RequestCapture:
    """Capture one HTTPX request in a test without network access."""

    def __init__(self) -> None:
        self.request: httpx.Request | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request = request
        return httpx.Response(
            200,
            json={
                "model": "router/model-test",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "analysis text"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )


def test_omniroute_or_9router_style_gateway_uses_openai_chat_contract() -> None:
    capture = RequestCapture()
    client = httpx.AsyncClient(transport=httpx.MockTransport(capture))
    settings = ModelGatewaySettings(
        base_url="http://127.0.0.1:20128/v1",
        api_key=SecretStr("gateway-secret"),
        model_name="route/model",
    )
    adapter = OpenAICompatibleChatAdapter(settings, http_client=client)

    response = asyncio.run(
        adapter.complete(
            ModelRequest(messages=[{"role": "user", "content": "summarize this snapshot"}])
        )
    )
    request = capture.request
    asyncio.run(client.aclose())

    assert request is not None
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer gateway-secret"
    assert request.read().decode("utf-8").find('"model":"route/model"') >= 0
    assert response.content == "analysis text"
    assert response.model == "router/model-test"
    assert "gateway-secret" not in repr(settings)


def test_environment_configuration_requires_server_side_credentials() -> None:
    with pytest.raises(ModelGatewayNotConfigured):
        OpenAICompatibleChatAdapter.from_environment(environ={})


def test_remote_plain_http_gateway_is_rejected_by_default() -> None:
    settings = ModelGatewaySettings(
        base_url="http://example.com/v1",
        api_key=SecretStr("test-secret"),
        model_name="model",
    )

    with pytest.raises(ValueError, match="loopback"):
        OpenAICompatibleChatAdapter(settings)


def test_environment_configuration_accepts_a_configured_local_router() -> None:
    values: Mapping[str, str] = {
        "SENTINEL_MODEL_BASE_URL": "http://localhost:20128/v1",
        "SENTINEL_MODEL_API_KEY": "test-secret",
        "SENTINEL_MODEL_NAME": "auto",
    }

    adapter = OpenAICompatibleChatAdapter.from_environment(environ=values)

    assert adapter.endpoint == "http://localhost:20128/v1/chat/completions"


def test_injected_client_uses_timeout_and_oversized_response_is_rejected() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"x" * (MAX_MODEL_RESPONSE_BYTES + 1))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = ModelGatewaySettings(
        base_url="http://127.0.0.1:20128/v1",
        api_key=SecretStr("test-secret"),
        model_name="model",
        timeout_seconds=1.25,
    )
    adapter = OpenAICompatibleChatAdapter(settings, http_client=client)

    with pytest.raises(ModelGatewayError, match="size limit"):
        asyncio.run(adapter.complete(ModelRequest(messages=[{"role": "user", "content": "test"}])))
    asyncio.run(client.aclose())

    assert captured[0].extensions["timeout"]["read"] == 1.25


def test_direct_model_gateway_settings_reject_nonfinite_timeout() -> None:
    with pytest.raises(ValueError, match="finite"):
        ModelGatewaySettings(
            base_url="https://gateway.example/v1",
            api_key=SecretStr("test-secret"),
            model_name="model",
            timeout_seconds=float("nan"),
        )
