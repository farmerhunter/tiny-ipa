import { expect, type Page, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const manifest = JSON.parse(readFileSync(resolve("../deploy/jingyun/core100-content-audio.manifest.json"), "utf8"));
const original = JSON.parse(readFileSync(resolve("../deploy/jingyun/p1b-content-audio.manifest.json"), "utf8"));
const oldIds = new Set<string>(original.audio.required_word_ids);

type Playback = { src: string; played: boolean; ended: boolean; maxTime: number; error: boolean };

async function state(page: Page, path: string) {
  const response = await page.request.get(`/api/${path}`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function signIn(page: Page) {
  await page.getByLabel("Username").fill("core100-owner");
  await page.getByLabel("Password").fill("local-only-core100");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".account-menu")).toContainText("core100-owner");
  await expect(page.getByText("Today practice hub")).toBeVisible();
}

async function chooseCorrect(page: Page) {
  const today = await state(page, "today");
  const item = today.items[today.resume_index ?? 0];
  await page.getByRole("button", { name: `Select ${item.display_ipa}`, exact: true }).click();
}

test("real packaged audio and attempts survive reload and logout/relogin", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const records: Playback[] = [];
    (window as unknown as { __core100Playback: Playback[] }).__core100Playback = records;
    const nativePlay = HTMLMediaElement.prototype.play;
    // Observe the native decoder/player; delegate without faking media events or promises.
    HTMLMediaElement.prototype.play = function () {
      const entry = { src: this.src, played: false, ended: false, maxTime: 0, error: false };
      records.push(entry);
      this.addEventListener("playing", () => { entry.played = true; });
      this.addEventListener("timeupdate", () => { entry.maxTime = Math.max(entry.maxTime, this.currentTime); });
      this.addEventListener("ended", () => { entry.ended = true; entry.maxTime = this.currentTime; });
      this.addEventListener("error", () => { entry.error = true; });
      return nativePlay.call(this);
    };
  });

  await page.goto("/");
  await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
  expect((await page.request.get("/api/progress")).status()).toBe(401);
  await signIn(page);
  const credits = await page.request.get(manifest.audio.credits.public_url);
  expect(credits.status()).toBe(200);
  expect(createHash("sha256").update(await credits.body()).digest("hex")).toBe(manifest.audio.credits.sha256);
  expect((await state(page, "progress")).total_attempts).toBe(0);
  await page.getByRole("button", { name: "Start Entry group", exact: true }).click();
  await expect(page.getByText("Practice group: 1 / 12", { exact: true })).toBeVisible();
  const first = await state(page, "today");
  expect(first.items).toHaveLength(12);
  expect(new Set(first.items.map((item: { word_id: string }) => item.word_id)).size).toBe(12);
  expect(first.items.filter((item: { word_id: string }) => !oldIds.has(item.word_id)).length).toBeGreaterThanOrEqual(2);
  const groupId = first.group_id;
  await chooseCorrect(page);
  await expect(page.getByText("Practice group: 2 / 12", { exact: true })).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  await expect(page.getByText("Practice group: 2 / 12", { exact: true })).toBeVisible();
  expect((await state(page, "today")).group_id).toBe(groupId);
  expect((await state(page, "progress")).total_attempts).toBe(1);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to practice" })).toBeVisible();
  expect((await page.request.get("/api/progress")).status()).toBe(401);
  await signIn(page);
  const resumed = await state(page, "today");
  expect(resumed.group_id).toBe(groupId);
  expect(resumed.resume_index).toBe(1);
  expect((await state(page, "progress")).resumable_normal_groups).toBe(1);
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();

  let playedExpansion = false;
  for (let index = 1; index < 12; index++) {
    await expect(page.getByText(`Practice group: ${index + 1} / 12`, { exact: true })).toBeVisible();
    const today = await state(page, "today");
    const item = today.items[today.resume_index];
    expect(item.audio_url).toBe(`/audio/us/${item.word_id}.mp3`);
    if (!playedExpansion && !oldIds.has(item.word_id)) {
      const asset = manifest.audio.assets.find((entry: { word_id: string }) => entry.word_id === item.word_id);
      expect(asset).toBeTruthy();
      const response = await page.request.get(item.audio_url);
      expect(response.status()).toBe(200);
      expect(response.headers()["content-type"]).toContain("audio/mpeg");
      expect(createHash("sha256").update(await response.body()).digest("hex")).toBe(asset.sha256);
      await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
      await expect.poll(() => page.evaluate((url: string) =>
        (window as unknown as { __core100Playback: Playback[] }).__core100Playback.some(
          (entry) => entry.src.endsWith(url) && entry.played && entry.ended && entry.maxTime > 0 && !entry.error,
        ), item.audio_url), { timeout: 10_000 }).toBeTruthy();
      const media = await page.evaluate(() => (window as unknown as { __core100Playback: Playback[] }).__core100Playback);
      await test.info().attach("native-recorded-playback", { body: JSON.stringify(media), contentType: "application/json" });
      await expect(page.locator(".audio-source-label")).not.toContainText(/browser|fallback/i);
      playedExpansion = true;
    }
    await chooseCorrect(page);
  }
  expect(playedExpansion).toBeTruthy();
  await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible();
  const progress = await state(page, "progress");
  expect(progress.total_attempts).toBe(12);
  expect(progress.resumable_normal_groups).toBe(0);
  expect(progress.level_stats.entry.completed_normal_groups).toBe(1);
  await page.getByRole("button", { name: "Progress", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
  await expect(page.locator(".stat-card").filter({ has: page.getByText("all-time answered items", { exact: true }) }).locator(".stat-number")).toHaveText("12");
  await expect(page.locator(".stat-card").filter({ has: page.getByText("all-time completed regular groups", { exact: true }) }).locator(".stat-number")).toHaveText("1");
  await page.screenshot({ path: test.info().outputPath("completed-progress.png"), fullPage: true });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page);
  expect((await state(page, "progress")).total_attempts).toBe(12);
  await page.reload();
  expect((await state(page, "progress")).level_stats.entry.completed_normal_groups).toBe(1);
  await page.getByRole("button", { name: "Progress", exact: true }).click();
  await expect(page.locator(".stat-card").filter({ has: page.getByText("all-time answered items", { exact: true }) }).locator(".stat-number")).toHaveText("12");
});
