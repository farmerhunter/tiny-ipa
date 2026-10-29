import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const manifest = JSON.parse(readFileSync(resolve("../deploy/jingyun/core300-content-audio.manifest.json"), "utf8"));
const extraIds = new Set<string>(manifest.build.new_word_ids);
function reviewedFixtureAction(action: "disable" | "noop") {
  return JSON.parse(execFileSync("uv", ["run", "--frozen", "python", "-c", `
import json,os,sqlite3,tempfile
from pathlib import Path
import sys
root=Path.cwd().parent
sys.path.insert(0,str(root/'backend/scripts'))
from activate_sound_compare import plan as pair_plan,apply as pair_apply
from insert_core300_increment import plan as insert_plan,apply as insert_apply
path=Path(os.environ['CORE100_REAL_DB_PATH']).resolve(strict=True)
assert any(p in path.parents for p in (Path(tempfile.gettempdir()).resolve(),Path('/tmp').resolve()))
conn=sqlite3.connect(path)
conn.execute('PRAGMA foreign_keys=ON')
assert conn.execute("SELECT count(*) FROM users WHERE username='workflow-owner'").fetchone()[0]==1
assert conn.execute('SELECT count(*),count(audio_us) FROM words').fetchone()==(112,111)
audio=Path(os.environ['CORE100_REAL_AUDIO_DIR'])
if os.environ['ACTIVATION_TEST_ACTION']=='disable':
 p=pair_plan(conn,'disable',root,root/'content/sound_compare_pairs_candidate.json')
 result=pair_apply(conn,'disable',root,root/'content/sound_compare_pairs_candidate.json',None,p['plan_sha256'])
else:
 p=insert_plan(conn,root,audio)
 result=insert_apply(conn,root,audio,p['plan_sha256'])
print(json.dumps(result))
conn.close()
`], { cwd: "../backend", encoding: "utf8", env: { ...process.env, ACTIVATION_TEST_ACTION: action } }).trim());
}

test("reviewed eight-field and twelve-row plans compose with native media, resume and safe disable", async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    const ended: string[] = [];
    (window as unknown as { __activationEnded: string[] }).__activationEnded = ended;
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
  const normal = await (await started).json();
  expect(normal.items).toHaveLength(12);
  expect(normal.items.every((i: { word_id: string }) => extraIds.has(i.word_id))).toBe(true);
  const first = normal.items[0];
  const asset = manifest.audio.assets.find((a: { word_id: string }) => a.word_id === first.word_id);
  const media = await page.request.get(first.audio_url);
  const bytes = await media.body();
  expect(media.status()).toBe(200);
  expect(bytes.length).toBe(asset.bytes);
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(asset.sha256);
  await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
  await expect.poll(() => page.evaluate((url: string) =>
    (window as unknown as { __activationEnded: string[] }).__activationEnded.some(src => src.endsWith(url)), first.audio_url)).toBeTruthy();
  const answered = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
  await page.getByRole("button", { name: `Select ${first.display_ipa}`, exact: true }).click();
  expect((await (await answered).json()).is_correct).toBe(true);
  await page.reload();
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  expect((await (await page.request.get("/api/today")).json()).resume_index).toBe(1);
  expect(reviewedFixtureAction("noop").status).toBe("no_change");
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(100);
  expect((await page.request.get("/audio/us/wood.mp3")).status()).toBe(404);
  expect((await page.request.get("/audio/us/feb.mp3")).status()).toBe(404);
  await page.request.post("/api/auth/logout");
  await page.reload();
  await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
  await page.getByLabel("Username").fill("workflow-owner");
  await page.getByLabel("Password").fill("local-only-workflow");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Today practice hub")).toBeVisible();
  const settings = await page.request.put("/api/settings", { data: { daily_word_count: 8, practice_mode: "choose_word" } });
  expect(settings.ok()).toBe(true);
  expect((await settings.json()).daily_word_count).toBe(8);
  await page.reload();
  const paired = page.waitForResponse(r => r.url().endsWith("/api/practice/minimal-pairs"));
  await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
  const group = await (await paired).json();
  expect(group.items.map((i: { word_id: string }) => i.word_id).sort()).toEqual(["back", "bag", "came", "cat", "game", "hat", "map", "match"]);
  expect(reviewedFixtureAction("disable")).toEqual({ status: "blocked_unfinished_sessions", updated: 0, blocked_sessions: 1 });
  let lastPayload = {};
  for (const [index, item] of group.items.entries()) {
    await expect(page.getByLabel("Sound comparison", { exact: true })).toHaveCount(0);
    const partnerIds: Record<string, string> = { back: "bag", bag: "back", came: "game", game: "came", cat: "hat", hat: "cat", map: "match", match: "map" };
    const partner = group.items.find((i: { word_id: string }) => i.word_id === partnerIds[item.word_id]);
    expect(item.question.choices).toContain(partner.display_ipa);
    await page.getByRole("button", { name: "Play recorded pronunciation", exact: true }).click();
    await expect.poll(() => page.evaluate((url: string) =>
      (window as unknown as { __activationEnded: string[] }).__activationEnded.some(src => src.endsWith(url)), item.audio_url)).toBeTruthy();
    const graded = page.waitForResponse(r => r.url().endsWith("/api/attempt") && r.request().method() === "POST");
    await page.getByRole("button", { name: `Select ${item.display_ipa}`, exact: true }).click();
    const grade = await (await graded).json();
    expect(grade.is_correct).toBe(true);
    expect(grade.sound_compare.status).toBe("available");
    expect(grade.sound_compare.contrast.position).toBe(["came", "game", "cat", "hat"].includes(item.word_id) ? "initial" : "final");
    await expect(page.getByLabel("Sound comparison", { exact: true })).toContainText(partner.word);
    lastPayload = { session_item_id: item.session_item_id, selected_answer: item.display_ipa };
    expect((await (await page.request.post("/api/attempt", { data: lastPayload })).json()).replayed).toBe(true);
    if (index === 0) await page.waitForTimeout(1700);
    await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    if (index === 0) {
      await page.reload();
      await page.getByRole("button", { name: "Start Sound Compare", exact: true }).click();
      expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(2);
    }
  }
  await expect(page.getByRole("heading", { name: "Sound Compare group complete" })).toBeVisible();
  expect(reviewedFixtureAction("disable").updated).toBe(8);
  expect((await (await page.request.post("/api/practice/minimal-pairs")).json()).status).toBe("empty");
  const replay = await (await page.request.post("/api/attempt", { data: lastPayload })).json();
  expect(replay.replayed).toBe(true);
  expect(replay.sound_compare.status).toBe("unavailable");
  expect((await (await page.request.get("/api/progress")).json()).total_attempts).toBe(9);
  expect(reviewedFixtureAction("noop").status).toBe("no_change");
  expect((await (await page.request.get("/api/listening/current")).json()).enabled).toBe(false);
  await page.getByRole("button", { name: "Start next Entry group", exact: true }).click();
  await expect(page.getByText("Which word matches this IPA?")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
  expect((await (await page.request.get("/api/today")).json()).practice_mode).toBe("choose_word");
});
