import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X, ArrowUpRight, Sparkles, LayoutDashboard } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { MOTION } from '../lib/tokens'

const LINKS = [
  { label: 'Problem', href: '#problem' },
  { label: 'Journey', href: '#journey' },
  { label: 'Solution', href: '#solution' },
  { label: 'Capabilities', href: '#capabilities' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const onConsole = pathname.startsWith('/console')
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    // Passive listener: this never calls preventDefault, and saying so lets
    // the browser scroll without waiting on our handler.
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close the mobile sheet on Escape — a panel you can only dismiss by
  // pointer is a keyboard trap.
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: MOTION.slow, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
      className="fixed inset-x-0 top-0 z-50 px-4 pt-4 sm:px-6"
    >
      <nav
        className={[
          'mx-auto flex max-w-6xl items-center justify-between rounded-2xl px-4 py-3 sm:px-6',
          'transition-all duration-500',
          scrolled ? 'glass-strong' : 'glass',
        ].join(' ')}
      >
        <Link to="/" className="group flex items-center gap-2.5" aria-label="FRIDAY, home">
          <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-violet/20 ring-1 ring-white/10">
            <Sparkles className="h-4 w-4 text-cyan" aria-hidden="true" />
            <span className="absolute inset-0 rounded-xl bg-violet/30 opacity-0 blur-md transition-opacity duration-300 group-hover:opacity-100" />
          </span>
          <span className="font-semibold tracking-tight text-white">FRIDAY</span>
          <span className="hidden font-mono text-[10px] uppercase tracking-[0.18em] text-white/35 sm:inline">
            Fab3
          </span>
        </Link>

        <ul className="hidden items-center gap-1 md:flex">
          {(onConsole ? [] : LINKS).map((l) => (
            <li key={l.href}>
              <motion.a
                href={l.href}
                whileHover={{ y: -2 }}
                transition={{ type: 'spring', stiffness: 420, damping: 22 }}
                className="relative rounded-lg px-3.5 py-2 text-sm text-white/65 transition-colors hover:text-white"
              >
                {l.label}
              </motion.a>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          <Link to={onConsole ? '/' : '/console'}>
            <motion.span
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              transition={{ type: 'spring', stiffness: 400, damping: 18 }}
              className="hidden items-center gap-1.5 rounded-xl bg-violet px-4 py-2 text-sm font-medium text-white neon-violet sm:inline-flex"
            >
              {onConsole ? 'Overview' : 'Open console'}
              {onConsole
                ? <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                : <LayoutDashboard className="h-3.5 w-3.5" aria-hidden="true" />}
            </motion.span>
          </Link>

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'}
            /* 44px minimum touch target. */
            className="grid h-11 w-11 place-items-center rounded-xl text-white/75 ring-1 ring-white/10 transition-colors hover:text-white md:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            id="mobile-nav"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: MOTION.fast, ease: 'easeOut' }}
            className="glass-strong mx-auto mt-2 max-w-6xl overflow-hidden rounded-2xl md:hidden"
          >
            <ul className="flex flex-col p-2">
              {LINKS.map((l) => (
                <li key={l.href}>
                  <a
                    href={l.href}
                    onClick={() => setOpen(false)}
                    className="flex min-h-[44px] items-center rounded-xl px-4 text-sm text-white/75 transition-colors hover:bg-white/5 hover:text-white"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  )
}
