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

export default function Home() {
  const [focusMode, setFocusMode] = useState(false)
  const [commandWheelOpen, setCommandWheelOpen] = useState(false)
  const [riskLevel, setRiskLevel] = useState("AMBER")
  const [activeAgent, setActiveAgent] = useState(null)
  const [marketData, setMarketData] = useState(null)
  const [sentinelResult, setSentinelResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Mock data for demo
  const mockMarketState = {
    timestamp: new Date().toISOString(),
    instrument: "SPY",
    price: 450.0 + Math.random() * 10 - 5,
    regime: Math.random() > 0.7 ? "high_volatility" : Math.random() > 0.5 ? "trending" : "mean_reverting",
    indicators: {
      rsi: 50 + Math.random() * 40,
      macd: { line: Math.random() * 2 - 1, signal: Math.random() * 2 - 1, histogram: Math.random() * 0.5 - 0.25 },
      bollinger_bands: { upper: 460 + Math.random() * 5, middle: 450 + Math.random() * 5, lower: 440 + Math.random() * 5 }
    },
    order_book: { bid_vol: 1000 + Math.floor(Math.random() * 500), ask_vol: 1000 + Math.floor(Math.random() * 500), spread: 0.1 + Math.random() * 0.8 },
    sentiment: { bullish: Math.random(), bearish: Math.random() },
    fundamentals: { pe_ratio: 15 + Math.random() * 10, earnings_date: "2026-04-15" }
  }

  const mockAgentOpinions = [
    { agent_name: "TECH", opinion: "RED", confidence: 0.9, rationale: "RSI indicates overbought conditions.", data_used: ["indicators.rsi", "indicators.macd"] },
    { agent_name: "MACRO", opinion: "GREEN", confidence: 0.8, rationale: "Fed policy remains accommodative.", data_used: ["fundamentals.pe_ratio"] },
    { agent_name: "MICRO", opinion: "RED", confidence: 0.85, rationale: "Low liquidity detected.", data_used: ["order_book.spread"] },
    { agent_name: "SENT", opinion: "GREEN", confidence: 0.75, rationale: "Bullish sentiment.", data_used: ["sentiment.bullish"] },
    { agent_name: "FUND", opinion: "GREEN", confidence: 0.9, rationale: "Fair valuation.", data_used: ["fundamentals.pe_ratio"] }
  ]

  const mockDiscourseLog = [
    { type: "OPINION", agent: "TECH", opinion: "RED", timestamp: new Date().toISOString() },
    { type: "CHALLENGE", agent: "MACRO", target: "TECH", message: "Fed data contradicts RSI.", timestamp: new Date().toISOString() },
    { type: "AGREE", agent: "FUND", target: "TECH", message: "P/E supports bearish stance.", timestamp: new Date().toISOString() },
    { type: "DECISION", verdict: "BLOCK", critic_notes: "Consensus for RED.", timestamp: new Date().toISOString() }
  ]

  // Simulate loading
  useEffect(() => {
    const timer = setTimeout(() => {
      setMarketData(mockMarketState)
      setSentinelResult({
        agent_opinions: mockAgentOpinions,
        discourse_log: mockDiscourseLog,
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