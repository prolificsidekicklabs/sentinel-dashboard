"use client"

import { motion } from 'framer-motion'

const ProbabilityStack = ({ factors }) => (
  <div className="probability-stack space-y-1 mt-2">
    {factors.map((factor, index) => (
      <div key={index} className="flex items-center text-xs">
        <div className="w-20 truncate">{factor.data}</div>
        <div className="flex-1 mx-2">
          <div className="h-2 bg-gray-200 rounded-full">
            <div
              className={`h-full rounded-full ${factor.impact > 0 ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ width: `${Math.abs(factor.impact) * 100}%` }}
            />
          </div>
        </div>
        <div className="w-12 text-right">{factor.impact > 0 ? '+' : ''}{(factor.impact * 100).toFixed(0)}%</div>
      </div>
    ))}
  </div>
)

export default function FocusMode({ data, onClose }) {
  const activeAgent = data.agents[0]

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="focus-overlay fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center p-4 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4">Focus Mode: {activeAgent.agent_name}</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold mb-2">Market State</h3>
            <pre className="bg-gray-100 dark:bg-gray-700 p-3 rounded text-sm overflow-x-auto">
              {JSON.stringify(data.marketState, null, 2)}
            </pre>
          </div>

          <div>
            <h3 className="font-semibold mb-2">Agent Opinion</h3>
            <div className="space-y-2">
              <div>
                <span className="font-medium">Opinion:</span>
                <span className={`ml-2 px-2 py-1 rounded text-xs $
                  ${activeAgent.opinion === 'GREEN' ? 'bg-green-100 text-green-800' :
                   activeAgent.opinion === 'RED' ? 'bg-red-100 text-red-800' :
                   'bg-yellow-100 text-yellow-800'}`}>
                  {activeAgent.opinion}
                </span>
              </div>
              <div>
                <span className="font-medium">Confidence:</span>
                <span className="ml-2">{(activeAgent.confidence * 100).toFixed(0)}%</span>
              </div>
              <div>
                <span className="font-medium">Rationale:</span>
                <span className="ml-2">{activeAgent.rationale}</span>
              </div>
            </div>

            <h4 className="font-semibold mt-4 mb-2">Confidence Breakdown</h4>
            <ProbabilityStack factors={[
              { data: "RSI", impact: 0.35 },
              { data: "MACD", impact: 0.25 },
              { data: "Volume", impact: 0.15 },
              { data: "Regime", impact: -0.10 }
            ]} />
          </div>
        </div>

        <div className="mt-6 flex space-x-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition"
          >
            Exit Focus Mode
          </button>
        </div>
      </div>
    </motion.div>
  )
}