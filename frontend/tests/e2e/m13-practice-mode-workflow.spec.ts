import { expect, test, type Page, type Route } from "@playwright/test";

type PracticeMode = "ipa_first" | "choose_word";
type QuestionType = "choose_ipa" | "choose_word";

interface MockItem {
  session_item_id: string;
  word_id: string;
  display_ipa: string;
  word: string;
  meaning_zh: string | null;
  audio_url: string | null;
  target_phonemes: string[];
  question: {
    type: QuestionType;
    prompt: string;
    display_ipa?: string;
    choices: string[];
  };
}

interface MockState {
  practiceMode: PracticeMode;
  activeGroup: null | {
    id: string;
    mode: PracticeMode;
    item: MockItem;
  };
}

const ipaItem: MockItem = {
  session_item_id: "ipa-ship",
  word_id: "ship",
  display_ipa: "/ʃɪp/",
  word: "ship",
  meaning_zh: "船；大船",
  audio_url: null,
  target_phonemes: ["/ʃ/"],
  question: {
    type: "choose_ipa",
    prompt: "Which IPA matches this word?",
    choices: ["/sɪp/", "/ʃɪp/"],
  },
};

const wordItem: MockItem = {
  session_item_id: "word-ship",
  word_id: "ship",
  display_ipa: "/ʃɪp/",
  word: "ship",
  meaning_zh: "船；大船",
  audio_url: "/audio/us/ship.mp3",
  target_phonemes: ["/ʃ/"],
  question: {
    type: "choose_word",
    prompt: "Which word matches this IPA?",
    display_ipa: "/ʃɪp/",
    choices: ["sheep", "ship", "cat"],
  },
};

function itemForMode(mode: PracticeMode): MockItem {
  return mode === "choose_word" ? wordItem : ipaItem;
}

function todayResponse(state: MockState) {
  if (!state.activeGroup) {
    return {
      group_type: "normal",
      learner_level: "entry",
      selected_learner_level: "entry",
      pending_level_change: false,
      practice_mode: state.practiceMode,
      selected_practice_mode: state.practiceMode,
      pending_practice_mode_change: false,
      completed_normal_groups_today: { entry: 0, mid: 0, total: 0 },
      date: "2026-07-03",
      primary_accent: "US",
      daily_word_count: 1,
      recent_mistake_count: 0,
      word_count: 0,
      resume_index: 0,
      completed_item_count: 0,
      status: "idle",
      origin: "normal_empty",
      source_scope: "normal_none",
      focus_phonemes: [],
      source_session_item_ids: [],
      target_phoneme_options: [{ phoneme: "/ʃ/", symbol: "ʃ", example_word: "ship", candidate_count: 2 }],
      items: [],
    };
  }

  return {
    session_id: state.activeGroup.id,
    group_id: state.activeGroup.id,
    group_index: 1,
    group_type: "normal",
    learner_level: "entry",
    selected_learner_level: "entry",
    pending_level_change: false,
    practice_mode: state.activeGroup.mode,
    selected_practice_mode: state.practiceMode,
    pending_practice_mode_change: state.activeGroup.mode !== state.practiceMode,
    completed_normal_groups_today: { entry: 0, mid: 0, total: 0 },
    date: "2026-07-03",
    primary_accent: "US",
    daily_word_count: 1,
    recent_mistake_count: 0,
    word_count: 1,
    resume_index: 0,
    completed_item_count: 0,
    status: "in_progress",
    origin: "normal_resume",
    source_scope: "normal_current",
    focus_phonemes: [],
    source_session_item_ids: [],
    target_phoneme_options: [{ phoneme: "/ʃ/", symbol: "ʃ", example_word: "ship", candidate_count: 2 }],
    items: [state.activeGroup.item],
  };
}

async function setupApi(page: Page, state: MockState) {
  await page.route("**/api/**", async (route) => {
    await routeMock(route, state);
  });
}

async function routeMock(route: Route, state: MockState) {
  const request = route.request();
  const path = new URL(request.url()).pathname.replace(/^\/api/, "");

  if (path === "/health") {
    await route.fulfill({ json: { status: "ok", content_version: "m13-mode-workflow", db_ready: true } });
    return;
  }

  if (path === "/auth/me") {
    await route.fulfill({ json: { authenticated: true, user: { id: "default", username: "owner", is_owner: true } } });
    return;
  }

  if (path === "/settings") {
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as Partial<{ practice_mode: PracticeMode }>;
      if (body.practice_mode === "ipa_first" || body.practice_mode === "choose_word") {
        state.practiceMode = body.practice_mode;
      }
    }
    await route.fulfill({
      json: {
        primary_accent: "US",
        daily_word_count: 1,
        show_translation: true,
        show_accent_compare: false,
        practice_mode: state.practiceMode,
        review_strength: "normal",
        learner_level: "entry",
        ui_language: "en-US",
        focus_phonemes: [],
      },
    });
    return;
  }

  if (path === "/today") {
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/next-normal") {
    if (!state.activeGroup) {
      state.activeGroup = {
        id: `group-${state.practiceMode}`,
        mode: state.practiceMode,
        item: itemForMode(state.practiceMode),
      };
    }
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/focus") {
    await route.fulfill({
      json: {
        ...todayResponse({
          ...state,
          activeGroup: { id: "focus-group", mode: "ipa_first", item: ipaItem },
        }),
        group_type: "weak_focus",
        practice_mode: "ipa_first",
        selected_practice_mode: state.practiceMode,
        pending_practice_mode_change: false,
        source_scope: "focus_selection",
        focus_phonemes: ["/ʃ/"],
      },
    });
    return;
  }

  if (path === "/attempt") {
    await route.fulfill({
      json: {
        is_correct: true,
        correct_answer: state.activeGroup?.mode === "choose_word" ? "ship" : "/ʃɪp/",
        updated_phonemes: [{ phoneme: "/ʃ/", attempt_count: 1, correct_count: 1, mastery_status: "steady" }],
        next_action: "continue",
      },
    });
    return;
  }

  await route.fulfill({ status: 404, json: { detail: `Unhandled ${path}` } });
}

test.describe("M13 practice mode workflow", () => {
  test("Settings mode selection changes the next normal group without mutating the active group", async ({ page }) => {
    const state: MockState = { practiceMode: "ipa_first", activeGroup: null };
    await setupApi(page, state);

    await page.goto("/");
    await expect(page.getByText("Start Entry practice")).toBeVisible();
    await expect(page.getByText("Word to IPA")).toBeVisible();
    await page.getByRole("button", { name: "Start Entry group" }).click();
    await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
    await expect(page.getByText("Which IPA matches this word?")).toBeVisible();

    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Practice question type" })).toBeVisible();
    await expect(page.getByText("Active regular groups keep their current type")).toBeVisible();
    await page.getByRole("button", { name: /IPA to word/ }).click();
    await expect(page.getByText("Saved")).toBeVisible();

    await page.getByRole("button", { name: "Today", exact: true }).click();
    await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
    await expect(page.getByText("IPA to word is selected for your next new group")).toBeVisible();
    await page.getByRole("button", { name: "Resume Entry group" }).click();
    await expect(page.getByText("Which IPA matches this word?")).toBeVisible();
  });

  test("choose_word next group and focus boundary stay understandable", async ({ page }) => {
    const state: MockState = { practiceMode: "choose_word", activeGroup: null };
    await setupApi(page, state);

    await page.goto("/");
    await expect(page.getByText("Start Entry practice")).toBeVisible();
    await expect(page.getByText("IPA to word")).toBeVisible();
    await page.getByRole("button", { name: "Start Entry group" }).click();
    await expect(page.getByText("Current type: IPA to word")).toBeVisible();
    await expect(page.getByText("Which word matches this IPA?")).toBeVisible();
    await expect(page.locator(".word-display")).not.toContainText("ship");
    await expect(page.locator(".word-display .audio-btn")).toHaveCount(0);

    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByRole("button", { name: "Focus /ʃ/" }).click();
    await expect(page.getByText("Focused group: 1 / 1")).toBeVisible();
    await expect(page.getByText("Current type: Word to IPA")).toBeVisible();
    await expect(page.getByText("Which IPA matches this word?")).toBeVisible();
  });
});
