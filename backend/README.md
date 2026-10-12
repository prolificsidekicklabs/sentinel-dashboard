# Sentinel Python Service Foundation

This folder contains the Python service alongside the Next.js dashboard. It is an early **contract and local-runtime foundation**, not a production trading backend. The local Next.js development server is wired to the authenticated, read-only paper dashboard route. After implementation, a user-authorized Alpaca paper account read succeeded through the local API and proxy; temporary local credential and response files were removed afterward.

## Run locally

From this directory, install the service and development dependencies, then start FastAPI:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
uvicorn sentinel_core.api:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

The API listens at `http://127.0.0.1:8000`. Only `GET /healthz` is public. Plugin routes and `GET /api/v1/paper/dashboard` require a server-to-server bearer token in `SENTINEL_API_KEY`; the token must be at least 32 characters. OpenAPI docs are available at `/docs` during development. Do not bind this service to a public interface.

The paper dashboard route fetches bounded historical bars and paper-account/position data, then returns normalized decimal strings, source and timestamps, `paper: true`, and `execution_enabled: false`. It does not return the provider account ID. Its broker URL is forcibly set to `https://paper-api.alpaca.markets` even if a live URL or live-read opt-in is present in the environment. The service exposes no order, cancel, or liquidation route.

For a local dashboard connection, set the same strong `SENTINEL_API_KEY` in this service and the Next.js server's root `.env.local`. Put Alpaca paper credentials only in the backend process environment. See [the development guide](../docs/DEVELOPMENT.md) for the exact two-terminal setup. If configuration is absent, the dashboard safely stays in its fixed synthetic demo mode.

## Model gateway adapter

`sentinel_core.adapters.model_router.OpenAICompatibleChatAdapter` implements the common OpenAI-compatible `/v1/chat/completions` interface. It is configured server-side and can be used with OmniRoute, 9Router, or another compatible gateway. The gateway's exact model identifier is configuration; do not assume all routers support the same aliases or routing modes. Each request enforces its configured timeout even when the application injects an HTTP client; streamed responses are capped at 2 MB, and normalized model text is capped at 128 KB.

Configuration names are in `.env.example`. Copy values into the **backend process environment or a deployment secret manager**; the service does not load `.env` files automatically. Never commit populated credentials, put them in browser code, return them through an API, or log request headers. For a local gateway, the default endpoint pattern is `http://127.0.0.1:20128/v1`; plain HTTP is restricted to loopback unless an explicit trusted-network override is set. Model output is untrusted and cannot approve risk or orders.

## Alpaca read-only adapters

`AlpacaMarketDataAdapter` fetches bounded, paginated historical U.S.-equity bars and normalizes values to `Decimal`, with timestamps, feed and provider provenance preserved. The default feed is `iex`; the account's Alpaca market-data subscription controls coverage, delay, history and rate limits.

`AlpacaReadOnlyBrokerAdapter` reads account summary and open positions from the **paper** Trading API by default. It has no order, cancel, or liquidation method. The dashboard API forces paper mode regardless of live-read environment flags. The adapter uses Alpaca Trading API key headers from `SENTINEL_ALPACA_KEY_ID` and `SENTINEL_ALPACA_SECRET_KEY`. These credentials are not stored in the browser, database, or source tree.

`GET /api/v1/research/strategies/rsi-macd-candidate?symbol=SPY` fetches up to 365 calendar days of daily bars through the read-only market adapter, runs a pure deterministic strategy plugin, validates its typed output, and applies `CandidateRiskGate`. This route returns only a research candidate and market-quality metadata; it does not fetch account or position data. Generic plugin execution refuses strategy-category plugins, so this candidate cannot bypass the review gate through the generic API. The response can be blocked, contain no candidate, or require human review; it always has `execution_enabled: false`.

## Contracts and deterministic boundaries

- `adapters.ports` defines provider-neutral market-data and broker-read interfaces, Decimal-based finance records, and an order proposal that is separate from authorization.
- `RiskEvaluator` is an independent policy port. A model response is never a risk evaluation.
- The future execution contract accepts only a `RiskApprovedOrder` carrying an explicit versioned risk evaluation and idempotency key. There is currently **no concrete broker execution adapter**.
- The moving-average example is illustrative only. The RSI/MACD/EMA candidate is a research-only directional label, not a recommendation or evidence of a strategy edge. Its separate review gate checks input quality/freshness and only allows human review; it does not assess account exposure or position sizing. See [the candidate-strategy contract and Alpaca SDK review](docs/CANDIDATE_STRATEGY.md).

## Plugin contract and execution boundary

A local plugin directory contains `sentinel_manifest.yaml`, `SKILL.md`, `plugin.py`, and `tests/`. Manifests use safe YAML parsing, reject duplicate keys, and are checked against a versioned Pydantic schema. The current generic async contract is `async def run(context: PluginContext) -> PluginResult`; plugin types include `strategy`, whose API path must apply the separate candidate review gate.

The run context contains a caller-supplied seed, a per-run `random.Random` seeded from it, and JSON input. It intentionally exposes no provider or broker clients. The sample plugin is deterministic and does not use randomness. Each run hashes canonicalized input, manifest identity, seed, and output so repeated executions can be compared.

Plugin code runs in a fresh Python subprocess with a scrubbed environment, temporary working directory, wall-clock timeout, and best-effort POSIX CPU, address-space, file-size, and file-descriptor limits. This provides process separation and fault/resource containment for **trusted, repository-reviewed local plugins** only. It is not a security sandbox for untrusted marketplace plugins; network access, filesystem isolation, privilege dropping, seccomp/container policy, and marketplace threat testing are not implemented.

## Known production gaps

The current service does not yet provide user identity/session authentication, role-based authorization, tenant isolation, encrypted persistent secret storage, audited connection management, rate limiting, durable jobs, a database, live data streams, a secure untrusted-plugin sandbox, CI publishing, marketplace/payout flows, or broker order execution. Automated API/provider tests use mocks; a separate user-authorized read-only paper-data check succeeded through FastAPI and the Next.js proxy. No live-account credentials or order operations were used, and no balances or holdings were displayed. The Next.js proxy is intentionally restricted to local development and disabled in production.

## Verify

```bash
ruff format --check src plugins tests
ruff check src plugins tests
mypy src plugins/rsi-macd-candidate/plugin.py
pytest
```

The backend has a separate GitHub Actions workflow; it does not replace or alter the existing Next.js checks.
