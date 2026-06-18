import { expect, type Page, type Route, test } from "@playwright/test";

type LearnerLevel = "entry" | "mid";

interface MockState {
  learnerLevel: LearnerLevel;
}

const items = {
  entry: {
    session_item_id: "entry-item-1",
    word_id: "ship",
    display_ipa: "/ʃɪp/",
    word: "ship",
    meaning_zh: "船",
    target_phonemes: ["/ʃ/"],
    choices: ["/sɪp/", "/ʃɪp/"],
  },
  mid: {
    session_item_id: "mid-item-1",
    word_id: "mid_remember",
    display_ipa: "/rɪˈmembɚ/",
    word: "remember",
    meaning_zh: "记得",
    target_phonemes: ["/r/", "/ɚ/"],
    choices: ["/rɪˈmembɚ/", "/rɪˈmembə/"],
  },
};

function levelLabel(level: LearnerLevel) {
  return level === "mid" ? "Mid" : "Entry";
}

function todayResponse(level: LearnerLevel) {
  const item = items[level];
  return {
    session_id: `${level}-session-1`,
    group_id: `${level}-group-1`,
    group_index: 1,
    group_type: "normal",
    learner_level: level,
    learner_level_label: levelLabel(level),
    date: "2026-06-18",
    primary_accent: "US",
    origin: "normal_start",
    source_scope: "normal_current",
    focus_phonemes: [],
    daily_word_count: 1,
    word_count: 1,
    status: "active",
    source_session_item_ids: [],
    items: [
      {
        ...item,
        audio_url: `/audio/us/${item.word}.mp3`,
        question: {
          type: "ipa_choice",
          prompt: "Pick the matching IPA",
          choices: item.choices,
        },
      },
    ],
  };
}

function settingsResponse(state: MockState) {
  return {
    primary_accent: "US",
    daily_word_count: 1,
    show_translation: true,
    show_accent_compare: false,
    practice_mode: "ipa_first",
    review_strength: "normal",
    learner_level: state.learnerLevel,
    focus_phonemes: [],
  };
}

async function setupMockApi(page: Page): Promise<MockState> {
  const state: MockState = { learnerLevel: "entry" };
  await page.route("**/api/**", async (route) => {
    await routeMock(route, state);
  });
  return state;
}

async function routeMock(route: Route, state: MockState) {
  const request = route.request();
  const path = new URL(request.url()).pathname.replace(/^\/api/, "");

  if (path === "/health") {
    await route.fulfill({
      json: { status: "ok", content_version: "m8-level-selection", db_ready: true },
    });
    return;
  }

  if (path === "/settings") {
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as { learner_level?: LearnerLevel };
      if (body.learner_level === "entry" || body.learner_level === "mid") {
        state.learnerLevel = body.learner_level;
      }
    }
    await route.fulfill({ json: settingsResponse(state) });
    return;
  }

  if (path === "/today") {
    await route.fulfill({ json: todayResponse(state.learnerLevel) });
    return;
  }

  if (path === "/progress") {
    await route.fulfill({
      json: {
        today_completed: false,
        today_status: "active",
        streak_days: 0,
        total_attempts: 0,
        total_sessions: 0,
        weak_phonemes: [],
        strong_phonemes: [],
      },
    });
    return;
  }

  await route.fallback();
}

test.describe("M8 learner level selection walkthrough", () => {
  test("Entry is default and Mid switching is visible in Settings and Today", async ({ page }) => {
    await setupMockApi(page);

    await test.step("Entry default practice context", async () => {
      await page.goto("/");
      await expect(page.getByText("Practice group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Entry practice group.")).toBeVisible();
      await expect(page.getByText("ship")).toBeVisible();
      await expect(page.getByText("Mid")).toHaveCount(0);
    });

    await test.step("Settings exposes learner-facing level choices", async () => {
      await page.getByRole("button", { name: "Settings" }).click();
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Practice level" })).toBeVisible();
      await expect(page.getByRole("button", { name: /Entry/ })).toBeVisible();
      await page.getByRole("button", { name: /Mid/ }).click();
      await expect(page.getByText("Saved")).toBeVisible();
      await expect(page.getByText(/core_1000_words|core_300_words/i)).toHaveCount(0);
    });

    await test.step("Mid practice uses the Mid pool and visible context", async () => {
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByText("Practice group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Mid practice group.")).toBeVisible();
      await expect(page.getByText("remember")).toBeVisible();
      await expect(page.getByText("ship")).toHaveCount(0);
      const screenshotPath = test.info().outputPath("m8-mid-level-mobile.png");
      await page.screenshot({ fullPage: true, path: screenshotPath });
      await test.info().attach("m8-mid-level-mobile", {
        path: screenshotPath,
        contentType: "image/png",
      });
    });
  });
});
