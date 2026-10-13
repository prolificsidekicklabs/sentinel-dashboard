"""Local development API for Sentinel's plugin and read-only paper-data foundations."""

from __future__ import annotations

import asyncio
import hmac
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, ValidationError

from sentinel_core import __version__
from sentinel_core.adapters.alpaca import (
    AlpacaError,
    AlpacaMarketDataAdapter,
    AlpacaNotConfigured,
    AlpacaReadOnlyBrokerAdapter,
    AlpacaSettings,
)
from sentinel_core.adapters.ports import (
    AccountSnapshot,
    MarketDataQuery,
    MarketSnapshot,
    PositionSnapshot,
)
from sentinel_core.candidate_strategy import CandidateReview, CandidateRiskGate, CandidateSignal
from sentinel_core.contracts import PluginRunRequest
from sentinel_core.manifest import ManifestError, PluginManifest, PluginType
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
PAPER_TRADING_BASE_URL = "https://paper-api.alpaca.markets"
API_KEY_ENV = "SENTINEL_API_KEY"
CANDIDATE_PLUGIN_ID = "rsi-macd-candidate"
CANDIDATE_LOOKBACK_DAYS = 365
runtime = PluginRuntime(PLUGIN_ROOT)
candidate_risk_gate = CandidateRiskGate()
bearer = HTTPBearer(auto_error=False)
app = FastAPI(
    title="Sentinel Core API",
    version=__version__,
    description="Local, authenticated plugin and read-only paper-data API.",
)


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    """Require a strong server-to-server bearer token using constant-time comparison."""
    expected = os.environ.get(API_KEY_ENV, "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="local API authentication is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hmac.compare_digest(credentials.credentials.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def paper_settings_from_environment(environ: dict[str, str] | None = None) -> AlpacaSettings:
    """Load server-side keys but force the broker endpoint to Alpaca paper, never live."""
    configured = AlpacaSettings.from_environment(environ)
    return replace(
        configured,
        trading_base_url=PAPER_TRADING_BASE_URL,
        allow_live_reads=False,
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


class MarketBarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    instrument_id: str
    observed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    currency: str
    source_id: str


class MarketSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    instrument_id: str
    timeframe: str
    source_id: str
    observed_at: datetime
    received_at: datetime
    quality: str
    bars: list[MarketBarResponse]


class PaperAccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: Literal[True] = True
    currency: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    observed_at: datetime


class PaperPositionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    instrument_id: str
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    currency: str


class PaperDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["paper-read-only"] = "paper-read-only"
    execution_enabled: Literal[False] = False
    captured_at: datetime
    market: MarketSnapshotResponse
    account: PaperAccountResponse
    positions: list[PaperPositionResponse]


class CandidateMarketMetadata(BaseModel):
    """Small, non-account market-data envelope for a research candidate."""

    model_config = ConfigDict(extra="forbid")

    instrument_id: str
    timeframe: str
    source_id: str
    quality: str
    observed_at: datetime
    received_at: datetime
    bar_count: int


class CandidateEvaluationResponse(BaseModel):
    """Research-only candidate and review-gate result; no account data or orders."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["research-candidate"] = "research-candidate"
    execution_enabled: Literal[False] = False
    captured_at: datetime
    market: CandidateMarketMetadata
    signal: CandidateSignal
    review: CandidateReview
    output_sha256: str


@app.get("/healthz")
def health() -> dict[str, str]:
    """Return public liveness only, without provider or credential state."""
    return {"status": "ok", "service": "sentinel-core", "version": __version__}


def _provider_not_configured() -> HTTPException:
    return HTTPException(status_code=503, detail="paper data provider is not configured")


def _find_plugin_manifest(plugin_id: str) -> PluginManifest | None:
    try:
        return next(
            (manifest for manifest in runtime.list_plugins() if manifest.plugin_id == plugin_id),
            None,
        )
    except ManifestError as exc:
        raise HTTPException(status_code=500, detail="a local plugin manifest is invalid") from exc


def _make_market_adapter() -> AlpacaMarketDataAdapter:
    try:
        settings = paper_settings_from_environment()
        return AlpacaMarketDataAdapter(settings)
    except (AlpacaNotConfigured, ValueError):
        raise _provider_not_configured() from None


def _make_paper_broker_adapter() -> AlpacaReadOnlyBrokerAdapter:
    try:
        return AlpacaReadOnlyBrokerAdapter(paper_settings_from_environment())
    except (AlpacaNotConfigured, ValueError):
        raise _provider_not_configured() from None


@app.get(
    "/api/v1/plugins", response_model=list[PluginSummary], dependencies=[Depends(require_api_key)]
)
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


@app.post(
    "/api/v1/plugins/{plugin_id}/run",
    response_model=PluginRunResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_plugin(plugin_id: str, request: PluginRunRequest) -> PluginRunResponse:
    """Run a local, trusted plugin with caller-provided JSON and an explicit seed."""
    manifest = _find_plugin_manifest(plugin_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="plugin is not installed")
    if manifest.plugin_type is PluginType.STRATEGY:
        raise HTTPException(
            status_code=409,
            detail="strategy plugins must use the independent research review endpoint",
        )
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


@app.get(
    "/api/v1/research/strategies/rsi-macd-candidate",
    response_model=CandidateEvaluationResponse,
    dependencies=[Depends(require_api_key)],
)
async def evaluate_rsi_macd_candidate(
    symbol: str = Query(default="SPY", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$"),
) -> CandidateEvaluationResponse:
    """Run daily-bar candidate analysis and its separate review-only risk gate."""
    manifest = _find_plugin_manifest(CANDIDATE_PLUGIN_ID)
    if manifest is None or manifest.plugin_type is not PluginType.STRATEGY:
        raise HTTPException(status_code=404, detail="candidate strategy is not installed")

    now = datetime.now(UTC)
    normalized_symbol = symbol.strip().upper()
    query = MarketDataQuery(
        instrument_id=normalized_symbol,
        timeframe="1Day",
        start=now - timedelta(days=CANDIDATE_LOOKBACK_DAYS),
        end=now,
    )
    try:
        market = await _make_market_adapter().get_bars(query)
    except AlpacaError:
        raise HTTPException(status_code=502, detail="market data provider request failed") from None
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=502, detail="market data provider returned invalid data"
        ) from None

    if (
        market.instrument_id.strip().upper() != normalized_symbol
        or market.timeframe != query.timeframe
    ):
        raise HTTPException(
            status_code=502,
            detail="market data provider returned an unexpected instrument or timeframe",
        )

    plugin_request = PluginRunRequest(
        seed=0,
        input={
            "instrument_id": market.instrument_id,
            "timeframe": market.timeframe,
            "observed_at": market.observed_at.astimezone(UTC).isoformat(),
            "bars": [
                {
                    "instrument_id": bar.instrument_id,
                    "observed_at": bar.observed_at.astimezone(UTC).isoformat(),
                    "close": str(bar.close),
                }
                for bar in market.bars
            ],
        },
    )
    try:
        execution = await runtime.run(CANDIDATE_PLUGIN_ID, plugin_request)
    except PluginNotFound as exc:
        raise HTTPException(status_code=404, detail="candidate strategy is not installed") from exc
    except PluginPermissionDenied as exc:
        raise HTTPException(
            status_code=403, detail="strategy permissions were not granted"
        ) from exc
    except PluginInputTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except PluginOutputTooLarge as exc:
        raise HTTPException(
            status_code=502, detail="strategy output exceeded the runtime limit"
        ) from exc
    except PluginTimeout as exc:
        raise HTTPException(
            status_code=504, detail="strategy exceeded the runtime timeout"
        ) from exc
    except PluginExecutionError as exc:
        raise HTTPException(
            status_code=502, detail="strategy execution failed its contract"
        ) from exc
    except ManifestError as exc:
        raise HTTPException(status_code=500, detail="the strategy manifest is invalid") from exc

    try:
        signal = CandidateSignal.model_validate(execution.result.output["signal"])
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=502, detail="strategy returned an invalid typed signal"
        ) from exc
    review = candidate_risk_gate.evaluate(signal, market, evaluated_at=now)
    return CandidateEvaluationResponse(
        captured_at=now,
        market=CandidateMarketMetadata(
            instrument_id=market.instrument_id,
            timeframe=market.timeframe,
            source_id=market.source_id,
            quality=market.quality.value,
            observed_at=market.observed_at,
            received_at=market.received_at,
            bar_count=len(market.bars),
        ),
        signal=signal,
        review=review,
        output_sha256=execution.output_sha256,
    )


@app.get(
    "/api/v1/paper/dashboard",
    response_model=PaperDashboardResponse,
    dependencies=[Depends(require_api_key)],
)
async def read_paper_dashboard(
    symbol: str = Query(default="SPY", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$"),
    days: int = Query(default=30, ge=1, le=365),
) -> PaperDashboardResponse:
    """Fetch bounded historical bars and paper account/positions; no execution path exists."""
    market_adapter = _make_market_adapter()
    broker_adapter = _make_paper_broker_adapter()
    now = datetime.now(UTC)
    normalized_symbol = symbol.strip().upper()
    query = MarketDataQuery(
        instrument_id=normalized_symbol,
        timeframe="1Day",
        start=now - timedelta(days=days),
        end=now,
    )
    try:
        market, account, positions = await asyncio.gather(
            market_adapter.get_bars(query),
            broker_adapter.get_account(),
            broker_adapter.get_positions(),
        )
    except AlpacaError:
        raise HTTPException(status_code=502, detail="paper data provider request failed") from None
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=502, detail="paper data provider returned invalid data"
        ) from None

    return PaperDashboardResponse(
        captured_at=now,
        market=_market_response(market),
        account=_paper_account_response(account),
        positions=[_position_response(position) for position in positions],
    )


def _market_response(snapshot: MarketSnapshot) -> MarketSnapshotResponse:
    return MarketSnapshotResponse.model_validate(snapshot)


def _paper_account_response(account: AccountSnapshot) -> PaperAccountResponse:
    return PaperAccountResponse(
        currency=account.currency,
        equity=account.equity,
        cash=account.cash,
        buying_power=account.buying_power,
        observed_at=account.observed_at,
    )


def _position_response(position: PositionSnapshot) -> PaperPositionResponse:
    return PaperPositionResponse.model_validate(position)
