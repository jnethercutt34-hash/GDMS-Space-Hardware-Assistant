import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // LLM extraction on local Ollama can take 2-3 minutes
        timeout: 300000,
      },
    },
  },
})
