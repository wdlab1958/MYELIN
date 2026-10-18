import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const repo = fileURLToPath(new URL("../../..", import.meta.url));

// 개발 서버: Hub API(myelin-hub, 127.0.0.1:8765)로 /api 를 프록시한다.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    fs: { allow: [repo] },
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
});
