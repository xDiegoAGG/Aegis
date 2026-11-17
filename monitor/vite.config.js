import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development /api goes to the Aegis on this machine (python3 -m aegis.actuator or a port-forward).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.AEGIS_DEV_API || "http://localhost:8080",
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
  },
  test: {
    environment: "node",
  },
});
