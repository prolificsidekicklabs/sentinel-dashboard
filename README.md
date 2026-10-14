# Sentinel Dashboard

**Game-inspired trading intelligence interface**

Sentinel Dashboard is a React-based interface for exploring market-state information, analytical agent opinions, agent discourse, risk visualization, and decision-oriented trading workflows.

> **Current implementation status:** The dashboard supports a local, authenticated, read-only Alpaca paper-data path when server-side credentials are configured. Otherwise it displays a fixed synthetic demo. Agent opinions, discourse, risk visuals and the illustrative verdict remain simulated in either mode. This is not an execution-ready trading system.

## 1. Project Goals

Sentinel aims to provide a visual workspace for examining:

- Market prices, indicators, and market-regime labels.
- Specialized analytical perspectives, such as technical, macroeconomic, microstructure, sentiment, and fundamental analysis.
- Agent opinions, stated confidence, rationales, and referenced data fields.
- Challenges, agreements, and decision events.
- Risk status and focused analysis views.
- Future integration with governed trading-intelligence services.

The longer-term direction is to evolve from a demonstration interface into a reliable, evidence-grounded trading-intelligence application with explicit risk controls and auditable decisions.

## 2. Current Capabilities

The reviewed source includes:

| Component | Current purpose |
|---|---|
| `pages/index.jsx` | Dashboard composition, local state, and simulated data initialization |
| `pages/strategy-validation.jsx` | Separate research-only route for user-supplied historical data |
| `components/DemoModeBanner.jsx` | Persistent warning that generated market and decision content is simulated |
| `components/PriceChart.jsx` | D3-based chart of supplied OHLCV bars; no generated price series |
| `components/PaperAccountPanel.jsx` | Read-only paper-account and open-position summary |
| `components/ResearchCandidatePanel.jsx` | Manually triggered, local-only market-data candidate and review display; no order controls |
| `components/AgentRoster.jsx` | Analytical-agent opinion cards |
| `components/DiscourseTimeline.jsx` | Timeline of opinions, challenges, agreements, and decisions |
| `components/FocusMode.jsx` | Detail panel for the first predefined analytical perspective |
| `components/CommandWheel.jsx` | Animated command-wheel interface |
| `components/EventRail.jsx` | Horizontal event stream |
| `components/RiskGlow.jsx` | Visual risk-level indicator |
| `components/StrategyValidationPanel.jsx` | Client-side CSV import, experiment form, metrics, and record export |
| `lib/strategy-validation.js` | Deterministic daily-bar SMA crossover backtest and data validation |
| `lib/research-candidate.js` | Strict browser response validation and same-origin candidate GET helper |

The interface uses Next.js, React, Tailwind CSS, D3, and Framer Motion.

The dashboard uses fixed synthetic fixtures by default. In local development, its paper view uses the loopback-only same-origin Next.js proxy to retrieve normalized Alpaca historical bars and paper-account/position data. A separate RSI/MACD candidate panel starts idle and fetches daily market data only after the user submits a ticker. The proxy allowlists only these two GET operations, holds the bearer key server-side, disables caching, and is disabled in production; the browser never receives provider credentials or the internal API key. The candidate read returns no account or position data. No route submits, cancels, or liquidates orders.

The repository also includes a **research-only Strategy Validation Engine prototype** at `/strategy-validation`. It runs a fixed long-only, equity-style SMA crossover against user-supplied daily OHLCV CSV, models next-open fills and configurable transaction costs, compares a chronological holdout against buy-and-hold, and exports a reproducible JSON experiment record. It is not connected to a market-data provider or any trading/execution service. See the [prototype methodology and limitations](docs/STRATEGY_VALIDATION_ENGINE.md).

The Python service also provides API-key-protected local plugin discovery and bounded execution under a **versioned v1.0 contract**. Plugins receive defensive immutable JSON and, when needed, typed read-only OHLCV snapshots. The deterministic RSI/MACD/EMA output is validated by the host, evaluated by an independent review-only gate, and recorded in the local audit chain; its response has a host-issued record ID. Strategy plugins cannot use the generic run endpoint, and no plugin output has order authority. The candidate route reads market bars only and returns no account or position data. The label is not a recommendation or evidence of a trading edge. Untrusted plugins still require a configured and tested OCI/gVisor boundary, which remains fail-closed. See [backend setup and boundaries](backend/README.md), the [plugin contract](backend/docs/PLUGIN_CONTRACT.md), the [candidate strategy contract and Alpaca SDK review](backend/docs/CANDIDATE_STRATEGY.md), and the [implemented API subset](docs/API_CONTRACT.md).

## 3. What Is Not Yet Verified

The current implementation does not establish:

- A live Alpaca account, live trading, a real-time freshness guarantee, or production data reliability. A temporary read-only paper-account check returned valid market bars and account/position data through the local API and proxy.
- A production broker connection or any order-execution engine.
- A managed database/KMS, externally immutable audit log, or complete general decision/execution record lifecycle; candidate results and selected events are stored only in local SQLite.
- A production agent-orchestration backend.
- User identity/session authentication, tenant isolation or production authorization; the local API bearer token is a development server-to-server guard.
- A verified account-risk model; the paper panel only renders provider-supplied account and position fields.
- A tested integration with AEGIS Core.
- A production-grade audit trail or authorization system; the local hash-chained audit ledger is tamper-evident, not externally immutable.

The presence of simulated opinions and a `BLOCK` verdict does not establish that a real governance or trading-risk engine evaluated the market.

## 4. Technology Stack

The committed manifest and lockfile establish this baseline:

- Next.js `16.4.0`
- React `18.x` (the current build emits a deprecation warning; Next.js 16 recommends upgrading to React 19 before Next.js 17)
- Tailwind CSS `4.3.x`
- D3 `7.x`
- Framer Motion `11.x`
- TypeScript `5.x`, configured to check the JavaScript/JSX source
- ESLint `10.x` with `eslint-config-next` `16.4.0`
- Node's built-in test runner with `tsx`
- Node.js `^20.19.0 || ^22.13.0 || >=24.0.0` (declared in `package.json`)

Storybook scripts and dependencies were removed because the repository had no Storybook configuration or stories. The unused Husky/lint-staged setup was also removed.

**Supported browser floor:** Chrome 111+, Edge 111+, Firefox 128+, and Safari 16.4+. These targets are declared in `package.json`'s `browserslist` field, which Next.js uses for its build output. Firefox versions below 128 are unsupported because Tailwind CSS 4 relies on modern CSS features. See the [Tailwind upgrade guide](https://tailwindcss.com/docs/upgrade-guide) and [Next.js supported browsers](https://nextjs.org/docs/architecture/supported-browsers).

## 5. Prerequisites

Install Node.js 20.19.x, 22.13.x or later, or 24.x or later, plus npm. The `engines` field records the supported ranges. Then verify the versions:

```bash
node --version
npm --version
```

## 6. Local Setup

Clone the repository and install the exact dependency tree from the committed lockfile:

```bash
git clone https://github.com/prolificsidekicklabs/sentinel-dashboard.git
cd sentinel-dashboard
npm ci
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:3000`.

Run the supported checks:

```bash
npm run lint
npm run type-check
npm test
npm run build
```

**Verification status:** On Node.js `24.19.0` and npm `11.17.0` (2026-10-12), lint, JS/JSX type-checking, all 31 frontend tests, and the production build passed. Backend formatting, lint, strict typing of core and the strategy plugin, and all 95 backend tests pass from the pinned Python lockfile; the offline plugin harness confirmed matching replay hashes and a `review_required` candidate disposition on its fixed fixture. A separate user-authorized read-only paper-account check succeeded through FastAPI and the same-origin Next.js proxy; no live account or order operation was used. GitHub Actions runs on pull requests to `main`, the documentation-baseline branch, and the PR #2 and PR #3 feature branches, and pushes to `main`; see `.github/workflows/ci.yml` and `.github/workflows/backend-ci.yml`. The build still warns that React 18 is deprecated in Next.js 16 and will be removed in Next.js 17. See the [Development Guide](docs/DEVELOPMENT.md) for the full security-audit status.

## 7. Architecture and Development Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [API Contract (implemented subset and proposals)](docs/API_CONTRACT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Product Roadmap](docs/ROADMAP.md)
- [Quantitative Research Ecosystem and Repository Review](docs/QUANT_RESEARCH_ECOSYSTEM.md)
- [Strategy Validation Engine Prototype](docs/STRATEGY_VALIDATION_ENGINE.md)
- [Contributing Guide](docs/CONTRIBUTING.md)

The API, deployment architecture, threat controls, and roadmap describe proposed implementation direction unless explicitly identified as current code behavior.

## 8. Safety and Financial Disclaimer

This software is not represented as a validated investment adviser, broker, execution platform, or source of reliable real-time financial data.

Simulated prices, agent outputs, confidence values, and risk labels must not be used to make actual trading decisions. Before any live-market use, implement and independently test data provenance, risk limits, authorization, monitoring, failure handling, and operational controls.

The strategy-validation prototype's historical metrics are research-only and do not demonstrate an edge, authorize paper trading, or support live-trading decisions.

## 9. Documentation and Security Status

The code includes a browser-only strategy-validation prototype, a deterministic RSI/MACD/EMA candidate plugin behind an independent review-only gate, a versioned immutable plugin contract with an offline determinism harness, an authenticated local API, and paper-only read adapters with an explicit no-execution contract for plugins. Automated provider tests use mocked responses; in addition, a user-authorized, read-only paper-account check successfully retrieved paper-mode market bars, account, and positions through both the FastAPI route and local Next.js proxy. No live account or order operation was used. The candidate rule is not backtested or proven to have predictive value, and the review gate is not account-aware risk authorization. Candidate results are recorded in a local tamper-evident audit chain, not externally immutable storage. No plugin has order authority; the separate paper-order endpoint is disabled by default. The paper-data proxy is disabled in production, and no user-login/session system, durable secret store, tenant isolation, or secure untrusted-plugin sandbox has been established. Review the [development guide](docs/DEVELOPMENT.md), [threat model](docs/THREAT_MODEL.md), [deployment guide](docs/DEPLOYMENT.md), and [backend limits](backend/README.md) before use.

The production dependency audit (`npm audit --omit=dev`) reports no known vulnerabilities. The full development audit reports **5 high-severity findings** through the transitive `braces@3.0.3` dependency used by the Next.js ESLint plugin; no patched npm release was available when checked and the upstream advisory is disputed ([upstream issue](https://github.com/micromatch/braces/issues/73)). Next.js has also announced another security update for October 14, 2026, but had not published affected-version details at the time of the previous review ([announcement](https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026)). Re-run audits and update dependencies before release.

Last reviewed: 2026-10-13.
