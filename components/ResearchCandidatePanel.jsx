'use client'

import { useState } from 'react'
import {
  requestResearchCandidate,
  ResearchCandidateRequestError,
} from '../lib/research-candidate'

const SYMBOL_PATTERN = /^[A-Za-z0-9.\-]{1,20}$/

function displayCode(value) {
  return value.replaceAll('_', ' ')
}

function displayTimestamp(value) {
  return new Date(value).toLocaleString('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }) + ' UTC'
}

function candidateLabel(candidate) {
  if (candidate === 'bullish_candidate') return 'Bullish candidate'
  if (candidate === 'bearish_candidate') return 'Bearish candidate'
  return 'No candidate'
}

function dispositionLabel(disposition) {
  if (disposition === 'review_required') return 'Human review required'
  if (disposition === 'blocked') return 'Blocked by data checks'
  return 'No candidate'
}

function errorMessage(error) {
  if (error instanceof ResearchCandidateRequestError) {
    if (error.status === 401 || error.status === 403) return 'Local API authentication failed. Check the local server configuration.'
    if (error.status === 404) return 'This candidate endpoint is unavailable here; provider access is intentionally disabled in production.'
    if (error.status === 422) return 'The local API rejected this ticker request.'
    if (error.status === 502) return 'Market-data evaluation failed. Check the local provider configuration and feed entitlement.'
    if (error.status === 503) return 'The local API or market-data provider is not configured.'
    return 'The local research-candidate service did not return a successful response.'
  }
  if (error instanceof TypeError) return error.message
  return 'The response was invalid or the local research service could not be reached.'
}

function Indicator({ label, value, digits = 2 }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
      <dt className="text-xs uppercase tracking-wide text-slate-600 dark:text-slate-400">{label}</dt>
      <dd className="mt-1 font-semibold tabular-nums">{value === null ? '—' : value.toFixed(digits)}</dd>
    </div>
  )
}

/** @param {{ isProduction?: boolean }} [options] */
export default function ResearchCandidatePanel({ isProduction = process.env.NODE_ENV === 'production' } = {}) {
  const [symbol, setSymbol] = useState('SPY')
  const [candidate, setCandidate] = useState(null)
  const [message, setMessage] = useState('No provider request has been made. Choose a ticker and run a research-only check when ready.')
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    const requestedSymbol = symbol.trim().toUpperCase()
    setSymbol(requestedSymbol)
    setCandidate(null)
    setError('')

    if (!SYMBOL_PATTERN.test(requestedSymbol)) {
      setError('Enter a ticker using letters, numbers, periods, or hyphens (up to 20 characters).')
      return
    }
    if (isProduction) {
      setError('Provider access is intentionally disabled in production.')
      return
    }

    setWorking(true)
    setMessage(`Requesting daily market bars for ${requestedSymbol}…`)
    try {
      const result = await requestResearchCandidate(requestedSymbol)
      setCandidate(result)
      setMessage(`Research result received for ${requestedSymbol}. It is not a trading instruction.`)
    } catch (caught) {
      setMessage('No current candidate result is displayed.')
      setError(errorMessage(caught))
    } finally {
      setWorking(false)
    }
  }

  const indicators = candidate?.signal.indicators

  return (
    <section
      aria-labelledby="research-candidate-heading"
      aria-busy={working}
      className="space-y-4 rounded-xl border border-amber-300 bg-amber-50 p-5 shadow-xs dark:border-amber-800 dark:bg-amber-950/30"
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-800 dark:text-amber-300">Market data only · Local research</p>
        <h2 id="research-candidate-heading" className="mt-1 text-xl font-bold">RSI/MACD candidate review</h2>
        <p className="mt-2 text-sm text-amber-950 dark:text-amber-100">
          Research output, not investment advice or a buy/sell instruction. This check does not read account or position data and has no order capability. “Human review required” only means the data checks passed; account exposure, sizing, stops, drawdown, and execution risk are not evaluated.
        </p>
      </div>

      <form className="flex flex-wrap items-end gap-3" onSubmit={handleSubmit}>
        <label htmlFor="candidate-symbol" className="block space-y-1 text-sm font-medium">
          <span>Ticker</span>
          <input
            id="candidate-symbol"
            autoComplete="off"
            className="block w-40 rounded-md border border-slate-400 bg-white px-3 py-2 text-gray-900 outline-hidden focus:border-blue-600 focus:ring-2 focus:ring-blue-600/30 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-gray-100"
            disabled={working || isProduction}
            maxLength={20}
            onChange={(event) => {
              setSymbol(event.target.value.toUpperCase())
              setCandidate(null)
              setError('')
            }}
            pattern="[A-Za-z0-9.\-]{1,20}"
            required
            value={symbol}
          />
        </label>
        <button
          className="rounded-md bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-slate-700 dark:hover:bg-slate-600"
          disabled={working || isProduction}
          type="submit"
        >
          {isProduction ? 'Disabled in production' : working ? 'Checking…' : 'Run research-only check'}
        </button>
      </form>

      {isProduction && (
        <p role="note" className="rounded-md border border-slate-300 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-900">
          The local provider proxy is disabled in production. This panel is available only in the local development environment.
        </p>
      )}

      <p aria-live="polite" className="text-sm text-slate-700 dark:text-slate-300">{message}</p>
      {error && <p role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100">{error}</p>}

      {candidate && (
        <div className="space-y-4 border-t border-amber-300 pt-4 dark:border-amber-800">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs uppercase tracking-wide text-slate-600 dark:text-slate-400">Candidate label · not a recommendation</p>
              <p className="mt-1 text-lg font-bold">{candidateLabel(candidate.signal.candidate)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs uppercase tracking-wide text-slate-600 dark:text-slate-400">Independent review gate</p>
              <p className="mt-1 text-lg font-bold">{dispositionLabel(candidate.review.disposition)}</p>
              <p className="mt-1 text-xs">Execution enabled: no</p>
            </div>
          </div>

          {indicators ? (
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Indicator label="RSI (14)" value={indicators.rsi_14} />
              <Indicator label="MACD" value={indicators.macd} />
              <Indicator label="MACD signal" value={indicators.macd_signal} />
              <Indicator label="MACD histogram" value={indicators.macd_histogram} />
              <Indicator label="EMA (50)" value={indicators.ema_50} />
              <Indicator label="EMA (100)" value={indicators.ema_100} />
              <Indicator label="EMA (200)" value={indicators.ema_200} />
              <Indicator label="Latest close" value={indicators.last_close} />
            </dl>
          ) : (
            <p className="rounded-md border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-900">Indicators are unavailable, typically because the required history was not available.</p>
          )}

          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div><dt className="font-semibold">Data</dt><dd>{candidate.market.instrument_id} · {candidate.market.timeframe} · {candidate.market.bar_count} bars · {candidate.market.quality}</dd></div>
            <div><dt className="font-semibold">Source</dt><dd>{candidate.market.source_id}</dd></div>
            <div><dt className="font-semibold">Market observed (UTC)</dt><dd>{displayTimestamp(candidate.market.observed_at)}</dd></div>
            <div><dt className="font-semibold">Received by service (UTC)</dt><dd>{displayTimestamp(candidate.market.received_at)}</dd></div>
          </dl>

          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <h3 className="font-semibold">Review reasons</h3>
              <ul className="mt-1 list-inside list-disc text-sm">
                {candidate.review.reason_codes.map((code) => <li key={code}>{displayCode(code)}</li>)}
              </ul>
            </div>
            <div>
              <h3 className="font-semibold">Not assessed by this gate</h3>
              <ul className="mt-1 list-inside list-disc text-sm">
                {candidate.review.unassessed_risks.map((risk) => <li key={risk}>{displayCode(risk)}</li>)}
              </ul>
            </div>
          </div>

          <details className="text-xs text-slate-700 dark:text-slate-300">
            <summary className="cursor-pointer font-medium">Reproducibility metadata</summary>
            <p className="mt-2 break-all">Plugin {candidate.signal.plugin_id} v{candidate.signal.plugin_version} · review policy {candidate.review.policy_id} v{candidate.review.policy_version} · output SHA-256 {candidate.output_sha256}</p>
          </details>
        </div>
      )}
    </section>
  )
}
