import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
const old = JSON.parse(readFileSync(resolve("../content/sound_compare_pairs_candidate.json"), "utf8"));
const next = JSON.parse(readFileSync(resolve("../content/sound_compare_next_pairs_candidate.json"), "utf8"));
const newIds = new Set<string>(next.pairs.flatMap((p: { members: { word_id: string }[] }) => p.members.map(m => m.word_id)));
function disableCandidate() {
  return JSON.parse(execFileSync("uv", ["run", "--frozen", "python", "-c", `
import json,os,sys,sqlite3
from pathlib import Path
root=Path.cwd().parent
sys.path[:0]=[str(root/'frontend/tests/e2e/support'),str(root/'backend/scripts')]
from candidate_content_fixture import set_next_pairs
path=Path(os.environ['CORE100_REAL_DB_PATH']).resolve(strict=True)
with sqlite3.connect(path) as conn:
 result=set_next_pairs(conn,Path(os.environ['CORE100_REAL_AUDIO_DIR']),False)
 if result['status'] != 'blocked_unfinished_sessions':
  evidence=Path(str(path)+'.evidence.json')
  assert evidence.resolve().parent==path.parent
  evidence.write_bytes((root/'content/sound_compare_pairs_candidate.json').read_bytes())
print(json.dumps(result))
`], { cwd: "../backend", encoding: "utf8", env: process.env }).trim());
}

test("six-group offline evidence preserves old feedback and disables only the two new groups", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const ended: string[] = [];
    (window as unknown as { __nextPairEnded: string[] }).__nextPairEnded = ended;
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
  const started = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
  await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
  const group = await (await started).json();
  expect(group.items).toHaveLength(12);
  expect(newIds.size).toBe(4);
  const pairs = [...old.pairs, ...next.pairs];
  let oldReplay: object | null = null;
  let newReplay: object | null = null;
  for (const [index, item] of group.items.entries()) {
    await expect(page.locator(".word-text")).toContainText(item.word);
    const pair = pairs.find(p => p.members.some((m: { word_id: string }) => m.word_id === item.word_id));
    const partner = pair.members.find((m: { word_id: string }) => m.word_id !== item.word_id);
    expect(item.question.choices).toContain(partner.ipa_us);
    await expect(page.getByLabel("Sound comparison", { exact: true })).toHaveCount(0);
    if (newIds.has(item.word_id)) {
      await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
      await expect.poll(() => page.evaluate((url: string) =>
        (window as unknown as { __nextPairEnded: string[] }).__nextPairEnded.some(src => src.endsWith(url)), item.audio_url)).toBeTruthy();
    }
    const submitted = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
    await page.getByRole("button", { name: `Select ${item.display_ipa}`, exact: true }).click();
    const answer = await (await submitted).json();
    expect(answer.is_correct).toBe(true);
    expect(answer.sound_compare.status).toBe("available");
    expect(answer.sound_compare.counterpart.word_id).toBe(partner.word_id);
    if (newIds.has(item.word_id)) {
      expect(answer.sound_compare.contrast.position).toBe(["fun", "sun"].includes(item.word_id) ? "initial" : "final");
    }
    const replay = { session_item_id: item.session_item_id, selected_answer: item.display_ipa };
    if (newIds.has(item.word_id)) newReplay = replay;
    else oldReplay = replay;
    if (index === 0) {
      expect(disableCandidate()).toEqual({ status: "blocked_unfinished_sessions", updated: 0, blocked_sessions: 1 });
      await page.waitForTimeout(1700);
    }
    await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    if (index === 0) {
      await page.reload();
      const resumed = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
      await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
      expect((await (await resumed).json()).group_id).toBe(group.group_id);
      expect((await (await page.request.post("/api/attempt", { data: replay })).json()).replayed).toBe(true);
    }
  }
  await expect(page.getByText("12 / 12 correct", { exact: true })).toBeVisible();
  expect(disableCandidate().updated).toBe(4);
  const previous = await (await page.request.post("/api/attempt", { data: oldReplay! })).json();
  expect(previous.replayed).toBe(true);
  expect(previous.sound_compare.status).toBe("available");
  const candidate = await (await page.request.post("/api/attempt", { data: newReplay! })).json();
  expect(candidate.replayed).toBe(true);
  expect(candidate.sound_compare.status).toBe("unavailable");
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(13);
  const newGroup = await (await page.request.post("/api/practice/minimal-pairs")).json();
  expect(newGroup.items).toHaveLength(8);
  expect(newGroup.items.every((i: { word_id: string }) => !newIds.has(i.word_id))).toBe(true);
  expect((await (await page.request.get("/api/listening/current")).json()).enabled).toBe(false);
});
