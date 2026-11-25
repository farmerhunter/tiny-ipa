import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
import { realpathSync } from "node:fs";
import { tmpdir } from "node:os";
const nextAudio = process.env.NEXT_AUDIO_REAL === "true";
const nextPairs = process.env.NEXT_PAIRS_REAL === "true";
const recovery = process.env.CONTENT_RECOVERY_REAL === "true";
const activation = process.env.CONTENT_ACTIVATION_REAL === "true";
const pairCandidate = process.env.CORE100_REAL_PAIR_CANDIDATE === "true";
const core300Candidate = process.env.CORE300_REAL_CANDIDATE === "true";
const levelAccounts = process.env.CORE100_REAL_LEVEL_ACCOUNTS === "true";
if ([pairCandidate, core300Candidate, levelAccounts, activation, recovery, nextAudio, nextPairs].filter(Boolean).length > 1) throw new Error("Choose one isolated fixture scenario");
const suiteName = nextAudio ? "next-audio" : nextPairs ? "next-pairs" : recovery ? "activated-recovery" : activation ? "content-activation" : core300Candidate ? "core300-audio-candidate" : levelAccounts ? "level-account-real" : pairCandidate ? "sound-compare-candidate" : "core100-real";
const frontendPort = Number(process.env.CORE100_REAL_FRONTEND_PORT ?? "5185");
const backendPort = Number(process.env.CORE100_REAL_BACKEND_PORT ?? "8035");
for (const port of [frontendPort, backendPort]) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid test port");
}
const runId = `${Date.now()}-${process.pid}`;
const recoveryRoot = process.env.CONTENT_RECOVERY_ROOT ?? resolve(realpathSync(tmpdir()), `tiny-ipa-recovery-${runId}`);
process.env.CONTENT_RECOVERY_ROOT = recoveryRoot;
const dbPath = process.env.CORE100_REAL_DB_PATH ?? (recovery ? resolve(recoveryRoot, "restored/tiny-ipa.sqlite") : `/tmp/tiny-ipa-core100-${runId}.sqlite`);
process.env.CORE100_REAL_DB_PATH = dbPath;
const audioRoot = process.env.CORE100_REAL_AUDIO_DIR ?? (recovery ? resolve(recoveryRoot, "restored/audio") : resolve(realpathSync(tmpdir()), `tiny-ipa-core100-${runId}-audio`));
process.env.CORE100_REAL_AUDIO_DIR = audioRoot;
const evidencePath = recovery ? resolve(recoveryRoot, "restored/evidence.json") : nextPairs ? `${dbPath}.evidence.json` : (pairCandidate || activation || nextAudio ? resolve("../content/sound_compare_pairs_candidate.json") : "");
process.env.CONTENT_RECOVERY_RECEIPT = resolve(recoveryRoot, "recovery-receipt.json");
const frontendURL = `http://127.0.0.1:${frontendPort}`;
export default defineConfig({
  testDir: "./tests/e2e", testMatch: nextAudio ? ["next-audio-real.spec.ts"] : nextPairs ? ["next-pairs-real.spec.ts"] : recovery ? ["activated-recovery-real.spec.ts"] : activation ? ["content-activation-real.spec.ts"] : core300Candidate ? ["core300-audio-real.spec.ts"] : levelAccounts ? ["level-account-real.spec.ts"] : pairCandidate ? ["sound-compare-real.spec.ts"] : ["core100-real-workflow.spec.ts", "listening-real-workflow.spec.ts", "m13-real-practice-mode.spec.ts"],
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
        CONTENT_RECOVERY_REAL: String(recovery),
        NEXT_AUDIO_REAL: String(nextAudio), NEXT_PAIRS_REAL: String(nextPairs),
        CORE300_REAL_CANDIDATE: String(core300Candidate),
        TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH: evidencePath,
        CORE100_REAL_LEVEL_ACCOUNTS: String(levelAccounts),
        TINY_IPA_AUDIO_DIR: audioRoot, CORE100_REAL_AUDIO_DIR: audioRoot,
        TINY_IPA_REQUIRE_PACKAGED_AUDIO: levelAccounts ? "false" : "true", TINY_IPA_ENABLE_LISTENING_PREVIEW: core300Candidate || activation || recovery || nextAudio || nextPairs ? "false" : "true",
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
