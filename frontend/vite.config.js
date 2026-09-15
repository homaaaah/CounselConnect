import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Listen on all interfaces (IPv4 + IPv6) so `localhost` resolves reliably
    // across browsers/proxies that prefer 127.0.0.1 over [::1].
    host: true,
    port: 5173,
    // Backend CORS allowlist expects this origin (backend/.env.example).
  },
});
