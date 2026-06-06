import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Dev: proxy the backend's API + stream so the SPA runs same-origin against
// `ocular` on :8099 (or OCULAR_DEV_BACKEND). Prod: the backend serves dist/, so
// these paths are already same-origin and the proxy is unused.
const backend = process.env.OCULAR_DEV_BACKEND ?? "http://localhost:8099";

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/status": { target: backend, changeOrigin: true },
      "/stream.mjpg": { target: backend, changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
