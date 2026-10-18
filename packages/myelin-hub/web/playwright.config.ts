import { defineConfig } from "@playwright/test";

// Ports are configurable so e2e never collides with other dev servers on the workstation.
const WEB = process.env.MYELIN_E2E_WEB_PORT ?? "5199";
const API = process.env.MYELIN_E2E_API_PORT ?? "8799";
process.env.MYELIN_HUB_PORT = API; // vite proxy target (vite.config.ts)

/**
 * e2e runs against a real Hub API on a fresh temp Vault (see e2e/global-setup.ts) and the Vite dev
 * server. Uses the system Chrome channel so no browser download is needed.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://127.0.0.1:${WEB}`,
    channel: "chrome",
    headless: true,
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
  },
  webServer: {
    // --host 127.0.0.1: on Node ≥ 17 "localhost" may resolve to ::1 only, so the IPv4 health URL
    // never answers (CI runners). Output is piped so a failing start is visible in the log.
    command: `npx vite --host 127.0.0.1 --port ${WEB} --strictPort`,
    url: `http://127.0.0.1:${WEB}`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
