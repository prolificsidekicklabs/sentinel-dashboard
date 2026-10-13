# Strategy Validation Engine Prototype

## Status and boundary

This is a **research-only prototype**, not a validated strategy or trading system. It adds a client-side route at `/strategy-validation`; it does not connect to a market-data provider, persist data on a server, submit paper orders, or route live orders. The selected CSV is read in the browser and is not uploaded. No sample or synthetic performance dataset is bundled.

The current strategy is intentionally narrow: a single equity-style instrument, long-only simple moving-average crossover on daily bars, with a 252-session annualization convention. A 24/7 or other asset class needs its own reviewed execution and annualization assumptions. Results are descriptive and do not establish a durable edge, an investment recommendation, or permission to advance to paper or live trading.

## Data contract

Upload a CSV containing one bar per UTC date in strict chronological order. Required, case-insensitive column names are `date` (or `datetime`, `timestamp`, or `time`), `open`, `high`, `low`, and `close`; `volume` is optional. Dates must be `YYYY-MM-DD` or an ISO UTC timestamp ending in `Z`; other locale formats and timezone offsets are rejected. Header names must be non-empty and unique, and every row must have the same number of columns. Prices must be positive and internally consistent. The parser rejects malformed quoting, ambiguous headers, duplicate/out-of-order timestamps, multiple bars on one UTC date, missing values, inconsistent OHLC ranges, and files exceeding 50,000 bars or the UI's 20 MB limit.

These checks establish basic shape and ordering only. They do not authenticate the source, verify the timestamp convention, adjust for dividends or corporate actions, identify survivorship bias, detect every missing session, or prove that prices are tradable. Use a documented, appropriately adjusted historical source and preserve its original file.

## Strategy and execution semantics

The experiment records the following rules and assumptions:

- **Entry:** when the fast SMA crosses above the slow SMA at a completed daily close, schedule a long entry for the next bar's open.
- **Exit:** when the fast SMA crosses below the slow SMA at a completed daily close, schedule a sale for the next bar's open.
- **Sizing:** at most one long position; invest the configured percentage of available cash; fractional units; no leverage, shorting, stops, or pyramiding.
- **Costs:** the user must enter commission, half-spread, and slippage in basis points per side. Buys pay an adverse price adjustment; sells receive an adverse price adjustment; commission is charged on filled notional.
- **End of segment:** any remaining position is valued using an estimated adverse-cost liquidation at the segment's final close. This is a valuation convention, not a promised executable fill.
- **Benchmark:** buy-and-hold for each segment, with the same allocation and cost assumptions.

The instrument's prices and starting capital must use the same currency. There is no foreign-exchange conversion. The cost inputs are not inferred from the bars; they must be selected to fit the market, venue, and intended size.

## Holdout and metrics

The split is a fixed chronological **70% in-sample / 30% out-of-sample**. SMA calculations in the holdout may use only data already observed before each signal, including earlier training bars as indicator warm-up. Portfolio state is reset flat at the boundary, and no training-period pending order is carried into the holdout. Do not select or repeatedly tune SMA periods after inspecting holdout results; repeated trials invalidate the holdout, and this prototype does not adjust for multiple testing.

The report includes net return, CAGR, annualized volatility, Sharpe ratio with zero risk-free rate, peak-to-trough maximum drawdown, closed-trade count, win rate, profit factor, net expectancy per trade, average exposure, modeled costs, and the corresponding buy-and-hold metrics. CAGR uses the actual elapsed calendar time between segment bar dates. Volatility and Sharpe use 252 sessions per year; Sharpe uses the sample standard deviation of daily marked-to-market returns. Profit factor is `null` (shown as a dash) when there are no losing trades; that convention does not imply infinite performance. Each segment has its own starting capital and portfolio state.

There are no pass/fail thresholds. The prototype does not provide statistical significance, confidence intervals, bootstrap analysis, walk-forward validation, regime robustness, or an evaluation of the number of strategy trials.

## Reproducible experiment record

Each run has a deterministic experiment ID derived from the raw CSV SHA-256, engine/schema versions, full strategy rules and assumptions, recorded parameters, holdout definition, and both result segments (including metrics, curves, and trade ledgers). The downloadable JSON includes that identity, the source filename and hash, data range and bar count, strategy rules, costs, assumptions, in-sample and holdout metrics, equity curves, and trade ledgers. The CSV itself is not embedded; retain the exact source file alongside the exported record to reproduce the run. `createdAt` and the filename are informational and are not part of the deterministic ID.

## Important omissions and next gates

Not implemented: taxes, dividends, corporate-action processing, market impact, borrow/funding charges, partial fills, venue-specific lot rules, halts, order-book execution, independently verified data lineage, a persistent audit store, pre-registered acceptance thresholds, multiple-testing controls, paper trading, AEGIS governance, or live execution.

Before treating any result as evidence, the project needs independently sourced and adjusted data, predeclared asset-specific costs and risk limits, a relevant benchmark, out-of-sample and robustness tests designed before inspecting outcomes, reproducible multi-run records, and independent review. Paper trading and live execution remain separate future gates; this prototype does not authorize either.
