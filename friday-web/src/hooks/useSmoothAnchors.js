import { useEffect } from 'react'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

/**
 * Smooth anchor navigation.
 *
 * ── Why this is hand-rolled ─────────────────────────────────────────────
 * Two obvious options were tried and rejected:
 *
 *   `scroll-behavior: smooth` — fights ScrollTrigger. The browser animates
 *   scrollTop on its own schedule while a pin is active, which stutters at
 *   every pin boundary. Disabling it is what made anchor links jump.
 *
 *   GSAP ScrollToPlugin — the tween registered but never moved the page.
 *   Rather than keep debugging a plugin whose only job is writing one
 *   number, the loop below writes that number directly.
 *
 * A rAF loop has no registration step, no plugin bundle, and no silent
 * failure mode: if it runs, the page moves.
 *
 * ── Interruption ────────────────────────────────────────────────────────
 * Any wheel, touch or key input cancels the animation immediately. A scroll
 * you cannot escape from feels like the page has taken the controls away.
 */

// easeInOutCubic: slow start, quick middle, gentle settle.
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

export function useSmoothAnchors({ duration = 900, offset = 90 } = {}) {
  useEffect(() => {
    let frame = null
    let cancelled = false

    const stop = () => {
      cancelled = true
      if (frame) cancelAnimationFrame(frame)
      frame = null
    }

    // Passive listeners: these never call preventDefault, and saying so lets
    // the browser scroll without waiting on them.
    const interrupt = () => stop()
    const opts = { passive: true }
    window.addEventListener('wheel', interrupt, opts)
    window.addEventListener('touchstart', interrupt, opts)
    window.addEventListener('keydown', interrupt, opts)

    const scrollTo = (targetY, onDone) => {
      const startY = window.scrollY
      const delta = targetY - startY
      if (Math.abs(delta) < 2) return onDone?.()

      const t0 = performance.now()
      cancelled = false

      const step = (now) => {
        if (cancelled) return
        const p = Math.min((now - t0) / duration, 1)
        window.scrollTo(0, startY + delta * ease(p))
        if (p < 1) frame = requestAnimationFrame(step)
        else {
          frame = null
          onDone?.()
        }
      }
      frame = requestAnimationFrame(step)
    }

    const onClick = (e) => {
      const link = e.target.closest?.('a[href^="#"]')
      if (!link) return

      const id = link.getAttribute('href')
      if (!id || id === '#') return

      const target = document.querySelector(id)
      if (!target) return

      e.preventDefault()
      stop() // kill any in-flight scroll before starting a new one

      // Measure against the document, not the viewport: getBoundingClientRect
      // is relative to the current scroll position, so it must be added to it.
      const targetY = Math.max(
        0,
        window.scrollY + target.getBoundingClientRect().top - offset
      )

      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (reduced) {
        window.scrollTo(0, targetY)
        history.pushState(null, '', id)
        return
      }

      scrollTo(targetY, () => {
        history.pushState(null, '', id)
        // A programmatic jump can leave ScrollTrigger's cached start/end
        // values stale; refresh so pins re-measure against the new position.
        ScrollTrigger.refresh()
      })
    }

    document.addEventListener('click', onClick)

    return () => {
      stop()
      document.removeEventListener('click', onClick)
      window.removeEventListener('wheel', interrupt)
      window.removeEventListener('touchstart', interrupt)
      window.removeEventListener('keydown', interrupt)
    }
  }, [duration, offset])
}
