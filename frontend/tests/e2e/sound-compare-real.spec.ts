import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";

function setFixturePartnerStatus(status: string): string {
  const result = execFileSync("uv", ["run", "--frozen", "python", "-c", `
import json, os, sqlite3, tempfile
from pathlib import Path
path = Path(os.environ["CORE100_REAL_DB_PATH"]).resolve(strict=True)
roots = (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
if not any(root in path.parents for root in roots):
    raise ValueError("comparison failure probe requires a temporary fixture")
with sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True) as conn:
    if not conn.execute("SELECT 1 FROM users WHERE username='workflow-owner'").fetchone():
        raise ValueError("not the synthetic workflow fixture")
    old = conn.execute("SELECT content_status FROM words WHERE id='game'").fetchone()[0]
    conn.execute("UPDATE words SET content_status=? WHERE id='game'", (os.environ["PAIR_TEST_STATUS"],))
    print(json.dumps(old))
`], { cwd: "../backend", encoding: "utf8", env: { ...process.env, PAIR_TEST_STATUS: status } });
  return JSON.parse(result.trim());
}

test("opt-in eight-word comparison uses real recordings and returns to the selected normal mode", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const ended: string[] = [];
    (window as unknown as { __comparisonEnded: string[] }).__comparisonEnded = ended;
    const nativePlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      this.addEventListener("ended", () => { if (this.currentTime > 0) ended.push(this.src); });
      return nativePlay.call(this);
    };
  });
  await page.goto("/");
  await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
  await page.getByLabel("Username").fill("workflow-owner");
  await page.getByLabel("Password").fill("local-only-workflow");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Today practice hub")).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: /IPA to word/ }).click();
  await expect(page.getByText("Saved")).toBeVisible();
  await page.getByRole("spinbutton").fill("8");
  const saved = page.waitForResponse(r => r.url().endsWith("/api/settings") && r.request().method() === "PUT");
  await page.getByRole("spinbutton").press("Tab");
  expect((await saved).ok()).toBeTruthy();
  await page.getByRole("button", { name: "Today", exact: true }).click();
  const started = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
  await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
  const response = await started;
  expect(response.ok()).toBeTruthy();
  const group = await response.json();
  expect(group.group_type).toBe("minimal_pair");
  expect(group.items.map((item: { word_id: string }) => item.word_id).sort()).toEqual(["back", "bag", "came", "cat", "game", "hat", "map", "match"]);
  expect(group.items.every((item: { question: { type: string } }) => item.question.type === "choose_ipa")).toBe(true);
  await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Today practice hub")).toBeVisible();
  const originalStatus = setFixturePartnerStatus("disabled");
  try {
    const failed = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
    await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
    expect((await (await failed).json()).error).toBe("CONTENT_NOT_READY");
    await expect(page.locator(".save-error")).toContainText("CONTENT_NOT_READY");
    await expect(page.getByText("Today practice hub")).toBeVisible();
    await expect(page.getByRole("button", { name: /^Select / })).toHaveCount(0);
    expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(0);
  } finally {
    setFixturePartnerStatus(originalStatus);
  }
  const resumedRequest = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
  await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
  const resumed = await (await resumedRequest).json();
  expect(resumed.group_id).toBe(group.group_id);
  expect(resumed.items.map((item: { question: unknown }) => item.question)).toEqual(
    group.items.map((item: { question: unknown }) => item.question));
  const partnerIds: Record<string, string> = {
    came: "game", game: "came", back: "bag", bag: "back",
    cat: "hat", hat: "cat", map: "match", match: "map",
  };
  const phones: Record<string, string> = {
    came: "/k/", game: "/g/", back: "/k/", bag: "/g/",
    cat: "/k/", hat: "/h/", map: "/p/", match: "/tʃ/",
  };
  const initialIds = new Set(["came", "game", "cat", "hat"]);
  const missedIds = new Set(["back", "cat", "map"]);
  for (const [index, item] of group.items.entries()) {
    await expect(page.getByText(`Sound Compare group: ${index + 1} / 8`, { exact: true })).toBeVisible();
    const partner = group.items.find((other: { word_id: string }) => other.word_id === partnerIds[item.word_id]);
    expect(partner).toBeTruthy();
    expect(item.question.choices).toContain(partner.display_ipa);
    expect(item.question.choices).toContain(item.display_ipa);
    expect(new Set(item.question.choices).size).toBe(4);
    await expect(page.getByRole("button", { name: `Select ${partner.display_ipa}`, exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
    await expect.poll(() => page.evaluate((url: string) =>
      (window as unknown as { __comparisonEnded: string[] }).__comparisonEnded.some(src => src.endsWith(url)),
      item.audio_url)).toBeTruthy();
    await expect(page.getByLabel("Sound comparison", { exact: true })).toHaveCount(0);
    const wrong = missedIds.has(item.word_id);
    const answer = wrong ? partner.display_ipa : item.display_ipa;
    const submitted = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
    await page.getByRole("button", { name: `Select ${answer}`, exact: true }).click();
    const grading = await (await submitted).json();
    expect(grading.is_correct).toBe(!wrong);
    expect(grading.sound_compare.status).toBe("available");
    expect(grading.sound_compare.contrast).toEqual({
      position: initialIds.has(item.word_id) ? "initial" : "final",
      current_phoneme: phones[item.word_id], counterpart_phoneme: phones[partner.word_id],
    });
    const feedback = page.getByLabel("Sound comparison", { exact: true });
    await expect(feedback).toContainText(item.word);
    await expect(feedback).toContainText(partner.word);
    await expect(feedback).toContainText(item.display_ipa);
    await expect(feedback).toContainText(partner.display_ipa);
    await expect(feedback).toContainText(initialIds.has(item.word_id) ? "Initial sound" : "Final sound");
    await page.waitForTimeout(1700);
    await expect(feedback).toBeVisible();
    const replay = await page.request.post("/api/attempt", { data: {
      session_item_id: item.session_item_id, selected_answer: answer,
    } });
    expect(replay.ok()).toBeTruthy();
    const replayed = await replay.json();
    expect(replayed.replayed).toBe(true);
    expect(replayed.sound_compare).toEqual(grading.sound_compare);
    expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(index + 1);
    if (wrong) {
      await expect(page.getByText("Not quite.")).toBeVisible();
    }
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    if (index === 0) {
      await page.reload();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
      expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(1);
    }
  }
  await expect(page.getByRole("heading", { name: "Sound Compare group complete" })).toBeVisible();
  await expect(page.getByText("5 / 8 correct", { exact: true })).toBeVisible();
  const progress = await (await page.request.get("/api/progress")).json();
  expect(progress.total_attempts).toBe(8);
  expect(progress.level_stats.entry.completed_normal_groups).toBe(0);
  await page.screenshot({ path: test.info().outputPath("comparison-summary.png"), fullPage: true });
  await page.getByRole("button", { name: "Start next Entry group", exact: true }).click();
  await expect(page.getByText("Which word matches this IPA?")).toBeVisible();
  const normal = await (await page.request.get("/api/today")).json();
  expect(normal.group_type).toBe("normal");
  expect(normal.practice_mode).toBe("choose_word");
  expect(normal.items).toHaveLength(8);
  await page.reload();
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  expect((await (await page.request.get("/api/today")).json()).group_id).toBe(normal.group_id);
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(8);
});
