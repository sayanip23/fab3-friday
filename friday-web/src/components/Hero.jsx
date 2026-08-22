import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { ArrowDown, Zap } from 'lucide-react'

import { MOTION } from '../lib/tokens'

/**
 * Hero overlay.
 *
 * Framer Motion handles the entrance and the scroll fade here rather than
 * GSAP, because this is a simple single-element mapping and useScroll gives
 * it to us without registering another ScrollTrigger. GSAP takes over in
 * OverlayUI where sections need pinning and scrubbing.
 */

// Word-level stagger. `once: true` matters — replaying the entrance every
// time the hero scrolls back into view is the kind of animation that feels
// clever twice and irritating thereafter.
const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.075, delayChildren: 0.35 } },
}

const word = {
  hidden: { y: '110%', opacity: 0 },
  show: {
    y: '0%',
    opacity: 1,
    transition: { duration: 0.9, ease: [0.22, 1, 0.36, 1] },
  },
}

function Headline({ text, className }) {
  return (
    <motion.span variants={container} initial="hidden" animate="show" className={className}>
      {text.split(' ').map((w, i) => (
        // Each word gets a clipping wrapper so it rises out of an invisible
        // mask instead of sliding in from empty space.
        <span key={`${w}-${i}`} className="inline-block overflow-hidden pb-[0.12em] align-bottom">
          <motion.span variants={word} className="inline-block">
            {w}&nbsp;
          </motion.span>
        </span>
      ))}
    </motion.span>
  )
}

export default function Hero() {
  const ref = useRef(null)

  // Fade and lift the hero as it leaves. offset maps "section top at viewport
  // top" -> "section bottom at viewport top" onto 0 -> 1.
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const opacity = useTransform(scrollYProgress, [0, 0.65], [1, 0])
  const y = useTransform(scrollYProgress, [0, 1], [0, -120])
  const blur = useTransform(scrollYProgress, [0, 0.7], ['blur(0px)', 'blur(6px)'])

  return (
    <section
      id="top"
      ref={ref}
      className="relative flex min-h-[100svh] items-center justify-center px-5 sm:px-8"
    >
      <motion.div style={{ opacity, y, filter: blur }} className="mx-auto max-w-4xl text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: MOTION.base, delay: 0.2 }}
          className="glass mx-auto mb-7 inline-flex items-center gap-2 rounded-full px-4 py-1.5"
        >
          <Zap className="h-3.5 w-3.5 text-cyan" aria-hidden="true" />
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/65">
            Accenture Innovation Challenge 2026
          </span>
        </motion.div>

        <h1 className="text-balance text-5xl font-extrabold leading-[0.95] tracking-tight sm:text-7xl lg:text-8xl">
          <Headline text="Dashboards say what." className="block text-white" />
          <Headline text="FRIDAY says why." className="block text-gradient" />
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: MOTION.slow, delay: 0.95, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mt-7 max-w-xl text-pretty text-base leading-relaxed text-white/55 sm:text-lg"
        >
          A KPI intelligence engine that finds the cause of a business movement,
          proves every link with evidence, and refuses to guess when it cannot.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: MOTION.slow, delay: 1.15, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <motion.a
            href="#problem"
            whileHover={{ scale: 1.045 }}
            whileTap={{ scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 380, damping: 17 }}
            className="group inline-flex min-h-[48px] items-center gap-2 rounded-2xl bg-violet px-7 text-sm font-semibold text-white neon-violet"
          >
            See how it works
            <ArrowDown className="h-4 w-4 transition-transform duration-300 group-hover:translate-y-0.5" aria-hidden="true" />
          </motion.a>

          <motion.a
            href="#capabilities"
            whileHover={{ scale: 1.045 }}
            whileTap={{ scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 380, damping: 17 }}
            className="glass inline-flex min-h-[48px] items-center rounded-2xl px-7 text-sm font-medium text-white/85 transition-colors hover:text-white"
          >
            Capabilities
          </motion.a>
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.8, duration: 1 }}
        style={{ opacity }}
        className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <div className="flex h-11 w-6 items-start justify-center rounded-full border border-white/15 p-1.5">
          <motion.span
            animate={{ y: [0, 12, 0], opacity: [1, 0.2, 1] }}
            transition={{ duration: 1.9, repeat: Infinity, ease: 'easeInOut' }}
            className="block h-1.5 w-1.5 rounded-full bg-cyan"
          />
        </div>
      </motion.div>
    </section>
  )
}
