"use client"

import { motion } from 'framer-motion'

const commands = [
  { id: 'new-analysis', name: 'New Analysis', icon: '🔍', message: 'Demo only: no analysis was run because this dashboard has no analytical service.' },
  { id: 'view-discourse', name: 'View Discourse', icon: '💬', action: 'view-discourse', message: '' },
  { id: 'cycle-vault', name: 'Cycle Vault', icon: '🗄️', message: 'Demo only: no cycle vault or persistent history is connected.' },
  { id: 'research-mode', name: 'Research Mode', icon: '📚', href: '/strategy-validation', message: '' },
  { id: 'settings', name: 'Settings', icon: '⚙️', message: 'Demo only: no account settings were changed or saved.' },
  { id: 'ask-valentina', name: 'Ask Valentina', icon: '🤖', message: 'Demo only: no AI agent or language-model service is connected; no request was sent.' },
  { id: 'performance', name: 'Performance', icon: '📊', message: 'Demo only: no real portfolio or historical performance data is connected.' },
  { id: 'cost-awareness', name: 'Cost Awareness', icon: '💰', href: '/strategy-validation#cost-assumptions', message: '' },
]

function CommandContents({ command }) {
  return (
    <>
      <span className="mb-1 text-2xl" aria-hidden="true">{command.icon}</span>
      <span className="text-center text-xs">{command.name}</span>
    </>
  )
}

/** @param {{ onClose: () => void, onStatusMessage: (message: string) => void }} props */
export default function CommandWheel({ onClose, onStatusMessage }) {
  function runDemoAction(command) {
    if (command.action === 'view-discourse') {
      onStatusMessage('Showing the simulated demo discussion; it is not a real analysis record.')
      onClose()
      window.requestAnimationFrame(() => {
        document.getElementById('agent-discourse')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
      return
    }

    onStatusMessage(command.message)
    onClose()
  }

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-labelledby="command-wheel-title"
      tabIndex={-1}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="command-wheel fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={(event) => { if (event.target === event.currentTarget) onClose() }}
      onKeyDown={(event) => { if (event.key === 'Escape') onClose() }}
    >
      <div className="relative h-96 w-96 max-w-full">
        <h2 id="command-wheel-title" className="sr-only">Sentinel demo command menu</h2>
        <motion.div
          aria-hidden="true"
          className="absolute inset-0 rounded-full bg-gray-800/95"
          initial={{ rotate: 0 }}
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        />

        {commands.map((command, index) => {
          const angle = (index / commands.length) * 360
          const x = 120 * Math.cos((angle * Math.PI) / 180)
          const y = 120 * Math.sin((angle * Math.PI) / 180)
          const position = {
            left: `calc(50% + ${x}px)`,
            top: `calc(50% + ${y}px)`,
            transform: 'translate(-50%, -50%)',
          }
          const className = 'flex h-24 w-24 flex-col items-center justify-center rounded-full bg-gray-700 text-white hover:bg-gray-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white'

          return (
            <div key={command.id} className="absolute z-10" style={position}>
              {command.href ? (
                <motion.a href={command.href} className={className} whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.96 }}>
                  <CommandContents command={command} />
                </motion.a>
              ) : (
                <motion.button
                  type="button"
                  className={className}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => runDemoAction(command)}
                >
                  <CommandContents command={command} />
                </motion.button>
              )}
            </div>
          )
        })}

        <button
          type="button"
          className="absolute inset-0 z-20 m-auto flex h-32 w-32 items-center justify-center rounded-full bg-blue-600 text-white transition hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          onClick={onClose}
        >
          Close
        </button>
        <p className="absolute -bottom-8 w-full text-center text-xs text-white">
          Demo-only actions. Service connections are not available.
        </p>
      </div>
    </motion.div>
  )
}
