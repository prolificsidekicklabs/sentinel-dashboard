# Sentinel API Contract

## 1. Status

**Partially implemented local contract; the remaining general analysis and decision paths below are proposals.**

The Python service implements `GET /healthz`, API-key-protected plugin discovery, non-strategy plugin execution, `GET /api/v1/paper/dashboard`, and `GET /api/v1/research/strategies/rsi-macd-candidate`. The paper response contains normalized historical OHLCV bars, a paper-account summary and positions, uses decimal values serialized as strings, omits the provider account identifier, and explicitly sets `execution_enabled` to `false`. The broker adapter is forced to Alpaca's paper host. The candidate route reads market bars only, returns a typed RSI/MACD/EMA research label, and applies a separate review-only gate; it does not fetch account/position data or enable execution.

Protected routes require a server-to-server bearer token from `SENTINEL_API_KEY` with at least 32 characters. The Next.js proxy holds that token server-side, accepts same-origin GET requests only, targets loopback HTTP only, disables caching, and is disabled in production. The dashboard still shows fixed synthetic demo data unless server configuration and a provider connection succeed. A separate user-authorized read-only paper-data check previously succeeded through FastAPI and the Next.js proxy; automated provider tests remain mocked.

## 2. Design Principles

- Validate all input at the API boundary.
- Use explicit schema versions.
- Keep raw provider payloads separate from normalized market state.
- Include timestamps, source identity, and data-quality status.
- Return traceable assessment and decision identifiers.
- Make analysis requests idempotent where retries could create duplicate work.
- Never allow the browser to override server-side risk policy.
- Keep broker credentials and provider secrets server-side.
- Do not expose an execution endpoint until authorization and risk controls exist.

## 3. Proposed Base Path

```text
/api/v1
```

The following routes are implemented; all endpoint proposals in the later sections remain unimplemented.

| Method and path | Authentication | Behavior |
|---|---|---|
| `GET /healthz` | Public liveness only | Returns service status and version; no provider or credential state. |
| `GET /api/v1/plugins` | Bearer API key | Lists validated local plugin metadata without filesystem paths. |
| `POST /api/v1/plugins/{plugin_id}/run` | Bearer API key | Runs a repository-trusted non-strategy plugin with bounded input/output and an explicit seed; strategy plugins are refused here to prevent gate bypass. |
| `GET /api/v1/paper/dashboard?symbol=SPY&days=30` | Bearer API key | Fetches bounded historical bars and Alpaca paper-account/position data; no execution capability. |
| `GET /api/v1/research/strategies/rsi-macd-candidate?symbol=SPY` | Bearer API key | Fetches up to 365 calendar days of daily market bars, runs the deterministic strategy subprocess, validates its typed signal, and returns the independent review-gate result; no account or position data. |

The local Next.js API proxy exposes only the paper dashboard route. The candidate route is backend-only for now; it is a development capability, not user authentication or production authorization.

The candidate signal is one of `bullish_candidate`, `bearish_candidate`, or `no_candidate`; the review disposition is `blocked`, `no_candidate`, or `review_required`. Both the signal and response carry `execution_enabled: false`. `review_required` permits human inspection only. The gate checks source quality, instrument/timeframe consistency, minimum history, and observation/receipt freshness; it explicitly does not assess account exposure, position sizing, stop-loss/drawdown limits, or broker execution. Generic plugin execution returns `409` for strategy-category plugins.

## 4. Market State

### `GET /api/v1/market-state/{instrument}`

Returns the most recent validated market snapshot for an instrument.

Example response:

```json
{
  "schema_version": "1.0",
  "snapshot_id": "snap_example_001",
  "instrument": "SPY",
  "observed_at": "2026-10-11T14:30:00Z",
  "received_at": "2026-10-11T14:30:01Z",
  "source": "example-provider",
  "quality_status": "valid",
  "staleness_ms": 1000,
  "price": {
    "value": 650.25,
    "currency": "USD"
  },
  "indicators": {
    "rsi": 54.2
  },
  "regime": {
    "label": "trending",
    "method_version": "1.0"
  }
}
```

This is an illustrative schema, not live market data.

Possible quality states:

- `valid`
- `stale`
- `incomplete`
- `invalid`
- `unavailable`

Clients must not convert a non-valid state into a valid signal.

## 5. Request an Analysis

### `POST /api/v1/analyses`

Submits a request for analysis of a validated market snapshot.

Example request:

```json
{
  "schema_version": "1.0",
  "instrument": "SPY",
  "snapshot_id": "snap_example_001",
  "analysis_profile": "default",
  "requested_agents": [
    "TECH",
    "MACRO",
    "MICRO",
    "SENT",
    "FUND"
  ]
}
```

Example response:

```json
{
  "schema_version": "1.0",
  "analysis_id": "analysis_example_001",
  "status": "accepted",
  "created_at": "2026-10-11T14:30:02Z"
}
```

`accepted` means the request was accepted for processing. It does not mean the analysis completed or that a trade was approved.

Recommended request headers:

```text
Content-Type: application/json
Authorization: Bearer <access-token>
Idempotency-Key: <unique-request-key>
```

The authentication mechanism must be selected and implemented before deployment.

## 6. Retrieve an Analysis

### `GET /api/v1/analyses/{analysis_id}`

Example response:

```json
{
  "schema_version": "1.0",
  "analysis_id": "analysis_example_001",
  "status": "completed",
  "snapshot_id": "snap_example_001",
  "assessments": [
    {
      "assessment_id": "assessment_example_001",
      "agent_id": "TECH",
      "agent_version": "1.0",
      "opinion": "RED",
      "confidence": 0.72,
      "rationale": "Illustrative example only.",
      "evidence_refs": [
        "snapshot:snap_example_001"
      ],
      "limitations": [
        "Example payload; not a real analytical result."
      ]
    }
  ],
  "created_at": "2026-10-11T14:30:02Z",
  "completed_at": "2026-10-11T14:30:03Z"
}
```

The values above are fictional examples for contract design.

## 7. Decision Evaluation

### `POST /api/v1/decisions/evaluate`

Requests a decision evaluation under a named policy. This endpoint must not itself place a broker order.

Example request:

```json
{
  "schema_version": "1.0",
  "analysis_id": "analysis_example_001",
  "policy_id": "trading-risk-policy",
  "policy_version": "1.0"
}
```

Example response:

```json
{
  "schema_version": "1.0",
  "decision_id": "decision_example_001",
  "verdict": "BLOCK",
  "reasons": [
    "Illustrative policy result."
  ],
  "policy_id": "trading-risk-policy",
  "policy_version": "1.0",
  "created_at": "2026-10-11T14:30:04Z",
  "execution_authorized": false
}
```

`execution_authorized` must be determined by server-side governance and authorization. It must never be inferred from agent consensus or a client-controlled field.

## 8. Event History

### `GET /api/v1/analyses/{analysis_id}/events`

Returns a chronologically ordered event history.

Proposed event types include:

- `ANALYSIS_REQUESTED`
- `SNAPSHOT_VALIDATED`
- `ASSESSMENT_CREATED`
- `CHALLENGE_RECORDED`
- `DECISION_EVALUATED`
- `POLICY_BLOCKED`
- `ANALYSIS_FAILED`

Events should include unique IDs, timestamps, actor identities, and references to relevant records.

## 9. Error Format

Use a consistent error envelope.

```json
{
  "error": {
    "code": "MARKET_DATA_STALE",
    "message": "The requested market snapshot is stale.",
    "request_id": "req_example_001",
    "retryable": false
  }
}
```

Suggested HTTP status codes:

| Status | Meaning |
|---|---|
| `400` | Malformed request |
| `401` | Missing or invalid authentication |
| `403` | Authenticated caller lacks permission |
| `404` | Resource not found |
| `409` | Conflicting state or idempotency conflict |
| `422` | Valid JSON but invalid domain input |
| `429` | Rate limit exceeded |
| `500` | Unexpected server error |
| `503` | Required dependency unavailable |

Avoid returning stack traces, secrets, provider credentials, or internal security details.

## 10. Security and Reliability Requirements

- Authenticate and authorize every protected request.
- Validate identifiers and all request fields.
- Apply request size limits and rate limits.
- Use server-side policy evaluation.
- Enforce freshness requirements for market data.
- Persist decision and audit events durably.
- Use idempotency for retried operations.
- Propagate correlation IDs across services.
- Apply timeouts and bounded retries to external dependencies.
- Fail closed for any action that could increase financial exposure.
- Separate read-only analytics permissions from any future execution permissions.

## 11. API Acceptance Criteria

The contract is ready for implementation only after schemas, authentication, authorization, retention, error semantics, and compatibility policy are approved.

Each endpoint must have contract tests covering valid requests, malformed input, missing resources, stale data, unauthorized access, dependency failure, and retry behavior.
