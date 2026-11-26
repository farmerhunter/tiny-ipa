import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const manifest = JSON.parse(readFileSync(resolve("../content/core300_next_audio_candidate.json"), "utf8"));
test("three new licensed candidates play and preserve prior learning; wood stays deferred", async ({ page }) => {
  await page.addInitScript(() => {
    const ended: string[] = [];
    (window as unknown as { __nextAudioEnded: string[] }).__nextAudioEnded = ended;
    const nativePlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      this.addEventListener("ended", () => { if (this.currentTime > 0) ended.push(this.src); });
      return nativePlay.call(this);
    };
  });
  await page.goto("/");
  await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
  await page.getByLabel("Username").fill("core100-owner");
  await page.getByLabel("Password").fill("local-only-core100");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const started = page.waitForResponse(r => r.url().endsWith("/api/practice/next-normal"));
  await page.getByRole("button", { name: "Start Entry group", exact: true }).click();
  const group = await (await started).json();
  expect(group.items.map((i: { word_id: string }) => i.word_id).sort()).toEqual(["better", "family", "how"]);
  for (const [index, item] of group.items.entries()) {
    await expect(page.locator(".word-text")).toContainText(item.word);
    const asset = manifest.selected_new_words.find((a: { word_id: string }) => a.word_id === item.word_id);
    const response = await page.request.get(item.audio_url);
    const bytes = await response.body();
    expect(response.status()).toBe(200);
    expect(bytes.length).toBe(asset.bytes);
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(asset.sha256);
    await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
    await expect.poll(() => page.evaluate((url: string) =>
      (window as unknown as { __nextAudioEnded: string[] }).__nextAudioEnded.some(src => src.endsWith(url)), item.audio_url)).toBeTruthy();
    const graded = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
    await page.getByRole("button", { name: `Select ${item.display_ipa}`, exact: true }).click();
    expect((await (await graded).json()).is_correct).toBe(true);
    if (index === 0) {
      await page.reload();
      await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
      const resumed = await (await page.request.get("/api/today")).json();
      expect(resumed.group_id).toBe(group.group_id);
      expect(resumed.resume_index).toBe(1);
    }
  }
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(114);
  const credits = await page.request.get(`/audio/${manifest.credits.path}`);
  expect(credits.status()).toBe(200);
  expect(createHash("sha256").update(await credits.body()).digest("hex")).toBe(manifest.credits.sha256);
  expect((await page.request.get("/audio/us/wood.mp3")).status()).toBe(404);
  expect((await (await page.request.get("/api/listening/current")).json()).enabled).toBe(false);
});
