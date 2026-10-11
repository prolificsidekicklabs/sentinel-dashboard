"use client"

import { useState } from 'react'
import Link from 'next/link'
import { ENGINE_VERSION, experimentIdentityPayload, runValidation, parseOhlcvCsv } from '../lib/strategy-validation'

const INITIAL_FORM = {
  fastPeriod: '20',
  slowPeriod: '50',
  startingCapital: '100000',
  currencyCode: 'USD',
  allocationPct: '100',
  commissionBps: '',
  halfSpreadBps: '',
  slippageBps: '',
}

const costFields = ['commissionBps', 'halfSpreadBps', 'slippageBps']

function sha256Hex(value) {
  if (!globalThis.crypto?.subtle) {
    throw new Error('SHA-256 is unavailable in this browser. Open the app over HTTPS or localhost and try again.')
  }
  return globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)).then((buffer) => (
    Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, '0')).join('')
  ))
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
}

function formatAmount(value, currencyCode) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${currencyCode} ${formatNumber(value)}`
}

function formatPercent(value) {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : `${(value * 100).toFixed(2)}%`
}

function formatDate(value) {
  return value ? new Date(value).toISOString().slice(0, 10) : '—'
}

function Field({ label, hint = '', ...props }) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="font-medium">{label}</span>
      <input
        {...props}
        className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-xs outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
      />
      {hint && <span className="block text-xs text-gray-600 dark:text-gray-400">{hint}</span>}
    </label>
  )
}

function MetricCard({ label, value, note = null }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-xs dark:border-gray-700 dark:bg-gray-800">
      <dt className="text-xs uppercase tracking-wide text-gray-600 dark:text-gray-400">{label}</dt>
      <dd className="mt-1 text-lg font-semibold tabular-nums">{value}</dd>
      {note && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{note}</p>}
    </div>
  )
}

function buildPath(curve, startingCapital, width, height, padding, min, max) {
  if (!curve.length) return ''
  const usableWidth = width - padding * 2
  const usableHeight = height - padding * 2
  const span = max - min || 1
  return curve.map((point, index) => {
    const x = padding + (curve.length === 1 ? 0 : (index / (curve.length - 1)) * usableWidth)
    const normalized = point.equity / startingCapital * 100
    const y = height - padding - ((normalized - min) / span) * usableHeight
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
}

function EquityChart({ strategy, benchmark, startingCapital, title }) {
  const values = [...strategy, ...benchmark].map((point) => (point.equity / startingCapital) * 100)
  let min = values.reduce((lowest, value) => Math.min(lowest, value), Infinity)
  let max = values.reduce((highest, value) => Math.max(highest, value), -Infinity)
  if (min === max) {
    min -= 1
    max += 1
  }
  const width = 760
  const height = 220
  const padding = 24

  return (
    <figure className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <figcaption className="mb-3 font-semibold">{title}</figcaption>
      <svg className="w-full" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}, normalized equity paths`}>
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="currentColor" opacity="0.2" />
        <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="currentColor" opacity="0.1" />
        <path d={buildPath(benchmark, startingCapital, width, height, padding, min, max)} fill="none" stroke="#64748b" strokeWidth="2" />
        <path d={buildPath(strategy, startingCapital, width, height, padding, min, max)} fill="none" stroke="#0f766e" strokeWidth="2.5" />
        <text x={padding} y={padding - 7} fill="currentColor" fontSize="11">{max.toFixed(1)}%</text>
        <text x={padding} y={height - 5} fill="currentColor" fontSize="11">{min.toFixed(1)}%</text>
      </svg>
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-600 dark:text-gray-300">
        <span><span className="mr-1 inline-block h-2 w-3 bg-teal-700" />Strategy</span>
        <span><span className="mr-1 inline-block h-2 w-3 bg-slate-500" />Buy-and-hold baseline</span>
        <span>Normalized to 100 at segment start; net of modeled costs</span>
      </div>
    </figure>
  )
}

function TradeTable({ trades, currencyCode }) {
  if (!trades.length) return <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">No completed trades in this segment.</p>
  const displayed = trades.slice(-20).reverse()

  return (
    <div className="mt-4 overflow-x-auto">
      <p className="mb-2 text-xs text-gray-600 dark:text-gray-400">
        Showing the most recent {displayed.length} of {trades.length} closed trades. Full ledger is in the experiment JSON.
      </p>
      <table className="min-w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-xs uppercase text-gray-600 dark:border-gray-700 dark:text-gray-400">
            <th className="px-2 py-2">Entry</th><th className="px-2 py-2">Exit</th>
            <th className="px-2 py-2 text-right">Qty</th><th className="px-2 py-2 text-right">Net P&amp;L</th>
            <th className="px-2 py-2 text-right">Costs</th><th className="px-2 py-2">Exit reason</th>
          </tr>
        </thead>
        <tbody>
          {displayed.map((trade, index) => (
            <tr key={`${trade.entryDate}-${index}`} className="border-b border-gray-100 dark:border-gray-700">
              <td className="px-2 py-2 tabular-nums">{formatDate(trade.entryDate)}</td>
              <td className="px-2 py-2 tabular-nums">{formatDate(trade.exitDate)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{formatNumber(trade.quantity, 4)}</td>
              <td className={`px-2 py-2 text-right tabular-nums ${trade.netPnl < 0 ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'}`}>{formatAmount(trade.netPnl, currencyCode)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{formatAmount(trade.totalCosts, currencyCode)}</td>
              <td className="px-2 py-2 text-xs">{trade.exitReason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PeriodResults({ title, period, currencyCode }) {
  const metrics = period.strategy.metrics
  const benchmarkMetrics = period.buyAndHold.metrics
  const items = [
    ['Strategy net return', formatPercent(metrics.totalReturn)],
    ['Buy-and-hold net return', formatPercent(benchmarkMetrics.totalReturn)],
    ['CAGR', formatPercent(metrics.cagr)],
    ['Maximum drawdown', formatPercent(metrics.maxDrawdown)],
    ['Annualized volatility', formatPercent(metrics.annualizedVolatility)],
    ['Sharpe (rf = 0)', formatNumber(metrics.sharpe)],
    ['Closed trades / win rate', `${metrics.tradeCount} / ${formatPercent(metrics.winRate)}`],
    ['Net expectancy / trade', formatAmount(metrics.expectancyPerTrade, currencyCode)],
    ['Profit factor (— if no losses)', formatNumber(metrics.profitFactor)],
    ['Average exposure', formatPercent(metrics.averageExposure)],
    ['Modeled transaction costs', formatAmount(metrics.totalCosts, currencyCode)],
    ['Ending equity', formatAmount(metrics.endingEquity, currencyCode)],
  ]

  return (
    <section className="space-y-4 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/60">
      <div>
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">{formatDate(period.startDate)} to {formatDate(period.endDate)} · {period.barCount} daily bars · one-segment capital reset</p>
      </div>
      <EquityChart
        strategy={period.strategy.equityCurve}
        benchmark={period.buyAndHold.equityCurve}
        startingCapital={metrics.startingCapital}
        title="Strategy vs. baseline"
      />
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
        {items.map(([label, value]) => <MetricCard key={label} label={label} value={value} />)}
      </dl>
      {metrics.tradeCount === 0 && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
          No strategy trades completed in this segment. This is not evidence of a profitable or unprofitable edge.
        </p>
      )}
      <details>
        <summary className="cursor-pointer font-medium">Closed trade ledger ({period.strategy.trades.length})</summary>
        <TradeTable trades={period.strategy.trades} currencyCode={currencyCode} />
      </details>
    </section>
  )
}

export default function StrategyValidationPanel() {
  const [form, setForm] = useState(INITIAL_FORM)
  const [bars, setBars] = useState(null)
  const [source, setSource] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  function updateField(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setResult(null)
  }

  async function handleFileChange(event) {
    const input = event.currentTarget
    const file = input.files?.[0]
    input.value = ''
    if (!file) return

    setError('')
    setResult(null)
    setSource(null)
    setBars(null)
    if (file.size > 20 * 1024 * 1024) {
      setError('CSV exceeds the 20 MB prototype limit. Use a smaller daily-bar file.')
      return
    }

    setWorking(true)
    try {
      const text = await file.text()
      const parsed = parseOhlcvCsv(text)
      const sha256 = await sha256Hex(text)
      setBars(parsed)
      setSource({
        fileName: file.name,
        sha256,
        byteLength: file.size,
        barCount: parsed.length,
        firstDate: parsed[0].date,
        lastDate: parsed.at(-1).date,
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not read this CSV file.')
    } finally {
      setWorking(false)
    }
  }

  async function runExperiment() {
    setError('')
    setResult(null)
    if (!bars || !source) {
      setError('Upload and validate a historical daily-bar CSV first.')
      return
    }
    if (costFields.some((key) => form[key].trim() === '')) {
      setError('Enter an explicit commission, half-spread, and slippage assumption per side. Zero is allowed only when appropriate for your instrument and venue.')
      return
    }

    setWorking(true)
    try {
      const configuration = {
        fastPeriod: Number(form.fastPeriod),
        slowPeriod: Number(form.slowPeriod),
        startingCapital: Number(form.startingCapital),
        currencyCode: form.currencyCode.trim().toUpperCase(),
        allocationPct: Number(form.allocationPct),
        commissionBps: Number(form.commissionBps),
        halfSpreadBps: Number(form.halfSpreadBps),
        slippageBps: Number(form.slippageBps),
      }
      const output = runValidation(bars, configuration)
      const identity = JSON.stringify(experimentIdentityPayload(output, source.sha256))
      const experimentId = await sha256Hex(identity)
      setResult({
        ...output,
        experimentId,
        createdAt: new Date().toISOString(),
        source: {
          fileName: source.fileName,
          sha256: source.sha256,
          byteLength: source.byteLength,
        },
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The experiment could not be completed.')
    } finally {
      setWorking(false)
    }
  }

  function downloadRecord() {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `sentinel-experiment-${result.experimentId.slice(0, 16)}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const costsEntered = costFields.every((key) => form[key].trim() !== '')

  return (
    <main className="mx-auto min-h-screen max-w-7xl space-y-6 px-4 py-6 text-gray-900 dark:text-gray-100 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">Sentinel · Research prototype</p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Strategy Validation Engine</h1>
        </div>
        <Link href="/" className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800">
          Back to dashboard
        </Link>
      </header>

      <section className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100" role="note">
        <h2 className="font-semibold">Research only — no broker, paper-trading, or live-order connection</h2>
        <p className="mt-1">This prototype runs only on the historical CSV you select. The file is processed in your browser and is not uploaded. Results do not establish profitability, do not meet a live-trading validation gate, and must not be used as an instruction to trade.</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <section className="space-y-5 rounded-xl border border-gray-200 bg-white p-5 shadow-xs dark:border-gray-700 dark:bg-gray-800">
          <div>
            <h2 className="text-lg font-semibold">1. Historical data</h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Upload one daily bar per UTC date. Required columns: <code>date, open, high, low, close</code>; <code>volume</code> is optional. Dates must use YYYY-MM-DD or ISO UTC timestamps ending in Z, and bars must be ascending.</p>
          </div>
          <label className="block rounded-lg border-2 border-dashed border-gray-300 p-4 text-sm hover:border-teal-600 dark:border-gray-600">
            <span className="mb-2 block font-medium">Choose historical CSV (max 20 MB)</span>
            <input type="file" accept=".csv,text/csv" onChange={handleFileChange} className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-gray-100 file:px-3 file:py-2 file:font-medium hover:file:bg-gray-200 dark:file:bg-gray-700 dark:hover:file:bg-gray-600" />
          </label>
          {working && <p className="text-sm text-teal-800 dark:text-teal-200" aria-live="polite">Validating data / running experiment…</p>}
          {source && bars && (
            <div className="rounded-lg border border-green-300 bg-green-50 p-3 text-sm text-green-950 dark:border-green-800 dark:bg-green-950/30 dark:text-green-100">
              <p className="font-semibold">CSV format checks passed</p>
              <p className="mt-1 break-all">{source.fileName} · {source.barCount.toLocaleString()} bars · {formatDate(source.firstDate)} to {formatDate(source.lastDate)}</p>
              <p className="mt-1 break-all text-xs">Source SHA-256: {source.sha256}</p>
            </div>
          )}

          <div>
            <h2 className="text-lg font-semibold">2. Explicit strategy &amp; assumptions</h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Signals use completed daily closes; normal entries and exits fill at the next daily open. Any position still open at a segment boundary is instead estimated-liquidated at that segment’s final close with modeled costs.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Fast SMA (bars)" name="fastPeriod" type="number" min="2" step="1" value={form.fastPeriod} onChange={updateField} />
            <Field label="Slow SMA (bars)" name="slowPeriod" type="number" min="3" step="1" value={form.slowPeriod} onChange={updateField} />
            <Field label="Starting capital" name="startingCapital" type="number" min="0.01" step="any" value={form.startingCapital} onChange={updateField} />
            <Field label="Currency code" name="currencyCode" type="text" maxLength="3" value={form.currencyCode} onChange={updateField} hint="Three-letter code; must match your price data." />
            <Field label="Capital allocated per entry (%)" name="allocationPct" type="number" min="0.01" max="100" step="any" value={form.allocationPct} onChange={updateField} hint="Long-only, cash-funded, one position at a time; no leverage." />
            <Field label="Commission (bps per side)" name="commissionBps" type="number" min="0" step="any" value={form.commissionBps} onChange={updateField} hint="Required; use your venue’s estimate." />
            <Field label="Half-spread (bps per side)" name="halfSpreadBps" type="number" min="0" step="any" value={form.halfSpreadBps} onChange={updateField} hint="Required; charged adversely on entry and exit." />
            <Field label="Slippage (bps per side)" name="slippageBps" type="number" min="0" step="any" value={form.slippageBps} onChange={updateField} hint="Required; no market-impact model is included." />
          </div>
          <div className="rounded-lg bg-gray-100 p-3 text-sm dark:bg-gray-900">
            <p><strong>Entry:</strong> fast SMA crosses above slow SMA at close; buy next bar open.</p>
            <p className="mt-1"><strong>Exit:</strong> fast SMA crosses below slow SMA at close; sell next bar open. An open terminal position is estimated-liquidated at the segment’s final close, not at a next open.</p>
            <p className="mt-1"><strong>Holdout:</strong> chronological first 70% in-sample / final 30% out-of-sample; positions reset flat at the boundary.</p>
            <p className="mt-1"><strong>Costs:</strong> adverse half-spread + slippage in fill price and commission on filled notional, each side.</p>
          </div>
          <button
            type="button"
            onClick={runExperiment}
            disabled={!bars || !costsEntered || working}
            className="w-full rounded-md bg-teal-700 px-4 py-3 font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {working ? 'Working…' : 'Run historical validation'}
          </button>
          <p className="text-xs text-gray-600 dark:text-gray-400">The fee inputs are blank by design: supply explicit assumptions for your instrument and venue. Zero is allowed but may make results unrealistically optimistic.</p>
        </section>

        <section className="space-y-5">
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
            <h2 className="font-semibold">Limitations to keep in view</h2>
            <p className="mt-1">This is a one-instrument, equity-style daily-bar SMA example—not a selected or approved trading strategy. It assumes 252 sessions per year and is not directly suitable for 24/7 assets. The data is user-supplied and not independently sourced, adjusted, or checked for survivorship bias. Taxes, dividends, corporate actions, market impact, funding/borrow costs, halts, partial fills, regime analysis, statistical significance, and multiple-testing correction are not implemented.</p>
            <p className="mt-2 font-medium">Freeze strategy choices before reviewing the holdout. Tuning after seeing out-of-sample results invalidates that holdout; this prototype does not correct for repeated trials.</p>
          </div>

          {error && <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100" role="alert">{error}</div>}

          {!result && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 text-sm text-gray-600 shadow-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">Experiment results appear here</h2>
              <p className="mt-2">No sample or synthetic performance results are preloaded. Upload your own validated daily bars and enter the transaction-cost assumptions to run the fixed chronological split.</p>
            </div>
          )}

          {result && (
            <div className="space-y-5" aria-live="polite">
              <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-xs dark:border-gray-700 dark:bg-gray-800">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-teal-700 dark:text-teal-300">Experiment record · engine {ENGINE_VERSION}</p>
                    <h2 className="mt-1 text-lg font-semibold">{result.strategy.name}</h2>
                    <p className="mt-1 break-all text-xs text-gray-600 dark:text-gray-400">ID: {result.experimentId}</p>
                    <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">Created {new Date(result.createdAt).toLocaleString()} · input {result.dataset.barCount.toLocaleString()} daily bars</p>
                  </div>
                  <button type="button" onClick={downloadRecord} className="rounded-md bg-gray-900 px-3 py-2 text-sm font-semibold text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white">Download JSON record</button>
                </div>
                <p className="mt-3 text-xs text-gray-600 dark:text-gray-400">The record includes the exact source-file SHA-256, configuration, assumptions, metrics, equity curves, and full trade ledgers. Keep the original CSV; the file itself is not embedded in the JSON.</p>
              </section>
              <PeriodResults title="Out-of-sample holdout · final 30%" period={result.outOfSample} currencyCode={result.configuration.currencyCode} />
              <PeriodResults title="In-sample reference · first 70%" period={result.inSample} currencyCode={result.configuration.currencyCode} />
              <details className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                <summary className="cursor-pointer font-semibold">Experiment assumptions and recorded parameters</summary>
                <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-gray-100 p-3 text-xs dark:bg-gray-900">{JSON.stringify({ strategy: result.strategy, configuration: result.configuration, split: result.split, assumptions: result.assumptions, caveats: result.caveats }, null, 2)}</pre>
              </details>
              <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100">No pass/fail threshold is configured. These descriptive backtest metrics are not a validated edge and do not authorize paper trading or live trading.</p>
            </div>
          )}
        </section>
      </div>
      <footer className="border-t border-gray-200 pt-4 text-xs text-gray-600 dark:border-gray-700 dark:text-gray-400">
        Prototype {ENGINE_VERSION} · browser-only CSV analysis · no external data connection · no order-routing code · fixed 70/30 holdout.
      </footer>
    </main>
  )
}
