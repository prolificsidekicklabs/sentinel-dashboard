# Sentinel Dashboard Product Roadmap

## 1. Vision

Evolve Sentinel from a simulated trading-intelligence interface into a governed, evidence-grounded analytical system that can support human decision-making and, only after separate validation and authorization, controlled trading workflows.

The product should optimize for trustworthy decisions, risk-adjusted outcomes, reproducibility, and operational resilience—not visual sophistication or agent consensus alone.

## 2. Current Baseline

The reviewed repository contains:

- A Next.js and React dashboard.
- Fixed synthetic OHLCV fixtures plus a local authenticated read-only Alpaca paper-data path when server credentials are configured.
- Predefined agent opinion examples.
- A D3 chart that renders supplied OHLCV closes rather than inventing a series.
- A discourse timeline and event rail.
- Risk visualization.
- Focus Mode and a command-wheel interface.
- A browser-only, research-grade SMA validation prototype that accepts user-supplied daily bars and exports run records.
- A Python FastAPI service with protected plugin routes, a versioned v1.0 plugin API, deeply read-only typed market context, a deterministic offline fixture harness, and a typed RSI/MACD/EMA research candidate that the host validates, independently gates, and records in its local audit chain; the dashboard displays candidate results only after a manual local-development request.
- A configurable OIDC-verifying API with scope enforcement, encrypted owner-scoped Alpaca credentials, SQLite experiment/order persistence, hash-chained local audit events, a fixed-parameter walk-forward backtest, an account-aware paper risk evaluator, and an optional Alpaca-paper-only order route that is disabled by default.
- A fail-closed OCI/gVisor plugin runner for manifests marked untrusted. The image/runtime have not been built or adversarially tested in this environment.
- A curated, unreviewed open-source quant research directory and proposed AEGIS/Sentinel target flow in [Quantitative Research Ecosystem](QUANT_RESEARCH_ECOSYSTEM.md); no listed project has been cloned, audited, or adopted.

Mocked tests cover the backend contracts and provider paths; a prior user-authorized read-only paper connection was verified through the local API and proxy. The new order adapter has mocked submission/reconciliation and risk-expiry tests, but no paper order was placed here. OIDC validation is implemented but no identity provider or browser login flow is configured; SQLite/KMS, container isolation, production data reliability, real paper-fill evidence, live-account access, and AEGIS integration remain unverified. Neither research prototype establishes a strategy edge or completes independent strategy validation.

## 3. Phase 0 — Stabilize the Prototype

**Objective:** Establish a reliable, reproducible baseline.

Work items:

- [x] Complete the repository documentation baseline.
- [x] Validate dependency and framework compatibility and establish a lockfile.
- [ ] Fix remaining rendering and data-shape issues.
- [x] Configure and validate lint, test, type-check, and build scripts.
- [x] Add initial automated component tests.
- [x] Clearly label simulated data and decisions in the UI.
- [x] Replace placeholder command alerts with explicit demo actions.
- [x] Establish CI checks.

**Exit criteria:**

- [x] The application installs and builds reproducibly from its lockfile.
- [x] Selected core dashboard components render under automated tests.
- [x] Demo mode is unambiguously identified in the UI.
- [x] Known issues and the supported Node.js runtime are documented.

## 4. Phase 1 — Define the Domain and Data Contracts

**Objective:** Establish a canonical data model before connecting providers.

Work items:

- Define `MarketSnapshot`, `AgentAssessment`, `DiscourseEvent`, and `DecisionRecord`.
- Establish timestamps, source identity, units, and data-quality semantics.
- Add schema validation.
- Separate mock-data providers from production adapters.
- Define error and loading states.
- Add fixtures and contract tests.

**Exit criteria:**

- Components consume documented, validated view models.
- Invalid and stale data are handled explicitly.
- Tests verify the behavior of each quality state.
- Provider-specific schemas do not leak into the UI.

## 5. Phase 2 — Add Read-Only Market Data

**Objective:** Display validated market information without enabling order execution.

Work items:

- Select an approved market-data provider.
- Document licensing and permitted use.
- Implement server-side ingestion or a secure provider adapter.
- Normalize instruments, timestamps, and values.
- Implement freshness and outage detection.
- Display source and last-update information.
- Test reconnects, missing observations, and delayed feeds.

**Partial delivery:** An Alpaca market-bars adapter, authenticated paper account/positions route, and development-only dashboard proxy are implemented. Automated tests use mocked HTTP responses; a prior user-authorized local read-only paper connection was checked through FastAPI and the Next.js proxy. Backtest/risk routes validate provider provenance and freshness, but general freshness monitoring and data-quality telemetry are not present. Entitlement/licensing review, persistent production credentials, retries/reconnect behavior, broad account validation, and production reliability remain open.

**Exit criteria:**

- Source provenance is visible.
- Stale and unavailable states are explicit.
- The application does not present synthetic values as live data.
- Market-data failures cannot silently produce valid-looking assessments.

## 6. Phase 3 — Evidence-Grounded Analytical Services

**Objective:** Replace predefined agent opinions with reproducible analytical outputs.

**Prototype status:** The client-side SMA prototype remains browser-only. The backend additionally runs fixed-parameter chronological walk-forward tests with next-open estimated fills, explicit costs, a buy-and-hold baseline, cost stress, dataset digest, and persisted owner-scoped experiment records. The deterministic RSI/MACD/EMA candidate plugin remains review-only. These are software research prototypes: they do not establish predictive edge, production-quality source completeness, significance, or the acceptance criteria for this phase.

Work items:

- Define agent interfaces and versions.
- Implement or integrate selected analytical methods.
- Record evidence references and input snapshots.
- Define confidence semantics and calibration requirements.
- Add contradiction and missing-evidence handling.
- Measure latency, cost, reliability, and analytical quality.
- [x] Persist reproducible backtest inputs/results and dataset digests in the local single-node store.
- [ ] Persist versioned agent assessments and evidence references in a production-grade data service.
- Complete and maintain the repository due-diligence matrix before adopting upstream code or dependencies; see [Quantitative Research Ecosystem](QUANT_RESEARCH_ECOSYSTEM.md). No candidate is approved by inclusion in the directory.

**Exit criteria:**

- Assessments can be traced to their input data and method version.
- Outputs distinguish evidence, inference, uncertainty, and limitations.
- Historical results can be evaluated against outcomes.
- Agent agreement is not treated as sufficient proof of correctness.

## 7. Phase 4 — Governance and Risk Evaluation

**Objective:** Make risk and authorization explicit before any execution work.

**Partial delivery:** Configurable OIDC JWT verification and server-side scope checks protect backend APIs; paper risk policy version `1.0.0` checks fresh Alpaca data/account state, active account status, an instrument allowlist, buying power, fixed notional/exposure limits, and long-only sell constraints. The local audit chain records policy reasons and order provenance. The API fails closed on invalid audit integrity. This does not provide interactive login, AEGIS governance, a managed/immutable audit service, intraday-loss limits, or live-trading authorization.

Work items:

- [x] Define a versioned paper-only risk policy.
- [x] Establish instrument, notional, buying-power, gross/symbol exposure, and long-only constraints.
- [x] Separate analytical recommendations from the server-generated `RiskApprovedOrder` contract.
- [x] Record policy decisions and reasons in the local hash-chained audit store.
- [ ] Add intraday loss/drawdown controls and independent operational kill-switch procedures.
- Add human review workflows for consequential actions.
- Integrate AEGIS Core only through verified, documented contracts.
- Test fail-closed behavior and policy overrides.

**Exit criteria:**

- Decisions identify the policy version and evaluation result.
- Denied actions cannot be re-enabled by changing browser state.
- Audit records capture approval, denial, and override events.
- AEGIS integration has defined ownership and failure behavior.

## 8. Phase 5 — Paper Trading and Reconciliation

**Objective:** Validate proposed trading workflows without risking real capital.

**Partial delivery:** A fixed-host Alpaca paper adapter accepts only a short-lived server-approved market order. The route is operator-disabled by default, OIDC-scope gated, requires explicit request confirmation, uses idempotent client order IDs, persists each transition, limits each user to one active order, and exposes reconciliation by idempotency key. Mocked tests cover submission, risk expiry, and reconciliation boundaries. No order was sent, no real broker fill/cancel/partial-fill lifecycle was observed, and the backtest fixtures are not paper-trading performance evidence.

Work items:

- [x] Define order-intent and paper-execution contracts.
- Model order lifecycle, partial fills, cancellations, and rejection.
- Simulate slippage, transaction costs, and latency.
- Reconcile intended actions with simulated outcomes.
- [x] Test duplicate requests, unresolved outcomes, and concurrent-order reservation behavior at the persistence boundary.
- [ ] Run and retain supervised paper-order/fill/reconciliation evidence with a paper-trading-enabled broker credential.
- Compare performance against appropriate baselines.
- Track risk-adjusted metrics and drawdowns.

**Exit criteria:**

- Paper execution is reproducible and auditable.
- Failures and partial fills are handled correctly.
- Performance includes realistic cost assumptions.
- Evaluation avoids look-ahead bias and data leakage.

## 9. Phase 6 — Controlled Live Execution Evaluation

**Objective:** Consider live execution only after independent approval.

This phase is not authorization to trade.

Prerequisites include:

- Completed security and architecture reviews.
- Approved broker integration and credential handling.
- Independent server-side risk controls.
- Account and instrument allowlists.
- Hard exposure and loss limits.
- Order idempotency and reconciliation.
- Kill switch and incident response.
- Extensive paper-trading validation.
- Legal, compliance, and operational review appropriate to the intended use.
- Explicit human approval.

Any rollout should begin with restricted permissions, limited scope, monitoring, and an immediate shutdown path.

## 10. Phase 7 — Learning and Optimization

**Objective:** Improve analytical quality using measured outcomes.

Work items:

- Attribute decisions to their evidence and policies.
- Compare predictions with realized outcomes.
- Measure calibration, drift, false positives, and false negatives.
- Evaluate model and strategy versions.
- Track compute cost and operational reliability.
- Require controlled evaluation before promoting changes.

Learning systems must not automatically loosen risk constraints or increase trading authority without approved governance.

## 11. Cross-Phase Metrics

Track:

- Market-data freshness and completeness.
- Application availability and error rates.
- Analysis latency and cost.
- Evidence coverage.
- Calibration and out-of-sample performance.
- Decision reproducibility.
- Policy rejection and override rates.
- Paper-trading drawdown and transaction-cost sensitivity.
- Order reconciliation accuracy, if execution is eventually approved.
- Mean time to detect and recover from incidents.

## 12. Prioritization Rule

Prioritize correctness, traceability, and safety before adding additional agents, visual complexity, or live execution.

The roadmap should be revised after each phase based on measured outcomes, implementation evidence, operational risk, and the cost of maintaining the system.
