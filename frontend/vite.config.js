import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Backend CORS allowlist expects this origin (backend/.env.example).
    proxy: {
      // Same-origin API access for both localhost and dev tunnels:
      // the browser only ever talks to this Vite server, which forwards
      // /api/* to the FastAPI backend. Avoids CORS and HTTPS mixed-content
      // blocks when the page is served over a public HTTPS tunnel URL.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
