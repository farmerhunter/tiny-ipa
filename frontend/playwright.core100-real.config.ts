import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
const frontendPort = Number(process.env.CORE100_REAL_FRONTEND_PORT ?? "5185");
const backendPort = Number(process.env.CORE100_REAL_BACKEND_PORT ?? "8035");
for (const port of [frontendPort, backendPort]) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid test port");
}
const runId = `${Date.now()}-${process.pid}`;
const dbPath = process.env.CORE100_REAL_DB_PATH ?? `/tmp/tiny-ipa-core100-${runId}.sqlite`;
const frontendURL = `http://127.0.0.1:${frontendPort}`;
export default defineConfig({
  testDir: "./tests/e2e", testMatch: "core100-real-workflow.spec.ts",
  outputDir: "./test-results/core100-real",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report/core100-real" }]],
  workers: 1,
  use: { baseURL: frontendURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "core100-real-mobile-chromium", use: { ...devices["Pixel 5"] } }],
  webServer: [
    {
      command: `cd ../backend && uv run --frozen python ../frontend/tests/e2e/support/prepare_core100_real_db.py && uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/health`, reuseExistingServer: false, timeout: 120_000,
      env: {
        TINY_IPA_DB_PATH: dbPath, CORE100_REAL_DB_PATH: dbPath,
        TINY_IPA_AUDIO_DIR: resolve("../audio/core100-candidate"), TINY_IPA_REQUIRE_PACKAGED_AUDIO: "true",
        TINY_IPA_ENV: "development", TINY_IPA_ALLOWED_ORIGINS: frontendURL,
        TINY_IPA_SESSION_SECRET: "local-core100-disposable-fixture-only",
      },
    },
    {
      command: `pnpm exec vite --config vite.core100-test.config.ts --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: frontendURL, reuseExistingServer: false, timeout: 120_000,
      env: { VITE_API_BASE: "/api", CORE100_REAL_BACKEND_PORT: String(backendPort) },
    },
  ],
});
