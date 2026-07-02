import { expect, type Page, type Route, test } from "@playwright/test";

type LearnerLevel = "entry" | "mid";
type GroupKey = "none" | "entry" | "mid" | "currentReview" | "recentReview" | "focused" | "minimalPair" | "targetPhoneme";
type GroupType = "normal" | "mistake_review" | "weak_focus" | "minimal_pair" | "target_phoneme";

interface MockItem {
  session_item_id: string;
  word_id: string;
  display_ipa: string;
  word: string;
  meaning_zh: string | null;
  target_phonemes: string[];
  choices: string[];
  audio_url: string | null;
  accent_compare?: {
    enabled: boolean;
    primary: {
      accent: "US";
      label: string;
      ipa: string;
    };
    comparison: {
      accent: "UK";
      label: string;
      ipa: string;
      phoneme_tags: string[];
      review_note: string;
    };
  };
}

interface MockState {
  selectedLevel: LearnerLevel;
  activeGroup: GroupKey;
  completed: Record<LearnerLevel, number>;
  focusPhonemes: string[];
  recentMistakeCount: number;
  recentReviewEmpty: boolean;
  showAccentCompare: boolean;
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
      accent_compare: {
        enabled: true,
        primary: {
          accent: "US",
          label: "American sound",
          ipa: "/ʃɪp/",
        },
        comparison: {
          accent: "UK",
          label: "British note",
          ipa: "/ʃɪp-uk/",
          phoneme_tags: ["/ʃ/", "/ɪ/", "/p/"],
          review_note: "Display-only comparison. Your answer is still graded against the American IPA.",
        },
      },
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
  minimalPair: [
    {
      session_item_id: "minimal-ship",
      word_id: "ship",
      display_ipa: "/ʃɪp/",
      word: "ship",
      meaning_zh: "船",
      target_phonemes: ["/ʃ/", "/ɪ/", "/p/"],
      choices: ["/ʃɪp/", "/ʃiːp/"],
      audio_url: null,
    },
    {
      session_item_id: "minimal-sheep",
      word_id: "sheep",
      display_ipa: "/ʃiːp/",
      word: "sheep",
      meaning_zh: "羊",
      target_phonemes: ["/ʃ/", "/iː/", "/p/"],
      choices: ["/ʃɪp/", "/ʃiːp/"],
      audio_url: null,
    },
  ],
  targetPhoneme: [
    {
      session_item_id: "target-ship",
      word_id: "ship",
      display_ipa: "/ʃɪp/",
      word: "ship",
      meaning_zh: "船",
      target_phonemes: ["/ʃ/", "/ɪ/", "/p/"],
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
  if (group === "minimalPair") return "minimal_pair";
  if (group === "targetPhoneme") return "target_phoneme";
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
      recent_mistake_count: state.recentMistakeCount,
      word_count: 0,
      status: "idle",
      source_session_item_ids: [],
      target_phoneme_options: [
        {
          phoneme: "/ʃ/",
          symbol: "ʃ",
          example_word: "ship",
          candidate_count: 2,
        },
        {
          phoneme: "/θ/",
          symbol: "θ",
          example_word: "thin",
          candidate_count: 1,
        },
      ],
      items: [],
    };
  }

  const level = groupLevel(state.activeGroup);
  const review = state.activeGroup === "currentReview" || state.activeGroup === "recentReview";
  const focus = state.activeGroup === "focused";
  const minimalPair = state.activeGroup === "minimalPair";
  const targetPhoneme = state.activeGroup === "targetPhoneme";
  return {
    session_id: `${state.activeGroup}-session`,
    group_id: `${state.activeGroup}-group`,
    group_index: state.activeGroup === "mid" ? 2 : 1,
    group_type: groupType(state.activeGroup),
    learner_level: level,
    learner_level_label: levelLabel(level),
    selected_learner_level: state.selectedLevel,
    selected_learner_level_label: levelLabel(state.selectedLevel),
    pending_level_change: !review && !focus && !minimalPair && !targetPhoneme && state.selectedLevel !== level,
    completed_normal_groups_today: {
      entry: state.completed.entry,
      mid: state.completed.mid,
      total: state.completed.entry + state.completed.mid,
    },
    date: "2026-06-18",
    primary_accent: "US",
    origin: targetPhoneme
      ? "target_phoneme_start"
      : minimalPair
      ? "minimal_pair_start"
      : focus
        ? "focus_start"
        : review
          ? "current_group_review_start"
          : "normal_start",
    source_scope:
      state.activeGroup === "currentReview"
        ? "current_group"
        : state.activeGroup === "recentReview"
          ? "recent_global"
          : focus
            ? "focus_selection"
            : minimalPair
              ? "specialty_minimal_pair"
              : targetPhoneme
                ? "specialty_target_phoneme"
              : "normal_current",
    source_group_id: review ? "entry-group" : undefined,
    focus_phonemes: focus || targetPhoneme ? state.focusPhonemes : [],
    daily_word_count: items[state.activeGroup].length,
    recent_mistake_count: state.recentMistakeCount,
    word_count: items[state.activeGroup].length,
    status: "active",
    source_session_item_ids: review ? ["entry-ship"] : [],
    source_count: review ? 1 : 0,
    action_label: targetPhoneme
      ? "Start Sound Practice Group 1"
      : minimalPair
        ? "Start Sound Compare Group 1"
        : undefined,
    target_phoneme_options: [
      {
        phoneme: "/ʃ/",
        symbol: "ʃ",
        example_word: "ship",
        candidate_count: 2,
      },
      {
        phoneme: "/θ/",
        symbol: "θ",
        example_word: "thin",
        candidate_count: 1,
      },
    ],
    items: items[state.activeGroup].map((item) => ({
      session_item_id: item.session_item_id,
      word_id: item.word_id,
      display_ipa: item.display_ipa,
      word: item.word,
      meaning_zh: item.meaning_zh,
      audio_url: item.audio_url,
      target_phonemes: item.target_phonemes,
      accent_compare: state.showAccentCompare ? item.accent_compare : undefined,
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
    show_accent_compare: state.showAccentCompare,
    practice_mode: "ipa_first",
    review_strength: "normal",
    learner_level: state.selectedLevel,
    ui_language: "en-US",
    focus_phonemes: state.focusPhonemes,
  };
}

function progressResponse(state: MockState) {
  const entryResumableGroups = state.activeGroup === "entry" ? 1 : 0;
  const midResumableGroups = state.activeGroup === "mid" ? 1 : 0;
  return {
    today_completed: false,
    today_status: state.activeGroup === "none" ? "none" : "in_progress",
    streak_days: state.completed.entry > 0 ? 0 : 0,
    total_attempts: state.completed.entry > 0 ? 2 : 0,
    total_sessions: state.completed.entry + state.completed.mid,
    total_normal_groups: state.completed.entry + state.completed.mid + entryResumableGroups + midResumableGroups,
    resumable_normal_groups: entryResumableGroups + midResumableGroups,
    stat_scope: "global",
    level_stats: {
      entry: {
        learner_level: "entry",
        label: "Entry",
        attempts: state.completed.entry > 0 ? 2 : 0,
        correct_attempts: state.completed.entry > 0 ? 1 : 0,
        accuracy: state.completed.entry > 0 ? 0.5 : null,
        normal_groups: state.completed.entry + entryResumableGroups,
        completed_normal_groups: state.completed.entry,
        completed_normal_groups_today: state.completed.entry,
        resumable_normal_groups: entryResumableGroups,
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
        resumable_normal_groups: midResumableGroups,
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
    recentMistakeCount: options.recentMistakeCount ?? 0,
    recentReviewEmpty: options.recentReviewEmpty ?? false,
    showAccentCompare: options.showAccentCompare ?? false,
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

  if (path === "/auth/me") {
    await route.fulfill({
      json: { authenticated: true, user: { id: "default", username: "owner", is_owner: true } },
    });
    return;
  }

  if (path === "/settings") {
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as {
        learner_level?: LearnerLevel;
        focus_phonemes?: string[];
        daily_word_count?: number;
        show_accent_compare?: boolean;
      };
      if (body.learner_level) state.selectedLevel = body.learner_level;
      if (body.focus_phonemes) state.focusPhonemes = body.focus_phonemes;
      if (typeof body.show_accent_compare === "boolean") {
        state.showAccentCompare = body.show_accent_compare;
      }
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

  if (path === "/practice/minimal-pairs") {
    state.activeGroup = "minimalPair";
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/practice/target-phoneme") {
    const body = request.postDataJSON() as { phoneme?: string };
    state.focusPhonemes = body.phoneme ? [body.phoneme] : ["/ʃ/"];
    state.activeGroup = "targetPhoneme";
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
    if (body.selected_answer !== item.display_ipa) {
      state.recentMistakeCount = Math.max(state.recentMistakeCount, 1);
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
    if (state.recentReviewEmpty || state.recentMistakeCount === 0) {
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
        detail: "Focus cleared. Back to regular practice.",
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
    test.setTimeout(60_000);
    await setupM10Api(page);

    await test.step("Today start orientation", async () => {
      await page.goto("/");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Start Entry practice" })).toBeVisible();
      await expect(page.getByText("Ready when you are")).toBeVisible();
      await expect(page.getByText("A short listening group is ready.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Start Entry group" })).toBeVisible();
      await expect(page.getByRole("button", { name: "No older mistakes to review" })).toBeDisabled();
      await expect(page.getByRole("button", { name: "End this group and start fresh Entry" })).toHaveCount(0);
      await attachScreenshot(page, "m10-today-start");
    });

    await test.step("Wrong answer feedback remains inspectable until learner continues", async () => {
      await page.getByRole("button", { name: "Start Entry group" }).click();
      await expect(page.getByText("Practice group: 1 / 2")).toBeVisible();
      await expect(page.getByRole("button", { name: "Play pronunciation with browser voice" })).toBeVisible();
      await expect(page.getByText("Browser voice")).toBeVisible();
      await answer(page, "/sɪp/");
      await expect(page.getByText("Not quite")).toBeVisible();
      await expect(page.getByText("You picked")).toBeVisible();
      await expect(page.getByText("Correct IPA")).toBeVisible();
      await expect(page.getByText("Target sound")).toBeVisible();
      await expect(page.getByRole("button", { name: "Play pronunciation with browser voice" })).toBeVisible();
      await expect(page.getByText("Browser voice")).toBeVisible();
      await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();
      await attachScreenshot(page, "m10-wrong-answer-feedback");
      await page.waitForTimeout(1_800);
      await expect(page.getByText("Practice group: 1 / 2")).toBeVisible();
      await expect(page.getByText("Not quite")).toBeVisible();
      await page.getByRole("button", { name: "Continue" }).click();
      await expect(page.getByRole("button", { name: "Select /θɪn/" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Play recorded pronunciation" })).toBeVisible();
      await expect(page.getByText("Recorded audio")).toBeVisible();
    });

    await test.step("Completion summary exposes current-group recovery and next choices", async () => {
      await answer(page, "/θɪn/");
      await expect(page.getByRole("heading", { name: "Practice group complete" })).toBeVisible({
        timeout: 10_000,
      });
      await expect(page.getByText("1 / 2 correct")).toBeVisible();
      await expect(page.getByRole("heading", { name: "This group's misses" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review this group's misses" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review 1 older mistake" })).toBeVisible();
      await attachScreenshot(page, "m10-completion-recovery-actions");
    });

    await test.step("Current-group review and recent review use different source copy", async () => {
      await page.getByRole("button", { name: "Review this group's misses" }).click();
      await expect(page.getByText("Current-group review: 1 / 1")).toBeVisible();
      await expect(page.getByText("Reviewing misses from the group you just finished, before older mistakes.")).toBeVisible();
      await attachScreenshot(page, "m10-current-group-review");
      await answer(page, "/ʃɪp/");
      await expect(page.getByRole("heading", { name: "Current-group review complete" })).toBeVisible();
      await page.getByRole("button", { name: "Review 1 older mistake" }).click();
      await expect(page.getByText("Recent mistake review: 1 / 1")).toBeVisible();
      await expect(page.getByText("Reviewing older mistakes from earlier practice.")).toBeVisible();
      await attachScreenshot(page, "m10-recent-review");
    });

    await test.step("Progress focus entry can launch and clear focused practice", async () => {
      await page.getByRole("button", { name: "Progress" }).click();
      await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Sounds to revisit in Entry" })).toBeVisible();
      await expect(page.getByText("today's practice state")).toBeVisible();
      await expect(page.getByText("In progress", { exact: true })).toBeVisible();
      await expect(page.getByText("all-time answered items", { exact: true })).toBeVisible();
      await expect(page.getByText("all-time completed regular groups", { exact: true })).toBeVisible();
      await expect(page.getByText("Entry has sounds ready for focused practice.")).toBeVisible();
      await expect(page.getByText("Mid has no all-time answered items yet. Select this level in Settings, then start from Today.")).toBeVisible();
      await expect(page.getByText("1 active", { exact: true })).toHaveCount(0);
      await expect(page.getByText("1 active groups", { exact: true })).toHaveCount(0);
      await page.getByRole("button", { name: "Focus /ʃ/" }).first().click();
      await expect(page.getByText("Focused group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Entry focused practice for /ʃ/.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Clear focus" })).toBeVisible();
      await attachScreenshot(page, "m10-progress-focus-entry");
    });
  });

  test("Sound Compare specialty practice is distinct from review and focus", async ({ page }) => {
    await setupM10Api(page);

    await page.goto("/");
    await expect(page.getByText("Today practice hub")).toBeVisible();
    await expect(page.getByText("Specialty practice").first()).toBeVisible();
    await expect(page.getByText("Sound Compare", { exact: true })).toBeVisible();
    await expect(page.getByText("Compare words with easily confused sounds. This is separate from mistake review and weak-sound focus.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start Sound Compare" })).toBeVisible();
    await attachScreenshot(page, "m9-minimal-pair-entry");

    await page.getByRole("button", { name: "Start Sound Compare" }).click();
    await expect(page.getByText("Sound Compare group: 1 / 2")).toBeVisible();
    await expect(page.getByText("Compare words with easily confused sounds. This is separate from mistake review and weak-sound focus.")).toBeVisible();
    await expect(page.getByText("Current-group review:")).toHaveCount(0);
    await expect(page.getByText("Recent mistake review:")).toHaveCount(0);
    await expect(page.getByText("Focused group:")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Select /ʃɪp/" })).toBeVisible();
    await attachScreenshot(page, "m9-minimal-pair-active");
  });

  test("Sound Practice uses guided chosen-sound entry distinct from weak focus", async ({ page }) => {
    await setupM10Api(page);

    await page.goto("/");
    await expect(page.getByText("Today practice hub")).toBeVisible();
    await expect(page.getByText("Sound Practice", { exact: true })).toBeVisible();
    await expect(page.getByText("Pick one approved American sound for intentional practice. This is separate from weak-sound recovery.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Practice /ʃ/" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Practice /θ/" })).toBeVisible();
    await attachScreenshot(page, "m9-target-phoneme-entry");

    await page.getByRole("button", { name: "Practice /ʃ/" }).click();
    await expect(page.getByText("Sound Practice group: 1 / 1")).toBeVisible();
    await expect(page.getByText("Intentional practice for /ʃ/. This is a chosen-sound specialty group, not weak-sound recovery.")).toBeVisible();
    await expect(page.getByText("Chosen sound")).toBeVisible();
    await expect(page.getByText("Current focus")).toHaveCount(0);
    await expect(page.getByText("Focused group:")).toHaveCount(0);
    await expect(page.getByText("Current-group review:")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Select /ʃɪp/" })).toBeVisible();
    await attachScreenshot(page, "m9-target-phoneme-active");
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
      await expect(page.getByText("Entry uses the starter word pool. Mid uses the larger intermediate word pool. This choice applies to the next new regular group; active groups stay unchanged.")).toBeVisible();
      await expect(page.getByRole("button", { name: /Mid\s+Larger intermediate word pool/ })).toBeVisible();
      await page.getByRole("button", { name: /Mid\s+Larger intermediate word pool/ }).click();
      await expect(page.getByText("Saved")).toBeVisible();
      await page.getByRole("button", { name: "Today", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Entry practice in progress" })).toBeVisible();
      await expect(page.getByText("Mid is selected for your next new group. Your current Entry group stays active until you finish it or switch now.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Resume Entry group" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Switch to Mid now" })).toBeVisible();
      await attachScreenshot(page, "m10-settings-mid-pending");
    });

    await test.step("Intentional switch starts Mid and keeps level-specific copy visible", async () => {
      page.once("dialog", (dialog) => dialog.accept());
      await page.getByRole("button", { name: "Switch to Mid now" }).click();
      await expect(page.getByText("Practice group: 1 / 1")).toBeVisible();
      await expect(page.getByText("Mid practice group.")).toBeVisible();
      await expect(page.getByText("remember")).toBeVisible();
      await attachScreenshot(page, "m10-mid-active");
    });

    await test.step("Recent-review empty state keeps the hub actionable", async () => {
      state.activeGroup = "none";
      state.recentMistakeCount = 1;
      await page.goto("/");
      await expect(page.getByText("Today practice hub")).toBeVisible();
      await page.getByRole("button", { name: "Review 1 older mistake" }).click();
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
      await expect(page.getByText("Manual IPA focus entry")).toBeVisible();
      await attachScreenshot(page, "m10-mobile-settings");
      await page.getByRole("button", { name: "Progress" }).click();
      await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
      await expect(page.getByText("today's practice state")).toBeVisible();
      await expect(page.getByText("Ready", { exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Sounds to revisit in Entry" })).toBeVisible();
      await expect(page.getByText("1 active", { exact: true })).toHaveCount(0);
      await expect(page.getByText("1 active groups", { exact: true })).toHaveCount(0);
      await attachScreenshot(page, "m10-mobile-progress");
    });
  });

  test("Audio confidence state explains unavailable playback", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, "speechSynthesis", {
        configurable: true,
        value: undefined,
      });
    });
    await setupM10Api(page, { activeGroup: "entry" });

    await page.goto("/");
    await page.getByRole("button", { name: "Resume Entry group" }).click();
    await expect(page.getByText("Browser voice")).toBeVisible();
    await page.getByRole("button", { name: "Play pronunciation with browser voice" }).click();
    await expect(page.getByText("Audio unavailable")).toBeVisible();
    await attachScreenshot(page, "m10-audio-unavailable-state");
  });

  test("UK comparison is settings-gated and display-only", async ({ page }) => {
    const state = await setupM10Api(page);

    await page.goto("/");
    await page.getByRole("button", { name: "Start Entry group" }).click();
    await answer(page, "/sɪp/");
    await expect(page.getByLabel("Accent comparison")).toHaveCount(0);

    state.activeGroup = "none";
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByLabel("Accent comparison").click();
    await expect(page.getByText("Saved")).toBeVisible();
    await expect(page.getByText("Primary accent")).toHaveCount(0);

    await page.getByRole("button", { name: "Today", exact: true }).click();
    await page.getByRole("button", { name: "Start Entry group" }).click();
    await answer(page, "/sɪp/");

    await expect(page.getByLabel("Accent comparison")).toBeVisible();
    await expect(page.getByText("American sound")).toBeVisible();
    await expect(page.getByText("British note")).toBeVisible();
    await expect(page.getByText("/ʃɪp-uk/")).toBeVisible();
    await expect(page.getByText("Your answer is still graded against the American IPA")).toBeVisible();
    await attachScreenshot(page, "m9-uk-comparison-note");
  });
});
