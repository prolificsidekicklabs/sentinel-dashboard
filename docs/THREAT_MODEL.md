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

Implemented or proposed boundaries include:

- Browser to application server.
- Application server to market-data provider.
- Application server to analytical services.
- Analytical services to governance and risk evaluation.
- Application server to persistence.
- Browser/client to configured OIDC issuer and backend bearer-token validation.
- Backend process to the vault-encryption key and SQLite database.
- Backend plugin host to the isolated OCI runtime and read-only plugin mount.
- Sentinel to AEGIS Core.
- Sentinel paper-order adapter to the official paper broker API.
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
- The research candidate route applies a separate fail-closed gate to quality, source/instrument/timeframe consistency, minimum history, and observation/receipt freshness. Eligible output means human review only; this gate is not an account-aware risk model.

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

- No live-execution route or UI exists. The optional order API is paper-only, disabled by default, and always targets the official Alpaca paper host.
- Backend routes verify OIDC token signature, issuer, audience, expiry, and scopes. The legacy shared bearer-key path is development-only and does not authorize credential management or paper trading. The Next.js proxy remains local-development-only and is not connected to an interactive login flow.
- Paper orders require `paper:trade`, explicit `confirm_paper_order: true`, user-owned encrypted credentials, a valid idempotency key, fresh market/account snapshots, an active account, an instrument allowlist, bounded notional/exposure, and a short-lived server-generated risk approval.
- A SQLite partial unique index and API check allow at most one non-terminal paper order per user, including concurrent submissions. Unknown/active orders require reconciliation before another order is accepted; no cancel or liquidation endpoint is implemented.
- Paper order intent, provider status, risk policy/version/reasons, and market/account provenance are written to a hash-chained audit log. These checks are server-side; browser state and synthetic risk visuals do not authorize execution.
- Strategy-category plugins remain blocked from the generic runner and the research candidate route remains execution-disabled.

**Remaining risk:** The order path is disabled and was not used to submit a paper trade. A provider key with paper-trading permissions, operator enablement, end-to-end failure/reconciliation testing, monitoring, and operational kill-switch procedures are not established. Intraday-loss limits and actual fill/slippage quality are explicitly unassessed; live execution is not supported.

### 4.6 Compromised credentials

**Threat:** Provider or broker credentials leak through source code, client bundles, logs, or build artifacts.

**Controls:**

- Store each user's provider secret encrypted with AES-GCM and owner/provider-bound associated data; keep the 32-byte master key outside SQLite in the process environment or secret manager.
- Never commit credentials.
- Never ship privileged secrets to the browser.
- OIDC signatures, issuer, audience, and expiry are verified before deriving the user owner ID. Credential routes additionally require `credentials:read` or `credentials:write`; values are masked on input and never returned by status routes.
- Credential retrieval is audit logged. The legacy development key uses constant-time comparison, is disabled in production, and cannot authorize credential management.
- Restrict and rotate provider credentials; explicit master-key rotation/re-encryption and managed KMS integration remain deployment work.
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

- The local SQLite store uses append-only update/delete triggers, WAL/full synchronization, restrictive file permissions, and a hash chain that the API verifies before exposing audit events or accepting paper orders.
- Persist credential updates/reads/deletes, experiment records, risk decisions, paper-order submissions, and provider status changes with owner identity and timestamps.
- These are local tamper-evident controls, not immutable storage: an operator with database-file access can replace the file, drop triggers, or recompute hashes. External replication, retention policy, privileged-access monitoring, backup/restore, and managed production storage remain open.

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

### 4.10 Candidate signal mistaken for advice or approval

**Threat:** A deterministic indicator label is interpreted as a recommendation, a calibrated forecast, a position-size instruction, or a risk approval; alternatively, a caller tries to bypass the review gate through generic plugin execution.

**Controls:**

- Use typed `bullish_candidate`, `bearish_candidate`, and `no_candidate` labels rather than order-side fields; do not emit confidence or quantity.
- Run strategy-category plugins only through the authenticated route that schema-validates the signal and invokes `CandidateRiskGate`; generic plugin execution returns `409` for strategy plugins.
- The gate can block, report no candidate, or require human review. It always returns `execution_enabled: false` and identifies account exposure, sizing, and stop-loss/drawdown controls as unassessed.
- Keep the plugin deterministic and local, with no network, provider credential, account, or broker context. The local subprocess is for trusted repository-reviewed code, not hostile marketplace plugins.

**Remaining risk:** The technical rule is not validated, backtested, or demonstrated to have predictive value. The review gate checks data/contract conditions only and must never be reused as an order-risk evaluator.

### 4.11 Malicious third-party plugin escape

**Threat:** Untrusted plugin code attempts network access, reads host files or credentials, exhausts resources, or escapes its worker process.

**Controls:**

- Untrusted manifests are routed only to a digest-pinned OCI image under rootless Docker/gVisor (`runsc`); missing runtime or image configuration fails closed.
- The container has no network, a read-only root filesystem and plugin mount, a non-root UID, no added capabilities, `no-new-privileges`, CPU/memory/PID limits, bounded input/output, and a hard timeout with container cleanup.
- Trusted repository-reviewed plugins continue to use the local subprocess runner; that path is not represented as a hostile-code sandbox.

**Remaining risk:** The OCI image has not been built or run in this environment, and container escape/adversarial testing has not been performed. Do not enable marketplace plugin execution until the exact deployment runtime and image have been independently reviewed and tested.

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
