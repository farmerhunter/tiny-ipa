import { expect, test, type Page, type Route } from "@playwright/test";

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
  locale: "zh-CN" | "en-US";
  item: MockItem;
  practiceMode: "ipa_first" | "choose_word";
}

const chooseIpaItem: MockItem = {
  session_item_id: "item-choose-ipa",
  word_id: "ship",
  display_ipa: "/ʃɪp/",
  word: "ship",
  meaning_zh: "船；大船",
  audio_url: "/audio/us/ship.mp3",
  target_phonemes: ["/ʃ/", "/ɪ/", "/p/"],
  question: {
    type: "choose_ipa",
    prompt: "Which IPA matches this word?",
    choices: ["/sɪp/", "/ʃɪp/"],
  },
};

const chooseWordItem: MockItem = {
  session_item_id: "item-choose-word",
  word_id: "ship",
  display_ipa: "/ʃɪp/",
  word: "ship",
  meaning_zh: "船；大船",
  audio_url: "/audio/us/ship.mp3",
  target_phonemes: ["/ʃ/", "/ɪ/", "/p/"],
  question: {
    type: "choose_word",
    prompt: "Which word matches this IPA?",
    display_ipa: "/ʃɪp/",
    choices: ["sheep", "ship", "cat"],
  },
};

async function setupApi(
  page: Page,
  state: Omit<MockState, "practiceMode"> & { practiceMode?: MockState["practiceMode"] },
) {
  const mockState: MockState = {
    ...state,
    practiceMode: state.practiceMode ?? (
      state.item.question.type === "choose_word" ? "choose_word" : "ipa_first"
    ),
  };
  await page.route("**/api/**", async (route) => {
    await routeMock(route, mockState);
  });
  return mockState;
}

async function routeMock(route: Route, state: MockState) {
  const request = route.request();
  const path = new URL(request.url()).pathname.replace(/^\/api/, "");

  if (path === "/health") {
    await route.fulfill({
      json: { status: "ok", content_version: "m13-question-renderer", db_ready: true },
    });
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
        ui_language?: MockState["locale"];
        practice_mode?: MockState["practiceMode"];
      };
      if (body.ui_language) state.locale = body.ui_language;
      if (body.practice_mode) state.practiceMode = body.practice_mode;
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
        ui_language: state.locale,
        focus_phonemes: [],
      },
    });
    return;
  }

  if (path === "/today" || path === "/practice/next-normal") {
    await route.fulfill({
      json: {
        session_id: "m13-session",
        group_id: "m13-session",
        group_index: 1,
        group_type: "normal",
        learner_level: "entry",
        selected_learner_level: "entry",
        practice_mode: state.item.question.type === "choose_word" ? "choose_word" : "ipa_first",
        selected_practice_mode: state.practiceMode,
        pending_practice_mode_change:
          state.practiceMode !== (state.item.question.type === "choose_word" ? "choose_word" : "ipa_first"),
        completed_normal_groups_today: { entry: 0, mid: 0, total: 0 },
        date: "2026-07-03",
        primary_accent: "US",
        daily_word_count: 1,
        recent_mistake_count: 0,
        word_count: 1,
        resume_index: 0,
        completed_item_count: 0,
        status: "in_progress",
        origin: "normal_next",
        source_scope: "normal_next",
        items: [state.item],
      },
    });
    return;
  }

  if (path === "/attempt") {
    const body = request.postDataJSON() as { selected_answer: string };
    const correctAnswer = state.item.word;
    const isChooseIpa = state.item.question.type === "choose_ipa";
    await route.fulfill({
      json: {
        is_correct: body.selected_answer === (isChooseIpa ? state.item.display_ipa : correctAnswer),
        correct_answer: isChooseIpa ? state.item.display_ipa : correctAnswer,
        updated_phonemes: [
          {
            phoneme: "/ʃ/",
            attempt_count: 1,
            correct_count: 0,
            mastery_status: "weak",
          },
        ],
        next_action: "continue",
      },
    });
    return;
  }

  await route.fulfill({ status: 404, json: { detail: `Unhandled ${path}` } });
}

test.describe("M13 generic practice question renderer", () => {
  test("choose_ipa keeps the existing word-to-IPA UI", async ({ page }) => {
    await setupApi(page, { locale: "zh-CN", item: chooseIpaItem });
    await page.goto("/");

    await page.getByRole("button", { name: "继续 入门 组" }).click();
    await expect(page.getByText("ship")).toBeVisible();
    await expect(page.getByText("船；大船")).toBeVisible();
    await expect(page.getByText("哪个 IPA 与这个词匹配？")).toBeVisible();
    await page.getByRole("button", { name: "选择 /sɪp/" }).click();

    const feedback = page.getByRole("alert");
    await expect(feedback.getByText("还不对。")).toBeVisible();
    await expect(feedback.getByText("正确 IPA")).toBeVisible();
    await expect(feedback.getByText("/ʃɪp/")).toBeVisible();
  });

  test("practice mode setting affects future groups while active groups keep their type", async ({ page }) => {
    const state = await setupApi(page, { locale: "zh-CN", item: chooseIpaItem });
    await page.goto("/");

    await page.getByRole("button", { name: "设置" }).click();
    await expect(page.getByRole("heading", { name: "练习题型" })).toBeVisible();
    await expect(page.getByText("选择下一组新的常规练习题型。")).toBeVisible();
    await page.getByRole("button", { name: /看 IPA 选单词/ }).click();
    await expect(page.getByText("已保存")).toBeVisible();
    expect(state.practiceMode).toBe("choose_word");

    await page.getByRole("button", { name: "今日", exact: true }).click();
    await expect(page.getByText("当前题型：看单词选 IPA")).toBeVisible();
    await expect(page.getByText("下一组已选择「看 IPA 选单词」。当前组仍是「看单词选 IPA」，直到你完成或开始新的常规组。")).toBeVisible();

    await page.getByRole("button", { name: "继续 入门 组" }).click();
    await expect(page.getByText("当前题型：看单词选 IPA")).toBeVisible();
    await expect(page.getByText("哪个 IPA 与这个词匹配？")).toBeVisible();
    await expect(page.locator(".word-display .audio-btn")).toHaveCount(1);
  });

  test("choose_word uses IPA stimulus and word feedback without leaking the answer first", async ({ page }) => {
    await setupApi(page, { locale: "zh-CN", item: chooseWordItem });
    await page.goto("/");

    await page.getByRole("button", { name: "继续 入门 组" }).click();
    await expect(page.getByText("看 IPA，选择单词")).toBeVisible();
    await expect(page.getByText("哪个单词与这个 IPA 匹配？")).toBeVisible();
    await expect(page.locator(".ipa-cue")).toContainText("/ʃɪp/");
    await expect(page.locator(".word-display")).not.toContainText("ship");
    await expect(page.locator(".word-display")).not.toContainText("船；大船");
    await expect(page.locator(".word-display .audio-btn")).toHaveCount(0);

    await page.getByRole("button", { name: "选择 sheep" }).click();
    const feedback = page.getByRole("alert");
    await expect(feedback.getByText("还不对。")).toBeVisible();
    await expect(feedback.getByText("正确单词")).toBeVisible();
    await expect(feedback.getByText("ship")).toBeVisible();
  });

  test("choose_word uses localized English prompt and correct-word feedback", async ({ page }) => {
    await setupApi(page, { locale: "en-US", item: chooseWordItem });
    await page.goto("/");

    await page.getByRole("button", { name: "Resume Entry group" }).click();
    await expect(page.getByText("Read the IPA, then choose the word")).toBeVisible();
    await expect(page.getByText("Which word matches this IPA?")).toBeVisible();
    await page.getByRole("button", { name: "Select sheep" }).click();

    const feedback = page.getByRole("alert");
    await expect(feedback.getByText("Not quite.")).toBeVisible();
    await expect(feedback.getByText("Correct word")).toBeVisible();
    await expect(feedback.getByText("ship")).toBeVisible();
    await expect(feedback.getByText("Correct IPA")).toHaveCount(0);
  });
});
