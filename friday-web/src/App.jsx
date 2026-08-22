import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'

import Navbar from './components/Navbar'
import Hero from './components/Hero'
import OverlayUI from './components/OverlayUI'
import Capabilities from './components/Capabilities'
import Footer from './components/Footer'
import Console from './components/console/Console'
import { useSmoothAnchors } from './hooks/useSmoothAnchors'
import { useLenis } from './hooks/useLenis'

const CanvasScene = lazy(() => import('./components/CanvasScene'))

function Marketing() {
  useSmoothAnchors({ duration: 900, offset: 90 })
  return (
    <main className="relative z-10">
      <Hero />
      <OverlayUI />
      <Capabilities />
    </main>
  )
}

function Shell() {
  const { pathname } = useLocation()
  const isConsole = pathname.startsWith('/console')

  // Lenis is for the marketing narrative. The console is a dense data surface
  // where a user scanning a table wants the scroll to stop when they stop —
  // inertia there reads as lag, not polish.
  useLenis(!isConsole)

  return (
    <>
      {/* The 3D canvas persists across both routes, so navigating between the
          site and the console never tears down and rebuilds the WebGL context.
          On the console it is dimmed so it reads as atmosphere behind data. */}
      <Suspense fallback={<div className="fixed inset-0 z-0 bg-void" />}>
        <CanvasScene />
      </Suspense>

      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-[1] transition-opacity duration-700"
        style={{
          opacity: isConsole ? 1 : 0.85,
          background: isConsole
            ? 'radial-gradient(ellipse at top, rgba(5,5,10,0.82) 0%, rgba(5,5,10,0.95) 60%)'
            : 'radial-gradient(ellipse at center, transparent 20%, rgba(5,5,10,0.55) 70%, rgba(5,5,10,0.9) 100%)',
        }}
      />

      <Navbar />

      <Routes>
        <Route path="/" element={<Marketing />} />
        <Route path="/console" element={<Console />} />
      </Routes>

      {!isConsole && <Footer />}
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}
