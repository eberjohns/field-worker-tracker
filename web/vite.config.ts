import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // Pages are split by route (Batch 9 step 3). The Google Maps script itself is loaded from
    // Google at run time, only by the pages that show a map (ADR-033).
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
