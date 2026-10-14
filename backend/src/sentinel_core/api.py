"""Authenticated API for Sentinel's research, durable-data, and guarded paper foundations."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from sentinel_core import __version__
from sentinel_core.adapters.alpaca import (
    AlpacaError,
    AlpacaMarketDataAdapter,
    AlpacaNotConfigured,
    AlpacaReadOnlyBrokerAdapter,
    AlpacaSettings,
)
from sentinel_core.adapters.alpaca_paper_execution import (
    AlpacaPaperExecutionAdapter,
    RiskAuthorizationRejected,
)
from sentinel_core.adapters.ports import (
    AccountSnapshot,
    MarketDataQuery,
    MarketSnapshot,
    OrderIntent,
    OrderSide,
    OrderType,
    PositionSnapshot,
    RiskApprovedOrder,
)
from sentinel_core.auth import (
    AuthConfigurationError,
    InvalidAccessToken,
    OIDCSettings,
    OIDCVerifier,
    Principal,
)
from sentinel_core.candidate_strategy import CandidateReview, CandidateRiskGate, CandidateSignal
from sentinel_core.contracts import PluginMarketBarV1, PluginMarketContextV1, PluginRunRequest
from sentinel_core.manifest import ManifestError, PluginManifest, PluginType
from sentinel_core.oci_sandbox import OCISandboxRunner
from sentinel_core.risk import PaperRiskEvaluator
from sentinel_core.robust_backtest import BacktestConfig, run_walk_forward_backtest
from sentinel_core.runtime import (
    PluginExecutionError,
    PluginInputTooLarge,
    PluginNotFound,
    PluginOutputTooLarge,
    PluginPermissionDenied,
    PluginRuntime,
    PluginSandboxUnavailable,
    PluginTimeout,
)
from sentinel_core.storage import (
    ACTIVE_PAPER_ORDER_STATUSES,
    ActivePaperOrderConflict,
    DurableStore,
    IdempotencyConflict,
    StorageError,
    StorageNotConfigured,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins"
PAPER_TRADING_BASE_URL = "https://paper-api.alpaca.markets"
API_KEY_ENV = "SENTINEL_API_KEY"
CANDIDATE_PLUGIN_ID = "rsi-macd-candidate"
CANDIDATE_LOOKBACK_DAYS = 365
runtime = PluginRuntime(PLUGIN_ROOT, sandbox_runner=OCISandboxRunner())
candidate_risk_gate = CandidateRiskGate()
paper_risk_evaluator = PaperRiskEvaluator()
bearer = HTTPBearer(auto_error=False)
_oidc_settings: OIDCSettings | None = None
_oidc_verifier: OIDCVerifier | None = None
app = FastAPI(
    title="Sentinel Core API",
    version=__version__,
    description="OIDC-authenticated research API with disabled-by-default paper execution.",
)


@app.exception_handler(RequestValidationError)
async def sanitize_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Do not echo submitted values, which may include provider credentials."""
    del request
    safe_errors = [
        {key: value for key, value in error.items() if key not in {"input", "ctx"}}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


async def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    """Authenticate OIDC users, with a non-production shared-key compatibility path."""
    global _oidc_settings, _oidc_verifier
    try:
        settings = OIDCSettings.from_environment()
    except AuthConfigurationError:
        raise HTTPException(status_code=503, detail="identity provider is not configured") from None
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if settings is not None:
        if _oidc_settings != settings or _oidc_verifier is None:
            _oidc_settings = settings
            _oidc_verifier = OIDCVerifier(settings)
        try:
            return await _oidc_verifier.verify(credentials.credentials)
        except InvalidAccessToken:
            raise HTTPException(
                status_code=401,
                detail="invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
    if os.environ.get("SENTINEL_ENV", "development").strip().lower() == "production":
        raise HTTPException(status_code=503, detail="OIDC authentication is required")
    expected = os.environ.get(API_KEY_ENV, "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="local API authentication is not configured")
    if not hmac.compare_digest(credentials.credentials.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    owner_id = hashlib.sha256(b"sentinel-local-development-service").hexdigest()
    return Principal(
        owner_id=owner_id,
        subject="local-development-service",
        scopes=frozenset(
            {"plugins:read", "plugins:run", "paper:read", "research:read", "research:run"}
        ),
        auth_method="api-key",
    )


VERIFIED_PRINCIPAL = Depends(require_api_key)


def paper_settings_from_environment(environ: dict[str, str] | None = None) -> AlpacaSettings:
    """Load server-side keys but force the broker endpoint to Alpaca paper, never live."""
    configured = AlpacaSettings.from_environment(environ)
    return replace(
        configured,
        trading_base_url=PAPER_TRADING_BASE_URL,
        allow_live_reads=False,
    )


@lru_cache(maxsize=8)
def _store_for_path(path: str) -> DurableStore:
    return DurableStore(path)


def _store() -> DurableStore:
    path = os.environ.get("SENTINEL_DATABASE_PATH", "./var/sentinel.sqlite3")
    return _store_for_path(path)


def _environment_for_principal(principal: Principal | None) -> dict[str, str]:
    values = dict(os.environ)
    if principal is None or principal.auth_method != "oidc":
        return values
    store = _store()
    if store.credential_exists(principal.owner_id, "alpaca"):
        try:
            credential = store.get_credential(principal.owner_id, "alpaca")
        except StorageError:
            raise HTTPException(
                status_code=503, detail="provider credentials are unavailable"
            ) from None
        if credential is None:
            raise HTTPException(status_code=503, detail="provider credentials are unavailable")
        values["SENTINEL_ALPACA_KEY_ID"] = credential.get("key_id", "")
        values["SENTINEL_ALPACA_SECRET_KEY"] = credential.get("secret_key", "")
        return values
    if os.environ.get("SENTINEL_ENV", "development").strip().lower() == "production":
        raise HTTPException(status_code=503, detail="provider credentials are not configured")
    return values


class PluginSummary(BaseModel):
    """Public plugin listing fields; filesystem paths are not exposed."""

    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    name: str
    version: str
    plugin_api_version: str
    plugin_type: str
    trust_level: str
    deterministic: bool
    permissions: list[str]
    description: str


class PluginRunResponse(BaseModel):
    """Response for a successful local plugin run."""

    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    plugin_version: str
    plugin_api_version: str
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
    plugin_api_version: Literal["1.0"] = "1.0"
    captured_at: datetime
    market: CandidateMarketMetadata
    signal: CandidateSignal
    review: CandidateReview
    output_sha256: str
    record_id: str


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


def _plugin_market_context(market: MarketSnapshot) -> PluginMarketContextV1:
    """Project a provider snapshot into the account-free, versioned plugin contract."""
    return PluginMarketContextV1(
        plugin_api_version="1.0",
        instrument_id=market.instrument_id,
        timeframe=market.timeframe,
        source_id=market.source_id,
        quality=market.quality.value,
        observed_at=market.observed_at,
        received_at=market.received_at,
        bars=tuple(
            PluginMarketBarV1(
                instrument_id=bar.instrument_id,
                observed_at=bar.observed_at,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                currency=bar.currency,
                source_id=bar.source_id,
            )
            for bar in market.bars
        ),
    )


def _make_market_adapter(principal: Principal | None = None) -> AlpacaMarketDataAdapter:
    try:
        settings = paper_settings_from_environment(_environment_for_principal(principal))
        return AlpacaMarketDataAdapter(settings)
    except (AlpacaNotConfigured, ValueError):
        raise _provider_not_configured() from None


def _make_paper_broker_adapter(principal: Principal | None = None) -> AlpacaReadOnlyBrokerAdapter:
    try:
        return AlpacaReadOnlyBrokerAdapter(
            paper_settings_from_environment(_environment_for_principal(principal))
        )
    except (AlpacaNotConfigured, ValueError):
        raise _provider_not_configured() from None


@app.get("/api/v1/plugins", response_model=list[PluginSummary])
def list_plugins(principal: Principal = VERIFIED_PRINCIPAL) -> list[PluginSummary]:
    """List locally installed, schema-valid plugin manifests."""
    _require_plugin_scope(principal, "plugins:read")
    try:
        manifests = runtime.list_plugins()
    except ManifestError as exc:
        raise HTTPException(status_code=500, detail="a local plugin manifest is invalid") from exc
    return [
        PluginSummary(
            plugin_id=manifest.plugin_id,
            name=manifest.name,
            version=manifest.version,
            plugin_api_version=manifest.plugin_api_version,
            plugin_type=manifest.plugin_type.value,
            trust_level=manifest.trust_level,
            deterministic=manifest.deterministic,
            permissions=[permission.value for permission in manifest.permissions],
            description=manifest.description,
        )
        for manifest in manifests
    ]


@app.post(
    "/api/v1/plugins/{plugin_id}/run",
    response_model=PluginRunResponse,
)
async def run_plugin(
    plugin_id: str,
    request: PluginRunRequest,
    principal: Principal = VERIFIED_PRINCIPAL,
) -> PluginRunResponse:
    """Run a local, trusted plugin with caller-provided JSON and an explicit seed."""
    _require_plugin_scope(principal, "plugins:run")
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
    except PluginSandboxUnavailable:
        raise HTTPException(
            status_code=503, detail="isolated plugin sandbox is unavailable"
        ) from None
    except PluginExecutionError as exc:
        raise HTTPException(status_code=502, detail="plugin execution failed its contract") from exc
    except ManifestError as exc:
        raise HTTPException(status_code=500, detail="the local plugin manifest is invalid") from exc

    return PluginRunResponse(
        plugin_id=execution.plugin_id,
        plugin_version=execution.plugin_version,
        plugin_api_version=execution.plugin_api_version,
        seed=execution.seed,
        result=execution.result.model_dump(mode="json"),
        output_sha256=execution.output_sha256,
    )


@app.get(
    "/api/v1/research/strategies/rsi-macd-candidate",
    response_model=CandidateEvaluationResponse,
)
async def evaluate_rsi_macd_candidate(
    symbol: str = Query(default="SPY", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$"),
    principal: Principal = VERIFIED_PRINCIPAL,
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
        market = await _make_market_adapter(principal).get_bars(query)
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

    try:
        plugin_request = PluginRunRequest(
            plugin_api_version=manifest.plugin_api_version,
            seed=0,
            input={},
            market_context=_plugin_market_context(market),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=502, detail="market snapshot failed the plugin contract"
        ) from exc
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
    except PluginSandboxUnavailable:
        raise HTTPException(
            status_code=503, detail="isolated plugin sandbox is unavailable"
        ) from None
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
    market_metadata = CandidateMarketMetadata(
        instrument_id=market.instrument_id,
        timeframe=market.timeframe,
        source_id=market.source_id,
        quality=market.quality.value,
        observed_at=market.observed_at,
        received_at=market.received_at,
        bar_count=len(market.bars),
    )
    try:
        record_id = _store().append_audit_event(
            principal.owner_id,
            "research.candidate.evaluated",
            {
                "plugin_id": execution.plugin_id,
                "plugin_version": execution.plugin_version,
                "plugin_api_version": execution.plugin_api_version,
                "market": market_metadata.model_dump(mode="json"),
                "signal": signal.model_dump(mode="json"),
                "review": review.model_dump(mode="json"),
                "output_sha256": execution.output_sha256,
            },
        )
    except (StorageError, sqlite3.Error, OSError) as exc:
        raise HTTPException(
            status_code=503, detail="candidate result could not be durably recorded"
        ) from exc
    return CandidateEvaluationResponse(
        captured_at=now,
        plugin_api_version=execution.plugin_api_version,
        market=market_metadata,
        signal=signal,
        review=review,
        output_sha256=execution.output_sha256,
        record_id=record_id,
    )


@app.get(
    "/api/v1/paper/dashboard",
    response_model=PaperDashboardResponse,
)
async def read_paper_dashboard(
    symbol: str = Query(default="SPY", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$"),
    days: int = Query(default=30, ge=1, le=365),
    principal: Principal = VERIFIED_PRINCIPAL,
) -> PaperDashboardResponse:
    """Fetch bounded historical bars and paper account/positions; no order submission here."""
    market_adapter = _make_market_adapter(principal)
    broker_adapter = _make_paper_broker_adapter(principal)
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


class AlpacaCredentialInput(BaseModel):
    """Credential body whose secret fields are masked in model representations."""

    model_config = ConfigDict(extra="forbid")

    key_id: SecretStr = Field(min_length=1, max_length=256)
    secret_key: SecretStr = Field(min_length=1, max_length=4096)


class CredentialStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["alpaca"] = "alpaca"
    configured: bool
    stored_encrypted: bool = True


class PaperOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$")
    side: OrderSide
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=6)
    order_type: Literal["market"] = "market"
    confirm_paper_order: Literal[True]


class PaperOrderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper: Literal[True] = True
    execution_enabled: Literal[True] = True
    client_order_id: str
    broker_order_id: str | None = None
    status: str
    risk_policy_id: str
    risk_policy_version: str
    risk_evaluation_id: str
    risk_reasons: list[str]
    unassessed_risks: list[str]
    submitted_at: str


class WalkForwardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(default="SPY", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$")
    fast_period: int = Field(default=10, ge=2, le=200)
    slow_period: int = Field(default=30, ge=3, le=500)
    starting_capital: Decimal = Field(
        default=Decimal("10000"), gt=0, max_digits=12, decimal_places=2
    )
    allocation_pct: Decimal = Field(
        default=Decimal("0.95"), gt=0, le=1, max_digits=4, decimal_places=3
    )
    commission_bps: Decimal = Field(
        default=Decimal("1"), ge=0, le=1000, max_digits=6, decimal_places=2
    )
    half_spread_bps: Decimal = Field(
        default=Decimal("2"), ge=0, le=1000, max_digits=6, decimal_places=2
    )
    slippage_bps: Decimal = Field(
        default=Decimal("3"), ge=0, le=1000, max_digits=6, decimal_places=2
    )
    folds: int = Field(default=5, ge=2, le=10)


def _require_oidc_scope(principal: Principal, scope: str) -> None:
    if principal.auth_method != "oidc":
        raise HTTPException(status_code=403, detail="verified user identity is required")
    if not principal.has_scope(scope):
        raise HTTPException(status_code=403, detail="required permission is missing")


def _require_plugin_scope(principal: Principal, scope: str) -> None:
    """Require a plugin capability explicitly present on the verified principal."""
    if not principal.has_scope(scope):
        raise HTTPException(status_code=403, detail="required permission is missing")


def _make_paper_execution_adapter(principal: Principal) -> AlpacaPaperExecutionAdapter:
    try:
        return AlpacaPaperExecutionAdapter(
            paper_settings_from_environment(_environment_for_principal(principal))
        )
    except (AlpacaNotConfigured, ValueError):
        raise _provider_not_configured() from None


def _paper_order_view(
    stored: dict[str, Any],
    *,
    risk_policy_id: str = "sentinel-paper-risk",
    risk_policy_version: str = "1.0.0",
    risk_evaluation_id: str = "persisted-order",
    risk_reasons: list[str] | None = None,
    unassessed_risks: list[str] | None = None,
) -> PaperOrderResponse:
    response = stored.get("response") or {}
    return PaperOrderResponse(
        client_order_id=stored["client_order_id"],
        broker_order_id=response.get("id"),
        status=stored["status"],
        risk_policy_id=risk_policy_id,
        risk_policy_version=risk_policy_version,
        risk_evaluation_id=risk_evaluation_id,
        risk_reasons=risk_reasons or ["risk evaluation is recorded in the audit ledger"],
        unassessed_risks=unassessed_risks
        or ["intraday loss and actual fill quality are not assessed"],
        submitted_at=stored["created_at"],
    )


@app.get("/api/v1/me/credentials/alpaca", response_model=CredentialStatusResponse)
def read_alpaca_credential_status(
    principal: Principal = VERIFIED_PRINCIPAL,
) -> CredentialStatusResponse:
    _require_oidc_scope(principal, "credentials:read")
    try:
        configured = _store().credential_exists(principal.owner_id, "alpaca")
    except StorageError:
        raise HTTPException(status_code=503, detail="credential status is unavailable") from None
    return CredentialStatusResponse(configured=configured)


@app.put("/api/v1/me/credentials/alpaca", response_model=CredentialStatusResponse)
def save_alpaca_credentials(
    credential: AlpacaCredentialInput,
    principal: Principal = VERIFIED_PRINCIPAL,
) -> CredentialStatusResponse:
    _require_oidc_scope(principal, "credentials:write")
    try:
        _store().put_credential(
            principal.owner_id,
            "alpaca",
            {
                "key_id": credential.key_id.get_secret_value(),
                "secret_key": credential.secret_key.get_secret_value(),
            },
        )
    except StorageNotConfigured:
        raise HTTPException(
            status_code=503, detail="encrypted credential storage is not configured"
        ) from None
    except StorageError:
        raise HTTPException(status_code=503, detail="credential could not be stored") from None
    except ValueError:
        raise HTTPException(status_code=400, detail="credential could not be stored") from None
    return CredentialStatusResponse(configured=True)


@app.delete("/api/v1/me/credentials/alpaca", response_model=CredentialStatusResponse)
def delete_alpaca_credentials(
    principal: Principal = VERIFIED_PRINCIPAL,
) -> CredentialStatusResponse:
    _require_oidc_scope(principal, "credentials:write")
    try:
        configured = _store().delete_credential(principal.owner_id, "alpaca")
    except StorageError:
        raise HTTPException(status_code=503, detail="credential could not be deleted") from None
    return CredentialStatusResponse(configured=not configured)


@app.get("/api/v1/audit/events")
def read_audit_events(
    principal: Principal = VERIFIED_PRINCIPAL,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    _require_oidc_scope(principal, "audit:read")
    store = _store()
    if not store.verify_audit_chain():
        raise HTTPException(status_code=503, detail="audit integrity verification failed")
    return {
        "events": store.list_audit_events(principal.owner_id, limit=limit),
        "integrity_verified": True,
    }


@app.post("/api/v1/research/backtests/walk-forward")
async def create_walk_forward_backtest(
    request: WalkForwardRequest,
    principal: Principal = VERIFIED_PRINCIPAL,
) -> dict[str, Any]:
    _require_oidc_scope(principal, "research:run")
    if request.slow_period <= request.fast_period:
        raise HTTPException(status_code=422, detail="slow_period must be greater than fast_period")
    now = datetime.now(UTC)
    try:
        market = await _make_market_adapter(principal).get_bars(
            MarketDataQuery(
                instrument_id=request.symbol.strip().upper(),
                timeframe="1Day",
                start=now - timedelta(days=365 * 5),
                end=now,
            )
        )
        result = run_walk_forward_backtest(
            market,
            BacktestConfig(
                fast_period=request.fast_period,
                slow_period=request.slow_period,
                starting_capital=request.starting_capital,
                allocation_pct=request.allocation_pct,
                commission_bps=request.commission_bps,
                half_spread_bps=request.half_spread_bps,
                slippage_bps=request.slippage_bps,
                folds=request.folds,
            ),
            evaluated_at=now,
        )
    except HTTPException:
        raise
    except AlpacaError:
        raise HTTPException(status_code=502, detail="market data provider request failed") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    try:
        _store().save_experiment(
            run_id=result["run_id"],
            owner_id=principal.owner_id,
            strategy_id=result["strategy_id"],
            source_id=result["source_id"],
            dataset_sha256=result["dataset_sha256"],
            parameters=result["parameters"],
            result=result,
        )
    except StorageError:
        raise HTTPException(
            status_code=503, detail="research record could not be persisted"
        ) from None
    return result


@app.get("/api/v1/research/backtests/{run_id}")
def read_walk_forward_backtest(
    run_id: str,
    principal: Principal = VERIFIED_PRINCIPAL,
) -> dict[str, Any]:
    _require_oidc_scope(principal, "research:read")
    if len(run_id) != 64 or any(character not in "0123456789abcdef" for character in run_id):
        raise HTTPException(status_code=404, detail="research run not found")
    result = _store().get_experiment(principal.owner_id, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="research run not found")
    return result


@app.post("/api/v1/paper/orders", response_model=PaperOrderResponse)
async def submit_paper_order(
    request: PaperOrderRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    principal: Principal = VERIFIED_PRINCIPAL,
) -> PaperOrderResponse:
    """Submit one explicitly confirmed, risk-approved paper order; live execution is impossible."""
    _require_oidc_scope(principal, "paper:trade")
    if os.environ.get("SENTINEL_PAPER_EXECUTION_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=503, detail="paper order submission is disabled")
    if any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
        for character in idempotency_key
    ):
        raise HTTPException(
            status_code=422, detail="idempotency key contains unsupported characters"
        )

    store = _store()
    symbol = request.symbol.strip().upper()
    order_request = {
        "symbol": symbol,
        "side": request.side.value,
        "quantity": str(request.quantity),
        "type": "market",
    }
    existing = store.get_paper_order(principal.owner_id, idempotency_key)
    if existing is not None:
        if existing["request"] != order_request:
            raise HTTPException(
                status_code=409, detail="idempotency key conflicts with an earlier order"
            )
        if existing["status"] in {"submitting", "unknown"}:
            raise HTTPException(
                status_code=409, detail="order outcome is unresolved; reconcile it before retrying"
            )
        return _paper_order_view(existing)
    if store.list_active_paper_orders(principal.owner_id):
        raise HTTPException(
            status_code=409,
            detail="reconcile the existing paper order before submitting another",
        )
    if not store.verify_audit_chain():
        raise HTTPException(status_code=503, detail="audit integrity verification failed")

    now = datetime.now(UTC)
    client_order_id = (
        "sentinel-"
        + hashlib.sha256(f"{principal.owner_id}:{idempotency_key}".encode()).hexdigest()[:32]
    )
    intent = OrderIntent(
        client_order_id=client_order_id,
        instrument_id=symbol,
        side=request.side,
        quantity=request.quantity,
        order_type=OrderType.MARKET,
    )
    query = MarketDataQuery(
        instrument_id=symbol,
        timeframe="1Min",
        start=now - timedelta(minutes=15),
        end=now,
    )
    try:
        market_adapter = _make_market_adapter(principal)
        broker_adapter = _make_paper_broker_adapter(principal)
        market, account, positions = await asyncio.gather(
            market_adapter.get_bars(query),
            broker_adapter.get_account(),
            broker_adapter.get_positions(),
        )
    except HTTPException:
        raise
    except AlpacaError:
        raise HTTPException(
            status_code=502, detail="paper account or market data request failed"
        ) from None
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=502, detail="provider data failed normalized validation"
        ) from None

    evaluation = paper_risk_evaluator.evaluate(intent, account, positions, market, evaluated_at=now)
    try:
        store.append_audit_event(
            principal.owner_id,
            "paper.order.risk-evaluated",
            {
                "client_order_id": client_order_id,
                "evaluation_id": evaluation.evaluation_id,
                "policy_id": evaluation.policy_id,
                "policy_version": evaluation.policy_version,
                "allowed": evaluation.allowed,
                "reasons": list(evaluation.reasons),
                "unassessed_risks": list(evaluation.unassessed_risks),
                "market_source": market.source_id,
                "market_observed_at": market.observed_at.isoformat(),
                "market_received_at": market.received_at.isoformat(),
                "market_quality": market.quality.value,
                "account_status": account.account_status,
                "account_observed_at": account.observed_at.isoformat(),
            },
        )
    except StorageError:
        raise HTTPException(
            status_code=503, detail="risk decision could not be durably recorded"
        ) from None
    if not evaluation.allowed:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "paper order rejected by server-side risk policy",
                "reasons": list(evaluation.reasons),
            },
        )

    execution_adapter = _make_paper_execution_adapter(principal)
    approved = RiskApprovedOrder(
        intent=intent,
        evaluation=evaluation,
        idempotency_key=idempotency_key,
        approved_by=principal.owner_id,
    )
    try:
        stored, is_new = store.create_paper_order(
            owner_id=principal.owner_id,
            idempotency_key=idempotency_key,
            client_order_id=client_order_id,
            request=order_request,
            risk_evaluation_id=evaluation.evaluation_id,
        )
    except IdempotencyConflict:
        raise HTTPException(
            status_code=409, detail="idempotency key conflicts with an earlier order"
        ) from None
    except ActivePaperOrderConflict:
        raise HTTPException(
            status_code=409,
            detail="another paper order became active; reconcile it before retrying",
        ) from None
    except StorageError:
        raise HTTPException(
            status_code=503, detail="paper order could not be durably recorded"
        ) from None
    if not is_new:
        if stored["status"] in {"submitting", "unknown"}:
            raise HTTPException(
                status_code=409, detail="order outcome is unresolved; reconcile it before retrying"
            )
        return _paper_order_view(stored)

    try:
        provider_order = await execution_adapter.submit_order(approved)
    except RiskAuthorizationRejected:
        store.update_paper_order(
            principal.owner_id,
            idempotency_key,
            "rejected",
            {"error": "paper_risk_approval_expired_or_invalid"},
        )
        raise HTTPException(
            status_code=409, detail="paper risk approval expired or became invalid"
        ) from None
    except AlpacaError:
        store.update_paper_order(
            principal.owner_id,
            idempotency_key,
            "unknown",
            {"error": "provider_submission_outcome_unknown"},
        )
        raise HTTPException(
            status_code=502,
            detail="paper order outcome is unknown; reconcile the stored order before retrying",
        ) from None
    updated = store.update_paper_order(
        principal.owner_id, idempotency_key, provider_order["status"], provider_order
    )
    if updated is None:
        raise HTTPException(status_code=503, detail="paper order response could not be recorded")
    return _paper_order_view(
        updated,
        risk_policy_id=evaluation.policy_id,
        risk_policy_version=evaluation.policy_version,
        risk_evaluation_id=evaluation.evaluation_id,
        risk_reasons=list(evaluation.reasons),
        unassessed_risks=list(evaluation.unassessed_risks),
    )


@app.get("/api/v1/paper/orders/{idempotency_key}", response_model=PaperOrderResponse)
async def reconcile_paper_order(
    idempotency_key: str,
    principal: Principal = VERIFIED_PRINCIPAL,
) -> PaperOrderResponse:
    _require_oidc_scope(principal, "paper:trade")
    stored = _store().get_paper_order(principal.owner_id, idempotency_key)
    if stored is None:
        raise HTTPException(status_code=404, detail="paper order not found")
    if stored["status"] in ACTIVE_PAPER_ORDER_STATUSES:
        try:
            provider_order = await _make_paper_execution_adapter(principal).get_order_by_client_id(
                stored["client_order_id"]
            )
        except (AlpacaError, HTTPException):
            raise HTTPException(
                status_code=502, detail="paper order reconciliation failed"
            ) from None
        if provider_order is not None:
            updated = _store().update_paper_order(
                principal.owner_id, idempotency_key, provider_order["status"], provider_order
            )
            if updated is not None:
                stored = updated
    return _paper_order_view(stored)
