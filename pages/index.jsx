'use client'

import { useCallback, useEffect, useState } from 'react'
import Head from 'next/head'
import Link from 'next/link'
import { motion } from 'framer-motion'
import AgentRoster from '../components/AgentRoster'
import CommandWheel from '../components/CommandWheel'
import DemoModeBanner from '../components/DemoModeBanner'
import DiscourseTimeline from '../components/DiscourseTimeline'
import EventRail from '../components/EventRail'
import FocusMode from '../components/FocusMode'
import PaperAccountPanel from '../components/PaperAccountPanel'
import PriceChart from '../components/PriceChart'
import ResearchCandidatePanel from '../components/ResearchCandidatePanel'
import RiskGlow from '../components/RiskGlow'
import { DEMO_AGENT_OPINIONS, DEMO_DISCOURSE_LOG, DEMO_MARKET_STATE } from '../lib/demo-data'
import { parsePaperDashboard, toMarketChartData } from '../lib/paper-dashboard'

const DEMO_RESULT = {
  agent_opinions: DEMO_AGENT_OPINIONS,
  discourse_log: DEMO_DISCOURSE_LOG,
  decision: 'BLOCK',
}

function getConnectionMessage(status) {
  if (status === 401) return 'The local API key is missing or mismatched. Keep the same strong SENTINEL_API_KEY in the Next.js and FastAPI server environments.'
  if (status === 502) return 'The paper-data provider could not return a valid response. Check Alpaca paper credentials and market-data feed access.'
  if (status === 503) return 'The local paper API is not configured yet. Add a strong server-only API key and Alpaca paper credentials; the fixed demo remains visible.'
  if (status === 404) return 'The paper-data bridge is available only in local development. This production build remains in demo mode.'
  return 'Could not load read-only paper data. The fixed synthetic demo remains visible.'
}

export default function Home() {
  const [focusMode, setFocusMode] = useState(false)
  const [commandWheelOpen, setCommandWheelOpen] = useState(false)
  const [commandStatus, setCommandStatus] = useState('')
  const [paperSnapshot, setPaperSnapshot] = useState(null)
  const [paperStatus, setPaperStatus] = useState('Checking the local read-only paper API…')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const riskLevel = 'AMBER'

  const refreshPaperData = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const response = await fetch('/api/sentinel/dashboard?symbol=SPY&days=30', {
        method: 'GET',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(30_000),
      })
      if (!response.ok) {
        setPaperSnapshot(null)
        setPaperStatus(getConnectionMessage(response.status))
        return
      }
      const snapshot = parsePaperDashboard(await response.json())
      setPaperSnapshot(snapshot)
      setPaperStatus('Paper account data loaded. This view is read-only; order execution is not available.')
    } catch {
      setPaperSnapshot(null)
      setPaperStatus('The local paper-data service is unavailable or returned invalid data. The fixed synthetic demo remains visible.')
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshPaperData()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [refreshPaperData])

  const connectedToPaper = paperSnapshot !== null
  const marketData = connectedToPaper ? toMarketChartData(paperSnapshot) : DEMO_MARKET_STATE
  const sentinelResult = DEMO_RESULT

  return (
    <>
      <Head>
        <title>Sentinel Dashboard</title>
        <meta name="description" content="Sentinel local paper-data dashboard and clearly labeled synthetic demo." />
      </Head>

      <main className="dashboard-container min-h-screen bg-gray-50 p-4 dark:bg-gray-900">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold">Sentinel Console</h1>
          <div className="flex flex-wrap gap-2">
            <Link href="/strategy-validation" className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800">
              Strategy Validation Prototype
            </Link>
            <button
              type="button"
              onClick={() => void refreshPaperData()}
              disabled={isRefreshing}
              className="rounded-md bg-blue-800 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-900 disabled:cursor-wait disabled:opacity-60"
            >
              {isRefreshing ? 'Refreshing…' : 'Refresh paper data'}
            </button>
            {connectedToPaper && (
              <button
                type="button"
                onClick={() => {
                  setPaperSnapshot(null)
                  setPaperStatus('Disconnected locally. The fixed synthetic demo is displayed.')
                }}
                className="rounded-md border border-gray-500 px-4 py-2 text-sm font-semibold"
              >
                Show demo
              </button>
            )}
          </div>
        </div>

        <div role="status" aria-live="polite" className="mb-4 rounded-md border border-gray-300 bg-white p-3 text-sm dark:border-gray-700 dark:bg-gray-800">
          {paperStatus}
        </div>

        {connectedToPaper ? (
          <aside role="note" className="mb-4 rounded-lg border border-blue-400 bg-blue-50 p-4 text-blue-950 dark:border-blue-700 dark:bg-blue-950/40 dark:text-blue-100">
            <h2 className="font-bold uppercase tracking-wide">Alpaca paper account · read-only</h2>
            <p className="mt-1 text-sm">
              The account and positions are read from Alpaca&apos;s paper environment. Historical bars use the configured market-data feed. Sentinel exposes no order, cancel, or liquidation operation. The agent opinions, discourse, risk glow, and illustrative BLOCK verdict below remain fixed synthetic examples and are not computed from this account or feed.
            </p>
          </aside>
        ) : (
          <DemoModeBanner />
        )}

        {!connectedToPaper && <RiskGlow riskLevel={riskLevel} />}
        {commandStatus && (
          <div role="status" aria-live="polite" className="mb-4 flex items-start justify-between gap-4 rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-950 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100">
            <p>{commandStatus}</p>
            <button type="button" className="shrink-0 font-semibold underline" onClick={() => setCommandStatus('')}>Dismiss</button>
          </div>
        )}

        <div className="main-content mb-16 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="price-chart-section lg:col-span-3">
            <PriceChart data={marketData} />
          </motion.div>

          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="lg:col-span-3">
            <ResearchCandidatePanel />
          </motion.div>

          {connectedToPaper && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="lg:col-span-3">
              <PaperAccountPanel snapshot={paperSnapshot} />
            </motion.div>
          )}

          <motion.div initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="agent-roster-section lg:col-span-3">
            <AgentRoster agents={sentinelResult.agent_opinions} />
            {connectedToPaper && <p className="mt-2 text-sm text-amber-800 dark:text-amber-200">These opinions are simulated demo content and are not based on the paper account or market data.</p>}
          </motion.div>

          <motion.div initial={{ y: 50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} id="agent-discourse" className="discourse-section scroll-mt-4 lg:col-span-3">
            <DiscourseTimeline log={sentinelResult.discourse_log} />
          </motion.div>
        </div>

        {!connectedToPaper && <div className="event-rail fixed bottom-0 left-0 right-0"><EventRail events={sentinelResult.discourse_log} /></div>}

        {focusMode && !connectedToPaper && (
          <FocusMode
            data={{ marketState: marketData, agents: sentinelResult.agent_opinions }}
            onClose={() => setFocusMode(false)}
          />
        )}

        {commandWheelOpen && (
          <CommandWheel
            onClose={() => setCommandWheelOpen(false)}
            onStatusMessage={setCommandStatus}
          />
        )}

        {!connectedToPaper && (
          <button type="button" onClick={() => setFocusMode(!focusMode)} className="focus-toggle fixed bottom-4 right-20 rounded-full bg-gray-800 px-4 py-2 text-white shadow-lg transition hover:bg-gray-700">
            {focusMode ? 'Exit Focus' : 'Focus Mode'}
          </button>
        )}

        <button type="button" onClick={() => setCommandWheelOpen(true)} className="command-wheel-toggle fixed bottom-4 right-4 rounded-full bg-gray-800 px-4 py-2 text-white shadow-lg transition hover:bg-gray-700">
          Commands
        </button>
      </main>
    </>
  )
}
