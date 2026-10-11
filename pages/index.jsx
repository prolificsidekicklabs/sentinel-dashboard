"use client"

import { useState, useEffect } from 'react'
import Head from 'next/head'
import AgentRoster from '../components/AgentRoster'
import PriceChart from '../components/PriceChart'
import DiscourseTimeline from '../components/DiscourseTimeline'
import FocusMode from '../components/FocusMode'
import CommandWheel from '../components/CommandWheel'
import RiskGlow from '../components/RiskGlow'
import EventRail from '../components/EventRail'
import { motion } from 'framer-motion'
import {
  DEMO_AGENT_OPINIONS,
  DEMO_DISCOURSE_LOG,
  DEMO_MARKET_STATE,
} from '../lib/demo-data'

export default function Home() {
  const [focusMode, setFocusMode] = useState(false)
  const [commandWheelOpen, setCommandWheelOpen] = useState(false)
  const [riskLevel, setRiskLevel] = useState("AMBER")
  const [activeAgent, setActiveAgent] = useState(null)
  const [marketData, setMarketData] = useState(null)
  const [sentinelResult, setSentinelResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Simulate loading
  useEffect(() => {
    const timer = setTimeout(() => {
      setMarketData(DEMO_MARKET_STATE)
      setSentinelResult({
        agent_opinions: DEMO_AGENT_OPINIONS,
        discourse_log: DEMO_DISCOURSE_LOG,
        decision: "BLOCK"
      })
      setLoading(false)
    }, 1000)
    return () => clearTimeout(timer)
  }, [])

  if (loading) return <div className="p-8 text-center">Loading Sentinel Dashboard...</div>
  if (error) return <div className="p-8 text-red-500 text-center">Error: {error}</div>

  return (
    <>
      <Head>
        <title>Sentinel Dashboard</title>
        <meta name="description" content="Sentinel Trading Intelligence" />
      </Head>

      <div className="dashboard-container min-h-screen p-4 bg-gray-50 dark:bg-gray-900">
        <RiskGlow riskLevel={riskLevel} />

        <div role="status" className="mb-4 rounded border border-amber-400 bg-amber-50 px-4 py-2 text-sm text-amber-950 dark:bg-amber-950 dark:text-amber-100">
          Demo mode: synthetic fixed sample data only. This is not live market data or a trading signal.
        </div>

        <div className="main-content grid grid-cols-1 lg:grid-cols-3 gap-4 mb-16">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="price-chart-section lg:col-span-3"
          >
            <PriceChart data={marketData} />
          </motion.div>

          <motion.div
            initial={{ x: -50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className="agent-roster-section lg:col-span-3"
          >
            <AgentRoster agents={sentinelResult.agent_opinions} />
          </motion.div>

          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="discourse-section lg:col-span-3"
          >
            <DiscourseTimeline log={sentinelResult.discourse_log} />
          </motion.div>
        </div>

        <div className="event-rail fixed bottom-0 left-0 right-0">
          <EventRail events={sentinelResult.discourse_log} />
        </div>

        {focusMode && (
          <FocusMode
            data={{ marketState: marketData, agents: sentinelResult.agent_opinions }}
            onClose={() => setFocusMode(false)}
          />
        )}

        {commandWheelOpen && (
          <CommandWheel onClose={() => setCommandWheelOpen(false)} />
        )}

        <button
          onClick={() => setFocusMode(!focusMode)}
          className="focus-toggle fixed bottom-4 right-20 px-4 py-2 bg-gray-800 text-white rounded-full shadow-lg hover:bg-gray-700 transition"
        >
          {focusMode ? 'Exit Focus' : 'Focus Mode'}
        </button>

        <button
          onClick={() => setCommandWheelOpen(true)}
          className="command-wheel-toggle fixed bottom-4 right-4 px-4 py-2 bg-gray-800 text-white rounded-full shadow-lg hover:bg-gray-700 transition"
        >
          Commands
        </button>
      </div>
    </>
  )
}
