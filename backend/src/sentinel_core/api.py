"""Development API for the local Sentinel plugin foundation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from sentinel_core import __version__
from sentinel_core.contracts import PluginRunRequest
from sentinel_core.manifest import ManifestError
from sentinel_core.runtime import (
    PluginExecutionError,
    PluginInputTooLarge,
    PluginNotFound,
    PluginOutputTooLarge,
    PluginPermissionDenied,
    PluginRuntime,
    PluginTimeout,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins"
runtime = PluginRuntime(PLUGIN_ROOT)
app = FastAPI(
    title="Sentinel Core API",
    version=__version__,
    description="Local development API for the Sentinel plugin-contract foundation.",
)


class PluginSummary(BaseModel):
    """Public plugin listing fields; filesystem paths are not exposed."""

    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    name: str
    version: str
    plugin_type: str
    deterministic: bool
    permissions: list[str]
    description: str


class PluginRunResponse(BaseModel):
    """Response for a successful local plugin run."""

    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    plugin_version: str
    seed: int
    result: dict[str, Any]
    output_sha256: str


@app.get("/healthz")
def health() -> dict[str, str]:
    """Return liveness only; this is not a dependency or data-feed health check."""
    return {"status": "ok", "service": "sentinel-core", "version": __version__}


@app.get("/api/v1/plugins", response_model=list[PluginSummary])
def list_plugins() -> list[PluginSummary]:
    """List locally installed, schema-valid plugin manifests."""
    try:
        manifests = runtime.list_plugins()
    except ManifestError as exc:
        raise HTTPException(status_code=500, detail="a local plugin manifest is invalid") from exc
    return [
        PluginSummary(
            plugin_id=manifest.plugin_id,
            name=manifest.name,
            version=manifest.version,
            plugin_type=manifest.plugin_type.value,
            deterministic=manifest.deterministic,
            permissions=[permission.value for permission in manifest.permissions],
            description=manifest.description,
        )
        for manifest in manifests
    ]


@app.post("/api/v1/plugins/{plugin_id}/run", response_model=PluginRunResponse)
async def run_plugin(plugin_id: str, request: PluginRunRequest) -> PluginRunResponse:
    """Run a locally installed plugin with caller-provided JSON and an explicit seed."""
    try:
        execution = await runtime.run(plugin_id, request)
    except PluginNotFound as exc:
        raise HTTPException(status_code=404, detail="plugin is not installed") from exc
    except PluginPermissionDenied as exc:
        raise HTTPException(status_code=403, detail="plugin permissions were not granted") from exc
    except PluginInputTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except PluginOutputTooLarge as exc:
        raise HTTPException(
            status_code=502, detail="plugin output exceeded the runtime limit"
        ) from exc
    except PluginTimeout as exc:
        raise HTTPException(status_code=504, detail="plugin exceeded the runtime timeout") from exc
    except PluginExecutionError as exc:
        raise HTTPException(status_code=502, detail="plugin execution failed its contract") from exc
    except ManifestError as exc:
        raise HTTPException(status_code=500, detail="the local plugin manifest is invalid") from exc

    return PluginRunResponse(
        plugin_id=execution.plugin_id,
        plugin_version=execution.plugin_version,
        seed=execution.seed,
        result=execution.result.model_dump(mode="json"),
        output_sha256=execution.output_sha256,
    )
