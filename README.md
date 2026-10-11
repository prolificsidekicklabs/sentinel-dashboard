# sentinel-dashboard

Sentinel Dashboard — game-inspired trading intelligence UI.

## Current implementation

The repository now contains a separate [Python service foundation](backend/README.md) alongside the Next.js dashboard. The backend includes validated plugin manifests, a seeded deterministic local-plugin example, a bounded subprocess runner, and a FastAPI local development API. It also defines provider-neutral Decimal-based market/risk/broker contracts, a generic OpenAI-compatible model gateway adapter, and read-only Alpaca historical-equity-data plus paper account/position adapters.

The model adapter is compatible with the documented OpenAI chat-completions interface used by [OmniRoute](https://github.com/diegosouzapw/OmniRoute) and [9Router](https://github.com/decolua/9router), subject to each gateway's configured model names and credentials. Alpaca keys are server-side configuration only; its broker read adapter defaults to paper. No provider account was connected while building this foundation.

The dashboard currently displays a fixed, clearly labeled synthetic demo scenario; it is not live market data or a trading signal. See [frontend tooling notes](docs/FRONTEND_TOOLING.md) for the pinned Next.js stack, security-baseline rationale, and verification commands.

## Important limits

This is an early implementation slice, **not a production-ready trading platform**. The dashboard is not wired to the backend; API routes are not authenticated; persistent encrypted credential management, tenant isolation, audit logging, streaming data, secure marketplace-plugin isolation, durable jobs, billing/marketplace publishing, and release operations remain unimplemented. There is no concrete order-submission, cancellation, liquidation, or live-trading code. The plugin runner is only for trusted, repository-reviewed code and is not a secure sandbox for untrusted plugins.

See [backend/README.md](backend/README.md) for setup and [backend/docs/ADAPTER_RESEARCH.md](backend/docs/ADAPTER_RESEARCH.md) for the verified provider behavior and current adapter boundaries.
