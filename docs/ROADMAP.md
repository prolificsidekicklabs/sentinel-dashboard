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
- A Python FastAPI service with protected plugin routes, a trusted-local deterministic plugin runner, and normalized paper-account/position and market-bar contracts.

The provider adapters and API data path are tested with mocked responses; no Alpaca account was connected. User-level authentication, fresh-data policy, persistent analytical history, broker execution, or tested AEGIS Core integration are not established. The validation prototype does not establish a strategy edge or complete independent strategy validation.

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

**Partial delivery:** An Alpaca market-bars adapter, an authenticated paper account/positions route, and a development-only dashboard proxy are implemented and tested with mocked HTTP responses. The route forces the paper broker host, and the interface separates synthetic agent content from provider bars/account fields. No keys were configured and no external connection was verified. Freshness thresholds, live entitlement/licensing review, credential management, retries/reconnect behavior, and account-specific validation remain open.

**Exit criteria:**

- Source provenance is visible.
- Stale and unavailable states are explicit.
- The application does not present synthetic values as live data.
- Market-data failures cannot silently produce valid-looking assessments.

## 6. Phase 3 — Evidence-Grounded Analytical Services

**Objective:** Replace predefined agent opinions with reproducible analytical outputs.

**Prototype status:** An initial client-side SMA crossover validator is implemented with basic CSV checks, next-open costed fills, a fixed chronological holdout, buy-and-hold comparison, risk summaries, and downloadable experiment records. This is a software prototype only; it does not complete this phase's evidence, provenance, robustness, or acceptance criteria.

Work items:

- Define agent interfaces and versions.
- Implement or integrate selected analytical methods.
- Record evidence references and input snapshots.
- Define confidence semantics and calibration requirements.
- Add contradiction and missing-evidence handling.
- Measure latency, cost, reliability, and analytical quality.
- Persist analysis history.

**Exit criteria:**

- Assessments can be traced to their input data and method version.
- Outputs distinguish evidence, inference, uncertainty, and limitations.
- Historical results can be evaluated against outcomes.
- Agent agreement is not treated as sufficient proof of correctness.

## 7. Phase 4 — Governance and Risk Evaluation

**Objective:** Make risk and authorization explicit before any execution work.

Work items:

- Define versioned risk policies.
- Establish instrument, exposure, quantity, and loss constraints.
- Separate analytical recommendations from authorization.
- Record policy decisions and reasons.
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

Work items:

- Define order-intent and paper-execution contracts.
- Model order lifecycle, partial fills, cancellations, and rejection.
- Simulate slippage, transaction costs, and latency.
- Reconcile intended actions with simulated outcomes.
- Test duplicate requests and service outages.
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
