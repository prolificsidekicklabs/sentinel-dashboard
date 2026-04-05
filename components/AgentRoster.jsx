"use client"

import { motion } from 'framer-motion'

const AgentCard = ({ agent }) => {
  const getColor = (opinion) => {
    switch (opinion) {
      case 'GREEN': return 'bg-green-500'
      case 'YELLOW': return 'bg-yellow-500'
      case 'RED': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <motion.div
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className={`agent-card ${getColor(agent.opinion)} p-4 rounded-lg shadow-md`}
    >
      <div className="flex items-center space-x-3">
        <div className="w-12 h-12 rounded-full bg-white flex items-center justify-center font-bold">
          {agent.agent_name}
        </div>
        <div className="flex-1">
          <div className="font-semibold">{agent.agent_name}</div>
          <div className="text-sm">Confidence: {(agent.confidence * 100).toFixed(0)}%</div>
        </div>
      </div>
      <div className="mt-2 text-sm">
        <div className="font-medium">{agent.opinion}</div>
        <div className="text-gray-700 dark:text-gray-300">{agent.rationale}</div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {agent.data_used.map((data, index) => (
          <span key={index} className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded text-xs">
            {data}
          </span>
        ))}
      </div>
    </motion.div>
  )
}

export default function AgentRoster({ agents }) {
  return (
    <div className="agent-roster grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
      <h2 className="col-span-full text-xl font-bold mb-4">Analytical Agents</h2>
      {agents.map((agent, index) => (
        <AgentCard key={index} agent={agent} />
      ))}
    </div>
  )
}