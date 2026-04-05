"use client"

import { motion } from 'framer-motion'

export default function EventRail({ events }) {
  return (
    <div className="event-rail fixed bottom-0 left-0 right-0 bg-gray-900 bg-opacity-80 p-2 overflow-x-auto z-20">
      <div className="flex space-x-2">
        {events.map((event, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className={`px-3 py-1 rounded-full text-xs flex-shrink-0 $
              ${event.type === 'OPINION' ? 'bg-blue-500' :
               event.type === 'CHALLENGE' ? 'bg-yellow-500' :
               event.type === 'AGREE' ? 'bg-green-500' :
               event.type === 'DECISION' ? 'bg-purple-500' : 'bg-gray-500'}`}
          >
            <span className="font-semibold">{event.type}</span>
            {event.agent && <span className="ml-1">{event.agent}</span>}
            <span className="ml-1 text-gray-200">
              {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}