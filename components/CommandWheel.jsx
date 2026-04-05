"use client"

import { motion } from 'framer-motion'

const CommandWheel = ({ onClose }) => {
  const commands = [
    { name: "New Analysis", icon: "🔍" },
    { name: "View Discourse", icon: "💬" },
    { name: "Cycle Vault", icon: "🗄️" },
    { name: "Research Mode", icon: "📚" },
    { name: "Settings", icon: "⚙️" },
    { name: "Ask Valentina", icon: "🤖" },
    { name: "Performance", icon: "📊" },
    { name: "Cost Awareness", icon: "💰" }
  ]

  return (
    <motion.div
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      exit={{ scale: 0 }}
      className="command-wheel fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="relative w-96 h-96">
        <motion.div
          className="absolute inset-0 rounded-full bg-gray-800 bg-opacity-90"
          initial={{ rotate: 0 }}
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />

        {commands.map((command, index) => {
          const angle = (index / commands.length) * 360
          const x = 120 * Math.cos((angle * Math.PI) / 180)
          const y = 120 * Math.sin((angle * Math.PI) / 180)

          return (
            <motion.button
              key={index}
              className="absolute w-24 h-24 flex flex-col items-center justify-center bg-gray-700 rounded-full hover:bg-gray-600 transition"
              style={{ transform: `translate(${x}px, ${y}px)` }}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={(e) => {
                e.stopPropagation()
                alert(`Executing: ${command.name}`)
                onClose()
              }}
            >
              <span className="text-2xl mb-1">{command.icon}</span>
              <span className="text-xs text-center">{command.name}</span>
            </motion.button>
          )
        })}

        <button
          className="absolute inset-0 w-32 h-32 m-auto rounded-full bg-blue-500 text-white flex items-center justify-center hover:bg-blue-600 transition"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </motion.div>
  )
}

export default CommandWheel