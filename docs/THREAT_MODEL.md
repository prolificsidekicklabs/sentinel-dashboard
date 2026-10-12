# Sentinel Threat Model

## 1. Status

This is an initial threat model covering the implemented local API/data path and proposed future controls. It is not a completed penetration test, formal security audit, or certification.

## 2. Assets to Protect

1. Market-data integrity and provenance.
2. Analytical outputs and their supporting evidence.
3. Decision records and policy versions.
4. User identities and authorization state.
5. Broker credentials, if a future integration is approved.
6. Account identifiers and financial information.
7. Audit records and operational telemetry.
8. Availability of the dashboard and any future services.
9. Integrity of deployments and dependencies.
10. AEGIS integration credentials and permissions, if introduced.

## 3. Trust Boundaries

Proposed boundaries include:

- Browser to application server.
- Application server to market-data provider.
- Application server to analytical services.
- Analytical services to governance and risk evaluation.
- Application server to persistence.
- Sentinel to AEGIS Core.
- Sentinel to any future broker adapter.
- Next.js server proxy to the local FastAPI service, then to Alpaca market-data and paper-trading APIs.
- CI/CD system to production deployment.

The browser must be treated as an untrusted environment. Client-side state is not an authorization mechanism.

## 4. Threats and Controls

### 4.1 Simulated or stale data mistaken for live data

**Threat:** Synthetic prices or old observations are presented as current market information.

**Controls:**

- Display a persistent simulation indicator in demo mode.
- The dashboard uses fixed synthetic fallback fixtures and labels them as demo-only; paper account/bars are shown separately, and agent opinions remain explicitly synthetic. These UI labels do not authenticate data or enforce a real trading control.
- Include source and timestamp information.
- Enforce freshness thresholds server-side.
- Mark stale or invalid data visibly.
- Prevent invalid snapshots from reaching decision evaluation.

### 4.2 Manipulated market-data input

**Threat:** Malformed, delayed, incomplete, or tampered provider data distorts analytical results.

**Controls:**

- Validate schemas and instrument identifiers.
- Check timestamp ordering and expected ranges.
- Detect duplicate, missing, or out-of-order observations.
- The browser-only strategy prototype applies file-size, daily ordering, positive-price, and OHLC-consistency checks to user-selected CSV; these are structural checks only and do not authenticate the source or verify corporate-action adjustments, completeness, or tradability.
- Record source identity and ingestion time.
- Quarantine anomalous input.
- Define behavior for provider outages.

### 4.3 False confidence or fabricated evidence

**Threat:** An analytical module reports a high confidence value or cites evidence that does not support its conclusion.

**Controls:**

- Require evidence references for material claims.
- Record model and methodology versions.
- Separate confidence from calibrated probability.
- Evaluate calibration against historical outcomes.
- Test for missing and contradictory evidence.
- Do not equate agent agreement with correctness.

### 4.4 Prompt injection and hostile external content

**Threat:** News, documents, or other external content instructs an AI component to bypass policy or disclose sensitive information.

**Controls:**

- Treat retrieved content as untrusted data.
- Separate data from executable instructions.
- Restrict tools to explicit allowlists.
- Keep authorization decisions outside model-generated text.
- Require validation and policy checks before consequential actions.
- Record relevant input references for later review.

### 4.5 Unauthorized trading action

**Threat:** A compromised client or service submits an order without permission or outside risk limits.

**Controls:**

- Do not expose live execution in the UI prototype.
- The implemented API has no order, cancel, or liquidation route; its paper dashboard handler forcibly selects Alpaca's official paper host even if environment variables request live reads.
- The browser-facing data proxy accepts one same-origin read, targets loopback HTTP, holds the bearer key server-side, disables caching, and returns 404 in production. This is a local development boundary, not user identity or production access control.
- Require server-side authentication and authorization.
- Use narrowly scoped execution credentials.
- Apply account, instrument, quantity, and exposure limits.
- Require independent risk evaluation.
- Use idempotency keys and order reconciliation.
- Provide a kill switch and a documented emergency process.

### 4.6 Compromised credentials

**Threat:** Provider or broker credentials leak through source code, client bundles, logs, or build artifacts.

**Controls:**

- Store secrets in a managed secret store.
- Never commit credentials.
- Never ship privileged secrets to the browser.
- The FastAPI bearer-token dependency requires a configured key of at least 32 characters and uses a constant-time comparison; the local proxy does not return or log the token.
- Restrict and rotate credentials.
- Scan repositories and build artifacts.
- Revoke compromised credentials immediately.

### 4.7 Dependency or build-chain compromise

**Threat:** A compromised package or CI/CD identity introduces malicious code.

**Controls:**

- Commit a lockfile.
- Review dependency changes.
- Use dependency and secret scanning.
- Restrict CI permissions.
- Protect release branches.
- Pin or constrain critical tooling where appropriate.
- Keep deployment credentials separate from general development credentials.

### 4.8 Audit tampering

**Threat:** A decision, risk override, or execution record is modified or deleted.

**Controls:**

- Store audit events in controlled persistence.
- Restrict mutation and deletion privileges.
- Record actor identity and timestamps.
- Use append-only or tamper-evident storage where justified.
- Monitor privileged changes.
- Retain records according to an approved policy.

### 4.9 Denial of service or resource exhaustion

**Threat:** Excessive requests or costly analytical jobs exhaust application resources.

**Controls:**

- Apply rate limits and request-size limits.
- Use bounded job queues.
- Enforce timeouts and concurrency limits.
- The local provider adapter and proxy apply request timeouts and bounded provider responses; rate limiting and production abuse controls are not implemented.
- Cache safe read-only results where appropriate.
- Monitor error rates and resource usage.
- Define graceful degradation.

## 5. Security Principles

- Least privilege.
- Explicit trust boundaries.
- Defense in depth.
- Fail closed for consequential actions.
- Separation of analysis, approval, and execution.
- Traceable evidence and decisions.
- Secure defaults.
- Human oversight for high-impact changes.
- Independent enforcement of financial risk limits.

## 6. Incident Response

For a suspected security incident:

1. Disable affected credentials or capabilities.
2. Stop any potentially unsafe execution path.
3. Preserve relevant logs and evidence.
4. Determine scope and affected assets.
5. Restore a known-good configuration.
6. Notify appropriate stakeholders according to the incident plan.
7. Document root cause and corrective action.
8. Verify that remediation is effective before re-enabling capabilities.

## 7. Required Validation

Before production use, conduct:

- Dependency and secret scans.
- Authentication and authorization tests.
- Input-validation tests.
- Abuse-case and rate-limit tests.
- Threat-focused integration tests.
- Failure-injection tests.
- Security review of any AEGIS or broker integration.

This document must be updated as actual backend services, data stores, credentials, and execution capabilities are implemented.
