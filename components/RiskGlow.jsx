"use client"

import { motion } from 'framer-motion'

export default function RiskGlow({ riskLevel }) {
  const glowColor =
    {
      GREEN: 'rgba(74, 222, 128, 0.3)',
      AMBER: 'rgba(251, 191, 36, 0.3)',
      RED: 'rgba(248, 113, 113, 0.5)',
    }[riskLevel] ?? 'rgba(148, 163, 184, 0.2)'

  return (
    <motion.div
      initial={{ boxShadow: `0 0 0 0 ${glowColor}` }}
      animate={{
        boxShadow: `0 0 30px 10px ${glowColor}`,
        transition: { duration: 1.5, repeat: Infinity, repeatType: 'reverse' },
      }}
      className="pointer-events-none fixed inset-0 -z-10"
      style={{ borderRadius: 'inherit' }}
    />
  )
}
