import { expect, type Page, type Route, test } from "@playwright/test";

type LearnerLevel = "entry" | "mid";

interface MockState {
  selectedLevel: LearnerLevel;
  activeLevel: LearnerLevel | null;
  completed: Record<LearnerLevel, number>;
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

function todayResponse(state: MockState) {
  if (state.activeLevel === null) {
    return {
      group_type: "normal",
      learner_level: state.selectedLevel,
      learner_level_label: levelLabel(state.selectedLevel),
      selected_learner_level: state.selectedLevel,
      selected_learner_level_label: levelLabel(state.selectedLevel),
      pending_level_change: false,
      completed_normal_groups_today: {
        entry: state.completed.entry,
        mid: state.completed.mid,
        total: state.completed.entry + state.completed.mid,
      },
      date: "2026-06-18",
      primary_accent: "US",
      origin: "normal_empty",
      source_scope: "normal_none",
      focus_phonemes: [],
      action_label: `Start ${levelLabel(state.selectedLevel)} group`,
      daily_word_count: 1,
      recent_mistake_count: 0,
      word_count: 0,
      status: "idle",
      source_session_item_ids: [],
      items: [],
    };
  }
  const item = items[state.activeLevel];
  const pending = state.selectedLevel !== state.activeLevel;
  return {
    session_id: `${state.activeLevel}-session-1`,
    group_id: `${state.activeLevel}-group-1`,
    group_index: 1,
    group_type: "normal",
    learner_level: state.activeLevel,
    learner_level_label: levelLabel(state.activeLevel),
    selected_learner_level: state.selectedLevel,
    selected_learner_level_label: levelLabel(state.selectedLevel),
    pending_level_change: pending,
    completed_normal_groups_today: {
      entry: state.completed.entry,
      mid: state.completed.mid,
      total: state.completed.entry + state.completed.mid,
    },
    date: "2026-06-18",
    primary_accent: "US",
    origin: "normal_start",
    source_scope: "normal_current",
    focus_phonemes: [],
    daily_word_count: 1,
    recent_mistake_count: 0,
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
    learner_level: state.selectedLevel,
    focus_phonemes: [],
  };
}

async function setupMockApi(page: Page): Promise<MockState> {
  const state: MockState = {
    selectedLevel: "entry",
    activeLevel: null,
    completed: { entry: 0, mid: 0 },
  };
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
        state.selectedLevel = body.learner_level;
      }
    }
    await route.fulfill({ json: settingsResponse(state) });
    return;
  }

  if (path === "/today") {
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/next-normal") {
    state.activeLevel = state.selectedLevel;
    await route.fulfill({
      json: {
        ...todayResponse(state),
        origin: "normal_next",
        source_scope: "normal_next",
      },
    });
    return;
  }

  if (path === "/practice/abandon-current-and-next") {
    state.activeLevel = state.selectedLevel;
    await route.fulfill({
      json: {
        ...todayResponse(state),
        origin: "normal_abandon_next",
        source_scope: "normal_next",
        abandoned_group_id: "entry-session-1",
        detail: "Ended Entry Group 1 and started Mid Group 1.",
      },
    });
    return;
  }

  if (path === "/progress") {
    await route.fulfill({
      json: {
        today_completed: false,
        today_status: "active",
        streak_days: 0,
        total_attempts: 6,
        total_sessions: 2,
        total_normal_groups: 2,
        stat_scope: "global",
        level_stats: {
          entry: {
            learner_level: "entry",
            label: "Entry",
            attempts: 3,
            correct_attempts: 1,
            accuracy: 0.33,
            normal_groups: 1,
            completed_normal_groups: state.completed.entry,
            completed_normal_groups_today: state.completed.entry,
            weak_phonemes: [
              {
                phoneme: "/ʃ/",
                accuracy: 0.33,
                attempt_count: 3,
                correct_count: 1,
                mastery_status: "weak",
              },
            ],
            strong_phonemes: [],
          },
          mid: {
            learner_level: "mid",
            label: "Mid",
            attempts: 3,
            correct_attempts: 3,
            accuracy: 1,
            normal_groups: 1,
            completed_normal_groups: state.completed.mid,
            completed_normal_groups_today: state.completed.mid,
            weak_phonemes: [],
            strong_phonemes: [
              {
                phoneme: "/r/",
                accuracy: 1,
                attempt_count: 3,
                correct_count: 3,
                mastery_status: "learning",
              },
            ],
          },
        },
        weak_phonemes: [],
        strong_phonemes: [],
      },
    });
    return;
  }

  await route.fallback();
}

test.describe("M8 learner level selection walkthrough", () => {
  test("Entry-to-Mid lifecycle is explicit from Today hub through Progress stats", async ({ page }) => {
    await setupMockApi(page);

    await test.step("Entry default hub context", async () => {
      await page.goto("/");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Start Entry practice" })).toBeVisible();
      await expect(page.getByText("Ready when you are")).toBeVisible();
      await expect(page.getByRole("button", { name: "No older mistakes to review" })).toBeDisabled();
      await page.getByRole("button", { name: "Start Entry group" }).click();
      await expect(page.getByText("Practice group: 1 / 1")).toBeVisible();
      await expect(page.getByText("ship")).toBeVisible();
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

    await test.step("Today explains pending level change and intentional switch", async () => {
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Entry practice in progress" })).toBeVisible();
      await expect(page.getByText("Mid is selected for your next new group. Your current Entry group stays active until you finish it or switch now.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Resume Entry group" })).toBeVisible();
      page.once("dialog", (dialog) => dialog.accept());
      await page.getByRole("button", { name: "Switch to Mid now" }).click();
      await expect(page.getByText("Practice group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Mid practice group.")).toBeVisible();
      await expect(page.getByText("remember")).toBeVisible();
      await expect(page.getByText("ship")).toHaveCount(0);
    });

    await test.step("Progress distinguishes Entry and Mid statistics", async () => {
      await page.getByRole("button", { name: "Progress" }).click();
      await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Entry progress" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Mid progress" })).toBeVisible();
      await expect(page.getByText("Sounds to revisit overall")).toHaveCount(0);
      await expect(page.getByText("Entry has sounds ready for focused practice.")).toBeVisible();
      await expect(page.getByText("Mid is looking steady so far. Keep practicing to confirm strong sounds.")).toBeVisible();
      const screenshotPath = test.info().outputPath("m8-mid-level-mobile.png");
      await page.screenshot({ fullPage: true, path: screenshotPath });
      await test.info().attach("m8-mid-level-mobile", {
        path: screenshotPath,
        contentType: "image/png",
      });
    });
  });
});
