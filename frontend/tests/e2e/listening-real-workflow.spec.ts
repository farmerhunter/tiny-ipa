import { expect, test, type Page } from "@playwright/test";
import { renameSync } from "node:fs";
import { join } from "node:path";

async function state(page: Page) {
  const response = await page.request.get("/api/listening/current");
  expect(response.status()).toBe(200);
  return (await response.json()).lesson;
}
async function signIn(page: Page) {
  await page.getByLabel("Username").fill("core100-owner");
  await page.getByLabel("Password").fill("local-only-core100");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".account-menu")).toContainText("core100-owner");
}
async function enter(page: Page) {
  await page.getByRole("button", { name: "Listening lesson (preview)", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Listening lesson (preview)" })).toBeVisible();
}
async function hear(page: Page) {
  await page.getByRole("button", { name: "Play question recording", exact: true }).click();
  await expect(page.getByText("Choose the word you heard.", { exact: true })).toBeVisible();
  await expect(page.locator(".listening-preview .choice-btn").first()).toBeEnabled();
}

test("native listening, failed playback, resume, first answers and independent summary", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const records: { ended: boolean; time: number }[] = [];
    (window as unknown as { __listeningMedia: typeof records }).__listeningMedia = records;
    const original = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      const result = { ended: false, time: 0 }; records.push(result);
      this.addEventListener("ended", () => { result.ended = true; result.time = this.currentTime; });
      return original.call(this);
    };
  });
  await page.goto("/");
  await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
  await signIn(page);
  const baseline = await (await page.request.get("/api/progress")).json();
  await enter(page);
  await expect(page.getByText(/not yet phonetically certified/)).toBeVisible();
  await page.getByRole("button", { name: "Begin eight questions" }).click();
  const first = await state(page);
  const id = first.id;
  await expect(page.locator(".listening-preview .choice-btn").first()).toBeDisabled();
  await expect(page.locator(".listening-feedback-ipa")).toHaveCount(0);
  const mediaPath = join(process.env.CORE100_REAL_AUDIO_DIR!, first.item.audio_url.replace("/audio/", ""));
  renameSync(mediaPath, `${mediaPath}.held`);
  try {
    await page.getByRole("button", { name: "Play question recording", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Recording unavailable");
    await expect(page.locator(".listening-preview .choice-btn").first()).toBeDisabled();
    expect((await state(page)).summary.total).toBe(0);
  } finally { renameSync(`${mediaPath}.held`, mediaPath); }
  await hear(page);
  const target = first.item.audio_url.split("/").at(-1).replace(".mp3", "");
  const wrong = first.item.choices.find((w: string) => w !== target);
  await page.getByRole("button", { name: wrong, exact: true }).click();
  await expect(page.getByRole("status")).toContainText(`The recording was: ${target}`);
  await expect(page.locator(".listening-feedback-ipa")).toHaveText((await state(page)).item.feedback.ipa);
  await expect(page.getByRole("status")).toContainText("word-initial /k/ and /g/");
  const retry = await page.request.post(`/api/listening/lessons/${id}/actions`, { data: {
    action: "answer", index: 0, selected_answer: wrong,
  } });
  expect((await retry.json()).replayed).toBe(true);
  expect((await state(page)).summary.total).toBe(1);
  await expect.poll(() => page.evaluate(() =>
    (window as unknown as { __listeningMedia: { ended: boolean; time: number }[] }).__listeningMedia.some((m) => m.ended && m.time > 0),
  )).toBe(true);
  await page.getByRole("button", { name: "Continue listening", exact: true }).click();
  await page.reload();
  await enter(page);
  expect((await state(page)).id).toBe(id);
  await expect(page.getByRole("heading", { name: "Listening question 2 / 8" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page);
  await enter(page);
  expect((await state(page)).cursor).toBe(1);
  for (let i = 1; i < 8; i++) {
    await hear(page);
    const current = await state(page);
    const word = current.item.audio_url.split("/").at(-1).replace(".mp3", "");
    await page.getByRole("button", { name: word, exact: true }).click();
    await expect(page.getByRole("status")).toContainText(`Correct: ${word}`);
    await expect(page.locator(".listening-feedback-ipa")).toHaveText((await state(page)).item.feedback.ipa);
    if (i >= 4) await expect(page.getByRole("status")).toContainText("word-final /k/ and /g/");
    await page.getByRole("button", { name: "Continue listening", exact: true }).click();
  }
  await expect(page.getByRole("heading", { name: "Listening group complete" })).toBeVisible();
  await expect(page.getByTestId("listening-score")).toHaveText("First answers correct: 7 / 8");
  expect(await (await page.request.get("/api/progress")).json()).toEqual(baseline);
  const before = await state(page);
  await page.getByRole("button", { name: `Play ${target}`, exact: true }).click();
  await expect.poll(() => page.getByRole("button", { name: "Start another listening group" }).isEnabled()).toBe(true);
  expect((await state(page)).summary).toEqual(before.summary);
  await page.screenshot({ path: test.info().outputPath("completed-listening.png"), fullPage: true });
  await page.getByRole("button", { name: "Start another listening group" }).click();
  await expect(page.getByRole("heading", { name: "Listen to the contrast" })).toBeVisible();
  expect((await state(page)).id).not.toBe(id);
  await page.getByRole("button", { name: "← Today", exact: true }).click();
  await expect(page.getByText("Today practice hub")).toBeVisible();
});
