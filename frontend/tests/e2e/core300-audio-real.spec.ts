import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const manifest = JSON.parse(readFileSync(resolve("../deploy/jingyun/core300-content-audio.manifest.json"), "utf8"));
const newIds = new Set<string>(manifest.build.new_word_ids);

test("Core300 new licensed recording loads, plays and persists through normal resume", async ({ page, request }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const ended: string[] = [];
    (window as unknown as { __core300Ended: string[] }).__core300Ended = ended;
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
  await expect(page.getByText("Today practice hub")).toBeVisible();
  const started = page.waitForResponse(r => r.url().endsWith("/api/practice/next-normal"));
  await page.getByRole("button", { name: "Start Entry group", exact: true }).click();
  const group = await (await started).json();
  expect(group.group_type).toBe("normal");
  expect(group.items).toHaveLength(12);
  expect(group.items.every((item: { word_id: string }) => newIds.has(item.word_id))).toBe(true);
  expect(group.items.every((item: { audio_url: string }) => item.audio_url)).toBe(true);
  const targetIndex = group.items.findIndex((item: { word_id: string }) => newIds.has(item.word_id));
  expect(targetIndex).toBeGreaterThanOrEqual(0);
  for (const item of group.items.slice(0, targetIndex)) {
    const graded = await page.request.post("/api/attempt", { data: {
      session_item_id: item.session_item_id, selected_answer: item.display_ipa,
    } });
    expect((await graded.json()).is_correct).toBe(true);
  }
  await page.reload();
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  const item = group.items[targetIndex];
  await expect(page.locator(".word-text")).toContainText(item.word);
  const asset = manifest.audio.assets.find((entry: { word_id: string }) => entry.word_id === item.word_id);
  const media = await page.request.get(item.audio_url);
  expect(media.status()).toBe(200);
  expect(media.headers()["content-type"]).toContain("audio/mpeg");
  const bytes = await media.body();
  expect(bytes.length).toBe(asset.bytes);
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(asset.sha256);
  await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
  await expect.poll(() => page.evaluate((url: string) =>
    (window as unknown as { __core300Ended: string[] }).__core300Ended.some(src => src.endsWith(url)),
    item.audio_url)).toBeTruthy();
  const submitted = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
  await page.getByRole("button", { name: `Select ${item.display_ipa}`, exact: true }).click();
  expect((await (await submitted).json()).is_correct).toBe(true);
  await page.reload();
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  const resumed = await (await page.request.get("/api/today")).json();
  expect(resumed.group_id).toBe(group.group_id);
  expect(resumed.resume_index).toBe(targetIndex + 1);
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(99 + targetIndex + 1);
  expect((await page.request.get("/audio/us/wood.mp3")).status()).toBe(404);
  expect((await page.request.get("/audio/us/feb.mp3")).status()).toBe(404);
  expect((await (await page.request.get("/api/listening/current")).json()).enabled).toBe(false);
  await request.post("/api/auth/login", { data: { username: "workflow-owner", password: "local-only-workflow" } });
  expect((await (await request.get("/api/progress")).json()).total_attempts).toBe(1);
});
