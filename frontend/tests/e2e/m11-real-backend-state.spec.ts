import { expect, type Page, test } from "@playwright/test";

const backendPort = process.env.M11_REAL_BACKEND_PORT ?? "8028";
const apiBase = `http://127.0.0.1:${backendPort}/api`;

async function attachScreenshot(page: Page, name: string) {
  const path = test.info().outputPath(`${name}.png`);
  await page.screenshot({ fullPage: true, path });
  await test.info().attach(name, { path, contentType: "image/png" });
}

async function selectCorrectAnswer(page: Page) {
  const todayResponse = await page.request.get(`${apiBase}/today`);
  expect(todayResponse.ok()).toBeTruthy();
  const today = await todayResponse.json();
  const resumeIndex = today.resume_index ?? 0;
  const currentItem = today.items[resumeIndex];
  expect(currentItem, `expected an item at resume_index ${resumeIndex}`).toBeTruthy();
  await page.getByRole("button", { name: `Select ${currentItem.display_ipa}` }).click();
}

test.describe("M11 real backend Today/Progress/Settings consistency", () => {
  test("unfinished regular practice is resumable and clears after completion", async ({ page }) => {
    test.setTimeout(90_000);

    await test.step("Settings review strength persists and affects the next regular group", async () => {
      await page.goto("/");
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
      await expect(page.getByText("Affects future regular practice groups only. Existing active groups stay unchanged.")).toBeVisible();
      await expect(page.getByText("Entry uses the starter word pool. Mid uses the larger intermediate word pool. This choice applies to the next new regular group; active groups stay unchanged.")).toBeVisible();

      const reviewStrength = page.getByLabel(/Review strength/);
      await reviewStrength.selectOption("extra_review");
      await expect(page.getByText("Saved")).toBeVisible();
      await expect(reviewStrength).toHaveValue("extra_review");

      const settingsResponse = await page.request.get(`${apiBase}/settings`);
      expect(settingsResponse.ok()).toBeTruthy();
      const settings = await settingsResponse.json();
      expect(settings.review_strength).toBe("extra_review");

      await attachScreenshot(page, "m11-real-settings-review-strength");
    });

    await test.step("Today creates a future group using seeded extra-review weighting", async () => {
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await page.getByRole("button", { name: "Start Entry group" }).click();
      await expect(page.getByText(/ship|sheep/)).toBeVisible();
      await expect(page.getByText("cat")).toHaveCount(0);

      const progressResponse = await page.request.get(`${apiBase}/progress`);
      const progress = await progressResponse.json();
      expect(progress.resumable_normal_groups).toBe(1);
      expect(progress.level_stats.entry.resumable_normal_groups).toBe(1);

      await attachScreenshot(page, "m11-real-extra-review-group");
    });

    await test.step("Progress callout routes to Today resume for the same group", async () => {
      await page.getByRole("button", { name: "Progress", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
      await expect(page.getByText("Unfinished regular practice", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Go to Today to continue" })).toBeVisible();
      await expect(page.getByText("1 active", { exact: true })).toHaveCount(0);
      await expect(page.getByText("1 active groups", { exact: true })).toHaveCount(0);
      await attachScreenshot(page, "m11-real-progress-unfinished");

      await page.getByRole("button", { name: "Go to Today to continue" }).click();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByRole("button", { name: "Resume Entry group" })).toBeVisible();
      await attachScreenshot(page, "m11-real-today-resume");
    });

    await test.step("Completing the group clears unfinished Progress state", async () => {
      await page.getByRole("button", { name: "Resume Entry group" }).click();
      await selectCorrectAnswer(page);
      await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible({
        timeout: 10_000,
      });

      await page.getByRole("button", { name: "Progress", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
      await expect(page.getByText("Unfinished regular practice", { exact: true })).toHaveCount(0);
      await expect(page.getByText("1 completed today")).toBeVisible();

      const progressResponse = await page.request.get(`${apiBase}/progress`);
      const progress = await progressResponse.json();
      expect(progress.resumable_normal_groups).toBe(0);
      expect(progress.today_status).toBe("completed");
      expect(progress.level_stats.entry.completed_normal_groups_today).toBe(1);

      await attachScreenshot(page, "m11-real-progress-completed");
    });

    await test.step("Partial regular group resumes at the first unanswered item", async () => {
      const settingsResponse = await page.request.put(`${apiBase}/settings`, {
        data: { learner_level: "entry", daily_word_count: 3 },
      });
      expect(settingsResponse.ok()).toBeTruthy();

      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await page.getByRole("button", { name: /Start (next )?Entry group/ }).click();
      await expect(page.getByText("Practice group: 1 / 3")).toBeVisible();

      await selectCorrectAnswer(page);
      await expect(page.getByText("Practice group: 2 / 3")).toBeVisible({ timeout: 10_000 });
      await selectCorrectAnswer(page);
      await expect(page.getByText("Practice group: 3 / 3")).toBeVisible({ timeout: 10_000 });

      await page.getByRole("button", { name: "Progress", exact: true }).click();
      await expect(page.getByText("Unfinished regular practice", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Go to Today to continue" }).click();
      await expect(page.getByRole("button", { name: "Resume Entry group" })).toBeVisible();
      await page.getByRole("button", { name: "Resume Entry group" }).click();
      await expect(page.getByText("Practice group: 3 / 3")).toBeVisible();
      await attachScreenshot(page, "m11-real-resume-breakpoint-third-item");

      await selectCorrectAnswer(page);
      await expect(page.getByText("3 / 3 correct")).toBeVisible({ timeout: 10_000 });

      await page.getByRole("button", { name: "Progress", exact: true }).click();
      await expect(page.getByText("Unfinished regular practice", { exact: true })).toHaveCount(0);
      await expect(page.getByText("2 completed today")).toBeVisible();
      await attachScreenshot(page, "m11-real-resume-breakpoint-completed");
    });

    await test.step("zh-CN real-state Progress copy avoids unexplained 普通", async () => {
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByLabel(/UI language/).selectOption("zh-CN");
      await expect(page.getByText("已保存")).toBeVisible();
      await expect(page.getByText("入门使用适合起步练习的入门词库；进阶使用更大的进阶词库。此选择影响下一组新的常规练习，已进行中的练习组保持不变。")).toBeVisible();
      await page.getByRole("button", { name: "进度" }).click();
      await expect(page.getByText("累计完成常规练习组")).toBeVisible();
      await expect(page.getByText("有未完成的常规练习")).toHaveCount(0);
      const visibleText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
      expect(visibleText).not.toContain("普通");
      await attachScreenshot(page, "m11-real-zh-progress-completed");
    });
  });
});
