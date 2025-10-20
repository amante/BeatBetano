import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// IMPORTANT: base must match the GitHub repo name for project pages
export default defineConfig({
  plugins: [react()],
  base: '/amante.beatbetano/',
})
