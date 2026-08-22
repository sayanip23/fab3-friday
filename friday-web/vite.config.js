import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, open: true },
  build: {
    // three.js is large; split it out so the initial HTML/CSS paints before
    // the 3D engine is parsed. The canvas fades in when it is ready.
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          r3f: ['@react-three/fiber', '@react-three/drei'],
          motion: ['gsap', 'framer-motion'],
        },
      },
    },
  },
})
