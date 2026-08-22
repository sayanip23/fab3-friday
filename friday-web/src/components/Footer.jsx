import { motion } from 'framer-motion'

export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-white/5 px-5 py-12 sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-5 sm:flex-row">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center font-mono text-[11px] uppercase tracking-[0.16em] text-white/35 sm:text-left"
        >
          FRIDAY · Team Fab3 · Accenture Innovation Challenge 2026
        </motion.p>

        <p className="font-mono text-[11px] text-white/25">
          Track 3 — BusinessIntelligence.ai
        </p>
      </div>
    </footer>
  )
}
