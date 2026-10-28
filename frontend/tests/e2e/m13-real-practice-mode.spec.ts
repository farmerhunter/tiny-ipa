import { expect, type Page, test } from "@playwright/test";

const apiBase = "/api";

async function attachScreenshot(page: Page, name: string) {
  const path = test.info().outputPath(`${name}.png`);
  await page.screenshot({ fullPage: true, path });
  await test.info().attach(name, { path, contentType: "image/png" });
}

async function todayJson(page: Page) {
  const response = await page.request.get(`${apiBase}/today`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function actionState(page: Page, path: string, action: () => Promise<void>) {
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith(`/api/${path}`) && response.request().method() === "POST");
  await action();
  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function selectCorrectCurrentAnswer(page: Page, group?: Awaited<ReturnType<typeof todayJson>>) {
  const today = group ?? await todayJson(page);
  const item = today.items[today.resume_index ?? 0];
  expect(item).toBeTruthy();
  const answer = item.question.type === "choose_word" ? item.word : item.display_ipa;
  await page.getByRole("button", { name: `Select ${answer}` }).click();
}

async function selectIncorrectWordAnswer(page: Page) {
  const today = await todayJson(page);
  const item = today.items[today.resume_index ?? 0];
  expect(item?.question.type).toBe("choose_word");
  const wrong = item.question.choices.find((choice: string) => choice !== item.word);
  expect(wrong).toBeTruthy();
  await page.getByRole("button", { name: `Select ${wrong}` }).click();
}

test.describe("M13 real backend practice mode workflow", () => {
  test("Settings choose_word controls the next normal group while review and focus stay choose_ipa", async ({ page }) => {
    test.setTimeout(90_000);
    let missedWordId = "";

    await test.step("Sign in and start the default choose_ipa group", async () => {
      await page.goto("/");
      await page.getByLabel(/界面语言|UI language/).selectOption("en-US");
      await page.getByLabel("Username").fill("workflow-owner");
      await page.getByLabel("Password").fill("local-only-workflow");
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page.locator(".account-menu")).toContainText("workflow-owner");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByText("Word to IPA")).toBeVisible();
      await page.getByRole("button", { name: "Start Entry group" }).click();
      await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
      await expect(page.getByText("Which IPA matches this word?")).toBeVisible();

      const today = await todayJson(page);
      expect(today.practice_mode).toBe("ipa_first");
      expect(today.items[0].question.type).toBe("choose_ipa");
      await attachScreenshot(page, "m13-real-default-word-to-ipa");
    });

    await test.step("Switching Settings mode keeps the active group stable", async () => {
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Practice question type" })).toBeVisible();
      await expect(page.getByText("Active regular groups keep their current type")).toBeVisible();
      await page.getByRole("button", { name: /IPA to word/ }).click();
      await expect(page.getByText("Saved")).toBeVisible();

      const settings = await (await page.request.get(`${apiBase}/settings`)).json();
      expect(settings.practice_mode).toBe("choose_word");

      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
      await expect(page.getByText("IPA to word is selected for your next new group")).toBeVisible();
      const today = await todayJson(page);
      expect(today.practice_mode).toBe("ipa_first");
      expect(today.selected_practice_mode).toBe("choose_word");
      expect(today.pending_practice_mode_change).toBe(true);
      await attachScreenshot(page, "m13-real-mode-change-active-stable");
    });

    await test.step("Completing the active group starts the next normal group as choose_word", async () => {
      await page.getByRole("button", { name: "Resume Entry group" }).click();
      await selectCorrectCurrentAnswer(page);
      await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible({
        timeout: 10_000,
      });
      await page.getByRole("button", { name: "Start next Entry group" }).click();
      await expect(page.getByText("Current type: IPA to word")).toBeVisible();
      await expect(page.getByText("Which word matches this IPA?")).toBeVisible();

      const today = await todayJson(page);
      expect(today.practice_mode).toBe("choose_word");
      expect(today.items[0].question.type).toBe("choose_word");
      await expect(page.locator(".word-display")).not.toContainText(today.items[0].word);
      await expect(page.locator(".word-display .audio-btn")).toHaveCount(0);
      await attachScreenshot(page, "m13-real-next-group-ipa-to-word");
    });

    await test.step("Current-group review and focus remain word-to-IPA", async () => {
      missedWordId = (await todayJson(page)).items[0].word_id;
      await selectIncorrectWordAnswer(page);
      await expect(page.getByText("Not quite.")).toBeVisible();
      await page.getByRole("button", { name: "Continue" }).click();
      await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible({
        timeout: 10_000,
      });
      const review = await actionState(page, "review/current-group", () =>
        page.getByRole("button", { name: "Review this group's misses" }).click());
      await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
      await expect(page.getByText("Which IPA matches this word?")).toBeVisible();
      expect(review.group_type).toBe("mistake_review");
      expect(review.items[0].word_id).toBe(missedWordId);
      await attachScreenshot(page, "m13-real-current-review-word-to-ipa");
      await selectCorrectCurrentAnswer(page, review);
      await expect(page.getByRole("heading", { name: "Current-group review complete" })).toBeVisible();

      await page.getByRole("button", { name: "Settings", exact: true }).click();
      const focused = await actionState(page, "practice/focus", () =>
        page.getByRole("button", { name: "Focus /ʃ/" }).click());
      await expect(page.getByText("Focused group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
      await expect(page.getByText("Which IPA matches this word?")).toBeVisible();
      expect(focused.group_type).toBe("weak_focus");
      await attachScreenshot(page, "m13-real-focus-word-to-ipa");
      await selectCorrectCurrentAnswer(page, focused);
      await expect(page.getByRole("heading", { name: "Focused group complete" })).toBeVisible();
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByRole("button", { name: "Clear focus", exact: true }).click();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      const settings = await (await page.request.get(`${apiBase}/settings`)).json();
      expect(settings.focus_phonemes).toEqual([]);
      expect(settings.practice_mode).toBe("choose_word");
    });

    await test.step("Specialty groups complete and return to regular practice without changing selected mode", async () => {
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      const compared = await actionState(page, "practice/minimal-pairs", () =>
        page.getByRole("button", { name: "Start Sound Compare", exact: true }).click());
      expect(compared.group_type).toBe("minimal_pair");
      expect(compared.items).toEqual([]);
      expect(compared.group_id).toBeUndefined();
      expect(compared.status).toBe("empty");
      await expect(page.getByText("Sound Compare practice is not available yet. It needs at least two safe words with pair metadata.")).toBeVisible();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      expect((await (await page.request.get(`${apiBase}/progress`)).json()).total_attempts).toBe(4);
      const targeted = await actionState(page, "practice/target-phoneme", () =>
        page.locator(".target-phoneme-panel button").first().click());
      expect(targeted.group_type).toBe("target_phoneme");
      expect(targeted.items[0].target_phonemes).toContain(targeted.focus_phonemes[0]);
      await selectCorrectCurrentAnswer(page, targeted);
      await expect(page.getByRole("heading", { name: "Sound Practice group complete" })).toBeVisible();
      const progress = await (await page.request.get(`${apiBase}/progress`)).json();
      expect(progress.total_attempts).toBe(5);
      expect(progress.level_stats.entry.completed_normal_groups).toBe(2);
      await page.getByRole("button", { name: "Start next Entry group", exact: true }).click();
      await expect(page.getByText("Which word matches this IPA?")).toBeVisible();
      const next = await todayJson(page);
      expect(next.group_type).toBe("normal");
      expect(next.practice_mode).toBe("choose_word");
      await page.reload();
      await page.getByRole("button", { name: "Resume Entry group", exact: true }).click();
      expect((await todayJson(page)).group_id).toBe(next.group_id);
      await expect(page.getByText("Which word matches this IPA?")).toBeVisible();
      await attachScreenshot(page, "m13-real-specialty-return-regular");
    });
  });
});
