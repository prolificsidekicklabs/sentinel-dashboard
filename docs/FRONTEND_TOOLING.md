# Frontend tooling baseline

## Next.js 16 lint migration

**Checked:** 2026-10-11 against the [official Next.js ESLint guide](https://nextjs.org/docs/app/api-reference/config/eslint) (documentation version 16.4.0, updated 2026-10-05) and the [Next.js 16 upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-16).

Next.js 16 removed the `next lint` command. The official guide recommends invoking ESLint directly with a flat config, using `eslint-config-next` or its `core-web-vitals` export; the guide states the config supports ESLint 9 and 10. The repository's existing `lint: next lint` script therefore no longer matches its declared Next.js 16 dependency. The backend feature does not change this; the configuration is being updated as a development-tooling compatibility repair.

The pre-change workspace also had installed versions that differed from `package.json`, lacked a `tsconfig.json`, and had no local Jest executable. Those are treated as setup/test-environment issues; no UI behavior changes are intended by the tooling repair.

## Next.js security floor

The package installation warned that the repository's declared Next.js `16.0.0` has a security vulnerability. The [official CVE-2025-66478 advisory](https://nextjs.org/blog/CVE-2025-66478) lists `16.0.7` as its initial fix; the [December 11, 2025 update](https://nextjs.org/blog/security-update-2025-12-11) lists `16.0.10` as the fix for follow-up React Server Components issues. The [May 2026 Next.js security release](https://vercel.com/changelog/next-js-may-2026-security-release) states that Next.js 16 versions through `16.2.5` are affected by that release and identifies `16.2.6` as fixed. Therefore, `16.0.0` is below the currently documented security floor.

The npm registry check on 2026-10-11 showed `next@16.4.0` and `eslint-config-next@16.4.0` as the current 16.x versions. The repository is being updated within the same major line to `16.4.0`, with `eslint@10.12.0`, which the current Next.js ESLint guide supports. This is a development/security maintenance update; application feature behavior is not being changed.

The dashboard's previous inline demo values called `Math.random()` during render and generated fresh timestamps, making the same nominal demo scenario differ across renders. The sample values now live in `lib/demo-data.js` as immutable, fixed synthetic fixtures. The home page labels them visibly as demo-only data, not live market data or a trading signal. `lib/demo-data.test.js` checks the fixed snapshot/timestamps, while `jest.config.js` uses Next.js's Jest integration. The new `frontend-ci.yml` runs the npm-lock-based lint, type-check, and Jest checks independently from backend CI.

A successful first production build warned that Tailwind's `@tailwind` and `@apply` directives were unknown. The repository had no PostCSS config, so a Tailwind/Autoprefixer pipeline is now configured in `postcss.config.js`. Build-only and test-only packages are classified under `devDependencies`; PostCSS is upgraded to the audited `8.5.29` patch, and Jest to `30.5.2`. Tailwind 3 remains a development/build dependency; its npm advisory recommends a major Tailwind 4 upgrade, which is intentionally not bundled into this tooling repair because it needs a separate styling migration and visual regression review.

## Verification and remaining maintenance

Verified locally on 2026-10-11 after lockfile installation:

- `npm run lint`: passed.
- `npm run type-check`: passed; the dashboard remains JavaScript/JSX, so this currently validates framework-generated and any future TypeScript inputs rather than checking typed page components.
- `npm test -- --runInBand`: 2 tests passed.
- `npm run build`: passed; Tailwind/PostCSS directives were processed. Next.js emits a warning that React 18 support is deprecated in Next.js 16 and will be removed in Next.js 17.
- `npm audit --omit=dev`: 0 vulnerabilities in the production dependency set; this audit is now part of frontend CI.

The complete `npm audit` still reports **40 development/build-tool findings (12 high, 28 moderate, 0 critical)**. The remaining findings include the Tailwind 3 line, Storybook 7 packages, and development lint/test transitive dependencies. Tailwind 4 and Storybook upgrades are intentionally deferred because they are major toolchain changes; review them separately before relying on those tools. This status is distinct from the clean production-only dependency audit and does not claim the complete development toolchain is vulnerability-free.
