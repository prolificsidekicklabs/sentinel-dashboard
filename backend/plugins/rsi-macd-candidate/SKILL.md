# RSI/MACD candidate strategy contract

## Purpose

This local research plugin evaluates caller-supplied daily close bars and returns a typed directional candidate label plus indicator values. It is not investment advice, an order, a position-sizing rule, or evidence of a profitable strategy.

## Inputs

The runtime supplies `instrument_id`, `timeframe` (`1Day` only), the snapshot's `observed_at`, and an ascending `bars` list. Each bar has an aware ISO-8601 `observed_at`, matching `instrument_id`, and a finite positive `close`. The plugin accepts at most 1,000 bars and requires 200 for the full indicator set. No implicit clock, network client, API key, account, or broker state is available or permitted.

## Fixed calculations

- RSI(14): Wilder smoothing, seeded with the arithmetic mean of the first 14 gains/losses; flat data returns 50.
- MACD(12, 26, 9): recursive EMA lines and signal, each SMA-seeded.
- Trend context: SMA-seeded EMA(50), EMA(100), and EMA(200).
- A bullish candidate requires EMA50 > EMA100 > EMA200, MACD > signal, and RSI < 70. A bearish candidate requires the reverse EMA stack, MACD < signal, and RSI > 30. Otherwise return `no_candidate`.
- Values are rounded to 10 decimal places for stable JSON output. There is no confidence score, future-data access, sizing, stop, or trading action.

## Output and safety

Return `PluginResult.output.signal` conforming to `sentinel_core.candidate_strategy.CandidateSignal`. The `execution_enabled` field is permanently false. The generic plugin-run HTTP route must not invoke strategy plugins directly; use the dedicated authenticated research endpoint so the independent `CandidateRiskGate` runs after the signal is schema-validated. The gate can block stale, incomplete, mismatched, or invalid data, or mark a candidate as requiring human review. Passing the gate never authorizes execution. Position sizing, account exposure, stop-loss/drawdown policy, and broker execution are explicitly unassessed.

Do not import Alpaca trading clients, `TradingClient`, order request types, submit/cancel/close methods, network libraries, or environment-secret access. Do not change strategy parameters without a versioned manifest/plugin update and tests.
