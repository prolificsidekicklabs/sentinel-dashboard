# Frontend tooling and local data bridge

**Reviewed:** 2026-10-12. This guide reflects the dashboard candidate panel and its local-only proxy boundary.

## Toolchain

- Next.js `16.4.0`, React `18.x`, Tailwind CSS `4.3.x`, D3 `7.x`, and Framer Motion `11.x`.
- ESLint `10.x` with the flat `eslint-config-next` Core Web Vitals configuration.
- TypeScript checks the JavaScript/JSX project (`allowJs` and `checkJs`); the application source remains JavaScript.
- Node's built-in `node:test` runner with `tsx`; the lockfile is regenerated from the merged `package.json`.
- Tailwind 4 uses `@tailwindcss/postcss`; the obsolete Tailwind 3 configuration and unconfigured Jest/Storybook setup were removed.

Next.js 16 removed `next lint`, so `npm run lint` invokes ESLint directly. The framework build, lint and type checks succeed. npm reports non-fatal ESLint peer-range warnings because some nested Next.js plugins still declare ESLint support only through major 9. The production build also warns that React 18 is deprecated in Next.js 16 and will be removed in Next.js 17; plan a React 19 migration before upgrading the framework major.

## Deterministic demo and paper-data boundary

`lib/demo-data.js` contains fixed synthetic market bars, opinions and discourse. The D3 chart renders supplied OHLCV closes only; it does not fabricate price history. The dashboard defaults to this demo and labels it. When configured in local development, it can render normalized historical bars and a paper-account/position snapshot from the FastAPI route. A separate RSI/MACD candidate card starts idle and performs a market-only request only after the user submits a ticker. Agent opinions, discourse, risk visuals and the illustrative decision remain synthetic and are not calculated from either provider result.

The Next.js proxy accepts only same-origin GETs for the fixed paper-dashboard and research-candidate resources, holds the shared bearer key server-side, targets loopback HTTP, sends `Cache-Control: no-store`, and returns 404 in production. The browser adds no bearer header and validates candidate response provenance and non-execution flags with a strict schema. The backend requires a 32+ character `SENTINEL_API_KEY`, forces the Alpaca paper trading host for account reads, and exposes no order/cancel/liquidate route. User-authorized read-only checks succeeded for the paper dashboard and candidate market-data route; the candidate returned valid bars and `review_required` without account/position fields. No balances or holdings were displayed, and temporary local credential/response files, server, and token were removed. These checks do not establish freshness guarantees, live-account access, or production readiness; the local bridge is not user authentication, tenant isolation, or production authorization.

## Verification

Verified on 2026-10-12 after clean lockfile installation:

| Area | Commands | Result |
|---|---|---|
| Frontend | `npm run lint`, `npm run type-check`, `npm test`, `npm run build` | Passed; 31 tests passed; build emitted the React 18 deprecation warning noted above. |
| Production dependencies | `npm audit --omit=dev --audit-level=high` | Passed; 0 vulnerabilities reported. |
| Backend | `ruff format --check src plugins tests`, `ruff check src plugins tests`, `mypy src plugins/rsi-macd-candidate/plugin.py`, `pytest -q` | Passed; 58 tests passed. |
| Alpaca paper integration | Authenticated FastAPI GET and same-origin Next.js proxy GET | Both returned HTTP 200; response validated paper mode, execution disabled, and market/account/position data. No balances or holdings were displayed; temporary local credential/response files were removed. |
| Candidate-strategy integration | One authenticated GET using the read-only market-data route | Returned HTTP 200 with 250 valid daily bars; the result was `bullish_candidate`/`review_required`, `execution_enabled: false`, and contained no account or position fields. The temporary service and local bearer token were removed. |

The last full development dependency audit recorded 5 high-severity findings in the transitive `braces@3.0.3` path used by the Next.js ESLint plugin. The advisory was disputed upstream and no patched npm release was available in that review. The production-only audit is clean; do not describe the complete development dependency tree as vulnerability-free. Re-run the full audit before release.
