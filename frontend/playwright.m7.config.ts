import { defineConfig, devices } from "@playwright/test";

const port = process.env.M7_WALKTHROUGH_PORT ?? "5177";
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results/m7-walkthrough",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report/m7" }]],
  fullyParallel: false,
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "m7-mobile-chromium",
      use: {
        ...devices["Pixel 5"],
        browserName: "chromium",
      },
    },
  ],
  webServer: {
    command: `pnpm exec vite --host 127.0.0.1 --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
