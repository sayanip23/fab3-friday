import { useEffect, useRef, useState } from 'react'
import { motion, useInView, useMotionValue, useSpring, useTransform } from 'framer-motion'

/* ══════════════════════════════════════════════════════════════════════════
   Shared console primitives.

   Kept together because they share one idea: every one of them animates via
   MotionValues or CSS transforms, never React state on a per-frame basis.
   A dashboard is dense — a hundred re-rendering components is how these pages
   turn to treacle.
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Counter that rolls up to its value when scrolled into view.
 *
 * Animates a MotionValue and writes to textContent through a subscription,
 * so the surrounding component never re-renders. Doing this with useState
 * would re-render the whole card sixty times a second, per counter.
 */
export function Counter({ value, decimals = 0, prefix = '', suffix = '', className = '' }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const mv = useMotionValue(0)
  const spring = useSpring(mv, { stiffness: 60, damping: 20, mass: 0.8 })

  useEffect(() => {
    if (inView) mv.set(value ?? 0)
  }, [inView, value, mv])

  useEffect(() => {
    return spring.on('change', (v) => {
      if (ref.current) {
        ref.current.textContent =
          prefix +
          v.toLocaleString('en-IN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          }) +
          suffix
      }
    })
  }, [spring, decimals, prefix, suffix])

  return <span ref={ref} className={className}>{prefix}0{suffix}</span>
}

/** Status pill. `tone` is a semantic role so the palette lives in one place. */
export function Pill({ children, tone = 'neutral', className = '' }) {
  const tones = {
    good: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/25',
    warn: 'bg-amber-400/10 text-amber-300 ring-amber-400/25',
    bad: 'bg-rose-400/10 text-rose-300 ring-rose-400/25',
    info: 'bg-cyan/10 text-cyan ring-cyan/25',
    neutral: 'bg-white/5 text-white/55 ring-white/10',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.08em] ring-1 ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/**
 * Glass panel with a cursor-tracked spotlight.
 *
 * The spotlight is two MotionValues piped into a radial-gradient string. React
 * never re-renders on mousemove; the style object updates directly.
 */
export function Panel({ children, className = '', spotlight = true, ...rest }) {
  const ref = useRef(null)
  const px = useMotionValue(50)
  const py = useMotionValue(50)
  const sx = useSpring(px, { stiffness: 260, damping: 30 })
  const sy = useSpring(py, { stiffness: 260, damping: 30 })

  const glow = useTransform(
    [sx, sy],
    ([x, y]) =>
      `radial-gradient(420px circle at ${x}% ${y}%, rgba(124,58,237,0.14), transparent 65%)`
  )

  const onMove = (e) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    px.set(((e.clientX - r.left) / r.width) * 100)
    py.set(((e.clientY - r.top) / r.height) * 100)
  }

  return (
    <div
      ref={ref}
      onMouseMove={spotlight ? onMove : undefined}
      className={`group relative overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.025] ${className}`}
      {...rest}
    >
      {spotlight && (
        <motion.div
          aria-hidden="true"
          style={{ background: glow }}
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        />
      )}
      <div className="relative">{children}</div>
    </div>
  )
}

/**
 * Sparkline drawn as an inline SVG path.
 *
 * A charting library for a 120-point line is ~40 KB to draw one polyline.
 * The stroke-dash trick animates the draw without touching layout.
 */
export function Sparkline({ points = [], height = 44, stroke = '#22D3EE', fill = true }) {
  const vals = points.map((p) => p.value).filter((v) => typeof v === 'number')
  if (vals.length < 2) {
    return <div style={{ height }} className="grid place-items-center text-[11px] text-white/25">no series</div>
  }

  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const W = 100
  const step = W / (vals.length - 1)

  const coords = vals.map((v, i) => [i * step, height - ((v - min) / span) * (height - 6) - 3])
  const d = coords.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  const area = `${d} L${W},${height} L0,${height} Z`

  const last = vals[vals.length - 1]
  const first = vals[0]
  const up = last >= first

  return (
    <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none"
         className="w-full" style={{ height }} aria-hidden="true">
      <defs>
        <linearGradient id={`spark-${stroke.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#spark-${stroke.slice(1)})`} />}
      <motion.path
        d={d}
        fill="none"
        stroke={up ? stroke : '#F87171'}
        strokeWidth="1.4"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
      />
    </svg>
  )
}

/** Horizontal contribution bar. Width animates from 0 on mount. */
export function ContribBar({ label, value, share, unit = '' }) {
  const pct = Math.min(Math.abs(share) * 100, 100)
  const negative = value < 0

  return (
    <div className="py-2">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="truncate text-sm text-white/75">{label}</span>
        <span className="shrink-0 font-mono text-xs text-white/45">
          {value.toLocaleString('en-IN', { maximumFractionDigits: 0 })} {unit}
        </span>
      </div>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          initial={{ width: 0 }}
          whileInView={{ width: `${pct}%` }}
          viewport={{ once: true }}
          transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
          className={`absolute inset-y-0 left-0 rounded-full ${
            negative ? 'bg-gradient-to-r from-rose-500 to-rose-400' : 'bg-gradient-to-r from-violet to-cyan'
          }`}
        />
      </div>
      <div className="mt-1 text-right font-mono text-[10px] text-white/35">
        {(share * 100).toFixed(1)}% of movement
      </div>
    </div>
  )
}

/** Skeleton shimmer while a request is in flight. */
export function Skeleton({ className = '' }) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-gradient-to-r from-white/[0.04] via-white/[0.08] to-white/[0.04] ${className}`}
    />
  )
}

/** Magnetic button: pulls toward the cursor, springs back on leave. */
export function Magnetic({ children, className = '', strength = 0.35, ...rest }) {
  const ref = useRef(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 300, damping: 20, mass: 0.5 })
  const sy = useSpring(y, { stiffness: 300, damping: 20, mass: 0.5 })

  const onMove = (e) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    x.set((e.clientX - r.left - r.width / 2) * strength)
    y.set((e.clientY - r.top - r.height / 2) * strength)
  }

  return (
    <motion.button
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={() => { x.set(0); y.set(0) }}
      style={{ x: sx, y: sy }}
      whileTap={{ scale: 0.96 }}
      className={className}
      {...rest}
    >
      {children}
    </motion.button>
  )
}

/** Tiny hook: poll-free async state with loading + error, used by every panel. */
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    fn()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((error) => alive && setState({ data: null, loading: false, error }))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
