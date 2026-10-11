# Adapter research and implementation boundaries

**Checked:** 2026-10-11. These notes record the official documentation used to shape Sentinel's first adapters. Provider credentials were not requested, read, or added to the repository.

## Model gateways: OmniRoute and 9Router

The user's “Route9” reference is interpreted as **9Router**, the project at [`decolua/9router`](https://github.com/decolua/9router). If a different product was intended, Sentinel's adapter is still configurable for any gateway that implements the same OpenAI-compatible chat contract.

- [OmniRoute official site](https://omniroute.online/) documents a local endpoint such as `http://localhost:20128/v1`, `POST /chat/completions`, bearer authentication, and configurable model routing.
- [OmniRoute official repository](https://github.com/diegosouzapw/OmniRoute) documents its `/v1/*` API and an OpenAI-compatible chat-completions example.
- [9Router official repository](https://github.com/decolua/9router) documents an OpenAI-compatible API at `http://localhost:20128/v1`, `POST /chat/completions`, and a bearer API key.

**Sentinel scope:** use the common chat-completions interface only. Do not infer that embeddings, audio, images, MCP administration, model catalog synchronization, or every vendor-specific feature is supported by the shared adapter. Model responses are untrusted text and are not trading authority or deterministic financial calculations.

## Alpaca Trading API and market data

- [About Alpaca Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api) documents the Trading API key headers `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`, distinct from Broker API's client-credentials OAuth flow. The official data host is `https://data.alpaca.markets`.
- [Historical stock bars reference](https://docs.alpaca.markets/us/reference/stockbars) documents `GET /v2/stocks/bars`, `symbols`, `timeframe`, date-range parameters, ascending/descending sort, pagination using `next_page_token`, and feed selection. It identifies `iex`, `sip`, `boats`, and `otc` feeds.
- [Paper trading guide](https://docs.alpaca.markets/us/docs/paper-trading) documents the paper Trading API base URL `https://paper-api.alpaca.markets`, separate keys from live, and that a paper account is a simulation—not a substitute for live execution testing.
- [Get Account reference](https://docs.alpaca.markets/us/reference/getaccount-1) and [All Open Positions reference](https://docs.alpaca.markets/us/reference/getallopenpositions) document read endpoints on paper/live Trading API hosts. Account values and position amounts are returned as decimal strings.

Alpaca's market-data subscription determines available coverage, recency, rate limits, and feeds. The current documentation describes IEX-only real-time stock coverage and a latest-15-minute historical limitation for the Basic plan; do not present provider access as complete-market coverage without checking the user's plan. Paper executions also omit real-world effects such as market impact, queue position, and slippage assumptions.

**Sentinel scope:** the first concrete adapter is read-only: historical U.S.-equity bars from the Market Data API, plus paper-account summary and positions. Paper trading is an explicit simulation environment; no order placement or live execution is included. Live account reads are disabled by default and require an explicit server-side opt-in. Credentials remain server-side environment configuration; the browser and source tree never receive or store provider secrets.
