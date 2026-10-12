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
| `components/AgentRoster.jsx` | Analytical-agent opinion cards |
| `components/DiscourseTimeline.jsx` | Timeline of opinions, challenges, agreements, and decisions |
| `components/FocusMode.jsx` | Detail panel for the first predefined analytical perspective |
| `components/CommandWheel.jsx` | Animated command-wheel interface |
| `components/EventRail.jsx` | Horizontal event stream |
| `components/RiskGlow.jsx` | Visual risk-level indicator |
| `components/StrategyValidationPanel.jsx` | Client-side CSV import, experiment form, metrics, and record export |
| `lib/strategy-validation.js` | Deterministic daily-bar SMA crossover backtest and data validation |

The interface uses Next.js, React, Tailwind CSS, D3, and Framer Motion.

The dashboard uses fixed synthetic fixtures by default. In local development it attempts a same-origin Next.js server proxy to the FastAPI service; after a successful request, the price chart and account panel show normalized Alpaca historical bars and paper-account/position data. The server proxy is loopback-only, requires a long server-held bearer key, disables caching and is disabled in production. The browser never receives Alpaca credentials or the internal API key. The backend forcibly uses the Alpaca paper trading host and has no order, cancel or liquidation route.

The repository also includes a **research-only Strategy Validation Engine prototype** at `/strategy-validation`. It runs a fixed long-only, equity-style SMA crossover against user-supplied daily OHLCV CSV, models next-open fills and configurable transaction costs, compares a chronological holdout against buy-and-hold, and exports a reproducible JSON experiment record. It is not connected to a market-data provider or any trading/execution service. See the [prototype methodology and limitations](docs/STRATEGY_VALIDATION_ENGINE.md).

The Python service also provides API-key-protected local plugin discovery and bounded execution. It now includes a deterministic RSI/MACD/EMA research candidate plugin behind a typed, independent review gate; strategy plugins cannot use the generic run endpoint, and the gate never authorizes execution. The candidate endpoint reads historical market bars only and returns no account or position data. Its label is not a recommendation or evidence of a trading edge. The runner is for trusted, repository-reviewed plugins, not untrusted marketplace code. See [backend setup and boundaries](backend/README.md), the [candidate strategy contract and Alpaca SDK review](backend/docs/CANDIDATE_STRATEGY.md), and the [implemented API subset](docs/API_CONTRACT.md).

## 3. What Is Not Yet Verified

The current implementation does not establish:

- A live Alpaca account, live trading, a real-time freshness guarantee, or production data reliability. A temporary read-only paper-account check returned valid market bars and account/position data through the local API and proxy.
- A production broker connection or any order-execution engine.
- Persistent storage for analyses, decisions, or trades.
- A production agent-orchestration backend.
- User identity/session authentication, tenant isolation or production authorization; the local API bearer token is a development server-to-server guard.
- A verified account-risk model; the paper panel only renders provider-supplied account and position fields.
- A tested integration with AEGIS Core.
- A production-grade audit trail or authorization system.

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

**Verification status:** On Node.js `24.19.0` and npm `11.17.0` (2026-10-11), clean `npm ci`, lint, JS/JSX type-checking, all 23 frontend tests, the production build, and the production dependency audit passed. Backend formatting, lint, strict typing of core and the new strategy plugin, and all 58 backend tests passed from the pinned Python lockfile. A separate user-authorized read-only paper-account check succeeded through both FastAPI and the same-origin Next.js proxy; it confirmed paper mode and disabled execution without displaying balances or holdings. Temporary local credentials/response files were removed. GitHub Actions runs on pull requests to `main`, the documentation-baseline branch, and the PR #2 feature branch, and pushes to `main`; see `.github/workflows/ci.yml`, `.github/workflows/backend-ci.yml`, and the PR status checks. The build still warns that React 18 is deprecated in Next.js 16 and will be removed in Next.js 17. See the [Development Guide](docs/DEVELOPMENT.md) for the full security-audit status.

## 7. Architecture and Development Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [API Contract (implemented subset and proposals)](docs/API_CONTRACT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Product Roadmap](docs/ROADMAP.md)
- [Strategy Validation Engine Prototype](docs/STRATEGY_VALIDATION_ENGINE.md)
- [Contributing Guide](docs/CONTRIBUTING.md)

The API, deployment architecture, threat controls, and roadmap describe proposed implementation direction unless explicitly identified as current code behavior.

## 8. Safety and Financial Disclaimer

This software is not represented as a validated investment adviser, broker, execution platform, or source of reliable real-time financial data.

Simulated prices, agent outputs, confidence values, and risk labels must not be used to make actual trading decisions. Before any live-market use, implement and independently test data provenance, risk limits, authorization, monitoring, failure handling, and operational controls.

The strategy-validation prototype's historical metrics are research-only and do not demonstrate an edge, authorize paper trading, or support live-trading decisions.

## 9. Documentation and Security Status

The code includes a browser-only strategy-validation prototype, a deterministic RSI/MACD/EMA candidate plugin behind an independent review-only gate, a Python plugin/runtime foundation, an authenticated local API, and paper-only read adapters with an explicit no-execution response contract. Automated provider tests use mocked responses; in addition, a user-authorized, read-only paper-account check successfully retrieved paper-mode market bars, account, and positions through both the FastAPI route and local Next.js proxy. The response affirmed paper mode and disabled execution. No balances or holdings were displayed, and temporary local credential/response files were deleted after verification; no live account or order operation was used. The candidate rule is not backtested or proven to have predictive value, the review gate is not account-aware risk authorization, and no order operation exists. The paper-data proxy is disabled in production, and no user-login/session system, durable secret store, tenant isolation, audit service, or secure untrusted-plugin sandbox is implemented. Review the [development guide](docs/DEVELOPMENT.md), [threat model](docs/THREAT_MODEL.md), [deployment guide](docs/DEPLOYMENT.md), and [backend limits](backend/README.md) before use.

The production dependency audit (`npm audit --omit=dev`) reports no known vulnerabilities. The full development audit reports **5 high-severity findings** through the transitive `braces@3.0.3` dependency used by the Next.js ESLint plugin; no patched npm release was available when checked and the upstream advisory is disputed ([upstream issue](https://github.com/micromatch/braces/issues/73)). Next.js has also announced another security update for October 14, 2026, but had not published affected-version details at the time of the previous review ([announcement](https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026)). Re-run audits and update dependencies before release.

Last reviewed: 2026-10-11.
