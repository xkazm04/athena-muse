import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const at = (p: string) => fileURLToPath(new URL(p, import.meta.url));

// Three entries: the main window (index.html), her window (athena.html) and the theme preview
// (preview.html, no daemon needed). Port 1420 is the Tauri dev URL and one of the daemon's allowed origins.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  build: {
    target: "es2022",
    rollupOptions: {
      input: { main: at("index.html"), athena: at("athena.html"), preview: at("preview.html") },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
