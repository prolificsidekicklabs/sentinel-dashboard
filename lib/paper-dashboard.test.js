import assert from 'node:assert/strict'
import test from 'node:test'

import { parsePaperDashboard, toMarketChartData } from './paper-dashboard.js'

const fixture = {
  mode: 'paper-read-only',
  execution_enabled: false,
  captured_at: '2026-10-11T20:00:00.000Z',
  market: {
    instrument_id: 'SPY',
    timeframe: '1Day',
    source_id: 'alpaca:iex',
    observed_at: '2026-10-09T20:00:00.000Z',
    received_at: '2026-10-11T20:00:00.000Z',
    quality: 'valid',
    bars: [{
      instrument_id: 'SPY',
      observed_at: '2026-10-09T20:00:00.000Z',
      open: '451.00',
      high: '454.00',
      low: '450.00',
      close: '452.37',
      volume: '1234000',
      currency: 'USD',
      source_id: 'alpaca:iex',
    }],
  },
  account: {
    paper: true,
    currency: 'USD',
    equity: '1000.25',
    cash: '800.25',
    buying_power: '1600.50',
    observed_at: '2026-10-11T20:00:00.000Z',
  },
  positions: [],
}

test('accepts an explicitly read-only paper dashboard response and maps its actual bars', () => {
  const snapshot = parsePaperDashboard(fixture)
  const chart = toMarketChartData(snapshot)

  assert.equal(chart.instrument, 'SPY')
  assert.equal(chart.price, 452.37)
  assert.equal(chart.source_id, 'alpaca:iex')
  assert.equal(chart.bars.length, 1)
})

test('rejects live-mode flags, account identifiers, malformed decimals, and unknown fields', () => {
  assert.throws(() => parsePaperDashboard({ ...fixture, execution_enabled: true }))
  assert.throws(() => parsePaperDashboard({ ...fixture, account: { ...fixture.account, account_ref: 'private' } }))
  assert.throws(() => parsePaperDashboard({ ...fixture, account: { ...fixture.account, equity: 'NaN' } }))
  assert.throws(() => parsePaperDashboard({ ...fixture, unexpected: true }))
})
