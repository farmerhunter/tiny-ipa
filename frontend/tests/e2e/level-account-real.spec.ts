import { devices, expect, test, type Page } from "@playwright/test";

async function state(page: Page, path: string) {
  const response = await page.request.get(`/api/${path}`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function signIn(page: Page, suffix: string) {
  await page.getByLabel("Username").fill(`level-${suffix}`);
  await page.getByLabel("Password").fill(`local-only-level-${suffix}`);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator(".account-menu")).toContainText(`level-${suffix}`);
  await expect(page.getByText("Today practice hub")).toBeVisible();
}

async function saveSettings(page: Page, action: () => Promise<void>) {
  const saved = page.waitForResponse(r => r.url().endsWith("/api/settings") && r.request().method() === "PUT");
  await action();
  expect((await saved).ok()).toBeTruthy();
}

async function startNormal(page: Page, name: string) {
  const started = page.waitForResponse(r => r.url().endsWith("/api/practice/next-normal") && r.request().method() === "POST");
  await page.getByRole("button", { name, exact: true }).click();
  const response = await started;
  expect(response.ok()).toBeTruthy();
  const group = await response.json();
  await expect(page.getByText(`Practice group: 1 / ${group.items.length}`, { exact: true })).toBeVisible();
  expect((await state(page, "today")).group_id).toBe(group.group_id);
  return group;
}

async function answerCurrent(page: Page) {
  const today = await state(page, "today");
  const item = today.items[today.resume_index];
  const answer = item.question.type === "choose_word" ? item.word : item.display_ipa;
  await page.getByRole("button", { name: `Select ${answer}`, exact: true }).click();
}

async function deniedForeignGroup(page: Page, group: { group_id: string; items: { session_item_id: string; display_ipa: string; word: string; question: { type: string } }[] }) {
  for (const item of group.items) {
    const denied = await page.request.post("/api/attempt", { data: {
      session_item_id: item.session_item_id,
      selected_answer: item.question.type === "choose_word" ? item.word : item.display_ipa,
    } });
    expect(denied.status()).toBe(404);
    expect((await denied.json()).detail.error).toBe("ITEM_NOT_FOUND");
  }
  const review = await page.request.post("/api/review/current-group", {
    data: { group_id: group.group_id },
  });
  expect(review.status()).toBe(404);
  expect((await review.json()).detail.error).toBe("GROUP_NOT_FOUND");
}

test("real level transitions, separate progress, account denial and relogin persistence", async ({ page, browser }) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
  await signIn(page, "a");
  const entry = await startNormal(page, "Start Entry group");
  expect(entry.learner_level).toBe("entry");
  expect(entry.items).toHaveLength(2);
  await answerCurrent(page);
  await expect(page.getByText("Practice group: 2 / 2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await saveSettings(page, () => page.getByRole("button", { name: /^Mid/ }).click());
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.getByText("Mid is selected for your next new group. Your current Entry group stays active until you finish it or switch now.")).toBeVisible();
  const pending = await state(page, "today");
  expect(pending.group_id).toBe(entry.group_id);
  expect(pending.learner_level).toBe("entry");
  expect(pending.selected_learner_level).toBe("mid");
  expect(pending.pending_level_change).toBe(true);

  const peerContext = await browser.newContext({ ...devices["Pixel 5"], baseURL: new URL(page.url()).origin });
  try {
    const peer = await peerContext.newPage();
    await peer.goto("/");
    await peer.getByLabel(/界面语言|UI language/).selectOption("en-US");
    await signIn(peer, "b");
    expect((await state(peer, "progress")).total_attempts).toBe(0);
    await deniedForeignGroup(peer, entry);
    expect((await state(peer, "progress")).total_attempts).toBe(0);
    const peerReady = await state(peer, "today");
    expect(peerReady.group_id).toBeUndefined();
    expect(peerReady.items).toEqual([]);
    expect(peerReady.status).toBe("idle");
    expect((await state(page, "progress")).total_attempts).toBe(1);

    await peer.getByRole("button", { name: "Settings", exact: true }).click();
    await peer.getByRole("spinbutton").fill("3");
    await saveSettings(peer, () => peer.getByRole("spinbutton").press("Tab"));
    await saveSettings(peer, () => peer.getByRole("button", { name: /IPA to word/ }).click());
    await peer.getByRole("button", { name: "Today", exact: true }).click();
    const peerGroup = await startNormal(peer, "Start Entry group");
    await expect(peer.getByText("Which word matches this IPA?")).toBeVisible();
    expect(peerGroup.group_id).not.toBe(entry.group_id);
    expect(peerGroup.items).toHaveLength(3);
    await answerCurrent(peer);
    await expect(peer.getByText("Practice group: 2 / 3", { exact: true })).toBeVisible();
    await deniedForeignGroup(page, peerGroup);
    expect((await state(page, "progress")).total_attempts).toBe(1);
    expect((await state(peer, "progress")).total_attempts).toBe(1);
    expect((await state(page, "settings"))).toMatchObject({ learner_level: "mid", daily_word_count: 2, practice_mode: "ipa_first" });
    expect((await state(peer, "settings"))).toMatchObject({ learner_level: "entry", daily_word_count: 3, practice_mode: "choose_word" });

    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    expect((await page.request.get("/api/progress")).status()).toBe(401);
    expect((await state(peer, "auth/me")).user.username).toBe("level-b");
    await signIn(page, "a");
    expect((await state(page, "today")).group_id).toBe(entry.group_id);
    expect((await state(page, "today")).resume_index).toBe(1);
    await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
    await answerCurrent(page);
    await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible();
    const mid = await startNormal(page, "Start next Mid group");
    expect(mid.learner_level).toBe("mid");
    expect(mid.items).toHaveLength(2);
    expect(mid.items.every((item: { word_id: string; audio_url: string | null }) => item.word_id.startsWith("mid_") && item.audio_url === null)).toBe(true);
    await answerCurrent(page);
    await expect(page.getByText("Practice group: 2 / 2", { exact: true })).toBeVisible();
    await page.reload();
    expect((await state(page, "today")).group_id).toBe(mid.group_id);
    expect((await state(page, "today")).resume_index).toBe(1);
    await page.getByRole("button", { name: "Resume Mid group", exact: true }).click();
    await answerCurrent(page);
    await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible();
    const progress = await state(page, "progress");
    expect(progress.total_attempts).toBe(4);
    expect(progress.level_stats.entry).toMatchObject({ attempts: 2, completed_normal_groups: 1, resumable_normal_groups: 0 });
    expect(progress.level_stats.mid).toMatchObject({ attempts: 2, completed_normal_groups: 1, resumable_normal_groups: 0 });
    await page.getByRole("button", { name: "Progress", exact: true }).click();
    for (const level of ["Entry", "Mid"]) {
      const panel = page.locator(".level-progress-panel").filter({ has: page.getByRole("heading", { name: `${level} progress`, exact: true }) });
      await expect(panel).toContainText("2 all-time answered items");
      await expect(panel).toContainText("1 all-time completed groups");
    }
    await page.screenshot({ path: test.info().outputPath("separate-level-progress.png"), fullPage: true });
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await signIn(page, "a");
    expect((await state(page, "progress")).total_attempts).toBe(4);
    expect((await state(peer, "progress")).total_attempts).toBe(1);
    expect((await state(peer, "today")).group_id).toBe(peerGroup.group_id);
    expect((await state(peer, "today")).resume_index).toBe(1);
    await peer.reload();
    await peer.getByRole("button", { name: "Resume Entry group", exact: true }).click();
    await expect(peer.getByText("Which word matches this IPA?")).toBeVisible();
  } finally {
    await peerContext.close();
  }
});
