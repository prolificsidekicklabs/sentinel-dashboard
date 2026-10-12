const DEMO_TIMESTAMP = '2026-10-11T23:00:00.000Z'

// Stable, synthetic examples: not a real SPY price history.
export const DEMO_PRICE_BARS = Object.freeze([
  { observed_at: '2026-09-28T20:00:00.000Z', open: '446.20', high: '449.10', low: '445.70', close: '448.60', volume: '41000000' },
  { observed_at: '2026-09-29T20:00:00.000Z', open: '448.80', high: '451.20', low: '447.90', close: '450.30', volume: '38500000' },
  { observed_at: '2026-09-30T20:00:00.000Z', open: '450.00', high: '452.40', low: '449.10', close: '451.10', volume: '40200000' },
  { observed_at: '2026-10-01T20:00:00.000Z', open: '451.30', high: '453.00', low: '449.80', close: '450.20', volume: '39700000' },
  { observed_at: '2026-10-02T20:00:00.000Z', open: '450.00', high: '452.10', low: '448.90', close: '451.70', volume: '42100000' },
  { observed_at: '2026-10-05T20:00:00.000Z', open: '451.80', high: '454.20', low: '451.10', close: '453.40', volume: '43600000' },
  { observed_at: '2026-10-06T20:00:00.000Z', open: '453.10', high: '455.00', low: '451.80', close: '452.20', volume: '38900000' },
  { observed_at: '2026-10-07T20:00:00.000Z', open: '452.50', high: '454.60', low: '451.70', close: '453.80', volume: '41400000' },
  { observed_at: '2026-10-08T20:00:00.000Z', open: '453.60', high: '455.20', low: '452.50', close: '454.10', volume: '40100000' },
  { observed_at: '2026-10-09T20:00:00.000Z', open: '453.90', high: '455.10', low: '451.80', close: '452.37', volume: '42800000' },
])

export const DEMO_MARKET_STATE = Object.freeze({
  timestamp: DEMO_TIMESTAMP,
  instrument: 'SPY',
  price: 452.37,
  regime: 'trending',
  source_id: 'synthetic-demo',
  bars: DEMO_PRICE_BARS,
  indicators: {
    rsi: 58.2,
    macd: { line: 0.32, signal: 0.21, histogram: 0.11 },
    bollinger_bands: { upper: 458.0, middle: 452.0, lower: 446.0 },
  },
  order_book: { bid_vol: 1225, ask_vol: 1130, spread: 0.14 },
  sentiment: { bullish: 0.62, bearish: 0.38 },
  fundamentals: { pe_ratio: 20.5, earnings_date: '2026-12-15' },
})

export const DEMO_AGENT_OPINIONS = Object.freeze([
  Object.freeze({
    agent_name: 'TECH',
    opinion: 'GREEN',
    confidence: 0.72,
    rationale: 'Synthetic RSI and MACD values indicate a moderate upward bias.',
    data_used: ['indicators.rsi', 'indicators.macd'],
  }),
  Object.freeze({
    agent_name: 'MACRO',
    opinion: 'GREEN',
    confidence: 0.8,
    rationale: 'Illustrative macro opinion for the fixed demo scenario.',
    data_used: ['fundamentals.pe_ratio'],
  }),
  Object.freeze({
    agent_name: 'MICRO',
    opinion: 'RED',
    confidence: 0.65,
    rationale: 'Illustrative liquidity caution for the fixed demo scenario.',
    data_used: ['order_book.spread'],
  }),
  Object.freeze({
    agent_name: 'SENT',
    opinion: 'GREEN',
    confidence: 0.75,
    rationale: 'Synthetic demo sentiment is moderately bullish.',
    data_used: ['sentiment.bullish'],
  }),
  Object.freeze({
    agent_name: 'FUND',
    opinion: 'GREEN',
    confidence: 0.7,
    rationale: 'Illustrative valuation opinion for the fixed demo scenario.',
    data_used: ['fundamentals.pe_ratio'],
  }),
])

export const DEMO_DISCOURSE_LOG = Object.freeze([
  Object.freeze({
    type: 'OPINION',
    agent: 'TECH',
    opinion: 'GREEN',
    timestamp: DEMO_TIMESTAMP,
  }),
  Object.freeze({
    type: 'CHALLENGE',
    agent: 'MICRO',
    target: 'TECH',
    message: 'Synthetic liquidity values warrant a caution check.',
    timestamp: DEMO_TIMESTAMP,
  }),
  Object.freeze({
    type: 'AGREE',
    agent: 'SENT',
    target: 'TECH',
    message: 'Synthetic demo sentiment is directionally consistent.',
    timestamp: DEMO_TIMESTAMP,
  }),
  Object.freeze({
    type: 'DECISION',
    verdict: 'BLOCK',
    critic_notes: 'Demo-only block decision; no execution is connected.',
    timestamp: DEMO_TIMESTAMP,
  }),
])
