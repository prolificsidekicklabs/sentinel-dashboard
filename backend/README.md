# Sentinel Python Service Foundation

This backend now includes an **OIDC-verifying API, encrypted per-user provider credentials, hash-chained audit records, a fail-closed OCI plugin runner, reproducible walk-forward research, an account-aware paper risk gate, and an optional paper-only order adapter**. It is a tested research and backend foundation, not a production-ready brokerage platform, profitability claim, or live-trading system. Identity-provider login UX, deployment hardening, a managed multi-node database/KMS, and a tested production sandbox runtime still require operator configuration and validation.

## Run locally

From this directory, install the service and development dependencies, then start FastAPI:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
uvicorn sentinel_core.api:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Only `GET /healthz` is public. Protected routes require a bearer token. Configure OIDC issuer, audience, and HTTPS JWKS URL together for verified OIDC access tokens; user scopes are enforced server-side. The shared `SENTINEL_API_KEY` compatibility path is development-only and is disabled when `SENTINEL_ENV=production`. **This repository does not include an interactive sign-in flow or connect the Next.js dashboard to an identity provider.** The existing Next.js-to-local-API proxy remains development-only and is disabled in production.

Never bind the development server to a public interface. For local dashboard setup, see [the development guide](../docs/DEVELOPMENT.md).

## Identity and protected credentials

- OIDC JWT signatures, issuer, audience, expiry, and required claims are verified against a bounded HTTPS JWKS cache. The cache does not follow redirects; scopes come from verified `scope`/`scp` claims.
- User-owned Alpaca credentials are accepted only on OIDC-protected routes with explicit `credentials:write` scope. They are encrypted using AES-GCM with owner/provider-bound associated data and a 32-byte `SENTINEL_VAULT_MASTER_KEY` supplied outside the database. Secret values are never returned by credential-status endpoints.
- Credential retrieval is recorded in the audit log. A read-only Alpaca key cannot submit trades; the paper-order adapter requires a provider key with paper-trading permissions.
- SQLite is a **single-node durability foundation** with restrictive file permissions, WAL, full synchronization, and transactions. Use a managed database and KMS, backups, key rotation, and tested restore procedures before multi-instance production. The local hash chain and SQLite triggers are tamper-evident controls, not an external immutable audit service.

## Market data and research

`AlpacaMarketDataAdapter` fetches bounded, paginated historical U.S.-equity bars and normalizes prices to `Decimal`, preserving the feed, timestamps, and provider provenance. The configured market-data subscription controls coverage, delay, history, and rate limits. `AlpacaReadOnlyBrokerAdapter` reads the paper account and positions; the dashboard API forces the official `https://paper-api.alpaca.markets` host and returns no account identifier.

`POST /api/v1/research/backtests/walk-forward` runs a fixed-parameter, chronological out-of-sample evaluation with next-bar-open estimated fills, explicit commissions/spread/slippage, buy-and-hold comparison, and cost-stress scenarios. Inputs and results are persisted by owner and dataset digest. This is not a statistically validated strategy-selection pipeline: corporate actions, dividends, taxes, market impact, lot rules, and significance/multiple-testing corrections are not modeled. A backtest is not evidence of future profitability.

The separate `rsi-macd-candidate` route remains a research-only directional label behind a review gate. It does not contain an order side, quantity, or execution authorization.

## Plugin trust boundary

Trusted, repository-reviewed local plugins can use the existing bounded subprocess runner. A manifest explicitly marked untrusted is routed only to the OCI runner, which **fails closed** unless an operator configures a digest-pinned worker image and rootless Docker with gVisor (`runsc`). The container uses no network, a read-only plugin mount/root filesystem, dropped capabilities, non-root UID, resource limits, a bounded protocol, and a hard timeout.

The sandbox worker image recipe is in `sandbox/Dockerfile`. The current environment has not built or run the OCI image; no claim of adversarial security testing is made. Do not enable marketplace plugins until the image is built from reviewed, pinned dependencies and the exact deployment runtime passes isolation and escape testing.

## Paper risk and execution boundary

Paper order submission is **disabled by default** (`SENTINEL_PAPER_EXECUTION_ENABLED=false`). The optional route requires a verified OIDC principal with `paper:trade`, an explicit `confirm_paper_order: true` field, an idempotency key, and user-owned paper credentials. The server always fixes the broker host to Alpaca's paper endpoint; no live-order adapter or live URL is supported.

Before a paper submission, the service checks provider provenance and freshness, account age and `ACTIVE` status, a fixed instrument allowlist, positive buying power/equity, a per-order notional ceiling, long-only sell limits, and single-symbol/gross exposure limits. Risk approvals expire quickly. SQLite reserves at most one non-terminal order per user, including concurrent submissions; unknown/pending orders must be reconciled before another is accepted. Order intent, risk reasons/policy version, market/account provenance, and state changes are audited.

The controls explicitly do **not** assess an intraday loss limit, predict fills or slippage, or establish live-trading suitability. Provider execution outcomes can remain unresolved and safely block subsequent orders. There is no order-cancel or liquidation endpoint and the UI does not expose the execution route. This code is for paper testing only.

## Environment configuration

Names and safe defaults are in [`.env.example`](.env.example). The service does not load `.env` files automatically. Supply values through the process environment or a deployment secret manager. Never commit credentials, place them in browser code, return them from an API, or log request headers. OIDC issuer/audience/JWKS, vault key, database, and sandbox image/runtime must be configured and operationally validated before their dependent features can run.

## Verify

```bash
ruff format --check src plugins tests
ruff check src plugins tests
mypy src plugins/rsi-macd-candidate/plugin.py
pytest -q
```

The backend has a separate GitHub Actions workflow. Run the root Next.js lint, type-check, tests, dependency audit, and build as well; backend CI does not replace those checks.
