import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
import { realpathSync } from "node:fs";
import { tmpdir } from "node:os";
const activation = process.env.CONTENT_ACTIVATION_REAL === "true";
const pairCandidate = process.env.CORE100_REAL_PAIR_CANDIDATE === "true";
const core300Candidate = process.env.CORE300_REAL_CANDIDATE === "true";
const levelAccounts = process.env.CORE100_REAL_LEVEL_ACCOUNTS === "true";
if ([pairCandidate, core300Candidate, levelAccounts, activation].filter(Boolean).length > 1) throw new Error("Choose one isolated fixture scenario");
const suiteName = activation ? "content-activation" : core300Candidate ? "core300-audio-candidate" : levelAccounts ? "level-account-real" : pairCandidate ? "sound-compare-candidate" : "core100-real";
const frontendPort = Number(process.env.CORE100_REAL_FRONTEND_PORT ?? "5185");
const backendPort = Number(process.env.CORE100_REAL_BACKEND_PORT ?? "8035");
for (const port of [frontendPort, backendPort]) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid test port");
}
const runId = `${Date.now()}-${process.pid}`;
const dbPath = process.env.CORE100_REAL_DB_PATH ?? `/tmp/tiny-ipa-core100-${runId}.sqlite`;
process.env.CORE100_REAL_DB_PATH = dbPath;
const audioRoot = process.env.CORE100_REAL_AUDIO_DIR ?? resolve(realpathSync(tmpdir()), `tiny-ipa-core100-${runId}-audio`);
process.env.CORE100_REAL_AUDIO_DIR = audioRoot;
const frontendURL = `http://127.0.0.1:${frontendPort}`;
export default defineConfig({
  testDir: "./tests/e2e", testMatch: activation ? ["content-activation-real.spec.ts"] : core300Candidate ? ["core300-audio-real.spec.ts"] : levelAccounts ? ["level-account-real.spec.ts"] : pairCandidate ? ["sound-compare-real.spec.ts"] : ["core100-real-workflow.spec.ts", "listening-real-workflow.spec.ts", "m13-real-practice-mode.spec.ts"],
  outputDir: `./test-results/${suiteName}`,
  reporter: [["list"], ["html", { open: "never", outputFolder: `playwright-report/${suiteName}` }]],
  workers: 1,
  use: { baseURL: frontendURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "core100-real-mobile-chromium", use: { ...devices["Pixel 5"] } }],
  webServer: [
    {
      command: `cd ../backend && uv run --frozen --extra dev python ../frontend/tests/e2e/support/prepare_core100_real_db.py && uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/health`, reuseExistingServer: false, timeout: 120_000,
      env: {
        TINY_IPA_DB_PATH: dbPath, CORE100_REAL_DB_PATH: dbPath,
        CORE100_REAL_PAIR_CANDIDATE: String(pairCandidate),
        CONTENT_ACTIVATION_REAL: String(activation),
        CORE300_REAL_CANDIDATE: String(core300Candidate),
        TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH: pairCandidate || activation ? resolve("../content/sound_compare_pairs_candidate.json") : "",
        CORE100_REAL_LEVEL_ACCOUNTS: String(levelAccounts),
        TINY_IPA_AUDIO_DIR: audioRoot, CORE100_REAL_AUDIO_DIR: audioRoot,
        TINY_IPA_REQUIRE_PACKAGED_AUDIO: levelAccounts ? "false" : "true", TINY_IPA_ENABLE_LISTENING_PREVIEW: core300Candidate || activation ? "false" : "true",
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
