import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

test("backup rebuilds activated media and resumes first-answer learning history", async ({ page }) => {
  test.setTimeout(120_000);
  const receipt = JSON.parse(readFileSync(process.env.CONTENT_RECOVERY_RECEIPT!, "utf8"));
  expect(receipt.synthetic_only).toBe(true);
  expect(receipt.source_and_restore_all_table_fingerprints_equal).toBe(true);
  expect(receipt.fresh_pair_plan_noop).toBe(true);
  expect(receipt.fresh_insert_plan_noop).toBe(true);
  expect(receipt.source_database).not.toBe(receipt.restored_database);
  expect(receipt.source_audio).not.toBe(receipt.restored_audio);
  await page.addInitScript(() => {
    const ended: string[] = [];
    (window as unknown as { __recoveryEnded: string[] }).__recoveryEnded = ended;
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
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(101);
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  const normal = await (await page.request.get("/api/today")).json();
  expect(normal.group_id).toBe(receipt.normal_group.group_id);
  expect(normal.resume_index).toBe(1);
  expect(normal.items.map((i: { word_id: string }) => i.word_id)).toEqual(
    receipt.normal_group.items.map((i: { word_id: string }) => i.word_id));
  await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
  const normalItem = normal.items[1];
  await expect.poll(() => page.evaluate((url: string) =>
    (window as unknown as { __recoveryEnded: string[] }).__recoveryEnded.some(src => src.endsWith(url)), normalItem.audio_url)).toBeTruthy();
  await page.reload();
  await expect(page.getByText("Today practice hub")).toBeVisible();
  const resumedRequest = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
  await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
  const group = await (await resumedRequest).json();
  expect(group.group_id).toBe(receipt.pair_group.group_id);
  expect(group.resume_index).toBe(1);
  expect(group.items.map((i: { question: unknown }) => i.question)).toEqual(
    receipt.pair_group.items.map((i: { question: unknown }) => i.question));
  const replay = await (await page.request.post("/api/attempt", { data: receipt.first_answer_payload })).json();
  expect(replay.replayed).toBe(true);
  expect(replay.is_correct).toBe(false);
  expect(replay.sound_compare).toEqual(receipt.first_answer_result.sound_compare);
  expect((await page.request.post("/api/attempt", { data: {
    session_item_id: receipt.first_answer_payload.session_item_id,
    selected_answer: group.items[0].display_ipa,
  } })).status()).toBe(409);
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(101);
  for (const [index, item] of group.items.slice(1).entries()) {
    await expect(page.getByLabel("Sound comparison", { exact: true })).toHaveCount(0);
    if (index === 0) {
      const bytes = await (await page.request.get(item.audio_url)).body();
      const local = readFileSync(`${receipt.restored_audio}/${item.audio_url.replace("/audio/", "")}`);
      expect(createHash("sha256").update(bytes).digest("hex")).toBe(createHash("sha256").update(local).digest("hex"));
      await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
      await expect.poll(() => page.evaluate((url: string) =>
        (window as unknown as { __recoveryEnded: string[] }).__recoveryEnded.some(src => src.endsWith(url)), item.audio_url)).toBeTruthy();
    }
    const submitted = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
    await page.getByRole("button", { name: `Select ${item.display_ipa}`, exact: true }).click();
    const grade = await (await submitted).json();
    expect(grade.is_correct).toBe(true);
    expect(grade.sound_compare.status).toBe("available");
    await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
  }
  await expect(page.getByRole("heading", { name: "Sound Compare group complete" })).toBeVisible();
  await expect(page.getByText("7 / 8 correct", { exact: true })).toBeVisible();
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(108);
  expect((await (await page.request.get("/api/listening/current")).json()).enabled).toBe(false);
  await page.getByRole("button", { name: "Start next Entry group", exact: true }).click();
  expect((await (await page.request.get("/api/today")).json()).group_id).toBe(receipt.normal_group.group_id);
  await page.screenshot({ path: test.info().outputPath("restored-normal-resume.png"), fullPage: true });
});
