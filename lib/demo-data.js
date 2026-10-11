const DEMO_TIMESTAMP = "2026-10-11T23:00:00.000Z";

// These fixtures are synthetic and intentionally stable across renders and reloads.
export const DEMO_MARKET_STATE = Object.freeze({
  timestamp: DEMO_TIMESTAMP,
  instrument: "SPY",
  price: 452.37,
  regime: "trending",
  indicators: {
    rsi: 58.2,
    macd: { line: 0.32, signal: 0.21, histogram: 0.11 },
    bollinger_bands: { upper: 458.0, middle: 452.0, lower: 446.0 },
  },
  order_book: { bid_vol: 1225, ask_vol: 1130, spread: 0.14 },
  sentiment: { bullish: 0.62, bearish: 0.38 },
  fundamentals: { pe_ratio: 20.5, earnings_date: "2026-12-15" },
});

export const DEMO_AGENT_OPINIONS = Object.freeze([
  Object.freeze({
    agent_name: "TECH",
    opinion: "GREEN",
    confidence: 0.72,
    rationale: "Synthetic RSI and MACD values indicate a moderate upward bias.",
    data_used: ["indicators.rsi", "indicators.macd"],
  }),
  Object.freeze({
    agent_name: "MACRO",
    opinion: "GREEN",
    confidence: 0.8,
    rationale: "Illustrative macro opinion for the fixed demo scenario.",
    data_used: ["fundamentals.pe_ratio"],
  }),
  Object.freeze({
    agent_name: "MICRO",
    opinion: "RED",
    confidence: 0.65,
    rationale: "Illustrative liquidity caution for the fixed demo scenario.",
    data_used: ["order_book.spread"],
  }),
  Object.freeze({
    agent_name: "SENT",
    opinion: "GREEN",
    confidence: 0.75,
    rationale: "Synthetic demo sentiment is moderately bullish.",
    data_used: ["sentiment.bullish"],
  }),
  Object.freeze({
    agent_name: "FUND",
    opinion: "GREEN",
    confidence: 0.7,
    rationale: "Illustrative valuation opinion for the fixed demo scenario.",
    data_used: ["fundamentals.pe_ratio"],
  }),
]);

export const DEMO_DISCOURSE_LOG = Object.freeze([
  Object.freeze({
    type: "OPINION",
    agent: "TECH",
    opinion: "GREEN",
    timestamp: DEMO_TIMESTAMP,
  }),
  Object.freeze({
    type: "CHALLENGE",
    agent: "MICRO",
    target: "TECH",
    message: "Synthetic liquidity values warrant a caution check.",
    timestamp: DEMO_TIMESTAMP,
  }),
  Object.freeze({
    type: "AGREE",
    agent: "SENT",
    target: "TECH",
    message: "Synthetic demo sentiment is directionally consistent.",
    timestamp: DEMO_TIMESTAMP,
  }),
  Object.freeze({
    type: "DECISION",
    verdict: "BLOCK",
    critic_notes: "Demo-only block decision; no execution is connected.",
    timestamp: DEMO_TIMESTAMP,
  }),
]);
