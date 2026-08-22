import { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

import { CHAPTERS, MOTION } from '../lib/tokens'
import { useReducedMotion } from '../hooks/useEnvironment'

gsap.registerPlugin(ScrollTrigger)

/**
 * Scroll-driven chapters.
 *
 * ── Why GSAP here and Framer Motion in Hero ──────────────────────────────
 * Framer's useScroll maps one value to one style. That is enough for a hero
 * fade. These chapters need to *pin* — hold the section still while the
 * scroll wheel advances an internal timeline — and pinning requires taking
 * the element out of flow and compensating the scroll height. ScrollTrigger
 * does that properly; hand-rolling it produces layout jumps at the pin
 * boundaries.
 *
 * ── Why gsap.context ─────────────────────────────────────────────────────
 * Every selector inside the context is scoped to the root ref, and a single
 * ctx.revert() on unmount kills the tweens, the ScrollTriggers *and* the
 * pin-spacer divs GSAP injected into the DOM. Without revert, React Strict
 * Mode's double-mount leaves a second set of triggers attached and each
 * chapter animates twice at slightly different offsets.
 */
export default function OverlayUI() {
  const root = useRef(null)
  const reduced = useReducedMotion()

  useLayoutEffect(() => {
    // Reduced motion: render every chapter in its final readable state and
    // register nothing. The narrative has to survive without the effects.
    if (reduced) return

    document.documentElement.classList.add('js-scroll-driven')

    const ctx = gsap.context(() => {
      const chapters = gsap.utils.toArray('[data-chapter]')

      chapters.forEach((section) => {
        const kicker = section.querySelector('[data-kicker]')
        const lines = section.querySelectorAll('[data-line]')
        const bodyEl = section.querySelector('[data-body]')
        const statEl = section.querySelector('[data-stat]')
        const panel = section.querySelector('[data-panel]')

        // ── Entrance: scrubbed against scroll position ──────────────────
        // scrub:1 means "catch up to the scroll position over 1 second".
        // A raw scrub:true tracks the wheel exactly and feels twitchy on a
        // trackpad; the small lag reads as weight.
        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: section,
            start: 'top 78%',
            end: 'top 22%',
            scrub: 1,
          },
        })

        tl.from(kicker, { opacity: 0, x: -28, duration: 0.5 })
          .from(
            lines,
            {
              opacity: 0,
              yPercent: 110,
              duration: 0.9,
              stagger: MOTION.stagger * 2,
              ease: MOTION.ease,
            },
            '<0.1'
          )
          .from(bodyEl, { opacity: 0, y: 34, duration: 0.7 }, '<0.25')
          .from(statEl, { opacity: 0, scale: 0.86, duration: 0.6, ease: 'back.out(1.6)' }, '<0.15')

        // ── No pinning, deliberately ────────────────────────────────────
        // Pinning each chapter (hold the panel still while the wheel advances
        // an internal timeline) is the textbook scroll-storytelling technique,
        // and it was here. It was removed because it does not survive contact
        // with a real user: the page halting for ~half a viewport of scrolling
        // reads as the site freezing, not as emphasis. Three chapters meant
        // three separate "it froze again" moments.
        //
        // Everything the pin was for — the sense of dwelling on each chapter —
        // is still delivered by the scrubbed entrance above. The difference is
        // that scroll input now always produces scroll movement, which is the
        // one contract a page should never break.

        // ── Exit: fade out as the chapter leaves ────────────────────────
        gsap.to(panel, {
          opacity: 0,
          y: -60,
          ease: 'none',
          scrollTrigger: {
            trigger: section,
            start: 'bottom 62%',
            end: 'bottom 12%',
            scrub: true,
          },
        })
      })

      // Progress rail down the left edge — scaleY is compositor-only, so this
      // costs nothing per frame.
      gsap.to('[data-progress]', {
        scaleY: 1,
        ease: 'none',
        scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: 0.4 },
      })
    }, root)

    // Fonts land after first paint and change text height, which invalidates
    // every start/end GSAP measured. Recalculate once they are ready.
    if (document.fonts?.ready) {
      document.fonts.ready.then(() => ScrollTrigger.refresh())
    }

    return () => {
      ctx.revert()
      document.documentElement.classList.remove('js-scroll-driven')
    }
  }, [reduced])

  return (
    <div ref={root} className="relative z-10">
      {/* Progress rail. aria-hidden: it is decorative, and the scrollbar
          already conveys position to assistive tech. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed left-0 top-0 z-40 hidden h-full w-[2px] bg-white/5 lg:block"
      >
        <div
          data-progress
          className="h-full w-full origin-top scale-y-0 bg-gradient-to-b from-violet via-cyan to-violet"
        />
      </div>

      {CHAPTERS.map((c, i) => (
        <section
          key={c.id}
          id={c.id}
          data-chapter
          className="relative flex min-h-[100svh] items-center px-5 py-24 sm:px-8"
        >
          <div
            data-panel
            className={[
              'mx-auto w-full max-w-6xl',
              // Asymmetric layout — alternating sides give the scroll journey
              // a rhythm instead of a stack of identical centred blocks.
              i % 2 === 0 ? 'lg:pr-[38%]' : 'lg:pl-[38%] lg:text-right',
            ].join(' ')}
          >
            <span
              data-kicker
              className="mb-5 inline-block rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1 font-mono text-[11px] uppercase tracking-[0.2em] text-cyan"
            >
              {c.kicker}
            </span>

            <h2 className="text-balance text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
              <span className="block overflow-hidden pb-[0.1em]">
                <span data-line className="inline-block text-white">
                  {c.title}
                </span>
              </span>
              <span className="block overflow-hidden pb-[0.1em]">
                <span data-line className="inline-block text-gradient">
                  {c.accent}
                </span>
              </span>
            </h2>

            <p
              data-body
              className="mt-6 max-w-lg text-pretty text-base leading-relaxed text-white/55 sm:text-lg lg:inline-block"
            >
              {c.body}
            </p>

            <div
              data-stat
              className="glass mt-9 inline-flex items-baseline gap-3.5 rounded-2xl px-6 py-4"
            >
              <span className="font-mono text-3xl font-semibold text-cyan sm:text-4xl">
                {c.stat}
              </span>
              <span className="max-w-[16rem] text-left text-xs leading-snug text-white/45">
                {c.statLabel}
              </span>
            </div>
          </div>
        </section>
      ))}
    </div>
  )
}
