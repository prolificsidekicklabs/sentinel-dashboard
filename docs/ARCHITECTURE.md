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
          +-- FastAPI /api/v1/paper/dashboard
                |
                +-- Alpaca historical bars adapter
                +-- Alpaca paper account/positions adapter
          +-- FastAPI /api/v1/research/strategies/rsi-macd-candidate
                +-- Read-only market bars; no account or position data
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

GET /api/v1/research/strategies/rsi-macd-candidate
    |
    +-- Authenticated FastAPI route
    +-- Read-only Alpaca historical bars
    +-- Deterministic, isolated RSI/MACD/EMA plugin
    +-- Typed candidate signal
    +-- Independent CandidateRiskGate (review-only; never execution authorization)
```

The main dashboard defaults to fixed synthetic fixtures. In local development, the paper-account view and manually triggered candidate panel use two fixed same-origin GET routes to the FastAPI service; the proxy keeps the bearer key server-side, enforces same-origin and loopback HTTP, disables caching, and refuses production use. FastAPI forces Alpaca's paper trading host for account reads. The candidate route reads market bars only and returns no account or position fields. The chart draws only supplied bars. Agent opinions, discourse, risk glow and illustrative verdict remain fixed synthetic examples and are not computed from provider data. User-authorized read-only paper and candidate checks were verified locally; temporary credentials and response artifacts were removed afterward. This does not verify live-account access or market-data freshness. Separately, `/strategy-validation` accepts a user-selected historical CSV, validates basic shape and chronology, and runs a deterministic SMA crossover engine in the browser. The authenticated candidate-strategy route runs a local plugin in the bounded subprocess, validates its typed signal, and applies a separate fail-closed review gate. That gate checks market-data quality/freshness and contract consistency; eligible candidates still require human review, account exposure and sizing are unassessed, and execution is structurally disabled. Neither strategy path submits orders; the browser prototype's assumptions are documented in the [Strategy Validation Engine guide](STRATEGY_VALIDATION_ENGINE.md), while the backend plugin and Alpaca SDK review are documented in [Candidate Strategy](../backend/docs/CANDIDATE_STRATEGY.md).

The command wheel no longer uses browser alerts. It provides explicit demo-only status messages, scrolls to the illustrative discourse, or links to the local-file validation prototype. It does not connect to an analysis, vault, account-settings, language-model, performance, or trading service.

## 3. Technology Boundaries

### 3.1 Presentation layer

**Current:** React components render data and interactive visual states. Tailwind CSS provides styling, D3 draws the price chart, and Framer Motion animates interface elements.

**Future:** Keep presentation components focused on rendering validated view models. They should not independently determine trading authority, bypass risk controls, or send broker orders.

### 3.2 Application layer

**Current:** `pages/index.jsx` selects a fixed demo or validated paper response. `ResearchCandidatePanel` sends a user-triggered, same-origin candidate request only in local development; `lib/research-candidate.js` validates the strict typed response and non-execution flags. `lib/paper-dashboard.js` validates the separate paper response, while `pages/api/sentinel/[resource].js` delegates to the local server proxy. The separate validation route and user interaction live in `pages/strategy-validation.jsx` and `components/StrategyValidationPanel.jsx`; pure simulation functions live in `lib/strategy-validation.js`.

**Future:** Move orchestration into explicit application services. A service should own one defined operation, such as requesting market state, submitting an analysis request, or retrieving an approved decision record.

### 3.3 Intelligence layer

**Current:** Agent opinions are hard-coded example objects. They are not generated by verified autonomous agents.

**Future:** Introduce versioned analytical modules that receive typed input, identify evidence, report limitations, and return structured assessments. Each assessment should identify its input snapshot, method version, timestamp, and evidence references.

### 3.4 Data layer

**Current:** The dashboard has a local, optional Alpaca read-only paper data path plus a fixed synthetic fallback. The validation prototype processes a user-provided CSV in browser memory and downloads an experiment JSON record. The manually triggered candidate panel requests normalized daily bars only and displays a typed research signal plus review-gate outcome; it does not fetch paper account or position data. One-time paper-read and candidate checks were verified locally, but there is no persistent database, production provider secret store, or live-feed service.

**Future:** Separate raw market observations, normalized market state, analytical assessments, decisions, risk evaluations, and execution records. Maintain source identifiers and event timestamps.

### 3.5 Integration layer

**Current:** The Alpaca adapters are exercised with mocked provider responses, and a user-authorized read-only paper-account check returned normalized market bars and paper account/position data through the local route. The research candidate route reuses only the read-only market-data adapter. No live account, execution integration, or freshness guarantee has been verified. AEGIS Core and broker execution have not been implemented.

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
