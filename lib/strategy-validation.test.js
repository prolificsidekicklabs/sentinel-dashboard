import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  ENGINE_VERSION,
  experimentIdentityPayload,
  parseOhlcvCsv,
  runValidation,
} from './strategy-validation.js'

const closes = [10, 10, 10, 12, 14, 12, 8, 7, 9, 10, 10, 10]
const opens = [10, 10, 10, 12, 20, 12, 8, 10, 9, 10, 10, 10]

function makeBars(closeValues = closes) {
  return closeValues.map((close, index) => {
    const open = opens[index]
    return {
      date: new Date(Date.UTC(2024, 0, index + 1)).toISOString(),
      timestamp: Date.UTC(2024, 0, index + 1),
      open,
      high: Math.max(open, close) + 0.5,
      low: Math.min(open, close) - 0.5,
      close,
      volume: 100_000,
    }
  })
}

const bars = makeBars()
const config = {
  fastPeriod: 2,
  slowPeriod: 3,
  startingCapital: 1_000,
  currencyCode: 'USD',
  allocationPct: 100,
  commissionBps: 10,
  halfSpreadBps: 10,
  slippageBps: 10,
}

const csvHeader = 'date,open,high,low,close'

test('CSV parser accepts standard columns, quoted fields, and explicit UTC timestamps', () => {
  const parsed = parseOhlcvCsv([
    'DATE,Open,High,Low,Close,Volume',
    '"2024-01-02",10,11,9,10,1000',
    '2024-01-03T15:30:00Z,10,12,10,11,1200',
    '2024-01-04,11,12,10,11.5,1400',
  ].join('\n'))

  assert.equal(parsed.length, 3)
  assert.equal(parsed[0].date, '2024-01-02T00:00:00.000Z')
  assert.equal(parsed[1].date, '2024-01-03T15:30:00.000Z')
  assert.equal(parsed[1].close, 11)
  assert.equal(parsed[2].volume, 1400)
})

test('CSV parser rejects out-of-order, duplicate-session, and inconsistent OHLC bars', () => {
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-03,10,11,9,10\n2024-01-02,10,11,9,10\n2024-01-04,10,11,9,10`), /strictly chronological/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-03T10:00:00Z,10,11,9,10\n2024-01-03T15:00:00Z,10,11,9,10\n2024-01-04,10,11,9,10`), /multiple bars on one UTC date/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-02,10,10.5,9,11\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /OHLC values are inconsistent/)
})

test('CSV parser rejects malformed quoting, mismatched rows, duplicate/ambiguous headers, and ambiguous dates', () => {
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-02"oops,10,11,9,10\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /quote inside an unquoted field/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n"2024-01-02"oops,10,11,9,10\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /characters after a closing quote/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-02,10,11,9\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /expected 5 columns but found 4/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-02,10,11,9,10,extra\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /expected 5 columns but found 6/)
  assert.throws(() => parseOhlcvCsv('date,open,high,low,close,Close\n2024-01-02,10,11,9,10,10\n2024-01-03,10,11,9,10,10\n2024-01-04,10,11,9,10,10'), /duplicate column headers/)
  assert.throws(() => parseOhlcvCsv('date,timestamp,open,high,low,close\n2024-01-02,2024-01-02,10,11,9,10\n2024-01-03,2024-01-03,10,11,9,10\n2024-01-04,2024-01-04,10,11,9,10'), /ambiguous columns for date/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n01/02/2024,10,11,9,10\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /YYYY-MM-DD or an ISO UTC timestamp/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-01-02T10:00:00-05:00,10,11,9,10\n2024-01-03,10,11,9,10\n2024-01-04,10,11,9,10`), /YYYY-MM-DD or an ISO UTC timestamp/)
  assert.throws(() => parseOhlcvCsv(`${csvHeader}\n2024-02-30,10,11,9,10\n2024-03-01,10,11,9,10\n2024-03-02,10,11,9,10`), /valid UTC calendar date/)
})

test('SMA crossover uses next-open fills and charges costs on both sides', () => {
  const result = runValidation(bars, config)
  const trainTrade = result.inSample.strategy.trades[0]

  assert.equal(result.split.method, 'chronological-holdout')
  assert.equal(result.split.trainPercent, 70)
  assert.equal(result.split.trainingBarCount, 8)
  assert.equal(result.inSample.strategy.trades.length, 1)
  assert.equal(trainTrade.entryDate, bars[4].date)
  assert.equal(trainTrade.entryRawPrice, 20)
  assert.ok(Math.abs(trainTrade.entryFillPrice - 20 * 1.002) < 1e-10)
  assert.equal(trainTrade.exitDate, bars[7].date)
  assert.equal(trainTrade.exitRawPrice, 10)
  assert.ok(Math.abs(trainTrade.exitFillPrice - 10 * 0.998) < 1e-10)
  assert.ok(trainTrade.totalCosts > 0)
  assert.ok(trainTrade.netPnl < trainTrade.grossPnl)
  assert.equal(trainTrade.exitReason, 'sma-cross-down-next-open')
})

test('out-of-sample starts flat and estimates terminal-close liquidation with costs', () => {
  const result = runValidation(bars, config)
  const oosTrade = result.outOfSample.strategy.trades[0]

  assert.equal(result.split.outOfSampleStartDate, bars[8].date)
  assert.equal(result.outOfSample.barCount, 4)
  assert.equal(result.outOfSample.strategy.trades.length, 1)
  assert.equal(oosTrade.entryDate, bars[10].date)
  assert.equal(oosTrade.exitDate, bars[11].date)
  assert.equal(oosTrade.exitReason, 'end-of-test-liquidation-estimate')
  assert.ok(Math.abs(oosTrade.exitFillPrice - oosTrade.exitRawPrice * 0.998) < 1e-10)
  assert.ok(oosTrade.exitCosts.commission > 0)
  assert.ok(result.outOfSample.buyAndHold.metrics.totalCosts > 0)
})

test('a signal on the final bar is not filled using unavailable future data', () => {
  const lateSignalCloses = [...closes]
  lateSignalCloses[8] = 7
  lateSignalCloses[9] = 6
  lateSignalCloses[10] = 5
  lateSignalCloses[11] = 20
  const result = runValidation(makeBars(lateSignalCloses), config)

  assert.equal(result.outOfSample.strategy.trades.length, 0)
})

test('direct engine calls reject invalid dates and optional volume values', () => {
  assert.throws(() => runValidation(bars.map((bar, index) => index === 4 ? { ...bar, volume: -1 } : bar), config), /volume must be finite and non-negative/)
  assert.throws(() => runValidation(bars.map((bar, index) => index === 4 ? { ...bar, date: '2024-01-05T08:00:00-05:00' } : bar), config), /ISO UTC timestamp ending in Z/)
})

test('experiment results and identity payload are deterministic and bind the full output', () => {
  const first = runValidation(bars, config)
  const second = runValidation(bars, config)
  const identity = experimentIdentityPayload(first, 'same-source-hash')

  assert.deepEqual(first, second)
  assert.equal(ENGINE_VERSION, '0.2.0')
  assert.equal(first.engineVersion, ENGINE_VERSION)
  assert.equal(first.dataset.barCount, bars.length)
  assert.equal(typeof first.outOfSample.strategy.metrics.maxDrawdown, 'number')
  assert.equal(typeof first.outOfSample.strategy.metrics.annualizedVolatility, 'number')
  assert.equal(first.outOfSample.strategy.metrics.riskFreeRate, 0)
  assert.equal(first.outOfSample.buyAndHold.metrics.tradeCount, 1)
  assert.deepEqual(identity, experimentIdentityPayload({ ...first, createdAt: 'different-timestamp' }, 'same-source-hash'))
  assert.notDeepEqual(identity, experimentIdentityPayload(first, 'different-source-hash'))
  assert.notDeepEqual(identity, experimentIdentityPayload({ ...first, strategy: { ...first.strategy, entryRule: 'changed rule' } }, 'same-source-hash'))
  assert.notDeepEqual(identity, experimentIdentityPayload({ ...first, outOfSample: { ...first.outOfSample, strategy: { ...first.outOfSample.strategy, metrics: { ...first.outOfSample.strategy.metrics, totalReturn: 999 } } } }, 'same-source-hash'))
  assert.ok(first.caveats.some((value) => value.includes('Do not tune')))
  assert.ok(first.assumptions.omissions.includes('No taxes, dividends, corporate-action processing, market impact, borrow/funding costs, partial fills, halts, or venue-specific lot rules.'))
})

test('flat no-trade results have explicit zero-volatility and no-loss metric behavior', () => {
  const flatBars = makeBars(Array(closes.length).fill(10))
  const noCostRun = runValidation(flatBars, { ...config, commissionBps: 0, halfSpreadBps: 0, slippageBps: 0 })
  const metrics = noCostRun.inSample.strategy.metrics

  assert.equal(noCostRun.inSample.strategy.trades.length, 0)
  assert.equal(metrics.totalReturn, 0)
  assert.equal(metrics.cagr, 0)
  assert.equal(metrics.maxDrawdown, 0)
  assert.equal(metrics.annualizedVolatility, 0)
  assert.equal(metrics.sharpe, null)
  assert.equal(metrics.winRate, null)
  assert.equal(metrics.profitFactor, null)
  assert.equal(metrics.expectancyPerTrade, null)
  assert.equal(metrics.averageExposure, 0)
})

test('validation rejects invalid strategy rules and undersized holdout datasets', () => {
  assert.throws(() => runValidation(bars, { ...config, fastPeriod: 3, slowPeriod: 3 }), /greater than the fast period/)
  assert.throws(() => runValidation(bars.slice(0, 6), { ...config, slowPeriod: 4 }), /fixed 70\/30 split needs at least/)
  assert.throws(() => runValidation(bars, { ...config, allocationPct: 101 }), /no more than 100%/)
  assert.throws(() => runValidation(bars, { ...config, currencyCode: 'US' }), /Currency code must be three letters/)
})
