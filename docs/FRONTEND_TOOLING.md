# Frontend tooling and local data bridge

**Reviewed:** 2026-10-11. This guide reflects the reconciled PR #1 dashboard baseline and PR #2 local Python service.

## Toolchain

- Next.js `16.4.0`, React `18.x`, Tailwind CSS `4.3.x`, D3 `7.x`, and Framer Motion `11.x`.
- ESLint `10.x` with the flat `eslint-config-next` Core Web Vitals configuration.
- TypeScript checks the JavaScript/JSX project (`allowJs` and `checkJs`); the application source remains JavaScript.
- Node's built-in `node:test` runner with `tsx`; the lockfile is regenerated from the merged `package.json`.
- Tailwind 4 uses `@tailwindcss/postcss`; the obsolete Tailwind 3 configuration and unconfigured Jest/Storybook setup were removed.

Next.js 16 removed `next lint`, so `npm run lint` invokes ESLint directly. The framework build, lint and type checks succeed. npm reports non-fatal ESLint peer-range warnings because some nested Next.js plugins still declare ESLint support only through major 9. The production build also warns that React 18 is deprecated in Next.js 16 and will be removed in Next.js 17; plan a React 19 migration before upgrading the framework major.

## Deterministic demo and paper-data boundary

`lib/demo-data.js` contains fixed synthetic market bars, opinions and discourse. The D3 chart renders supplied OHLCV closes only; it does not fabricate price history. The dashboard defaults to this demo and labels it. When configured in local development, the page can instead render normalized historical bars and a paper-account/position snapshot from the FastAPI route. The agent opinions, discourse, risk visuals and illustrative decision remain synthetic and are not calculated from that feed.

The Next.js proxy accepts only a same-origin GET for the fixed dashboard resource, holds the shared bearer key server-side, targets loopback HTTP, sends `Cache-Control: no-store`, and returns 404 in production. The backend requires a 32+ character `SENTINEL_API_KEY`, forces the Alpaca paper trading host and exposes no order/cancel/liquidate route. A user-authorized read-only paper-account test succeeded through both FastAPI and the local Next.js proxy; it returned paper mode, execution disabled, market bars, and account/position data. No balances or holdings were displayed, and temporary local credential/response files were removed afterward. This test does not establish freshness, live-account access, or production readiness; the local bridge is not user authentication, tenant isolation, or production authorization.

## Verification

Verified on 2026-10-11 after clean lockfile installation:

| Area | Commands | Result |
|---|---|---|
| Frontend | `npm run lint`, `npm run type-check`, `npm test`, `npm run build` | Passed; 23 tests passed; build emitted the React 18 deprecation warning noted above. |
| Production dependencies | `npm audit --omit=dev --audit-level=high` | Passed; 0 vulnerabilities reported. |
| Backend | `ruff format --check src plugins tests`, `ruff check src plugins tests`, `mypy src`, `pytest -q` | Passed; 39 tests passed. |
| Alpaca paper integration | Authenticated FastAPI GET and same-origin Next.js proxy GET | Both returned HTTP 200; response validated paper mode, execution disabled, and market/account/position data. No balances or holdings were displayed; temporary local credential/response files were removed. |

The last full development dependency audit recorded 5 high-severity findings in the transitive `braces@3.0.3` path used by the Next.js ESLint plugin. The advisory was disputed upstream and no patched npm release was available in that review. The production-only audit is clean; do not describe the complete development dependency tree as vulnerability-free. Re-run the full audit before release.
