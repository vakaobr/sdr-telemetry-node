import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// vitest/config re-exports vite's defineConfig with the `test` key typed.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://tattoine-watcher.local:8080",
      "/ws": { target: "ws://tattoine-watcher.local:8080", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
