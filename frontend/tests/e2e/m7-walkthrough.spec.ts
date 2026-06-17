import { expect, type Page, type Route, test } from "@playwright/test";

type GroupType = "normal" | "mistake_review" | "weak_focus";

interface MockItem {
  session_item_id: string;
  word_id: string;
  display_ipa: string;
  word: string;
  meaning_zh: string;
  target_phonemes: string[];
  choices: string[];
}

interface MockGroup {
  session_id: string;
  group_id: string;
  group_index: number;
  group_type: GroupType;
  primary_accent: string;
  items: MockItem[];
}

const groups: Record<string, MockGroup> = {
  group1: {
    session_id: "session-group-1",
    group_id: "group-1",
    group_index: 1,
    group_type: "normal",
    primary_accent: "US",
    items: [
      {
        session_item_id: "group-1-item-1",
        word_id: "ship",
        display_ipa: "/ʃɪp/",
        word: "ship",
        meaning_zh: "船",
        target_phonemes: ["/ʃ/"],
        choices: ["/sɪp/", "/ʃɪp/"],
      },
      {
        session_item_id: "group-1-item-2",
        word_id: "thin",
        display_ipa: "/θɪn/",
        word: "thin",
        meaning_zh: "薄的",
        target_phonemes: ["/θ/"],
        choices: ["/θɪn/", "/sɪn/"],
      },
    ],
  },
  group2: {
    session_id: "session-group-2",
    group_id: "group-2",
    group_index: 2,
    group_type: "normal",
    primary_accent: "US",
    items: [
      {
        session_item_id: "group-2-item-1",
        word_id: "cheese",
        display_ipa: "/tʃiːz/",
        word: "cheese",
        meaning_zh: "奶酪",
        target_phonemes: ["/tʃ/"],
        choices: ["/tʃiːz/", "/ʃiːz/"],
      },
    ],
  },
  recentReview: {
    session_id: "session-recent-review",
    group_id: "recent-review",
    group_index: 3,
    group_type: "mistake_review",
    primary_accent: "US",
    items: [
      {
        session_item_id: "review-item-1",
        word_id: "ship",
        display_ipa: "/ʃɪp/",
        word: "ship",
        meaning_zh: "船",
        target_phonemes: ["/ʃ/"],
        choices: ["/sɪp/", "/ʃɪp/"],
      },
    ],
  },
  currentReview: {
    session_id: "session-current-review",
    group_id: "current-review",
    group_index: 3,
    group_type: "mistake_review",
    primary_accent: "US",
    items: [
      {
        session_item_id: "current-review-item-1",
        word_id: "ship",
        display_ipa: "/ʃɪp/",
        word: "ship",
        meaning_zh: "船",
        target_phonemes: ["/ʃ/"],
        choices: ["/sɪp/", "/ʃɪp/"],
      },
    ],
  },
  focused: {
    session_id: "session-focused",
    group_id: "focused-sh",
    group_index: 4,
    group_type: "weak_focus",
    primary_accent: "US",
    items: [
      {
        session_item_id: "focus-item-1",
        word_id: "shoe",
        display_ipa: "/ʃuː/",
        word: "shoe",
        meaning_zh: "鞋",
        target_phonemes: ["/ʃ/"],
        choices: ["/suː/", "/ʃuː/"],
      },
    ],
  },
};

interface MockState {
  activeGroup: keyof typeof groups;
  completedGroups: Set<string>;
  focusPhonemes: string[];
  failRecentReview: boolean;
}

function toTodayResponse(group: MockGroup) {
  const sourceScope =
    group.group_id === "current-review"
      ? "current_group"
      : group.group_id === "recent-review"
        ? "recent_global"
        : group.group_type === "weak_focus"
          ? "focus_selection"
          : group.group_index > 1
            ? "normal_next"
            : "normal_current";
  return {
    session_id: group.session_id,
    group_id: group.group_id,
    group_index: group.group_index,
    group_type: group.group_type,
    date: "2026-06-17",
    primary_accent: group.primary_accent,
    origin:
      group.group_type === "weak_focus"
        ? "focus_start"
        : sourceScope === "normal_next"
          ? "normal_next"
          : "normal_start",
    source_scope: sourceScope,
    source_group_id: sourceScope === "current_group" ? "group-1" : undefined,
    focus_phonemes: group.group_type === "weak_focus" ? ["/ʃ/"] : [],
    action_label:
      sourceScope === "normal_next" ? `Start Group ${group.group_index}` : undefined,
    daily_word_count: group.items.length,
    word_count: group.items.length,
    status: "active",
    source_session_item_ids:
      group.group_type === "mistake_review" ? ["group-1-item-1"] : [],
    source_count: group.group_type === "mistake_review" ? 1 : 0,
    items: group.items.map((item) => ({
      session_item_id: item.session_item_id,
      word_id: item.word_id,
      display_ipa: item.display_ipa,
      word: item.word,
      meaning_zh: item.meaning_zh,
      audio_url: `/audio/us/${item.word}.mp3`,
      target_phonemes: item.target_phonemes,
      question: {
        type: "ipa_choice",
        prompt: "Pick the matching IPA",
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
    practice_mode: "adaptive",
    review_strength: "normal",
    focus_phonemes: state.focusPhonemes,
  };
}

function progressResponse() {
  return {
    today_completed: false,
    today_status: "active",
    streak_days: 2,
    total_attempts: 8,
    total_sessions: 2,
    weak_phonemes: [
      {
        phoneme: "/ʃ/",
        accuracy: 0.25,
        attempt_count: 4,
        correct_count: 1,
        mastery_status: "weak",
      },
    ],
    strong_phonemes: [
      {
        phoneme: "/θ/",
        accuracy: 0.9,
        attempt_count: 4,
        correct_count: 3,
        mastery_status: "strong",
      },
    ],
  };
}

async function setupMockApi(
  page: Page,
  options: Partial<Pick<MockState, "failRecentReview">> = {},
): Promise<MockState> {
  const state: MockState = {
    activeGroup: "group1",
    completedGroups: new Set(),
    focusPhonemes: [],
    failRecentReview: options.failRecentReview ?? false,
  };

  await page.route("**/api/**", async (route) => {
    await routeMock(route, state);
  });

  return state;
}

async function routeMock(route: Route, state: MockState) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname.replace(/^\/api/, "");

  if (path === "/health") {
    await route.fulfill({
      json: { status: "ok", content_version: "m7-walkthrough", db_ready: true },
    });
    return;
  }

  if (path === "/settings") {
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as { focus_phonemes?: string[] };
      if (Array.isArray(body.focus_phonemes)) {
        state.focusPhonemes = body.focus_phonemes;
      }
    }
    await route.fulfill({ json: settingsResponse(state) });
    return;
  }

  if (path === "/progress") {
    await route.fulfill({ json: progressResponse() });
    return;
  }

  if (path === "/today") {
    if (state.activeGroup === "focused") {
      await route.fulfill({ json: toTodayResponse(groups.group2) });
      return;
    }
    if (state.completedGroups.has("group1")) {
      state.activeGroup = "group2";
    }
    await route.fulfill({ json: toTodayResponse(groups[state.activeGroup]) });
    return;
  }

  if (path === "/practice/next-normal") {
    state.activeGroup = "group2";
    await route.fulfill({ json: toTodayResponse(groups.group2) });
    return;
  }

  if (path === "/attempt") {
    const body = request.postDataJSON() as {
      session_item_id: string;
      selected_answer: string;
    };
    const item = Object.values(groups)
      .flatMap((group) => group.items)
      .find((candidate) => candidate.session_item_id === body.session_item_id);

    if (!item) {
      await route.fulfill({ status: 404, json: { detail: "Unknown item" } });
      return;
    }

    const currentGroup = groups[state.activeGroup];
    const lastItem = currentGroup.items.at(-1);
    if (lastItem?.session_item_id === body.session_item_id) {
      state.completedGroups.add(state.activeGroup);
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

  if (path === "/review/recent-mistakes") {
    if (state.failRecentReview) {
      await route.fulfill({
        status: 500,
        json: { detail: { error: "REVIEW_FAILED", detail: "Review unavailable" } },
      });
      return;
    }
    state.activeGroup = "recentReview";
    await route.fulfill({ json: toTodayResponse(groups.recentReview) });
    return;
  }

  if (path === "/review/current-group") {
    state.activeGroup = "currentReview";
    await route.fulfill({ json: toTodayResponse(groups.currentReview) });
    return;
  }

  if (path === "/practice/focus") {
    const body = request.postDataJSON() as { focus_phonemes?: string[] };
    state.focusPhonemes = body.focus_phonemes ?? ["/ʃ/"];
    state.activeGroup = "focused";
    await route.fulfill({ json: toTodayResponse(groups.focused) });
    return;
  }

  if (path === "/practice/clear-focus") {
    state.focusPhonemes = [];
    state.activeGroup = "group2";
    await route.fulfill({
      json: {
        ...toTodayResponse(groups.group2),
        origin: "focus_clear",
        source_scope: "normal_current",
        focus_phonemes: [],
        detail: "Focus selection cleared.",
      },
    });
    return;
  }

  await route.fallback();
}

async function openWalkthrough(page: Page) {
  await page.goto("/");
  await expect(page.getByText("Group 1: 1 / 2")).toBeVisible();
}

async function answerVisibleItem(page: Page, choice: string) {
  await page.getByRole("button", { name: `Select ${choice}` }).click();
}

async function completeFirstGroupWithOneMiss(page: Page) {
  await answerVisibleItem(page, "/sɪp/");
  await expect(page.getByText("Not quite")).toBeVisible();
  await expect(page.getByText("Target sound")).toBeVisible();
  await page.getByText("Focus on /ʃ/ before choosing.").waitFor();
  await expect(page.getByText("thin")).toBeVisible({ timeout: 4_000 });

  await answerVisibleItem(page, "/θɪn/");
  await expect(page.getByRole("heading", { name: "Group 1 complete" })).toBeVisible({
    timeout: 4_000,
  });
}

test.describe("M7 v2 learner workflow walkthrough", () => {
  test("1-2 normal group start and completion summary expose current result and next actions", async ({ page }) => {
    await setupMockApi(page);
    await test.step("1. normal group start", async () => {
      await openWalkthrough(page);
    });

    await test.step("2. completion summary with current group result and next action choices", async () => {
      await completeFirstGroupWithOneMiss(page);
      await expect(page.getByText("1 / 2 correct")).toBeVisible();
      await expect(page.getByText("ship")).toBeVisible();
      await expect(page.getByText("picked")).toBeVisible();
      await expect(page.getByText("Target sound: /ʃ/")).toBeVisible();
      await expect(page.getByRole("button", { name: "Start next 10-word group" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review misses from Group 1" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Review recent mistakes" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Return to Progress" })).toBeVisible();
    });
  });

  test("3. next normal group action is visibly new/resumed, not an ambiguous repeat", async ({ page }) => {
    await setupMockApi(page);
    await openWalkthrough(page);
    await completeFirstGroupWithOneMiss(page);

    await page.getByRole("button", { name: "Start next 10-word group" }).click();
    await expect(page.getByText("Group 2: 1 / 1")).toBeVisible();
    await expect(page.getByText("A new normal practice group.")).toBeVisible();
    await expect(page.getByText("cheese")).toBeVisible();
  });

  test("4. current-group review and recent/global review are distinguishable", async ({ page }) => {
    await setupMockApi(page);
    await openWalkthrough(page);
    await completeFirstGroupWithOneMiss(page);

    await expect(page.getByRole("button", { name: "Review misses from Group 1" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Review recent mistakes" })).toBeVisible();
    await page.getByRole("button", { name: "Review misses from Group 1" }).click();
    await expect(page.getByText("Reviewing misses from the group you just finished.")).toBeVisible();
  });

  test("5-6. focus can be selected without raw IPA typing and launches focused practice", async ({ page }) => {
    await setupMockApi(page);
    await openWalkthrough(page);
    await page.getByRole("button", { name: "Progress" }).click();
    await expect(page.getByRole("heading", { name: "Progress" })).toBeVisible();
    await expect(page.getByText("Start focused practice from a weak sound.")).toBeVisible();
    await page.getByRole("button", { name: "Focus /ʃ/" }).click();

    await expect(page.getByText("Focused group: 1 / 1")).toBeVisible();
    await expect(page.getByText("Focused practice for /ʃ/.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Clear focus" })).toBeVisible();
    await page.getByRole("button", { name: "Clear focus" }).click();
    await expect(page.getByText("Focus cleared. Back to normal practice.")).toBeVisible();
    const screenshotPath = test.info().outputPath("m7-focus-mobile.png");
    await page.screenshot({ fullPage: true, path: screenshotPath });
    await test.info().attach("m7-focus-mobile", {
      path: screenshotPath,
      contentType: "image/png",
    });
  });

  test("7. stop/return leaves the learner in a known meaningful state", async ({ page }) => {
    await setupMockApi(page);
    await openWalkthrough(page);
    await completeFirstGroupWithOneMiss(page);
    await page.getByRole("button", { name: "Return to Progress" }).click();

    await expect(page.getByRole("heading", { name: "Progress" })).toBeVisible();
    await expect(page.getByText("Needs practice")).toBeVisible();
    await expect(page.getByRole("button", { name: "Today", exact: true })).toBeVisible();
  });

  test("follow-up failure keeps completion summary visible with inline error", async ({ page }) => {
    await setupMockApi(page, { failRecentReview: true });
    await openWalkthrough(page);
    await completeFirstGroupWithOneMiss(page);
    await page.getByRole("button", { name: "Review recent mistakes" }).click();

    await expect(page.getByRole("heading", { name: "Group 1 complete" })).toBeVisible();
    await expect(page.getByText("REVIEW_FAILED: Review unavailable")).toBeVisible();
    await expect(page.getByRole("button", { name: "Review recent mistakes" })).toBeVisible();
  });
});
