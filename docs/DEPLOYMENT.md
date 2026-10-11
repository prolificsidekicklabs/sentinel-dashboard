# Sentinel Deployment Guide

## 1. Status and Scope

This remains a proposed deployment guide. The repository's install/build/check baseline is verified, but no production deployment, hosting provider, backend service, database, or CI/CD pipeline is established.

## 2. Current Application Profile

The package manifest identifies a Next.js application with development, build, and production-start scripts.

`npm ci`, lint, type-check, tests, and the production build passed on Node.js `24.19.0` and npm `11.17.0`. Repeat these checks on the target host and verify its runtime configuration before deployment.

## 3. Pre-Deployment Checklist

- [x] Confirm the supported Node.js range and record the tested npm version.
- [x] Review dependency compatibility and document known audit findings.
- [x] Commit the approved lockfile.
- [x] Run lint, type-check, tests, and production build.
- [ ] Resolve known rendering and data-shape issues.
- [ ] Verify responsive layout and accessibility.
- [ ] Confirm demo data is clearly labeled.
- [ ] Verify that no real credentials or sensitive data are in the repository.
- [ ] Establish error reporting and health monitoring.
- [ ] Document rollback procedures.

Do not label a deployment production-ready until the checks have actually passed.

## 4. Local Production Build

```bash
npm ci
npm run build
npm run start
```

The repository commits `package-lock.json`; `npm ci` installs that exact dependency tree and fails if the lockfile and manifest are out of sync. Regenerate the lockfile intentionally alongside dependency changes.

## 5. Hosting Options

Choose hosting after validating the actual application and its operational requirements.

Potential options include:

- A managed Next.js-compatible hosting platform.
- A container-based deployment.
- A controlled Node.js application host.

The selected platform must support the chosen Next.js runtime and any required server-side functionality. Do not assume a static export is suitable if future API routes, authentication, or server-rendered features are introduced.

## 6. Environment Configuration

The current reviewed dashboard does not establish a required external API credential. Do not add unnecessary secrets merely in anticipation of future integrations.

When providers and services are introduced:

- Define environment variables explicitly.
- Validate required variables at startup.
- Keep secrets in the hosting platform's secret manager.
- Use different credentials for development, staging, and production.
- Restrict credentials to required resources and permissions.
- Rotate compromised credentials promptly.
- Never expose secret values through client-side environment variables or logs.

A future environment template may document variable names and descriptions, but it must never contain actual secrets.

## 7. Deployment Pipeline

Recommended pipeline:

1. Install dependencies from the lockfile.
2. Run formatting and lint checks.
3. Run unit and component tests.
4. Run type checking.
5. Build the production application.
6. Run dependency and secret scans.
7. Deploy to staging.
8. Execute smoke and integration tests.
9. Obtain approval for production promotion.
10. Monitor the deployment and retain a rollback path.

The pipeline should fail if mandatory checks fail.

## 8. Monitoring

Recommended signals:

- Application availability and response latency.
- Client-side rendering errors.
- Server-side exceptions.
- API dependency health, when applicable.
- Market-data freshness, when a real feed exists.
- Analysis request failures and completion latency.
- Authentication failures and denied actions.
- Decision and risk-policy failures.

Do not log access tokens, credentials, private account information, or unnecessary sensitive user data.

## 9. Rollback

Maintain a known-good deployment artifact and documented rollback procedure.

After rollback:

- Verify application health.
- Confirm the expected version is running.
- Check for schema or state compatibility issues.
- Investigate the triggering failure.
- Record the incident and corrective action.

Database migrations, when introduced, must have a backward-compatibility and recovery strategy.

## 10. Live-Trading Deployment Gate

A live-trading capability must not be enabled merely because the dashboard is deployed.

Before any live execution is considered, require:

- A verified market-data integration.
- Independently tested order and risk controls.
- Server-side identity and authorization.
- Account and instrument allowlists.
- Position, exposure, and loss limits.
- Order idempotency and reconciliation.
- Broker error and partial-fill handling.
- A kill switch and operational escalation procedure.
- Durable audit logs and monitoring.
- Successful paper-trading and failure-injection tests.
- Explicit human approval for the transition to live execution.

A read-only dashboard deployment and an order-execution deployment are different risk categories and should have separate release gates.
