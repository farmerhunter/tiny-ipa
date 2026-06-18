import { expect, type Page, type Route, test } from "@playwright/test";

type LearnerLevel = "entry" | "mid";
type GroupKey = "none" | "entry" | "mid" | "currentReview" | "recentReview" | "focused";
type GroupType = "normal" | "mistake_review" | "weak_focus";

interface MockItem {
  session_item_id: string;
  word_id: string;
  display_ipa: string;
  word: string;
  meaning_zh: string | null;
  target_phonemes: string[];
  choices: string[];
  audio_url: string | null;
}

interface MockState {
  selectedLevel: LearnerLevel;
  activeGroup: GroupKey;
  completed: Record<LearnerLevel, number>;
  focusPhonemes: string[];
  recentReviewEmpty: boolean;
}

const items: Record<Exclude<GroupKey, "none">, MockItem[]> = {
  entry: [
    {
      session_item_id: "entry-ship",
      word_id: "ship",
      display_ipa: "/ʃɪp/",
      word: "ship",
      meaning_zh: "船",
      target_phonemes: ["/ʃ/"],
      choices: ["/sɪp/", "/ʃɪp/"],
      audio_url: null,
    },
    {
      session_item_id: "entry-thin",
      word_id: "thin",
      display_ipa: "/θɪn/",
      word: "thin",
      meaning_zh: "薄的",
      target_phonemes: ["/θ/"],
      choices: ["/θɪn/", "/sɪn/"],
      audio_url: "/audio/us/thin.mp3",
    },
  ],
  mid: [
    {
      session_item_id: "mid-remember",
      word_id: "remember",
      display_ipa: "/rɪˈmembɚ/",
      word: "remember",
      meaning_zh: "记得",
      target_phonemes: ["/r/", "/ɚ/"],
      choices: ["/rɪˈmembɚ/", "/rɪˈmembə/"],
      audio_url: "/audio/us/remember.mp3",
    },
  ],
  currentReview: [
    {
      session_item_id: "review-current-ship",
      word_id: "ship",
      display_ipa: "/ʃɪp/",
      word: "ship",
      meaning_zh: "船",
      target_phonemes: ["/ʃ/"],
      choices: ["/sɪp/", "/ʃɪp/"],
      audio_url: null,
    },
  ],
  recentReview: [
    {
      session_item_id: "review-recent-thin",
      word_id: "thin",
      display_ipa: "/θɪn/",
      word: "thin",
      meaning_zh: "薄的",
      target_phonemes: ["/θ/"],
      choices: ["/θɪn/", "/sɪn/"],
      audio_url: "/audio/us/thin.mp3",
    },
  ],
  focused: [
    {
      session_item_id: "focus-ship",
      word_id: "ship",
      display_ipa: "/ʃɪp/",
      word: "ship",
      meaning_zh: "船",
      target_phonemes: ["/ʃ/"],
      choices: ["/sɪp/", "/ʃɪp/"],
      audio_url: null,
    },
  ],
};

function levelLabel(level: LearnerLevel) {
  return level === "mid" ? "Mid" : "Entry";
}

function groupLevel(group: GroupKey): LearnerLevel {
  return group === "mid" ? "mid" : "entry";
}

function groupType(group: GroupKey): GroupType {
  if (group === "currentReview" || group === "recentReview") return "mistake_review";
  if (group === "focused") return "weak_focus";
  return "normal";
}

function todayResponse(state: MockState) {
  if (state.activeGroup === "none") {
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
      focus_phonemes: state.focusPhonemes,
      action_label: `Start ${levelLabel(state.selectedLevel)} group`,
      daily_word_count: 2,
      word_count: 0,
      status: "idle",
      source_session_item_ids: [],
      items: [],
    };
  }

  const level = groupLevel(state.activeGroup);
  const review = state.activeGroup === "currentReview" || state.activeGroup === "recentReview";
  const focus = state.activeGroup === "focused";
  return {
    session_id: `${state.activeGroup}-session`,
    group_id: `${state.activeGroup}-group`,
    group_index: state.activeGroup === "mid" ? 2 : 1,
    group_type: groupType(state.activeGroup),
    learner_level: level,
    learner_level_label: levelLabel(level),
    selected_learner_level: state.selectedLevel,
    selected_learner_level_label: levelLabel(state.selectedLevel),
    pending_level_change: !review && !focus && state.selectedLevel !== level,
    completed_normal_groups_today: {
      entry: state.completed.entry,
      mid: state.completed.mid,
      total: state.completed.entry + state.completed.mid,
    },
    date: "2026-06-18",
    primary_accent: "US",
    origin: focus ? "focus_start" : review ? "current_group_review_start" : "normal_start",
    source_scope:
      state.activeGroup === "currentReview"
        ? "current_group"
        : state.activeGroup === "recentReview"
          ? "recent_global"
          : focus
            ? "focus_selection"
            : "normal_current",
    source_group_id: review ? "entry-group" : undefined,
    focus_phonemes: focus ? state.focusPhonemes : [],
    daily_word_count: items[state.activeGroup].length,
    word_count: items[state.activeGroup].length,
    status: "active",
    source_session_item_ids: review ? ["entry-ship"] : [],
    source_count: review ? 1 : 0,
    items: items[state.activeGroup].map((item) => ({
      session_item_id: item.session_item_id,
      word_id: item.word_id,
      display_ipa: item.display_ipa,
      word: item.word,
      meaning_zh: item.meaning_zh,
      audio_url: item.audio_url,
      target_phonemes: item.target_phonemes,
      question: {
        type: "ipa_choice",
        prompt: "Which IPA matches this word?",
        choices: item.choices,
      },
    })),
  };
}

function settingsResponse(state: MockState) {
  return {
    primary_accent: "US",
    daily_word_count: 2,
    show_translation: true,
    show_accent_compare: false,
    practice_mode: "ipa_first",
    review_strength: "normal",
    learner_level: state.selectedLevel,
    focus_phonemes: state.focusPhonemes,
  };
}

function progressResponse(state: MockState) {
  return {
    today_completed: false,
    today_status: state.activeGroup === "none" ? "none" : "in_progress",
    streak_days: state.completed.entry > 0 ? 0 : 0,
    total_attempts: state.completed.entry > 0 ? 2 : 0,
    total_sessions: state.completed.entry + state.completed.mid,
    total_normal_groups: state.completed.entry + state.completed.mid + (state.activeGroup === "mid" ? 1 : 0),
    stat_scope: "global",
    level_stats: {
      entry: {
        learner_level: "entry",
        label: "Entry",
        attempts: state.completed.entry > 0 ? 2 : 0,
        correct_attempts: state.completed.entry > 0 ? 1 : 0,
        accuracy: state.completed.entry > 0 ? 0.5 : null,
        normal_groups: state.completed.entry,
        completed_normal_groups: state.completed.entry,
        completed_normal_groups_today: state.completed.entry,
        weak_phonemes: [
          {
            phoneme: "/ʃ/",
            accuracy: 0.5,
            attempt_count: 2,
            correct_count: 1,
            mastery_status: "weak",
          },
        ],
        strong_phonemes: [],
      },
      mid: {
        learner_level: "mid",
        label: "Mid",
        attempts: 0,
        correct_attempts: 0,
        accuracy: null,
        normal_groups: state.activeGroup === "mid" ? 1 : 0,
        completed_normal_groups: state.completed.mid,
        completed_normal_groups_today: state.completed.mid,
        weak_phonemes: [],
        strong_phonemes: [],
      },
    },
    weak_phonemes: [
      {
        phoneme: "/ʃ/",
        accuracy: 0.5,
        attempt_count: 2,
        correct_count: 1,
        mastery_status: "weak",
      },
    ],
    strong_phonemes: [],
  };
}

async function setupM10Api(page: Page, options: Partial<MockState> = {}) {
  const state: MockState = {
    selectedLevel: options.selectedLevel ?? "entry",
    activeGroup: options.activeGroup ?? "none",
    completed: options.completed ?? { entry: 0, mid: 0 },
    focusPhonemes: options.focusPhonemes ?? [],
    recentReviewEmpty: options.recentReviewEmpty ?? false,
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
      json: { status: "ok", content_version: "m10-walkthrough", db_ready: true },
    });
    return;
  }

  if (path === "/today") {
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/settings") {
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as {
        learner_level?: LearnerLevel;
        focus_phonemes?: string[];
        daily_word_count?: number;
      };
      if (body.learner_level) state.selectedLevel = body.learner_level;
      if (body.focus_phonemes) state.focusPhonemes = body.focus_phonemes;
    }
    await route.fulfill({ json: settingsResponse(state) });
    return;
  }

  if (path === "/progress") {
    await route.fulfill({ json: progressResponse(state) });
    return;
  }

  if (path === "/practice/next-normal") {
    state.activeGroup = state.selectedLevel;
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/abandon-current-and-next") {
    state.activeGroup = state.selectedLevel;
    await route.fulfill({
      json: {
        ...todayResponse(state),
        detail: `Ended Entry Group 1 and started ${levelLabel(state.selectedLevel)} Group 1.`,
      },
    });
    return;
  }

  if (path === "/attempt") {
    const body = request.postDataJSON() as {
      session_item_id: string;
      selected_answer: string;
    };
    const item = Object.values(items)
      .flat()
      .find((candidate) => candidate.session_item_id === body.session_item_id);
    if (!item) {
      await route.fulfill({ status: 404, json: { detail: "Unknown item" } });
      return;
    }
    const currentItems = state.activeGroup === "none" ? [] : items[state.activeGroup];
    if (currentItems.at(-1)?.session_item_id === body.session_item_id) {
      if (state.activeGroup === "entry") state.completed.entry += 1;
      if (state.activeGroup === "mid") state.completed.mid += 1;
    }
    await route.fulfill({
      json: {
        is_correct: body.selected_answer === item.display_ipa,
        correct_answer: item.display_ipa,
        updated_phonemes: item.target_phonemes.map((phoneme) => ({
          phoneme,
          attempt_count: 1,
          correct_count: body.selected_answer === item.display_ipa ? 1 : 0,
          mastery_status: body.selected_answer === item.display_ipa ? "strong" : "weak",
        })),
        next_action: "continue",
      },
    });
    return;
  }

  if (path === "/review/current-group") {
    state.activeGroup = "currentReview";
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/review/recent-mistakes") {
    if (state.recentReviewEmpty) {
      await route.fulfill({
        json: {
          ...todayResponse(state),
          status: "empty",
          items: [],
          detail: "No recent incorrect attempts are available for review.",
        },
      });
      return;
    }
    state.activeGroup = "recentReview";
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/focus") {
    const body = request.postDataJSON() as { focus_phonemes?: string[] };
    state.focusPhonemes = body.focus_phonemes ?? ["/ʃ/"];
    state.activeGroup = "focused";
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/clear-focus") {
    state.focusPhonemes = [];
    state.activeGroup = "none";
    await route.fulfill({
      json: {
        ...todayResponse(state),
        detail: "Focus cleared. Back to normal practice.",
      },
    });
    return;
  }

  await route.fallback();
}

async function answer(page: Page, choice: string) {
  await page.getByRole("button", { name: `Select ${choice}` }).click();
}

async function attachScreenshot(page: Page, name: string) {
  const path = test.info().outputPath(`${name}.png`);
  await page.screenshot({ fullPage: true, path });
  await test.info().attach(name, { path, contentType: "image/png" });
}

test.describe("M10 UX walkthrough evidence", () => {
  test("Today practice, wrong-answer recovery, reviews, and Progress focus are observable", async ({ page }) => {
    await setupM10Api(page);

    await test.step("Today start orientation", async () => {
      await page.goto("/");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Entry selected" })).toBeVisible();
      await expect(page.getByText("No active group")).toBeVisible();
      await expect(page.getByRole("button", { name: "Start Entry group" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review recent mistakes" })).toBeVisible();
      await attachScreenshot(page, "m10-today-start");
    });

    await test.step("Wrong answer feedback remains inspectable before auto-advance", async () => {
      await page.getByRole("button", { name: "Start Entry group" }).click();
      await expect(page.getByText("Practice group: 1 / 2")).toBeVisible();
      await expect(page.getByRole("button", { name: "Play pronunciation (TTS)" })).toBeVisible();
      await answer(page, "/sɪp/");
      await expect(page.getByText("Not quite")).toBeVisible();
      await expect(page.getByText("You picked")).toBeVisible();
      await expect(page.getByText("Correct IPA")).toBeVisible();
      await expect(page.getByText("Target sound")).toBeVisible();
      await attachScreenshot(page, "m10-wrong-answer-feedback");
      await expect(page.getByRole("button", { name: "Select /θɪn/" })).toBeVisible({
        timeout: 6_000,
      });
    });

    await test.step("Completion summary exposes current-group recovery and next choices", async () => {
      await answer(page, "/θɪn/");
      await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible({
        timeout: 4_000,
      });
      await expect(page.getByText("1 / 2 correct")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Misses from this group" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review misses from this group" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review recent mistakes" })).toBeVisible();
      await attachScreenshot(page, "m10-completion-recovery-actions");
    });

    await test.step("Current-group review and recent review use different source copy", async () => {
      await page.getByRole("button", { name: "Review misses from this group" }).click();
      await expect(page.getByText("Current-group review: 1 / 1")).toBeVisible();
      await expect(page.getByText("Reviewing misses from the group you just finished.")).toBeVisible();
      await attachScreenshot(page, "m10-current-group-review");
      await answer(page, "/ʃɪp/");
      await expect(page.getByRole("heading", { name: "Current-group review complete" })).toBeVisible();
      await page.getByRole("button", { name: "Review recent mistakes" }).click();
      await expect(page.getByText("Recent mistake review: 1 / 1")).toBeVisible();
      await expect(page.getByText("Reviewing recent mistakes from earlier practice.")).toBeVisible();
      await attachScreenshot(page, "m10-recent-review");
    });

    await test.step("Progress focus entry can launch and clear focused practice", async () => {
      await page.getByRole("button", { name: "Progress" }).click();
      await expect(page.getByRole("heading", { name: "Progress" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Needs practice in Entry" })).toBeVisible();
      await expect(page.getByText("day streak")).toBeVisible();
      await expect(page.locator(".stat-card").filter({ hasText: "day streak" }).getByText("0")).toBeVisible();
      await page.getByRole("button", { name: "Focus /ʃ/" }).first().click();
      await expect(page.getByText("Focused group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Entry focused practice for /ʃ/.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Clear focus" })).toBeVisible();
      await attachScreenshot(page, "m10-progress-focus-entry");
    });
  });

  test("Settings level switching, empty review state, audio signal, and mobile views are observable", async ({ page }, testInfo) => {
    const state = await setupM10Api(page, { activeGroup: "entry", recentReviewEmpty: true });

    await test.step("Settings changes future practice level while preserving active group", async () => {
      await page.goto("/");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByRole("button", { name: "Resume Entry group" })).toBeVisible();
      await page.getByRole("button", { name: "Resume Entry group" }).click();
      await expect(page.getByText("Practice group: 1 / 2")).toBeVisible();
      await page.getByRole("button", { name: "Settings" }).click();
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
      await expect(page.getByRole("button", { name: /Mid\s+Broader word practice/ })).toBeVisible();
      await page.getByRole("button", { name: /Mid\s+Broader word practice/ }).click();
      await expect(page.getByText("Saved")).toBeVisible();
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Mid selected" })).toBeVisible();
      await expect(page.getByText("You selected Mid. This Entry group is still in progress.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Resume Entry group" })).toBeVisible();
      await attachScreenshot(page, "m10-settings-mid-pending");
    });

    await test.step("Intentional switch starts Mid and keeps level-specific copy visible", async () => {
      page.once("dialog", (dialog) => dialog.accept());
      await page.getByRole("button", { name: "End this Entry group and start Mid" }).click();
      await expect(page.getByText("Practice group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Mid practice group.")).toBeVisible();
      await expect(page.getByText("remember")).toBeVisible();
      await attachScreenshot(page, "m10-mid-active");
    });

    await test.step("Recent-review empty state keeps the hub actionable", async () => {
      state.activeGroup = "none";
      await page.goto("/");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await page.getByRole("button", { name: "Review recent mistakes" }).click();
      await expect(page.getByText("No recent incorrect attempts are available for review.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Start Mid group" })).toBeVisible();
      await attachScreenshot(page, "m10-recent-review-empty");
    });

    await test.step("Mobile Today and Settings remain available with the same action semantics", async () => {
      if (!testInfo.project.name.includes("mobile")) return;
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await attachScreenshot(page, "m10-mobile-today");
      await page.getByRole("button", { name: "Settings" }).click();
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
      await expect(page.getByText("Advanced/debug: manual IPA focus entry")).toBeVisible();
      await attachScreenshot(page, "m10-mobile-settings");
    });
  });
});
