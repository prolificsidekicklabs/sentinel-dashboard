"use client"

import { motion } from 'framer-motion'

const DiscourseEvent = ({ event }) => {
  const getColor = (type) => {
    switch (type) {
      case 'OPINION': return 'bg-blue-500'
      case 'CHALLENGE': return 'bg-yellow-500'
      case 'AGREE': return 'bg-green-500'
      case 'DECISION': return 'bg-purple-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`discourse-event ${getColor(event.type)} p-3 rounded-lg mb-2`}
    >
      <div className="flex items-center space-x-2">
        <span className="font-bold">{event.type}</span>
        <span className="text-sm">{new Date(event.timestamp).toLocaleTimeString()}</span>
      </div>
      {event.agent && <div className="text-sm">Agent: {event.agent}</div>}
      {event.target && <div className="text-sm">Target: {event.target}</div>}
      {event.message && <div className="mt-1 text-sm">{event.message}</div>}
      {event.verdict && (
        <div className="mt-1 font-semibold">
          Verdict: {event.verdict}
          {event.critic_notes && <div className="text-xs mt-1">{event.critic_notes}</div>}
        </div>
      )}
    </motion.div>
  )
}

export default function DiscourseTimeline({ log }) {
  return (
    <div className="discourse-timeline p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
      <h2 className="text-xl font-bold mb-4">Agent Discourse</h2>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {log.map((event, index) => (
          <DiscourseEvent key={index} event={event} />
        ))}
      </div>
    </div>
  )
}