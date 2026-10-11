import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("@xyflow")) return "canvas";
            if (id.includes("/zod/")) return "validation";
            if (
              id.includes("/react/") ||
              id.includes("/react-dom/") ||
              id.includes("/scheduler/")
            )
              return "react";
          }
        },
      },
    },
  },
  server: { proxy: { "/api": "http://127.0.0.1:3001" } },
});
