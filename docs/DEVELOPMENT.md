# Sentinel Dashboard Development Guide

## 1. Purpose

This guide explains how to install, run, inspect, and extend Sentinel Dashboard. The documented baseline commands have been run successfully; current project limitations and security findings are recorded below.

## 2. Prerequisites

Install:

- Node.js `^20.19.0 || ^22.13.0 || >=24.0.0` (the repository engine range; Next.js 16 itself has a lower minimum).
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
| `test` | Run component tests with Node's built-in test runner and `tsx` |

Next.js 16 removed `next lint`; linting now runs through ESLint directly. Unconfigured Storybook and unused Husky/lint-staged scripts and dependencies were removed because no stories, Storybook configuration, hooks, or lint-staged rules existed in the repository.

## 6. Verification Run (2026-10-11)

Commands were run against the committed package manifest and lockfile on Node.js `24.19.0` and npm `11.17.0`.

| Command | Result |
|---|---|
| `npm ci` | Passed; installed the committed lockfile. npm reported allow-scripts and ESLint peer-dependency warnings, but no install failure. |
| `npm run lint` | Passed with ESLint 10.12.0 and `eslint-config-next` 16.4.0. |
| `npm run type-check` | Passed; TypeScript checks the repository's JavaScript and JSX files, including the D3 datum and Motion animation props. |
| `npm test` | Passed; three server-rendered component tests cover agent cards, Focus Mode, and discourse events. |
| `npm run build` | Passed; Next.js 16.4.0 generated the production build. The build warns that React 18 is deprecated in Next.js 16 and will be removed in Next.js 17. |
| `npm audit --omit=dev` | Passed with zero reported production dependency vulnerabilities. |
| `npm audit` | Reports 5 high, 0 moderate, 0 low, and 0 critical findings, stemming from `braces@3.0.3` in the `eslint-config-next` development dependency path. The Tailwind 3 dependency path is removed. |

The reported `braces` advisory is [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). No patched npm release was available at the time of review; the upstream discussion reports that the advisory is disputed and no fix release is planned ([maintainer issue](https://github.com/micromatch/braces/issues/73)). Do not describe the full dependency tree as vulnerability-free. Re-run `npm audit` when upstream status changes.

The production dependency audit is clean, but Next.js has announced another security release for October 14, 2026, covering two Critical and one High upstream issues. Affected versions and patches were not yet published at the time of this check; re-run the audit and upgrade to the appropriate patched release when available: [Next.js announcement](https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026).

Tailwind CSS 4.3 is configured through `@tailwindcss/postcss` and the CSS `@import`/`@theme` directives in `styles/globals.css`; the obsolete JavaScript Tailwind config was removed. The browser target intentionally requires Firefox 128+ (plus Chrome 111+, Edge 111+, and Safari 16.4+). See the [Tailwind upgrade guide](https://tailwindcss.com/docs/upgrade-guide), [PostCSS installation guide](https://tailwindcss.com/docs/installation/using-postcss), and [dark-mode guide](https://tailwindcss.com/docs/dark-mode).

## 7. Source Layout

```text
pages/
  index.jsx
components/
  AgentRoster.jsx
  CommandWheel.jsx
  DiscourseTimeline.jsx
  EventRail.jsx
  FocusMode.jsx
  PriceChart.jsx
  RiskGlow.jsx
  dashboard-components.test.jsx
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
  CONTRIBUTING.md
```

## 8. Data and Component Contracts

Current components accept JavaScript objects through props. For example, `PriceChart` expects a market-data object, while `AgentRoster` expects an array of agent opinion objects. The `type-check` script parses and checks these JS/JSX sources using TypeScript's `allowJs` and `checkJs` options; it does not turn them into a fully typed TypeScript application.

Before replacing simulated data with a provider:

1. Define canonical schemas.
2. Validate inputs at the application boundary.
3. Represent loading, empty, stale, and error states separately.
4. Ensure timestamps and units are explicit.
5. Reject invalid or incomplete market data.
6. Keep provider-specific response formats out of presentation components.
7. Add tests for valid and invalid inputs.

Do not treat a numeric value as a valid market price merely because it can be rendered.

## 9. Development Workflow

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

## 10. Testing Layers

### Current component tests

`npm test` uses Node's built-in `node:test` runner with `tsx` to render selected components to static markup. The current tests check agent opinion content, Focus Mode market data/opinion output and class correctness, and discourse-event rendering. They are a small regression baseline, not full DOM, browser, or end-to-end coverage.

### Recommended next layers

- **Unit tests:** pure transformations, schema validation, indicator calculations, and risk-policy functions.
- **Component tests:** empty states, invalid input handling, accessibility, and user interactions.
- **Integration tests:** the flow from a validated market snapshot through assessment display and decision rendering.
- **End-to-end tests:** loading, errors, stale data, keyboard navigation, and responsive layout.
- **Safety tests:** verify that missing data, stale data, rejected assessments, denied authorization, and risk-limit breaches cannot be represented as approval.

## 11. Known Limitations and Follow-Ups

- `FocusMode` still presents `data.agents[0]`; it does not let a user select another agent.
- `CommandWheel` still uses browser alerts for placeholder commands; replace these before building production workflows.
- The market snapshot, chart series, agent opinions, and event log are synthetic. They are not live or investment-grade data.
- React 18 works with the current build but triggers a Next.js 16 deprecation warning; plan migration to React 19 before upgrading to Next.js 17.
- The full npm audit retains the development-only `braces@3.0.3` advisory described above. Production dependencies have no reported audit findings as of this verification.
- Next.js announced a further security release for October 14, 2026; rerun audits and update after its advisories and patched versions are available.

## 12. Definition of Done

A change is complete when:

- Its intended behavior is documented.
- Inputs and outputs are validated.
- Tests cover normal and failure cases.
- No secrets or sensitive information are committed.
- Accessibility and responsive behavior are considered.
- Relevant checks have been run and results recorded.
- The pull request explains any unverified assumptions or follow-up work.
