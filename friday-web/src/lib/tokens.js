/**
 * Semantic layer of the token system.
 *
 * Tailwind holds the primitives (see tailwind.config.js). This file names the
 * *roles*, so the 3D scene and the DOM stay in colour lockstep — the neon rim
 * light on the sphere is literally the same value as the CTA glow, which is
 * what makes the canvas feel like part of the page rather than a video behind
 * it.
 */

export const COLOR = {
  primary: '#7C3AED',      // violet — brand, key light, primary CTA
  primarySoft: '#A78BFA',
  accent: '#22D3EE',       // cyan — rim light, focus ring, secondary CTA
  accentDeep: '#0891B2',
  bg: '#0A0A14',
  void: '#05050A',
  surface: '#0F172A',
}

/** Motion tier "Complex" from the design system's GSAP preset. */
export const MOTION = {
  fast: 0.3,
  base: 0.6,
  slow: 1.1,
  ease: 'power3.out',
  easeElastic: 'elastic.out(1, 0.55)',
  stagger: 0.08,
}

/** Content for the scroll chapters. Kept as data so the narrative is
 *  readable in the DOM even if every animation is disabled. */
export const CHAPTERS = [
  {
    id: 'problem',
    kicker: 'Chapter 01',
    title: 'Dashboards report what changed.',
    accent: 'They never say why.',
    body:
      'Revenue in a region falls nineteen percent. The chart shows the drop and stops there. ' +
      'Somebody forwards it to an analyst, and three days later an explanation comes back — ' +
      'by which point the month is half gone.',
    stat: '3 days',
    statLabel: 'typical wait for one explanation',
  },
  {
    id: 'journey',
    kicker: 'Chapter 02',
    title: 'The reason lives in the words,',
    accent: 'not in the numbers.',
    body:
      'Around eighty percent of what a company knows is text: support tickets, CRM notes, ' +
      'operations logs. No dashboard can read a single line of it, and yet that is almost ' +
      'always where the cause is hiding.',
    stat: '80%',
    statLabel: 'of enterprise data no dashboard reads',
  },
  {
    id: 'solution',
    kicker: 'Chapter 03',
    title: 'FRIDAY finds the chain,',
    accent: 'and proves every link.',
    body:
      'Delivery reliability degraded. One account stopped ordering. Revenue fell. ' +
      'Each step is arithmetic you can check by hand, each cause is dated and corroborated, ' +
      'and where the evidence runs out it says so instead of guessing.',
    stat: '105 ms',
    statLabel: 'question to answer, end to end',
  },
]

export const FEATURES = [
  {
    icon: 'ShieldCheck',
    title: 'Numbers it cannot invent',
    body:
      'Every figure is computed by deterministic code first, then handed to the model. ' +
      'Any number in the prose that no stage produced fails the render.',
  },
  {
    icon: 'GitBranch',
    title: 'Three gates before "cause"',
    body:
      'Sequence, magnitude and mechanism must all pass. Anything less is reported ' +
      'as an association, with the reason it fell short.',
  },
  {
    icon: 'EyeOff',
    title: 'Knows when to stop',
    body:
      'On thin history or split evidence it abstains, states why, and names the ' +
      'one check that would settle the question.',
  },
  {
    icon: 'Lock',
    title: 'Scoped at the data',
    body:
      'Entitlements filter rows before anything is computed, so a total is never ' +
      'derived from records the reader was not allowed to see.',
  },
  {
    icon: 'Gauge',
    title: 'Costed per insight',
    body:
      'Latency, model calls, tokens and rupees are stamped on every answer. ' +
      'No stage marked deterministic may issue a model call.',
  },
  {
    icon: 'RefreshCw',
    title: 'Learns from corrections',
    body:
      'An analyst marking an explanation wrong shifts driver priors — but never ' +
      'rewrites a contribution, because contributions are arithmetic.',
  },
]
