import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// The design system lives outside this package: alias it so the single source stays in design/.
const design = fileURLToPath(new URL("../../../design", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@design": design } },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": `http://127.0.0.1:${process.env.MYELIN_HUB_PORT ?? "8787"}` },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
