import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowUpRight, Loader2, AlertTriangle } from 'lucide-react'

const ENGINE_URL = 'http://localhost:8501'

/**
 * CTA to the live Streamlit engine, with a reachability probe.
 *
 * The naive version — a plain <a target="_blank"> — fails silently in the two
 * cases that actually happen in a demo: the engine is not running, or the
 * browser blocks the popup. Either way the user clicks and nothing visible
 * occurs, which reads as a broken site rather than a stopped server.
 *
 * So we probe first. `mode: 'no-cors'` gives an opaque response we cannot
 * read, but the fetch still *rejects* when nothing is listening on the port,
 * and that rejection is the only signal we need.
 */
export default function EngineLink() {
  const [status, setStatus] = useState('checking') // checking | up | down

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 2500)

    fetch(ENGINE_URL, { mode: 'no-cors', signal: controller.signal })
      .then(() => !cancelled && setStatus('up'))
      .catch(() => !cancelled && setStatus('down'))
      .finally(() => clearTimeout(timer))

    return () => {
      cancelled = true
      controller.abort()
      clearTimeout(timer)
    }
  }, [])

  const handleClick = (e) => {
    if (status === 'down') {
      // Do not navigate into a dead port and leave a blank tab behind.
      e.preventDefault()
      return
    }
    const win = window.open(ENGINE_URL, '_blank', 'noopener,noreferrer')
    if (win) {
      e.preventDefault() // handled; stop the anchor double-opening
    }
    // If window.open was blocked, fall through and let the anchor navigate.
  }

  const label =
    status === 'checking'
      ? 'Checking engine…'
      : status === 'down'
        ? 'Engine not running'
        : 'Open the live engine'

  return (
    <div className="flex flex-col items-center gap-2.5">
      <motion.a
        href={ENGINE_URL}
        target="_blank"
        rel="noreferrer noopener"
        onClick={handleClick}
        aria-disabled={status === 'down'}
        whileHover={status === 'down' ? {} : { scale: 1.045 }}
        whileTap={status === 'down' ? {} : { scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 380, damping: 17 }}
        className={[
          'group inline-flex min-h-[48px] items-center gap-2 rounded-2xl px-7 text-sm font-semibold',
          status === 'down'
            ? 'cursor-not-allowed bg-white/10 text-white/45'
            : 'bg-violet text-white neon-violet',
        ].join(' ')}
      >
        {status === 'checking' && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {status === 'down' && <AlertTriangle className="h-4 w-4" aria-hidden="true" />}
        {label}
        {status === 'up' && (
          <ArrowUpRight
            className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            aria-hidden="true"
          />
        )}
      </motion.a>

      {/* Tell the user how to fix it rather than leaving a dead button. */}
      {status === 'down' && (
        <p role="status" className="max-w-xs text-center font-mono text-[11px] leading-relaxed text-white/40">
          Start it with{' '}
          <span className="text-cyan">streamlit run app.py</span> in the{' '}
          <span className="text-cyan">friday</span> folder, then reload.
        </p>
      )}
    </div>
  )
}
