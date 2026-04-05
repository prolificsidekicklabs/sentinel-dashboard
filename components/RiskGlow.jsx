"use client"

import { motion } from 'framer-motion'

export default function RiskGlow({ riskLevel }) {
  const getGlowColor = () => {
    switch (riskLevel) {
      case 'GREEN': return 'rgba(74, 222, 128, 0.3)'
      case 'AMBER': return 'rgba(251, 191, 36, 0.3)'
      case 'RED': return 'rgba(248, 113, 113, 0.5)'
      default: return 'rgba(148, 163, 184, 0.2)'
    }
  }

  const pulseAnimation = {
    initial: { boxShadow: `0 0 0 0 ${getGlowColor()}` },
    animate: {
      boxShadow: `0 0 30px 10px ${getGlowColor()}`,
      transition: { duration: 1.5, repeat: Infinity, repeatType: "reverse" }
    }
  }

  return (
    <motion.div
      {...pulseAnimation}
      className="fixed inset-0 pointer-events-none -z-10"
      style={{ borderRadius: 'inherit' }}
    />
  )
}