import { expect, type Page, test } from "@playwright/test";

const backendPort = process.env.M11_REAL_BACKEND_PORT ?? "8028";
const apiBase = `http://127.0.0.1:${backendPort}/api`;

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

async function selectCorrectCurrentAnswer(page: Page) {
  const today = await todayJson(page);
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

    await test.step("Sign in and start the default choose_ipa group", async () => {
      await page.goto("/");
      await page.getByLabel("界面语言").selectOption("en-US");
      await page.getByLabel("Username").fill("owner");
      await page.getByLabel("Password").fill("secret123");
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page.locator(".account-menu")).toContainText("owner");
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
      await selectIncorrectWordAnswer(page);
      await expect(page.getByText("Not quite.")).toBeVisible();
      await page.getByRole("button", { name: "Continue" }).click();
      await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible({
        timeout: 10_000,
      });
      await page.getByRole("button", { name: "Review this group's misses" }).click();
      await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
      await expect(page.getByText("Which IPA matches this word?")).toBeVisible();
      await attachScreenshot(page, "m13-real-current-review-word-to-ipa");

      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByRole("button", { name: "Focus /ʃ/" }).click();
      await expect(page.getByText("Focused group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
      await expect(page.getByText("Which IPA matches this word?")).toBeVisible();
      await attachScreenshot(page, "m13-real-focus-word-to-ipa");
    });
  });
});
