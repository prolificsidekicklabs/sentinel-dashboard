import { z } from 'zod'

const timestamp = z.string().datetime({ offset: true })
const reasonCodes = z.array(z.string().min(1).max(100)).max(64)
const finite = z.number().finite()
const REQUIRED_UNASSESSED_RISKS = [
  'account_exposure_not_evaluated',
  'position_sizing_not_evaluated',
  'stop_loss_and_drawdown_not_evaluated',
  'broker_execution_not_enabled',
]

const indicatorsSchema = z.object({
  rsi_14: finite.min(0).max(100),
  macd: finite,
  macd_signal: finite,
  macd_histogram: finite,
  ema_50: finite.gt(0),
  ema_100: finite.gt(0),
  ema_200: finite.gt(0),
  last_close: finite.gt(0),
}).strict()

const marketSchema = z.object({
  instrument_id: z.string().regex(/^[A-Z0-9.\-]{1,20}$/),
  timeframe: z.literal('1Day'),
  source_id: z.string().min(1).max(100),
  quality: z.enum(['valid', 'stale', 'incomplete', 'invalid', 'unavailable']),
  observed_at: timestamp,
  received_at: timestamp,
  bar_count: z.number().int().min(0).max(1000),
}).strict()

const signalSchema = z.object({
  plugin_id: z.literal('rsi-macd-candidate'),
  plugin_version: z.literal('0.1.0'),
  instrument_id: z.string().regex(/^[A-Z0-9.\-]{1,20}$/),
  timeframe: z.literal('1Day'),
  as_of: timestamp,
  bar_count: z.number().int().min(0).max(1000),
  candidate: z.enum(['bullish_candidate', 'bearish_candidate', 'no_candidate']),
  reason_codes: reasonCodes,
  indicators: indicatorsSchema.nullable(),
  execution_enabled: z.literal(false),
}).strict()

const reviewSchema = z.object({
  policy_id: z.literal('candidate-review-gate'),
  policy_version: z.literal('0.1.0'),
  disposition: z.enum(['blocked', 'no_candidate', 'review_required']),
  eligible_for_human_review: z.boolean(),
  execution_enabled: z.literal(false),
  evaluated_at: timestamp,
  reason_codes: reasonCodes,
  unassessed_risks: reasonCodes,
}).strict()

export const researchCandidateSchema = z.object({
  mode: z.literal('research-candidate'),
  execution_enabled: z.literal(false),
  plugin_api_version: z.literal('1.0'),
  captured_at: timestamp,
  market: marketSchema,
  signal: signalSchema,
  review: reviewSchema,
  output_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  record_id: z.string().regex(/^[a-f0-9]{32}$/),
}).strict().superRefine((value, context) => {
  if (value.market.instrument_id !== value.signal.instrument_id) {
    context.addIssue({ code: 'custom', path: ['signal', 'instrument_id'], message: 'Signal instrument must match the market snapshot.' })
  }
  if (value.market.timeframe !== value.signal.timeframe) {
    context.addIssue({ code: 'custom', path: ['signal', 'timeframe'], message: 'Signal timeframe must match the market snapshot.' })
  }
  if (value.market.bar_count !== value.signal.bar_count) {
    context.addIssue({ code: 'custom', path: ['signal', 'bar_count'], message: 'Signal bar count must match the market snapshot.' })
  }
  if (value.market.observed_at !== value.signal.as_of) {
    context.addIssue({ code: 'custom', path: ['signal', 'as_of'], message: 'Signal timestamp must match the market snapshot.' })
  }

  const expectsHumanReview = value.review.disposition === 'review_required'
  if (value.review.eligible_for_human_review !== expectsHumanReview) {
    context.addIssue({ code: 'custom', path: ['review', 'eligible_for_human_review'], message: 'Review eligibility must agree with the disposition.' })
  }
  if (value.review.disposition === 'review_required' && value.signal.candidate === 'no_candidate') {
    context.addIssue({ code: 'custom', path: ['review', 'disposition'], message: 'A no-candidate signal cannot require human review.' })
  }
  if (value.review.disposition === 'no_candidate' && value.signal.candidate !== 'no_candidate') {
    context.addIssue({ code: 'custom', path: ['review', 'disposition'], message: 'A directional signal cannot use the no-candidate disposition.' })
  }
  for (const risk of REQUIRED_UNASSESSED_RISKS) {
    if (!value.review.unassessed_risks.includes(risk)) {
      context.addIssue({ code: 'custom', path: ['review', 'unassessed_risks'], message: `Required risk disclosure is missing: ${risk}.` })
    }
  }
  if (value.market.quality !== 'valid' && value.review.disposition !== 'blocked') {
    context.addIssue({ code: 'custom', path: ['review', 'disposition'], message: 'Non-valid market data must be blocked.' })
  }
  if (value.market.bar_count < 200 && value.review.disposition !== 'blocked') {
    context.addIssue({ code: 'custom', path: ['review', 'disposition'], message: 'Insufficient history must be blocked.' })
  }
  if (expectsHumanReview && !value.review.reason_codes.includes('human_review_required')) {
    context.addIssue({ code: 'custom', path: ['review', 'reason_codes'], message: 'Human-review disposition must be explicitly identified.' })
  }
  if (expectsHumanReview && value.signal.indicators === null) {
    context.addIssue({ code: 'custom', path: ['signal', 'indicators'], message: 'A review-required result must include validated indicators.' })
  }
})

function normalizeSymbol(symbol) {
  const normalized = typeof symbol === 'string' ? symbol.trim().toUpperCase() : ''
  if (!/^[A-Z0-9.\-]{1,20}$/.test(normalized)) {
    throw new TypeError('Enter a valid ticker symbol.')
  }
  return normalized
}

export function parseResearchCandidate(value, expectedSymbol) {
  const normalizedSymbol = normalizeSymbol(expectedSymbol)
  const parsed = researchCandidateSchema.parse(value)
  if (parsed.market.instrument_id !== normalizedSymbol) {
    throw new Error('Candidate response does not match the requested ticker.')
  }
  return parsed
}

export class ResearchCandidateRequestError extends Error {
  constructor(status = null) {
    super('The local research-candidate request could not be completed.')
    this.name = 'ResearchCandidateRequestError'
    this.status = status
  }
}

export async function requestResearchCandidate(symbol, fetchImpl = globalThis.fetch) {
  const normalizedSymbol = normalizeSymbol(symbol)
  if (typeof fetchImpl !== 'function') throw new ResearchCandidateRequestError()

  let response
  try {
    response = await fetchImpl(
      `/api/sentinel/research-candidate?symbol=${encodeURIComponent(normalizedSymbol)}`,
      {
        method: 'GET',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(30_000),
      },
    )
  } catch {
    throw new ResearchCandidateRequestError()
  }

  if (!response.ok) throw new ResearchCandidateRequestError(response.status)

  let body
  try {
    body = await response.json()
  } catch {
    throw new ResearchCandidateRequestError()
  }
  return parseResearchCandidate(body, normalizedSymbol)
}
