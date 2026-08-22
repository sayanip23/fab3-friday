# FRIDAY — Immersive 3D Site

A premium, scroll-driven 3D marketing site for FRIDAY. Separate from the
Streamlit prototype in `../friday`, which is untouched.

---

## Requirements

**Node.js 18 or newer.** It is not installed on this machine yet — that is the
one thing standing between this code and a running site.

Get it from <https://nodejs.org> (LTS), or with winget:

```bash
winget install OpenJS.NodeJS.LTS
```

Then **open a new terminal** so `node` and `npm` land on PATH.

## Running it

```bash
cd D:\Accenture\friday-web
npm install
npm run dev
```

Vite prints a URL, usually <http://localhost:5173>, and opens it.

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Production bundle into `dist/` |
| `npm run preview` | Serve the built bundle locally |

Note the port: **5173**, not 8501. The Streamlit engine and this site can run
side by side without colliding.

---

## Structure

```
src/
  main.jsx                  React entry
  App.jsx                   Layer stack: canvas → vignette → nav → content
  index.css                 Tailwind layers, glass utilities, reduced motion
  lib/tokens.js             Semantic colours, motion tiers, page copy
  hooks/useEnvironment.js   Device tier, reduced motion, page visibility
  components/
    CanvasScene.jsx         React Three Fiber scene (the 3D)
    Navbar.jsx              Glass nav, mobile sheet
    Hero.jsx                Full-height hero, word-stagger headline
    OverlayUI.jsx           GSAP ScrollTrigger chapters (pin + scrub)
    FeatureCard.jsx         Tilting glass card with cursor spotlight
    Capabilities.jsx        Feature grid + climax CTA
    Footer.jsx
```

### How the layers stack

```
z-0   CanvasScene   fixed, full-viewport WebGL
z-1   vignette      radial fade so text keeps contrast over a busy scene
z-10  DOM content   hero, chapters, capabilities, footer
z-40  progress rail
z-50  navbar
```

The canvas is `position: fixed`, so it stays put while the DOM scrolls over
it. That is what produces the "camera holds still while the story moves"
feeling, with no scroll-jacking.

---

## The 3D scene

| Element | Technique | Why |
|---|---|---|
| Morphing core | `MeshDistortMaterial` on an icosahedron | Vertex-shader noise displacement. Costs a uniform update per frame, not a geometry rebuild. |
| Particle field | One `THREE.Points`, 600–2600 pts | A single draw call. Rotating the parent is effectively free versus animating each point. |
| Glass shards | `MeshTransmissionMaterial` | Real refraction — renders the scene to a buffer and samples through the surface. The most expensive thing on screen. |
| Parallax | `MathUtils.damp` toward `state.pointer` | Frame-rate independent easing. A naive lerp moves twice as fast at 120fps as at 60. |
| Lighting | Violet key + cyan rim + violet fill | Same token values as the CTA glow, so canvas and UI look lit by one source. |

### Performance

Optimisation is tiered by device rather than applied uniformly:

| | low | mid | high |
|---|---|---|---|
| Particles | 600 | 1400 | 2600 |
| Icosahedron detail | 4 | 8 | 12 |
| Glass shards | 3 (cheap material) | 5 | 5 |
| Transmission samples | — | 3 | 6 |
| DPR cap | 1.5 | 1.5 | 2 |
| Shadows | off | on | on, 1024px |

Plus:

- **`frameloop="never"` on a hidden tab.** A WebGL loop keeps burning GPU on a
  background tab unless you stop it. Biggest battery win here.
- **`frameloop="demand"` under reduced motion.** Nothing animates, so it
  renders once and idles at 0%.
- **`AdaptiveDpr` + `PerformanceMonitor`.** A weak GPU degrades to a softer
  image instead of a stuttering one.
- **DPR clamping.** The single highest-impact mobile fix: a 3× retina phone
  would otherwise render nine times the pixels.
- **Lazy-loaded canvas.** three + R3F + drei is a large bundle. The hero text
  paints first and the canvas fades in behind it.

---

## Animation split

**Framer Motion** for component entrances and micro-interactions — hero word
stagger, card tilt, hover springs, mobile sheet.

**GSAP ScrollTrigger** for the scroll journey — because these chapters *pin*,
and pinning means taking an element out of flow and compensating the scroll
height. Framer's `useScroll` maps one value to one style; it cannot do that.

Card tilt runs on `useMotionValue`, not React state. State would re-render on
every mousemove, up to 120 times a second. MotionValues write straight to the
DOM node's transform, so React never re-renders.

`gsap.context()` scopes every selector to the root ref, and one `ctx.revert()`
on unmount removes the tweens, the ScrollTriggers *and* the pin-spacer divs
GSAP injects. Without it, React Strict Mode's double-mount leaves two sets of
triggers attached and each chapter animates twice.

---

## Design decisions

Palette and pattern came from the `ui-ux-pro-max` skill, with two overrides:

- **Style:** it returned *Brutalism* (sharp corners, no transitions,
  anti-design) because the variance dial was set high. That is the opposite of
  a premium glassmorphic look, so it was discarded. The
  **Scroll-Triggered Storytelling** pattern it returned was kept in full,
  including its accessibility requirements.
- **Palette:** taken from the colour domain profile *"Editor violet + filter
  cyan on dark"* — violet `#7C3AED`, cyan `#22D3EE`, background `#0A0A14`,
  borders `rgba(255,255,255,0.08)`.

### Accessibility

- Visible focus ring on every interactive control
- 44px minimum touch targets
- `prefers-reduced-motion` fully honoured: ScrollTrigger never registers, the
  3D freezes in a readable state, and the canvas stops rendering
- Content is complete in the DOM — the story reads with JS animation disabled
- Canvas is `aria-hidden`; it is decorative
- Escape closes the mobile menu

---

## Known limits

- **Never executed.** Node was unavailable, so this was written but not run.
  Expect the usual first-run friction of an untested build.
- Version matrix is a known-good combination (React 18.3 / three 0.169 /
  R3F 8.17 / drei 9.114) but was not installed and verified.
- The "Open the live engine" CTA points at `http://localhost:8501`, which
  only resolves while the Streamlit app is running.
