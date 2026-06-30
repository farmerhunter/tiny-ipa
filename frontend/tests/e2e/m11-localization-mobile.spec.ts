import { expect, type Locator, type Page, type Route, test } from "@playwright/test";

type Locale = "zh-CN" | "en-US";
type LearnerLevel = "entry" | "mid";
type GroupKey = "none" | "entry" | "currentReview" | "recentReview" | "focused";
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
  uiLanguage: Locale;
  selectedLevel: LearnerLevel;
  activeGroup: GroupKey;
  completed: Record<LearnerLevel, number>;
  focusPhonemes: string[];
  recentMistakeCount: number;
  recentReviewEmpty: boolean;
}

const copy = {
  "zh-CN": {
    todayHub: "今日练习中心",
    startPractice: "开始 入门 练习",
    startGroup: "开始 入门 组",
    resumeGroup: "继续 入门 组",
    settings: "设置",
    languageTitle: "界面语言",
    saved: "已保存",
    practiceLabel: "练习组: 1 / 2",
    browserVoice: "浏览器语音",
    recordedAudio: "录音音频",
    incorrect: "还不对。",
    continue: "继续",
    complete: "练习组 完成",
    currentReviewAction: "复习本组错题",
    currentReviewLabel: "当前组复习: 1 / 1",
    recentReviewAction: "复习 1 个较早错题",
    recentReviewLabel: "近期错题复习: 1 / 1",
    progress: "进度",
    progressHeading: "入门 需要回顾的声音",
    focusAction: "聚焦 /ʃ/",
    focusedLabel: "聚焦练习组: 1 / 1",
    emptyReview: "没有可供复习的近期错误记录。",
    audioUnavailable: "音频不可用",
    errorTitle: "练习暂不可用",
    backToday: "← 今日",
    soundCompareStart: "开始声音对比",
    soundCompareUnavailable: "声音对比练习暂不可用。需要至少两个带配对元数据的安全词。",
  },
  "en-US": {
    todayHub: "Today practice hub",
    startPractice: "Start Entry practice",
    startGroup: "Start Entry group",
    resumeGroup: "Resume Entry group",
    settings: "Settings",
    languageTitle: "UI language",
    saved: "Saved",
    practiceLabel: "Practice group: 1 / 2",
    browserVoice: "Browser voice",
    recordedAudio: "Recorded audio",
    incorrect: "Not quite.",
    continue: "Continue",
    complete: "Practice group complete",
    currentReviewAction: "Review this group's misses",
    currentReviewLabel: "Current-group review: 1 / 1",
    recentReviewAction: "Review 1 older mistake",
    recentReviewLabel: "Recent mistake review: 1 / 1",
    progress: "Progress",
    progressHeading: "Sounds to revisit in Entry",
    focusAction: "Focus /ʃ/",
    focusedLabel: "Focused group: 1 / 1",
    emptyReview: "No recent incorrect attempts are available for review.",
    audioUnavailable: "Audio unavailable",
    errorTitle: "Practice unavailable",
    backToday: "← Today",
    soundCompareStart: "Start Sound Compare",
    soundCompareUnavailable: "Sound Compare practice is not available yet. It needs at least two safe words with pair metadata.",
  },
} as const;

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
      date: "2026-06-29",
      primary_accent: "US",
      origin: "normal_empty",
      source_scope: "normal_none",
      focus_phonemes: state.focusPhonemes,
      daily_word_count: 2,
      recent_mistake_count: state.recentMistakeCount,
      word_count: 0,
      status: "idle",
      source_session_item_ids: [],
      target_phoneme_options: [
        { phoneme: "/ʃ/", symbol: "ʃ", example_word: "ship", candidate_count: 2 },
      ],
      items: [],
    };
  }

  const review = state.activeGroup === "currentReview" || state.activeGroup === "recentReview";
  const focus = state.activeGroup === "focused";
  return {
    session_id: `${state.activeGroup}-session`,
    group_id: `${state.activeGroup}-group`,
    group_index: 1,
    group_type: groupType(state.activeGroup),
    learner_level: "entry",
    learner_level_label: "Entry",
    selected_learner_level: state.selectedLevel,
    selected_learner_level_label: levelLabel(state.selectedLevel),
    pending_level_change: false,
    completed_normal_groups_today: {
      entry: state.completed.entry,
      mid: state.completed.mid,
      total: state.completed.entry + state.completed.mid,
    },
    date: "2026-06-29",
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
    recent_mistake_count: state.recentMistakeCount,
    word_count: items[state.activeGroup].length,
    status: "active",
    source_session_item_ids: review ? ["entry-ship"] : [],
    source_count: review ? 1 : 0,
    target_phoneme_options: [
      { phoneme: "/ʃ/", symbol: "ʃ", example_word: "ship", candidate_count: 2 },
    ],
    items: items[state.activeGroup].map((item) => ({
      ...item,
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
    ui_language: state.uiLanguage,
    focus_phonemes: state.focusPhonemes,
  };
}

function progressResponse(state: MockState) {
  return {
    today_completed: false,
    today_status: state.activeGroup === "none" ? "none" : "in_progress",
    streak_days: 0,
    total_attempts: 2,
    total_sessions: 1,
    total_normal_groups: 1,
    stat_scope: "global",
    level_stats: {
      entry: {
        learner_level: "entry",
        label: "Entry",
        attempts: 2,
        correct_attempts: 1,
        accuracy: 0.5,
        normal_groups: 1,
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
        normal_groups: 0,
        completed_normal_groups: 0,
        completed_normal_groups_today: 0,
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

async function setupApi(page: Page, locale: Locale, options: Partial<MockState> = {}) {
  const state: MockState = {
    uiLanguage: locale,
    selectedLevel: options.selectedLevel ?? "entry",
    activeGroup: options.activeGroup ?? "none",
    completed: options.completed ?? { entry: 0, mid: 0 },
    focusPhonemes: options.focusPhonemes ?? [],
    recentMistakeCount: options.recentMistakeCount ?? 0,
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
      json: { status: "ok", content_version: "m11-localization-mobile", db_ready: true },
    });
    return;
  }

  if (path === "/settings") {
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as {
        learner_level?: LearnerLevel;
        ui_language?: Locale;
        focus_phonemes?: string[];
      };
      if (body.learner_level) state.selectedLevel = body.learner_level;
      if (body.ui_language) state.uiLanguage = body.ui_language;
      if (body.focus_phonemes) state.focusPhonemes = body.focus_phonemes;
    }
    await route.fulfill({ json: settingsResponse(state) });
    return;
  }

  if (path === "/today") {
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/progress") {
    await route.fulfill({ json: progressResponse(state) });
    return;
  }

  if (path === "/practice/next-normal") {
    state.activeGroup = "entry";
    await route.fulfill({ json: todayResponse(state) });
    return;
  }

  if (path === "/attempt") {
    const body = request.postDataJSON() as { session_item_id: string; selected_answer: string };
    const item = Object.values(items)
      .flat()
      .find((candidate) => candidate.session_item_id === body.session_item_id);
    if (!item) {
      await route.fulfill({ status: 404, json: { detail: "Unknown item" } });
      return;
    }
    if (state.activeGroup === "entry" && item.session_item_id === "entry-thin") {
      state.completed.entry += 1;
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
          detail:
            state.uiLanguage === "zh-CN"
              ? "没有可供复习的近期错误记录。"
              : "No recent incorrect attempts are available for review.",
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

  if (path === "/practice/minimal-pairs") {
    await route.fulfill({
      json: {
        ...todayResponse(state),
        status: "empty",
        items: [],
        detail: "Sound Compare practice is not available yet. It needs at least two safe words with pair metadata.",
      },
    });
    return;
  }

  await route.fallback();
}

async function answer(page: Page, choice: string) {
  await page.getByRole("button", { name: new RegExp(escapeRegExp(choice)) }).first().click();
}

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function attachScreenshot(page: Page, name: string) {
  const path = test.info().outputPath(`${name}.png`);
  await page.screenshot({ fullPage: true, path });
  await test.info().attach(name, { path, contentType: "image/png" });
}

async function visibleBoxes(locator: Locator) {
  return locator.evaluateAll((elements) =>
    elements
      .filter((element) => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.visibility !== "hidden" && style.display !== "none" && box.width > 0 && box.height > 0;
      })
      .map((element) => {
        const box = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          text: (element.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80),
          left: box.left,
          right: box.right,
          top: box.top,
          bottom: box.bottom,
          width: box.width,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
        };
      }),
  );
}

async function expectMobileTextFit(page: Page, label: string) {
  const checked = page.locator(
    "main, header, nav, section, .focus-panel, .settings-form, .summary-actions, button, input, select, h1, h2, h3, p, li, span",
  );
  const boxes = await visibleBoxes(checked);
  const viewportWidth = page.viewportSize()?.width ?? 393;
  const overflow = boxes.filter(
    (box) =>
      box.left < -1 ||
      box.right > viewportWidth + 1 ||
      (box.clientWidth > 0 && box.scrollWidth - box.clientWidth > 1),
  );
  expect(overflow, `${label}: visible localized UI should not overflow mobile width`).toEqual([]);

  const actionBoxes = await visibleBoxes(page.locator("button:visible"));
  const overlaps: string[] = [];
  for (let index = 0; index < actionBoxes.length; index += 1) {
    for (let next = index + 1; next < actionBoxes.length; next += 1) {
      const a = actionBoxes[index];
      const b = actionBoxes[next];
      const horizontal = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const vertical = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (horizontal > 1 && vertical > 1) {
        overlaps.push(`${a.text} <> ${b.text}`);
      }
    }
  }
  expect(overlaps, `${label}: visible primary/action buttons should not overlap`).toEqual([]);
}

async function expectLocalizedShell(page: Page, locale: Locale, label: string) {
  await expect(page.getByText(copy[locale].todayHub)).toBeVisible();
  await expectMobileTextFit(page, label);
  if (locale === "zh-CN") {
    await expectNoZhCnBlockerLeaks(page, label);
  }
}

async function expectNoZhCnBlockerLeaks(page: Page, label: string) {
  const visibleText = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  const forbidden = [
    "Start Mid group",
    "Start Entry group",
    "Resume Entry group",
    "Entry practice",
    "Mid practice",
    "Entry group",
    "Mid group",
    "Sounds to revisit in Entry",
    "Sounds to revisit in Mid",
    "Sound Compare practice is not available yet. It needs at least two safe words with pair metadata.",
  ];
  for (const text of forbidden) {
    expect(visibleText, `${label}: should not show ${text}`).not.toContain(text);
  }
  expect(visibleText, `${label}: unresolved locale placeholders`).not.toMatch(/\{(?:level|groupIndex|selectedLevel|currentLevel)\}/);
}

test.describe("M11 bilingual mobile walkthrough and text-fit evidence", () => {
  for (const locale of ["zh-CN", "en-US"] as const) {
    test(`${locale} mobile learner workflow surfaces keep localized copy visible and fitted`, async ({ page }) => {
      test.setTimeout(90_000);
      await setupApi(page, locale);

      await test.step("Settings language selection is visible and can round-trip locale", async () => {
        await page.goto("/");
        await expectLocalizedShell(page, locale, `${locale} today hub initial`);
        await page.getByRole("button", { name: copy[locale].settings }).click();
        await expect(page.getByRole("heading", { name: copy[locale].settings })).toBeVisible();
        await expect(page.getByText(copy[locale].languageTitle)).toBeVisible();
        await expectMobileTextFit(page, `${locale} settings language`);
        if (locale === "zh-CN") {
          await expectNoZhCnBlockerLeaks(page, `${locale} settings language`);
        }

        const otherLocale = locale === "zh-CN" ? "en-US" : "zh-CN";
        await page.locator("select").filter({ hasText: /zh-CN|en-US/ }).selectOption(otherLocale);
        await expect(page.getByText(copy[otherLocale].saved)).toBeVisible();
        await expect(page.getByRole("heading", { name: copy[otherLocale].settings })).toBeVisible();
        await expectMobileTextFit(page, `${locale} settings switched to ${otherLocale}`);
        await page.locator("select").filter({ hasText: /zh-CN|en-US/ }).selectOption(locale);
        await expect(page.getByText(copy[locale].saved)).toBeVisible();
        await page.getByRole("button", { name: copy[locale].backToday }).click();
      });

      await test.step("Today hub, normal practice, audio controls, and completion fit mobile", async () => {
        await expect(page.getByRole("heading", { name: copy[locale].startPractice })).toBeVisible();
        await expect(page.getByRole("button", { name: copy[locale].startGroup })).toBeVisible();
        await attachScreenshot(page, `m11-${locale}-today-hub`);
        await expectMobileTextFit(page, `${locale} today hub`);

        await page.getByRole("button", { name: copy[locale].startGroup }).click();
        await expect(page.getByText(copy[locale].practiceLabel)).toBeVisible();
        await expect(page.getByText(copy[locale].browserVoice)).toBeVisible();
        await expectMobileTextFit(page, `${locale} normal practice browser audio`);
        if (locale === "zh-CN") {
          await expectNoZhCnBlockerLeaks(page, `${locale} normal practice browser audio`);
        }
        await answer(page, "/sɪp/");
        await expect(page.getByText(copy[locale].incorrect)).toBeVisible();
        await expect(page.getByRole("button", { name: copy[locale].continue })).toBeVisible();
        await attachScreenshot(page, `m11-${locale}-wrong-answer-audio`);
        await expectMobileTextFit(page, `${locale} wrong-answer feedback`);

        await page.getByRole("button", { name: copy[locale].continue }).click();
        await expect(page.getByText(copy[locale].recordedAudio)).toBeVisible();
        await answer(page, "/θɪn/");
        await expect(page.getByRole("heading", { name: copy[locale].complete })).toBeVisible();
        await expect(page.getByRole("button", { name: copy[locale].currentReviewAction })).toBeVisible();
        await attachScreenshot(page, `m11-${locale}-completion-review-actions`);
        await expectMobileTextFit(page, `${locale} completion summary`);
      });

      await test.step("Review, Progress, and focused practice surfaces fit mobile", async () => {
        await page.getByRole("button", { name: copy[locale].currentReviewAction }).click();
        await expect(page.getByText(copy[locale].currentReviewLabel)).toBeVisible();
        await expectMobileTextFit(page, `${locale} current-group review`);
        await answer(page, "/ʃɪp/");
        await expect(page.getByRole("heading", { name: new RegExp(copy[locale].currentReviewLabel.split(":")[0]) })).toBeVisible();
        await page.getByRole("button", { name: copy[locale].recentReviewAction }).click();
        await expect(page.getByText(copy[locale].recentReviewLabel)).toBeVisible();
        await attachScreenshot(page, `m11-${locale}-recent-review`);
        await expectMobileTextFit(page, `${locale} recent review`);

        await page.getByRole("button", { name: copy[locale].progress }).click();
        await expect(page.getByRole("heading", { name: copy[locale].progress, exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: copy[locale].progressHeading })).toBeVisible();
        await expectMobileTextFit(page, `${locale} progress`);
        if (locale === "zh-CN") {
          await expectNoZhCnBlockerLeaks(page, `${locale} progress`);
        }
        await page.getByRole("button", { name: copy[locale].focusAction }).first().click();
        await expect(page.getByText(copy[locale].focusedLabel)).toBeVisible();
        await attachScreenshot(page, `m11-${locale}-progress-focus`);
        await expectMobileTextFit(page, `${locale} focused practice`);
        if (locale === "zh-CN") {
          await expectNoZhCnBlockerLeaks(page, `${locale} focused practice`);
        }
      });
    });

    test(`${locale} mobile common empty, API error, and unavailable audio states stay fitted`, async ({ page }) => {
      await page.addInitScript(() => {
        Object.defineProperty(window, "speechSynthesis", {
          configurable: true,
          value: undefined,
        });
      });
      const state = await setupApi(page, locale, {
        activeGroup: "entry",
        recentMistakeCount: 1,
        recentReviewEmpty: true,
      });

      await page.goto("/");
      await page.getByRole("button", { name: copy[locale].resumeGroup }).click();
      await page.getByRole("button", { name: new RegExp(locale === "zh-CN" ? "浏览器语音" : "browser voice", "i") }).click();
      await expect(page.getByText(copy[locale].audioUnavailable)).toBeVisible();
      await attachScreenshot(page, `m11-${locale}-audio-unavailable`);
      await expectMobileTextFit(page, `${locale} audio unavailable`);

      state.activeGroup = "none";
      await page.goto("/");
      await page.getByRole("button", { name: copy[locale].recentReviewAction }).click();
      await expect(page.getByText(copy[locale].emptyReview)).toBeVisible();
      await attachScreenshot(page, `m11-${locale}-empty-review`);
      await expectMobileTextFit(page, `${locale} empty review`);
      if (locale === "zh-CN") {
        await expectNoZhCnBlockerLeaks(page, `${locale} empty review`);
      }

      await page.getByRole("button", { name: copy[locale].soundCompareStart }).click();
      await expect(page.getByText(copy[locale].soundCompareUnavailable)).toBeVisible();
      await expectMobileTextFit(page, `${locale} sound compare unavailable`);
      if (locale === "zh-CN") {
        await expectNoZhCnBlockerLeaks(page, `${locale} sound compare unavailable`);
      }

      await page.unroute("**/api/**");
      await page.route("**/api/health", async (route) => {
        await route.fulfill({ json: { status: "ok", content_version: "m11-error", db_ready: true } });
      });
      await page.route("**/api/settings", async (route) => {
        await route.fulfill({ json: settingsResponse(state) });
      });
      await page.route("**/api/today", async (route) => {
        await route.fulfill({ status: 500, json: { detail: "forced test failure" } });
      });
      await page.reload();
      await expect(page.getByText(copy[locale].errorTitle)).toBeVisible();
      await attachScreenshot(page, `m11-${locale}-today-error`);
      await expectMobileTextFit(page, `${locale} today error`);
    });
  }
});
