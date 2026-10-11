from __future__ import annotations

import asyncio

import httpx

from sentinel_core.api import app


async def _request(
    method: str, path: str, *, json: dict[str, object] | None = None
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=json)


def test_health_route_reports_liveness() -> None:
    response = asyncio.run(_request("GET", "/healthz"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_plugin_catalog_lists_only_validated_local_metadata() -> None:
    response = asyncio.run(_request("GET", "/api/v1/plugins"))

    assert response.status_code == 200
    plugins = response.json()
    assert [plugin["plugin_id"] for plugin in plugins] == ["moving-average"]
    assert "plugin_file" not in plugins[0]


def test_plugin_run_returns_deterministic_indicator_output() -> None:
    payload: dict[str, object] = {
        "seed": 7,
        "input": {"instrument": "DEMO", "prices": [9, 10, 11, 12], "window": 3},
    }
    first = asyncio.run(_request("POST", "/api/v1/plugins/moving-average/run", json=payload))
    second = asyncio.run(_request("POST", "/api/v1/plugins/moving-average/run", json=payload))

    assert first.status_code == 200
    assert first.json()["output_sha256"] == second.json()["output_sha256"]
    assert first.json()["result"]["output"]["simple_moving_average"] == 11.0


def test_plugin_run_rejects_unknown_plugins_and_extra_request_fields() -> None:
    unknown = asyncio.run(
        _request("POST", "/api/v1/plugins/not-installed/run", json={"seed": 1, "input": {}})
    )
    invalid = asyncio.run(
        _request(
            "POST",
            "/api/v1/plugins/moving-average/run",
            json={"seed": 1, "input": {}, "force": True},
        )
    )

    assert unknown.status_code == 404
    assert invalid.status_code == 422
