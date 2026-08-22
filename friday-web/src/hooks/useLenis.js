import { useEffect } from 'react'
import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

/**
 * Lenis smooth scroll, driven by GSAP's ticker.
 *
 * The critical detail is that Lenis is NOT given its own requestAnimationFrame
 * loop. Two independent rAF loops — one moving the scroll position, one running
 * ScrollTrigger — resolve in an undefined order, so ScrollTrigger routinely
 * measures a scroll position one frame stale. That is the source of the classic
 * "smooth scroll makes my pinned sections judder" bug.
 *
 * Driving lenis.raf from gsap.ticker puts both on one clock, in a guaranteed
 * order: scroll moves, then triggers evaluate. lagSmoothing(0) stops GSAP
 * silently skipping time after a long frame, which would otherwise teleport
 * the scroll.
 */
export function useLenis(enabled = true) {
  useEffect(() => {
    if (!enabled) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const lenis = new Lenis({
      duration: 1.05,
      // Exponential ease-out: fast pickup, long settle.
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      // Touch devices already have momentum scrolling in hardware; layering
      // ours on top fights the OS and feels laggy.
      smoothTouch: false,
    })

    lenis.on('scroll', ScrollTrigger.update)

    const tick = (time) => lenis.raf(time * 1000) // GSAP gives seconds, Lenis wants ms
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)

    return () => {
      gsap.ticker.remove(tick)
      gsap.ticker.lagSmoothing(500, 33) // restore the default
      lenis.destroy()
    }
  }, [enabled])
}
