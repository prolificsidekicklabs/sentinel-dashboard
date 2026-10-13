# Sentinel Dashboard Architecture

## 1. Purpose

This document describes the reviewed dashboard architecture and the proposed path toward a reliable trading-intelligence application.

It distinguishes three states:

- **Implemented in reviewed code:** directly visible in the inspected files.
- **Unverified:** not established by the reviewed files or not tested.
- **Proposed:** recommended future architecture, not a claim of existing implementation.

## 2. Current Architecture

The current implementation is a client-rendered dashboard assembled from React components.

```text
pages/index.jsx
    |
    +-- Fixed synthetic market fixture (safe fallback)
    |
    +-- Same-origin local provider proxy (development only; two allowlisted GETs)
          |
          +-- Server-held bearer token
          +-- FastAPI API (OIDC JWT validation; dev API-key compatibility only)
                |
                +-- SQLite: encrypted user credentials, experiments, paper orders, audit chain
                +-- Trusted plugin subprocess; untrusted plugin -> fail-closed OCI/gVisor runner
                +-- Alpaca bars + paper account/positions adapters
                +-- Fixed-parameter walk-forward backtest
                +-- Independent account-aware paper risk evaluator
                +-- Optional Alpaca paper order adapter (operator-disabled by default)
          +-- Next.js proxy remains local-development-only; no OIDC login UI/integration yet
    |
    +-- Fixed synthetic analytical-agent opinions
    |
    +-- Fixed synthetic discourse events
    |
    +-- Dashboard state
          |
          +-- PriceChart
          +-- AgentRoster
          +-- DiscourseTimeline
          +-- EventRail
          +-- RiskGlow
          +-- FocusMode
          +-- CommandWheel
          +-- ResearchCandidatePanel (manual request; development only)

pages/strategy-validation.jsx
    |
    +-- User-selected historical daily CSV (browser-only)
    +-- lib/strategy-validation.js
          |
          +-- SMA crossover backtest and buy-and-hold comparison
          +-- Downloadable experiment record

Authenticated FastAPI research routes
    |
    +-- OIDC verification / scope enforcement
    +-- Alpaca historical bars with provider provenance and freshness checks
    +-- Deterministic RSI/MACD/EMA research candidate behind CandidateRiskGate
    +-- Reproducible rolling walk-forward backtest with cost stress and baseline
    +-- Owner-scoped experiment persistence

Optional paper order route (disabled unless operator-enabled)
    |
    +-- OIDC paper:trade scope + explicit per-request confirmation
    +-- Fresh account/market snapshot -> fixed fail-closed risk policy
    +-- One-active-order-per-user reservation + idempotency + reconciliation
    +-- Paper host hard-coded; no live execution adapter
```

The main dashboard still defaults to fixed synthetic fixtures. In local development, the paper-account view and candidate panel use two fixed same-origin GET routes; the proxy keeps its bearer key server-side, enforces same-origin and loopback HTTP, disables caching, and refuses production use. Agent opinions, discourse, risk glow, and the illustrative verdict remain synthetic and are not computed from provider data. The backend now verifies configured OIDC access tokens and scopes, stores owner-scoped encrypted credentials/experiments/orders in single-node SQLite, and maintains a local hash-chained audit ledger. It also has fixed-parameter walk-forward backtesting, a versioned paper risk evaluator, and a paper-only Alpaca order adapter guarded by an operator-off switch, explicit request confirmation, idempotency, and one-active-order reservation. The dashboard has no OIDC login or execution UI; no paper order was submitted or independently reconciled in this change. Browser and backend backtests are research tools, not evidence of a strategy edge. The untrusted-plugin container runner is fail-closed until a digest-pinned image and rootless Docker/gVisor runtime are configured; sandbox escape testing, multi-node storage/KMS, external immutable audit, and production identity integration remain unverified.

The command wheel no longer uses browser alerts. It provides explicit demo-only status messages, scrolls to the illustrative discourse, or links to the local-file validation prototype. It does not connect to an analysis, vault, account-settings, language-model, performance, or trading service.

## 3. Technology Boundaries

### 3.1 Presentation layer

**Current:** React components render data and interactive visual states. Tailwind CSS provides styling, D3 draws the price chart, and Framer Motion animates interface elements.

**Future:** Keep presentation components focused on rendering validated view models. They should not independently determine trading authority, bypass risk controls, or send broker orders.

### 3.2 Application layer

**Current:** `pages/index.jsx` selects a fixed demo or validated paper response. `ResearchCandidatePanel` sends a user-triggered, same-origin candidate request only in local development; `lib/research-candidate.js` validates the strict typed response and non-execution flags. `lib/paper-dashboard.js` validates the separate paper response, while `pages/api/sentinel/[resource].js` delegates to the local development-only proxy. The FastAPI backend separately exposes OIDC-protected credential, audit, backtest, and disabled-by-default paper-order routes, but the Next.js app has no sign-in or execution UI integration. The `/strategy-validation` page remains a browser-only CSV prototype; pure simulation functions live in `lib/strategy-validation.js`.

**Future:** Move orchestration into explicit application services. A service should own one defined operation, such as requesting market state, submitting an analysis request, or retrieving an approved decision record.

### 3.3 Intelligence layer

**Current:** Agent opinions are hard-coded example objects. They are not generated by verified autonomous agents.

**Future:** Introduce versioned analytical modules that receive typed input, identify evidence, report limitations, and return structured assessments. Each assessment should identify its input snapshot, method version, timestamp, and evidence references.

### 3.4 Data layer

**Current:** The dashboard has a local, optional Alpaca paper-read path plus a fixed synthetic fallback. The validation prototype processes user CSV in browser memory. The backend adds file-backed SQLite for encrypted credentials, hash-chained audit events, paper-order idempotency, and persisted walk-forward experiment runs. This is single-node local persistence, not a managed database/KMS or externally immutable log. The candidate panel still requests daily bars only. Market quality, source, age, and paper-account status are checked by backend research/risk functions; no live feed or end-to-end production reliability has been verified.

**Future:** Separate raw market observations, normalized market state, analytical assessments, decisions, risk evaluations, and execution records. Maintain source identifiers and event timestamps.

### 3.5 Integration layer

**Current:** Alpaca read adapters are exercised with mocked responses; a prior user-authorized read-only paper-data path was checked locally. The new execution adapter can target only the official paper host, is disabled by default, and has mocked tests for risk approvals, idempotency, and reconciliation behavior. No paper order was placed as part of implementation, no live account or fill behavior was verified, and no profitability or operational guarantee follows from these tests. AEGIS Core is not integrated.

**Future:** Use explicit service interfaces and least-privilege credentials. Integrations must not be able to circumvent policy enforcement, risk checks, or authorization requirements.

## 4. Proposed Target Architecture

```text
Market Data Providers
        |
        v
Ingestion and Validation
        |
        v
Normalized Market State
        |
        v
Analytical Services
        |
        v
Evidence and Agent Assessments
        |
        v
Decision and Risk Evaluation
        |
        v
Governance / Authorization
        |
        +------> Read-only Dashboard
        |
        +------> Approved Paper-Trading Adapter
        |
        +------> Future Live-Execution Adapter
```

Cross-cutting services should provide identity, observability, audit records, configuration management, and failure handling.

This is a proposed design, not a description of deployed services.
Potential open-source research references are catalogued in [Quantitative Research Ecosystem](QUANT_RESEARCH_ECOSYSTEM.md). The directory is not an audit or endorsement; no source code or dependency is adopted, and AEGIS remains the proposed authority and governance layer.

## 5. Canonical Domain Objects

The following objects are recommended for the future application.

### 5.1 MarketSnapshot

Represents a time-bounded view of an instrument or market.

Suggested fields:

- `snapshot_id`
- `instrument_id`
- `observed_at`
- `received_at`
- `source`
- `source_sequence`
- `price`
- `currency`
- `market_session`
- `indicators`
- `quality_status`
- `staleness_ms`

### 5.2 AgentAssessment

Represents an analytical result.

Suggested fields:

- `assessment_id`
- `agent_id`
- `agent_version`
- `snapshot_id`
- `opinion`
- `confidence`
- `rationale`
- `evidence_refs`
- `limitations`
- `created_at`

Confidence must be defined and calibrated before it is interpreted as a probability of correctness.

### 5.3 DiscourseEvent

Represents an auditable interaction or analytical event.

Suggested fields:

- `event_id`
- `analysis_id`
- `event_type`
- `actor_id`
- `target_id`
- `message`
- `evidence_refs`
- `created_at`

### 5.4 DecisionRecord

Represents the output of an explicit decision process.

Suggested fields:

- `decision_id`
- `analysis_id`
- `policy_version`
- `risk_evaluation_id`
- `verdict`
- `reasons`
- `approved_by`
- `created_at`
- `expires_at`

A decision record is not a broker order. Any future execution request must pass its own authorization, freshness, idempotency, and risk checks.

### 5.5 ExecutionRecord

A future object for paper or live execution.

Suggested fields:

- `execution_id`
- `decision_id`
- `broker`
- `account_reference`
- `client_order_id`
- `order_status`
- `requested_quantity`
- `filled_quantity`
- `average_fill_price`
- `submitted_at`
- `updated_at`

Never store broker credentials in these records.

## 6. Integration With AEGIS Core

AEGIS integration is a proposed extension until verified in source and tested end to end.

Recommended responsibilities:

- Sentinel produces structured market assessments and decision proposals.
- AEGIS supplies or enforces applicable identity, authority, policy, workflow, and audit controls.
- Sentinel does not assume that a proposed action is authorized merely because an analytical model recommends it.
- Execution adapters enforce risk and authorization checks independently of UI state.
- Decisions and outcomes return through a traceable event path.

A conceptual flow is:

`Market State → Evidence → Assessment → Proposal → Governance → Approved Action → Verification → Outcome → Learning`

The dashboard should consume governed records rather than become the authority for trading actions.

## 7. Current Technical Risks to Verify

1. A paper-account read-only connection was verified for a local dashboard request; this does not validate live-account access, all feed entitlements, freshness policy, or production reliability. The fallback fixture is fixed and labeled synthetic.
2. The chart renders only supplied OHLCV bars. The successful paper read confirms one provider path, not freshness or a reliability guarantee for future market data.
3. Agent confidence and rationales are predefined examples.
4. The simulated verdict is not evidence of a real risk engine.
5. The command wheel provides demo-only feedback/navigation; no analytical service action is wired to it.
6. Focus Mode still selects the first predefined agent and is not driven by paper-data outputs.
7. Next.js ESLint plugins emit non-fatal ESLint 10 peer-range warnings; lint passes, but plugin compatibility should be rechecked on upgrades. React 18 also has a Next.js 16 deprecation warning.
8. The strategy prototype's execution-cost assumptions are user-entered estimates, and its end-of-segment liquidation is a valuation convention rather than a guaranteed fill.
9. OIDC validation is implemented at the backend API boundary, but the repository has no interactive identity-provider login flow or Next.js session integration; issuer, audience, and scopes still require deployment configuration.
10. SQLite, its local hash chain, and a digest-pinned OCI/gVisor design are foundations only. Managed persistence/KMS, backups, a running sandbox image, adversarial isolation testing, external audit retention, rate limiting, and production monitoring have not been verified.
11. The paper-order path is disabled by default and has not been used to submit or reconcile a paper trade. The risk evaluator deliberately reports intraday-loss, fill-quality, and live-suitability controls as unassessed.

## 8. Architecture Acceptance Criteria

The architecture should not be considered production-ready until:

- Market observations have documented provenance and freshness checks.
- Analytical outputs are reproducible from recorded inputs and versions.
- Decisions identify their policy and risk-evaluation versions.
- Authorization is enforced outside the browser.
- Failed, stale, or incomplete inputs cannot silently become valid trading signals.
- Audit events are durable and traceable.
- Paper-trading behavior has automated tests.
- Broker execution, if ever introduced, has independent risk controls and a kill switch.
- AEGIS integration has explicit contracts and tested failure behavior.
