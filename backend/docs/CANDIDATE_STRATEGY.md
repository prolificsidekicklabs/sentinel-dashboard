# RSI/MACD candidate strategy (research-only)

## What is implemented

Sentinel now includes a local `strategy` plugin, `rsi-macd-candidate`, implementing plugin API v1.0. It receives a typed, deeply read-only `PluginMarketContextV1` with chronological OHLCV bars and provenance, and returns a versioned, Pydantic-validated candidate signal. It is deterministic, receives no network/client/account context, requests no permissions, does not size a position, and cannot submit or manage orders. The signal’s `execution_enabled` field is fixed to `false`.

The authenticated endpoint `GET /api/v1/research/strategies/rsi-macd-candidate?symbol=SPY` retrieves up to 365 calendar days of normalized historical bars through Sentinel’s existing Alpaca market-data adapter, runs the plugin in the bounded child process, validates its typed result, and then passes it to the separate core `CandidateRiskGate`. After validation, the host records the signal, review disposition, plugin/API versions, market metadata, and output hash in the local append-only audit chain; the response includes that record ID. A strategy plugin cannot be run through the generic plugin-execution endpoint, preventing callers from bypassing the gate. The response contains no broker account or position data. Audit-chain integrity is tamper-evident but is not external immutable storage.

## Rule and reproducibility

The current, versioned parameters are RSI(14), MACD(12, 26, 9), and SMA-seeded EMA(50/100/200). RSI uses Wilder’s recursive smoothing (initial arithmetic seed followed by Wilder recurrence), not a rolling moving average. A `bullish_candidate` requires EMA50 > EMA100 > EMA200, MACD above its signal line, and RSI below 70. A `bearish_candidate` requires the reverse EMA stack, MACD below its signal line, and RSI above 30. All other states, including fewer than 200 bars, return `no_candidate` with reason codes. Values are finite and rounded to 10 decimal places. The plugin is explicitly not backtested here; the rule is not evidence of predictive value or a trading edge.

## Independent review gate

`CandidateRiskGate` independently checks provider quality, instrument/timeframe and bar-count agreement, chronological latest-bar/source consistency, minimum history, and observation/receipt freshness. It returns `blocked`, `no_candidate`, or `review_required`. `review_required` means eligible for human inspection only—it is not a risk approval or an order intent. Every response states `execution_enabled: false`. The gate explicitly reports that account exposure, sizing, stop-loss/drawdown controls, and broker execution are unassessed. A future order system would need its own separate account-aware risk evaluator and authorization workflow; this candidate gate must not be reused as an order-approval object.

## Alpaca SDK review

The official [alpaca-py repository](https://github.com/alpacahq/alpaca-py) is an API SDK, not a plugin strategy framework. Its README and [market-data docs](https://github.com/alpacahq/alpaca-py/blob/master/docs/market_data.rst) show distinct typed stock/crypto/options market-data clients and request models. Its [TradingClient docs](https://github.com/alpacahq/alpaca-py/blob/master/docs/trading.rst) define `paper=True` as a boolean. The repository’s [RSI/MACD ChatGPT bot example](https://github.com/alpacahq/alpaca-py/blob/master/examples/stocks/build_trading_bot_with_ChatGPT/strategy.py) combines market data, account/position reads, scheduling, sizing, and `submit_order` calls in one program. It also passes an environment string to the boolean paper argument, declares but does not use `MAX_RISK_PCT`, and labels RSI as Wilder-smoothed while using rolling means.

Sentinel borrows only the indicator concept. It intentionally does not import the SDK or its trading client into the plugin and does not copy the execution loop. The existing bounded HTTPX market-data adapter remains the data boundary; a separately reviewed read-only SDK adapter can be considered later if it adds value, with its own pinned dependency and tests.

## Local verification

Use the normal backend quality suite (Ruff formatting/lint, mypy, pytest) and `python -m sentinel_core.validation_harness` from `backend/`. Tests cover exact Wilder recurrence, immutable typed input, deterministic output, invalid and insufficient bar input, stale/inconsistent snapshots, host-side output validation and audit recording, generic-run bypass prevention, and the non-execution invariant. Live market-data freshness depends on provider response and entitlement; no account or order method is used by this endpoint. See the [plugin contract](PLUGIN_CONTRACT.md) for versioning and boundary details.
