import { useEffect, useState } from 'react'

/**
 * Device and preference probes that both the canvas and the UI depend on.
 *
 * These live in one place because performance decisions have to be consistent:
 * if we cut the particle count for mobile but leave the DOM animations running
 * at full weight, we have moved the jank rather than removed it.
 */

/** True when the user has asked their OS to reduce motion. Live-updates. */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false
  )

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (e) => setReduced(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return reduced
}

/**
 * Reads the real GPU string via WEBGL_debug_renderer_info.
 *
 * This matters more than it looks. CPU cores and RAM say nothing about GPU
 * capability, and the most common desktop configuration that breaks a naive
 * heuristic is a many-core workstation with *integrated* graphics — 16 cores,
 * 16 GB, and an Intel UHD chip that cannot sustain five refraction passes.
 * Without this check such a machine is graded "high" and gets the heaviest
 * scene on the weakest GPU in the lineup.
 *
 * Returns null when the extension is blocked (some privacy settings strip it),
 * in which case we fall back to the CPU heuristic rather than guessing.
 */
function detectGpu() {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    if (!gl) return { renderer: null, integrated: true, software: true }

    const dbg = gl.getExtension('WEBGL_debug_renderer_info')
    const renderer = String(
      dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)
    )

    // Software rasterisers — no GPU at all. Always the cheapest scene.
    const software = /swiftshader|llvmpipe|software|basic render/i.test(renderer)

    // Integrated GPUs. Capable of the scene, but not of five transmission
    // buffers at 512px with 6 samples each.
    const integrated =
      /intel.*(uhd|hd graphics|iris)|radeon.*(vega \d|graphics$)|apple gpu|mali|adreno|powervr/i.test(
        renderer
      )

    return { renderer, integrated, software }
  } catch {
    return { renderer: null, integrated: false, software: false }
  }
}

/**
 * Coarse device tier. Drives particle counts, shadow quality and DPR.
 *
 * `deviceMemory` and `hardwareConcurrency` are absent on Safari, so the
 * pointer check carries the decision there: a coarse pointer with a narrow
 * viewport is a phone, and phones get the cheap scene.
 *
 * The GPU check runs last and only ever lowers the grade — it is a ceiling,
 * not an override, so a weak GPU can never be talked back up by a strong CPU.
 */
export function useDeviceTier() {
  const [tier, setTier] = useState('mid') // start conservative, upgrade after probing

  useEffect(() => {
    const coarse = window.matchMedia('(pointer: coarse)').matches
    const narrow = window.innerWidth < 768
    const cores = navigator.hardwareConcurrency ?? 8
    const mem = navigator.deviceMemory ?? 8

    let next
    if ((coarse && narrow) || cores <= 4 || mem <= 4) next = 'low'
    else if (cores <= 8 || window.innerWidth < 1280) next = 'mid'
    else next = 'high'

    const gpu = detectGpu()
    if (gpu.software) next = 'low'
    else if (gpu.integrated && next === 'high') next = 'mid'

    setTier(next)
  }, [])

  return tier
}

/**
 * True while the document is visible.
 *
 * A WebGL loop keeps burning GPU on a background tab unless you stop it. We
 * flip the Canvas `frameloop` to "never" when hidden, which is the single
 * biggest battery win available here.
 */
export function usePageVisible() {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const onChange = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', onChange)
    return () => document.removeEventListener('visibilitychange', onChange)
  }, [])

  return visible
}
