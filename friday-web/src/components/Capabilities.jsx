import { motion } from 'framer-motion'
import { Github } from 'lucide-react'

import FeatureCard from './FeatureCard'
import EngineLink from './EngineLink'
import { FEATURES } from '../lib/tokens'

export default function Capabilities() {
  return (
    <section id="capabilities" className="relative z-10 px-5 py-28 sm:px-8 sm:py-36">
      <div className="mx-auto max-w-6xl">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-2xl text-center"
        >
          <span className="mb-5 inline-block rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1 font-mono text-[11px] uppercase tracking-[0.2em] text-cyan">
            Capabilities
          </span>
          <h2 className="text-balance text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl">
            <span className="text-white">Built so the answer </span>
            <span className="text-gradient">can be checked.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-lg text-pretty text-base leading-relaxed text-white/50">
            Every claim on this page is enforced somewhere in the engine, not
            asserted in a slide.
          </p>
        </motion.div>

        <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <FeatureCard key={f.title} index={i} {...f} />
          ))}
        </div>

        {/* Climax CTA — the final beat of the Scroll-Triggered Storytelling
            pattern, after the chapters have earned it. */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
          className="glass-solid relative mt-20 overflow-hidden rounded-[2rem] px-8 py-16 text-center sm:px-14"
        >
          {/* Aurora wash. Transform-only animation, compositor-driven. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -inset-40 animate-drift opacity-45"
            style={{
              background:
                'radial-gradient(closest-side, rgba(124,58,237,0.35), transparent 72%)',
            }}
          />

          <div className="relative">
            <h3 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-5xl">
              The engine is real, and it is running.
            </h3>
            <p className="mx-auto mt-5 max-w-xl text-pretty text-base leading-relaxed text-white/55">
              Five verification suites, ten out of ten prototype requirements,
              and a decision record you can download for any answer it gives.
            </p>

            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <EngineLink />

              <motion.a
                href="#top"
                whileHover={{ scale: 1.045 }}
                whileTap={{ scale: 0.97 }}
                transition={{ type: 'spring', stiffness: 380, damping: 17 }}
                className="glass inline-flex min-h-[48px] items-center gap-2 rounded-2xl px-7 text-sm font-medium text-white/85 transition-colors hover:text-white"
              >
                <Github className="h-4 w-4" aria-hidden="true" />
                Back to top
              </motion.a>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
