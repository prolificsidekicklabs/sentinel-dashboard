import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DEMO_AGENT_OPINIONS,
  DEMO_DISCOURSE_LOG,
  DEMO_MARKET_STATE,
} from './demo-data.js'

test('the demo market fixture is fixed, labeled synthetic, and includes fixed bars', () => {
  assert.equal(DEMO_MARKET_STATE.instrument, 'SPY')
  assert.equal(DEMO_MARKET_STATE.price, 452.37)
  assert.equal(DEMO_MARKET_STATE.timestamp, '2026-10-11T23:00:00.000Z')
  assert.equal(DEMO_MARKET_STATE.source_id, 'synthetic-demo')
  assert.equal(DEMO_MARKET_STATE.bars.length, 10)
  assert.equal(DEMO_MARKET_STATE.bars.at(-1).close, '452.37')
  assert.ok(Object.isFrozen(DEMO_MARKET_STATE))
  assert.ok(Object.isFrozen(DEMO_MARKET_STATE.bars))
})

test('demo agents and discourse use the same fixed timestamp', () => {
  assert.equal(DEMO_AGENT_OPINIONS.length, 5)
  assert.deepEqual(
    new Set(DEMO_DISCOURSE_LOG.map((entry) => entry.timestamp)),
    new Set([DEMO_MARKET_STATE.timestamp]),
  )
  assert.ok(Object.isFrozen(DEMO_AGENT_OPINIONS))
  assert.ok(Object.isFrozen(DEMO_DISCOURSE_LOG))
})
