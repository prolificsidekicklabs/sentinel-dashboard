import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseResearchCandidate,
  requestResearchCandidate,
  ResearchCandidateRequestError,
} from './research-candidate.js'

const NOW = '2026-10-12T12:00:00.000Z'

function sampleCandidate() {
  return {
    mode: 'research-candidate',
    execution_enabled: false,
    plugin_api_version: '1.0',
    captured_at: NOW,
    market: {
      instrument_id: 'SPY',
      timeframe: '1Day',
      source_id: 'alpaca:iex',
      quality: 'valid',
      observed_at: NOW,
      received_at: NOW,
      bar_count: 250,
    },
    signal: {
      plugin_id: 'rsi-macd-candidate',
      plugin_version: '0.1.0',
      instrument_id: 'SPY',
      timeframe: '1Day',
      as_of: NOW,
      bar_count: 250,
      candidate: 'bullish_candidate',
      reason_codes: ['ema_bullish_stack', 'macd_bullish'],
      indicators: {
        rsi_14: 55.5,
        macd: 2.1,
        macd_signal: 1.9,
        macd_histogram: 0.2,
        ema_50: 600.1,
        ema_100: 590.2,
        ema_200: 570.3,
        last_close: 610.4,
      },
      execution_enabled: false,
    },
    review: {
      policy_id: 'candidate-review-gate',
      policy_version: '0.1.0',
      disposition: 'review_required',
      eligible_for_human_review: true,
      execution_enabled: false,
      evaluated_at: NOW,
      reason_codes: ['market_data_quality_valid', 'human_review_required'],
      unassessed_risks: [
        'account_exposure_not_evaluated',
        'position_sizing_not_evaluated',
        'stop_loss_and_drawdown_not_evaluated',
        'broker_execution_not_enabled',
      ],
    },
    output_sha256: 'a'.repeat(64),
    record_id: 'b'.repeat(32),
  }
}

test('accepts a complete typed research candidate while keeping execution disabled', () => {
  const parsed = parseResearchCandidate(sampleCandidate(), 'spy')

  assert.equal(parsed.market.instrument_id, 'SPY')
  assert.equal(parsed.review.disposition, 'review_required')
  assert.equal(parsed.execution_enabled, false)
  assert.equal(parsed.signal.execution_enabled, false)
  assert.equal(parsed.review.execution_enabled, false)
})

test('rejects execution, unknown fields, mismatched provenance, and a different requested ticker', () => {
  const executionEnabled = sampleCandidate()
  executionEnabled.signal.execution_enabled = true
  assert.throws(() => parseResearchCandidate(executionEnabled, 'SPY'))

  const extraField = sampleCandidate()
  extraField.account = { equity: '1000' }
  assert.throws(() => parseResearchCandidate(extraField, 'SPY'))

  const mismatchedBars = sampleCandidate()
  mismatchedBars.signal.bar_count = 249
  assert.throws(() => parseResearchCandidate(mismatchedBars, 'SPY'))

  const missingRiskDisclosure = sampleCandidate()
  missingRiskDisclosure.review.unassessed_risks = ['broker_execution_not_enabled']
  assert.throws(() => parseResearchCandidate(missingRiskDisclosure, 'SPY'))

  const staleReviewApproval = sampleCandidate()
  staleReviewApproval.market.quality = 'stale'
  assert.throws(() => parseResearchCandidate(staleReviewApproval, 'SPY'))

  assert.throws(() => parseResearchCandidate(sampleCandidate(), 'QQQ'), /requested ticker/)
})

test('fetches only the same-origin candidate GET and never sends a browser bearer key', async () => {
  const observed = { url: '', method: '', cache: '', accept: '', authorization: null }
  const result = await requestResearchCandidate('spy', async (url, options) => {
    observed.url = url
    observed.method = options.method
    observed.cache = options.cache
    const headers = new Headers(options.headers)
    observed.accept = headers.get('Accept')
    observed.authorization = headers.get('Authorization')
    return Response.json(sampleCandidate())
  })

  assert.equal(observed.url, '/api/sentinel/research-candidate?symbol=SPY')
  assert.equal(observed.method, 'GET')
  assert.equal(observed.cache, 'no-store')
  assert.equal(observed.accept, 'application/json')
  assert.equal(observed.authorization, null)
  assert.equal(result.market.instrument_id, 'SPY')
})

test('rejects invalid tickers before fetch and preserves only safe upstream status codes', async () => {
  let called = false
  await assert.rejects(
    requestResearchCandidate('SPY/QQQ', async () => {
      called = true
      return Response.json({})
    }),
    TypeError,
  )
  assert.equal(called, false)

  await assert.rejects(
    requestResearchCandidate('SPY', async () => new Response(null, { status: 503 })),
    (error) => error instanceof ResearchCandidateRequestError && error.status === 503,
  )
})
