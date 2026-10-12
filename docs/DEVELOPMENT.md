# Sentinel Dashboard Development Guide

## 1. Purpose

This guide explains how to install, run, inspect, and extend Sentinel Dashboard. The documented baseline commands have been run successfully; current project limitations and security findings are recorded below.

## 2. Prerequisites

Install:

- Node.js `^20.19.0 || ^22.13.0 || >=24.0.0` (the repository engine range; Next.js 16 itself has a lower minimum).
- Python 3.11 or newer for the FastAPI service.
- npm.
- Git.
- A code editor with JavaScript and JSX support.

Check versions:

```bash
node --version
npm --version
git --version
```

The checks in this guide were run with Node.js `24.19.0` and npm `11.17.0`.

Supported browsers are Chrome 111+, Edge 111+, Firefox 128+, and Safari 16.4+, as declared in the `browserslist` field of `package.json` and used by Next.js for build output. Firefox below 128 is unsupported; Tailwind CSS 4 uses modern CSS features unavailable in older Firefox releases. See the [Tailwind upgrade guide](https://tailwindcss.com/docs/upgrade-guide) and [Next.js supported browsers](https://nextjs.org/docs/architecture/supported-browsers).

## 3. Clone and Install

```bash
git clone https://github.com/prolificsidekicklabs/sentinel-dashboard.git
cd sentinel-dashboard
npm ci
```

`package-lock.json` is committed. Use `npm ci` for reproducible installs and CI; update the lockfile intentionally alongside dependency changes. The validation environment's npm emitted allow-scripts and ESLint peer-dependency warnings; installation, tests, lint, and build still completed successfully. Next.js documents ESLint 10 support, while some bundled plugins do not yet declare ESLint 10 in their peer ranges.

## 4. Run Locally

```bash
npm run dev
```

Open `http://localhost:3000`.

### Optional local paper-data bridge

The dashboard starts in fixed synthetic demo mode and keeps doing so if the backend or Alpaca is not configured. To enable the optional **read-only paper** view:

1. Create a long random API token with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
2. Copy `backend/.env.example` to the ignored `backend/.env`. Set `SENTINEL_API_KEY` to that token and add an Alpaca **paper-account** key ID and secret. Do not use live account credentials.
3. Copy `.env.local.example` to `.env.local` and set `SENTINEL_API_KEY` to the same token. Do not prefix it with `NEXT_PUBLIC_`; the key must remain server-side.
4. In one terminal, start the backend from `backend/`:

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install -r requirements.lock
   python -m pip install -e . --no-deps
   set -a
   . ./.env
   set +a
   uvicorn sentinel_core.api:app --app-dir src --host 127.0.0.1 --port 8000
   ```

5. In another terminal at the repository root, run `npm run dev`, then use **Refresh paper data** for the paper account view. The separate candidate panel below the chart stays idle until you enter a ticker and select **Run research-only check**.

The browser can reach only a same-origin Next.js proxy; the proxy targets loopback HTTP, holds the shared bearer token server-side, and sends only two fixed GET reads: the paper dashboard or the market-only candidate endpoint. Candidate requests are manual; the browser validates the typed response and sends no bearer credential itself. FastAPI rejects missing or incorrect keys and forces paper mode for the paper account route. The chart/account panel and candidate result appear only after their respective successful validated responses. Opinions, discourse and risk visuals remain synthetic. Both provider proxy resources are disabled in production; this is not a user-login or production authorization system. Prior user-authorized read-only paper and candidate checks succeeded locally, with candidate data containing no account or position fields. No balances or holdings were displayed; temporary local credentials, response files, server, and bearer token were removed. Automated provider tests remain mocked.

### Research-only candidate panel and API

The dashboard's **RSI/MACD candidate review** panel starts without making a provider request. In local development, enter a ticker and choose **Run research-only check**. The request goes through the allowlisted same-origin proxy to the authenticated market-bars route. The panel validates plugin/version, ticker, daily timeframe, source and data quality, bar count, timestamps, review disposition, required unassessed-risk disclosures, and fixed `execution_enabled: false` fields before rendering. Non-valid market data or insufficient history cannot be presented as eligible for human review. Production builds disable the panel and the server proxy independently refuses provider access.

With the backend running and `SENTINEL_API_KEY` loaded in the shell, the route can also be requested directly:

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer $SENTINEL_API_KEY" \
  "http://127.0.0.1:8000/api/v1/research/strategies/rsi-macd-candidate?symbol=SPY"
```

The endpoint reads up to 365 calendar days of daily market bars only. It returns indicator values, one typed candidate label, and an independent review-gate result; it does not read the paper account or positions. The result may be blocked, contain no candidate, or require human review, and always has `execution_enabled: false`. The generic plugin-run route refuses strategy plugins with HTTP 409 so callers cannot bypass the gate. The review gate does not assess account exposure, position sizing, or stop-loss/drawdown limits; it is not trade authorization. See [Candidate Strategy](../backend/docs/CANDIDATE_STRATEGY.md) for formula details and the Alpaca SDK review.

Build and run the production application:

```bash
npm run build
npm run start
```

## 5. Available Scripts

| Script | Purpose |
|---|---|
| `dev` | Start the Next.js development server |
| `build` | Build the production application |
| `start` | Start the production server |
| `lint` | Run the ESLint CLI with the Next.js Core Web Vitals config |
| `type-check` | Run TypeScript over the JavaScript/JSX project (`allowJs` and `checkJs`) |
| `test` | Run component, strategy-engine, response-schema, and server-proxy tests with Node's built-in test runner and `tsx` |

Next.js 16 removed `next lint`; linting now runs through ESLint directly. Unconfigured Storybook and unused Husky/lint-staged scripts and dependencies were removed because no stories, Storybook configuration, hooks, or lint-staged rules existed in the repository.

## 6. Continuous Integration

`.github/workflows/ci.yml` runs `npm ci`, lint, type-check, tests, a production dependency audit, and the production build. `.github/workflows/backend-ci.yml` runs Python formatting, lint, type checks for core and the candidate plugin, and tests. Both workflows include the PR #2 and PR #3 feature branches as pull-request targets so stacked PRs are checked. Local results do not guarantee that a hosted workflow is enabled or passes; check the pull request's status checks.

## 7. Verification Run (2026-10-12)

Commands were run against the committed package manifest and lockfile on Node.js `24.19.0` and npm `11.17.0`.

| Command | Result |
|---|---|
| `npm ci` | Passed from the reconciled lockfile; npm reported ESLint peer-range/deprecation warnings, but no install failure. |
| `npm run lint` | Passed with ESLint 10.12.0 and `eslint-config-next` 16.4.0. |
| `npm run type-check` | Passed; TypeScript checks the JavaScript/JSX application and local API proxy/test helpers. |
| `npm test` | Passed; 31 tests across dashboard components, candidate response validation, deterministic fixtures, paper response validation, proxy behavior, and strategy validation. |
| `npm run build` | Passed; Next.js 16.4.0 generated the production build. The build warns that React 18 is deprecated in Next.js 16 and will be removed in Next.js 17. |
| `npm audit --omit=dev --audit-level=high` | Passed with zero reported production dependency vulnerabilities. |
| Backend `ruff format --check`, `ruff check`, `mypy src plugins/rsi-macd-candidate/plugin.py`, `pytest -q` | Passed; 58 backend tests, including candidate/plugin and provider-integrity coverage. |
| One-time Alpaca paper-data integration check | Authenticated FastAPI GET and same-origin Next.js proxy GET returned HTTP 200 with paper mode, execution disabled, and market/account/position data present; no balances or holdings were displayed, and temporary local credential/response files were removed. |
| One-time research-candidate integration check | Authenticated FastAPI GET and same-origin Next.js proxy GET returned HTTP 200 with 250 valid SPY daily bars and a `review_required` result; the response contained no account or position data and execution remained disabled. |
| Last full `npm audit` | Reported 5 high, 0 moderate, 0 low, and 0 critical findings, stemming from `braces@3.0.3` in the `eslint-config-next` development dependency path. Re-run the full development audit before release; the production-only audit is clean. |

The reported `braces` advisory is [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). No patched npm release was available at the time of review; the upstream discussion reports that the advisory is disputed and no fix release is planned ([maintainer issue](https://github.com/micromatch/braces/issues/73)). Do not describe the full dependency tree as vulnerability-free. Re-run `npm audit` when upstream status changes.

The production dependency audit is clean, but Next.js has announced another security release for October 14, 2026, covering two Critical and one High upstream issues. Affected versions and patches were not yet published at the time of this check; re-run the audit and upgrade to the appropriate patched release when available: [Next.js announcement](https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026).

Tailwind CSS 4.3 is configured through `@tailwindcss/postcss` and the CSS `@import`/`@theme` directives in `styles/globals.css`; the obsolete JavaScript Tailwind config was removed. The browser target intentionally requires Firefox 128+ (plus Chrome 111+, Edge 111+, and Safari 16.4+). See the [Tailwind upgrade guide](https://tailwindcss.com/docs/upgrade-guide), [PostCSS installation guide](https://tailwindcss.com/docs/installation/using-postcss), and [dark-mode guide](https://tailwindcss.com/docs/dark-mode).

## 8. Source Layout

```text
.github/
  workflows/
    ci.yml
pages/
  index.jsx
  strategy-validation.jsx
components/
  AgentRoster.jsx
  CommandWheel.jsx
  DemoModeBanner.jsx
  DiscourseTimeline.jsx
  EventRail.jsx
  FocusMode.jsx
  PriceChart.jsx
  RiskGlow.jsx
  ResearchCandidatePanel.jsx
  StrategyValidationPanel.jsx
  dashboard-components.test.jsx
  ResearchCandidatePanel.test.jsx
lib/
  research-candidate.js
  research-candidate.test.js
  sentinel-api-proxy.js
  sentinel-api-proxy.test.js
  strategy-validation.js
  strategy-validation.test.js
styles/
  globals.css
next.config.js
postcss.config.js
eslint.config.mjs
tsconfig.json
package.json
package-lock.json
docs/
  ARCHITECTURE.md
  DEVELOPMENT.md
  API_CONTRACT.md
  DEPLOYMENT.md
  THREAT_MODEL.md
  ROADMAP.md
  STRATEGY_VALIDATION_ENGINE.md
  CONTRIBUTING.md
```

## 9. Data and Component Contracts

`lib/paper-dashboard.js` validates the server response with a strict Zod schema before it reaches the page. `PriceChart` draws only the provided bars; it no longer synthesizes a series. The account panel receives normalized decimal strings and formats them for display. Agent opinions and discourse remain separate fixed demo objects. The `type-check` script checks the JS/JSX sources using TypeScript's `allowJs` and `checkJs` options; it does not turn them into a fully typed TypeScript application.

Before extending the provider integration:

1. Keep canonical schemas versioned and strict.
2. Validate inputs at the application boundary.
3. Represent loading, empty, stale, and error states separately.
4. Ensure timestamps and units are explicit.
5. Reject invalid or incomplete market data.
6. Keep provider-specific response formats out of presentation components.
7. Add tests for valid and invalid inputs.

Do not treat a numeric value as a valid market price merely because it can be rendered.

## 10. Development Workflow

1. Create a branch from the current default branch.
2. Make one logically scoped change.
3. Add or update tests.
4. Run the checks:

   ```bash
   npm run lint
   npm run type-check
   npm test
   npm run build
   ```

5. Review the diff for security and data-integrity concerns.
6. Update documentation when behavior or contracts change.
7. Open a pull request.
8. Merge only after required reviews and checks pass.

Run only commands supported by the actual repository configuration; do not assume a command passes because it is listed in the manifest.

## 11. Testing Layers

### Current component tests

`npm test` uses Node's built-in `node:test` runner with `tsx` to render selected components to static markup and exercise pure boundary helpers. It includes deterministic-fixture, response-schema, and proxy tests; they are a regression baseline, not full DOM, browser, or end-to-end coverage.

### Strategy engine unit tests

Ten pure-engine tests cover strict CSV quoting/column/date rules, OHLC and direct-input validation, next-open entry/exit fills, terminal-close cost estimates, final-bar no-look-ahead behavior, out-of-sample isolation, deterministic identity, baseline/risk metrics (including flat/no-trade cases), and invalid configurations. These fixtures test software behavior only; they are not a market dataset and do not demonstrate financial performance. See the [Strategy Validation Engine Prototype guide](STRATEGY_VALIDATION_ENGINE.md) for the assumptions and omissions.

### Recommended next layers

- **Unit tests:** pure transformations, schema validation, indicator calculations, candidate review-gate checks, and future account-aware risk-policy functions.
- **Component tests:** empty states, invalid input handling, accessibility, and user interactions.
- **Integration tests:** the flow from a validated market snapshot through assessment display and decision rendering.
- **End-to-end tests:** loading, errors, stale data, keyboard navigation, and responsive layout.
- **Safety tests:** verify that missing data, stale data, rejected assessments, denied authorization, and risk-limit breaches cannot be represented as approval.

## 12. Known Limitations and Follow-Ups

- `FocusMode` still presents `data.agents[0]`; it does not let a user select another agent.
- Automated provider behavior is covered by mocked tests; separate user-authorized read-only paper/proxy and candidate market-data checks succeeded. The candidate panel is local-development-only and user-triggered; its route has no account/position reads or order integration. Live access and provider freshness guarantees remain unverified.
- The shared bearer token is a local development guard, not user identity, per-user authorization, or tenant isolation. The production proxy is disabled.
- The paper route does not implement a server-side freshness policy, durable audit trail, or account consent workflow.
- Agent opinions, discourse, risk labels and verdict remain fixed synthetic content and are not based on provider data.
- The strategy-validation prototype consumes user-supplied daily bars, but does not authenticate or independently validate their source, corporate-action adjustments, or survivorship properties; its results do not establish a trading edge.
- React 18 works with the current build but triggers a Next.js 16 deprecation warning; plan migration to React 19 before upgrading to Next.js 17.
- The full npm audit retains the development-only `braces@3.0.3` advisory described above. Production dependencies have no reported audit findings as of this verification.
- Next.js announced a further security release for October 14, 2026; rerun audits and update after its advisories and patched versions are available.

## 13. Definition of Done

A change is complete when:

- Its intended behavior is documented.
- Inputs and outputs are validated.
- Tests cover normal and failure cases.
- No secrets or sensitive information are committed.
- Accessibility and responsive behavior are considered.
- Relevant checks have been run and results recorded.
- The pull request explains any unverified assumptions or follow-up work.
