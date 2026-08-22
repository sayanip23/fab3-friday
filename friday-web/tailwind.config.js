/** @type {import('tailwindcss').Config} */

// Palette source: ui-ux-pro-max colour domain, profile "Editor violet + filter
// cyan on dark". Three-layer tokens — primitives here, semantic roles in
// src/lib/tokens.js, component usage in the components themselves.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: '#05050A',       // deepest background, behind the canvas
        abyss: '#0A0A14',      // page background
        slate: '#0F172A',      // raised surfaces
        violet: {
          DEFAULT: '#7C3AED',  // primary
          soft: '#A78BFA',
          deep: '#4C1D95',
        },
        cyan: {
          DEFAULT: '#22D3EE',  // neon accent
          deep: '#0891B2',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      backdropBlur: { xs: '2px' },
      keyframes: {
        // Slow aurora drift behind the glass panels. Transform-only so it runs
        // on the compositor and never triggers layout.
        drift: {
          '0%,100%': { transform: 'translate3d(0,0,0) scale(1)' },
          '50%': { transform: 'translate3d(3%,-4%,0) scale(1.08)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        drift: 'drift 18s ease-in-out infinite',
        shimmer: 'shimmer 3s linear infinite',
      },
    },
  },
  plugins: [],
}
