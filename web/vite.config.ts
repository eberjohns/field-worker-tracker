import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // Pages are split by route (Batch 9 step 3). The one chunk over the default 500 kB is the map
    // library (maplibre-gl, about 1 MB), loaded only by the pages that show a map.
    chunkSizeWarningLimit: 1100,
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
