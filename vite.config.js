import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins:[react()],
  // IMPORTANT: Match exact repo name with case sensitivity
  base:'/BeatBetano/'
})
