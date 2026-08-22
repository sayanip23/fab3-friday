import { useRef } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import * as Icons from 'lucide-react'

/**
 * Glass feature card with pointer-tracked 3D tilt and a spotlight that
 * follows the cursor.
 *
 * The tilt is driven by two MotionValues rather than React state. That
 * distinction is the whole performance story: state would re-render the
 * component on every mousemove, at up to 120 events per second. MotionValues
 * write straight to the DOM node's transform, so React never re-renders and
 * the work stays on the compositor.
 */
export default function FeatureCard({ icon, title, body, index }) {
  const ref = useRef(null)

  // Raw normalised pointer position within the card, -0.5 .. 0.5
  const px = useMotionValue(0)
  const py = useMotionValue(0)

  // Spring the raw values so the card settles rather than snapping. Low
  // stiffness + high damping = weighted glass, not a jittery panel.
  const sx = useSpring(px, { stiffness: 220, damping: 26, mass: 0.6 })
  const sy = useSpring(py, { stiffness: 220, damping: 26, mass: 0.6 })

  // Invert Y so pushing the cursor up tips the top edge away from the viewer,
  // which is what the eye expects from a physical object.
  const rotateX = useTransform(sy, [-0.5, 0.5], ['7deg', '-7deg'])
  const rotateY = useTransform(sx, [-0.5, 0.5], ['-7deg', '7deg'])

  // Spotlight position, expressed as a percentage for the radial gradient.
  const glowX = useTransform(sx, [-0.5, 0.5], ['0%', '100%'])
  const glowY = useTransform(sy, [-0.5, 0.5], ['0%', '100%'])

  const handleMove = (e) => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    px.set((e.clientX - rect.left) / rect.width - 0.5)
    py.set((e.clientY - rect.top) / rect.height - 0.5)
  }

  const handleLeave = () => {
    px.set(0)
    py.set(0)
  }

  // Hoisted out of JSX: calling a hook inside a style prop works, but it
  // trips the rules-of-hooks lint and breaks the moment the element becomes
  // conditional. Keep every hook at the top level of the component body.
  const spotlight = useTransform(
    [glowX, glowY],
    ([x, y]) =>
      `radial-gradient(340px circle at ${x} ${y}, rgba(124,58,237,0.18), transparent 70%)`
  )

  const Icon = Icons[icon] ?? Icons.Sparkles

  return (
    <motion.article
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      // once: true — replaying the entrance on every scroll-by is noise.
      // margin pulls the trigger point up so the card is already settled by
      // the time it is comfortably in view.
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.65, delay: index * 0.07, ease: [0.22, 1, 0.36, 1] }}
      style={{ rotateX, rotateY, transformStyle: 'preserve-3d', perspective: 1000 }}
      whileHover={{ scale: 1.025 }}
      className="glass group relative overflow-hidden rounded-3xl p-7"
    >
      {/* Cursor spotlight. pointer-events-none so it never eats the hover. */}
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: spotlight }}
      />

      {/* Content sits forward in Z so it lifts off the glass as the card
          tilts, which is what sells the depth. */}
      <div style={{ transform: 'translateZ(38px)' }}>
        <span className="mb-5 inline-grid h-12 w-12 place-items-center rounded-2xl bg-violet/15 ring-1 ring-white/10 transition-colors duration-300 group-hover:bg-violet/25">
          <Icon className="h-5 w-5 text-cyan" aria-hidden="true" />
        </span>

        <h3 className="text-lg font-semibold tracking-tight text-white">{title}</h3>
        <p className="mt-2.5 text-sm leading-relaxed text-white/50">{body}</p>
      </div>

      {/* Hairline that sweeps in on hover — a cheap way to make the top edge
          catch the light. */}
      <span
        aria-hidden="true"
        className="hairline absolute inset-x-0 top-0 h-px scale-x-0 transition-transform duration-500 group-hover:scale-x-100"
      />
    </motion.article>
  )
}
