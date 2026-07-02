import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.M11_REAL_FRONTEND_PORT ?? "5182";
const backendPort = process.env.M11_REAL_BACKEND_PORT ?? "8028";
const runId = process.env.M11_REAL_RUN_ID ?? `${Date.now()}-${process.pid}`;
const dbPath = process.env.M11_REAL_DB_PATH ?? `/tmp/tiny-ipa-m11-real-${runId}.sqlite`;
const uvCacheDir = process.env.M11_REAL_UV_CACHE_DIR ?? `/tmp/tiny-ipa-m11-real-uv-${runId}`;
const frontendURL = `http://127.0.0.1:${frontendPort}`;
const backendURL = `http://127.0.0.1:${backendPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results/m11-real-backend",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report/m11-real" }]],
  fullyParallel: false,
  use: {
    baseURL: frontendURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "m11-real-mobile-chromium",
      use: {
        ...devices["Pixel 5"],
        browserName: "chromium",
      },
    },
  ],
  webServer: [
    {
      command: [
        `cd ../backend && UV_CACHE_DIR=${uvCacheDir} uv run python ../frontend/tests/e2e/support/prepare_m11_real_db.py ${dbPath}`,
        `cd ../backend && TINY_IPA_DB_PATH=${dbPath} TINY_IPA_CORS_ORIGINS=${frontendURL} UV_CACHE_DIR=${uvCacheDir} uv run uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      ].join(" && "),
      url: `${backendURL}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `VITE_API_BASE=${backendURL}/api pnpm exec vite --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: frontendURL,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
