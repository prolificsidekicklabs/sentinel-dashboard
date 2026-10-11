# Sentinel Python Service Foundation

This folder adds a small Python service alongside the existing Next.js dashboard. It is an early **contract and local-runtime foundation**, not a production trading backend. The dashboard is not yet wired to this API.

## Run locally

From this directory, install the service and development dependencies, then start FastAPI:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
uvicorn sentinel_core.api:app --app-dir src --reload
```

The API listens at `http://127.0.0.1:8000` by default. `GET /healthz`, `GET /api/v1/plugins`, and `POST /api/v1/plugins/{plugin_id}/run` are local development routes. OpenAPI docs are available at `/docs` during development. These routes are not authenticated and must not be exposed publicly as-is.

## Model gateway adapter

`sentinel_core.adapters.model_router.OpenAICompatibleChatAdapter` implements the common OpenAI-compatible `/v1/chat/completions` interface. It is configured server-side and can be used with OmniRoute, 9Router, or another compatible gateway. The gateway's exact model identifier is configuration; do not assume all routers support the same aliases or routing modes. Each request enforces its configured timeout even when the application injects an HTTP client; streamed responses are capped at 2 MB, and normalized model text is capped at 128 KB.

Configuration names are in `.env.example`. Copy values into the **backend process environment or a deployment secret manager**; the service does not load `.env` files automatically. Never commit populated credentials, put them in browser code, return them through an API, or log request headers. For a local gateway, the default endpoint pattern is `http://127.0.0.1:20128/v1`; plain HTTP is restricted to loopback unless an explicit trusted-network override is set. Model output is untrusted and cannot approve risk or orders.

## Alpaca read-only adapters

`AlpacaMarketDataAdapter` fetches bounded, paginated historical U.S.-equity bars and normalizes values to `Decimal`, with timestamps, feed and provider provenance preserved. The default feed is `iex`; the account's Alpaca market-data subscription controls coverage, delay, history and rate limits.

`AlpacaReadOnlyBrokerAdapter` reads account summary and open positions from the **paper** Trading API by default. It has no order, cancel, or liquidation method. Live-account reads require an explicit server-side opt-in. The adapter uses Alpaca Trading API key headers from `SENTINEL_ALPACA_KEY_ID` and `SENTINEL_ALPACA_SECRET_KEY`. These credentials are not stored in the browser, database, or source tree.

## Contracts and deterministic boundaries

- `adapters.ports` defines provider-neutral market-data and broker-read interfaces, Decimal-based finance records, and an order proposal that is separate from authorization.
- `RiskEvaluator` is an independent policy port. A model response is never a risk evaluation.
- The future execution contract accepts only a `RiskApprovedOrder` carrying an explicit versioned risk evaluation and idempotency key. There is currently **no concrete broker execution adapter**.
- The moving-average example is illustrative only; it is not a trading signal or recommendation.

## Plugin contract and execution boundary

A local plugin directory contains `sentinel_manifest.yaml`, `SKILL.md`, `plugin.py`, and `tests/`. Manifests use safe YAML parsing, reject duplicate keys, and are checked against a versioned Pydantic schema. The current generic async contract is `async def run(context: PluginContext) -> PluginResult`; plugin-type identifiers are included for future specialization.

The run context contains a caller-supplied seed, a per-run `random.Random` seeded from it, and JSON input. It intentionally exposes no provider or broker clients. The sample plugin is deterministic and does not use randomness. Each run hashes canonicalized input, manifest identity, seed, and output so repeated executions can be compared.

Plugin code runs in a fresh Python subprocess with a scrubbed environment, temporary working directory, wall-clock timeout, and best-effort POSIX CPU, address-space, file-size, and file-descriptor limits. This provides process separation and fault/resource containment for **trusted, repository-reviewed local plugins** only. It is not a security sandbox for untrusted marketplace plugins; network access, filesystem isolation, privilege dropping, seccomp/container policy, and marketplace threat testing are not implemented.

## Known production gaps

The current service does not yet provide user authentication/authorization, tenant isolation, encrypted persistent secret storage, audited connection management, rate limiting, durable jobs, a database, live data streams, a secure untrusted-plugin sandbox, CI publishing, marketplace/payout flows, broker order execution, or frontend-to-backend integration. No live data or trading account was connected during this implementation.

## Verify

```bash
ruff format --check src plugins tests
ruff check src plugins tests
mypy src
pytest
```

The backend has a separate GitHub Actions workflow; it does not replace or alter the existing Next.js checks.
