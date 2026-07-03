import { expect, test, type Page, type Route } from "@playwright/test";

type Locale = "zh-CN" | "en-US";

interface AuthState {
  authenticated: boolean;
  locale: Locale;
  username: string | null;
  invalidDailyWordCountRequests: number;
  settings: {
    daily_word_count: number;
    review_strength: "quick" | "normal" | "extra_review";
  };
}

function settingsResponse(state: AuthState) {
  return {
    primary_accent: "US",
    daily_word_count: state.settings.daily_word_count,
    show_translation: true,
    show_accent_compare: false,
    practice_mode: "ipa_first",
    review_strength: state.settings.review_strength,
    learner_level: "entry",
    ui_language: state.locale,
    focus_phonemes: [],
  };
}

function todayResponse() {
  return {
    date: "2026-07-02",
    primary_accent: "US",
    daily_word_count: 3,
    recent_mistake_count: 0,
    status: "ready",
    selected_learner_level: "entry",
    completed_normal_groups_today: { entry: 0, mid: 0, total: 0 },
    items: [],
  };
}

async function setupAuthApi(page: Page, locale: Locale) {
  const state: AuthState = {
    authenticated: false,
    locale,
    username: null,
    invalidDailyWordCountRequests: 0,
    settings: {
      daily_word_count: 3,
      review_strength: "normal",
    },
  };

  await page.route("**/api/**", async (route) => {
    await routeMock(route, state);
  });
  return state;
}

async function routeMock(route: Route, state: AuthState) {
  const request = route.request();
  const path = new URL(request.url()).pathname.replace(/^\/api/, "");

  if (path === "/health") {
    await route.fulfill({
      json: { status: "ok", content_version: "m12-auth-ux", db_ready: true },
    });
    return;
  }

  if (path === "/auth/me") {
    await route.fulfill({
      json: {
        authenticated: state.authenticated,
        user: state.authenticated
          ? { id: "default", username: state.username, is_owner: true }
          : null,
      },
    });
    return;
  }

  if (path === "/auth/login") {
    const body = request.postDataJSON() as { username?: string; password?: string };
    if (body.username === "owner" && body.password === "secret") {
      state.authenticated = true;
      state.username = "owner";
      await route.fulfill({
        json: { authenticated: true, user: { id: "default", username: "owner", is_owner: true } },
      });
      return;
    }

    await route.fulfill({
      status: 401,
      json: { detail: { error: "INVALID_CREDENTIALS", detail: "Invalid username or password." } },
    });
    return;
  }

  if (path === "/auth/logout") {
    state.authenticated = false;
    state.username = null;
    await route.fulfill({ json: { ok: true } });
    return;
  }

  if (path === "/settings") {
    if (!state.authenticated) {
      await route.fulfill({
        status: 401,
        json: { detail: { error: "AUTH_REQUIRED", detail: "Sign in required." } },
      });
      return;
    }
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as {
        ui_language?: Locale;
        daily_word_count?: number;
        review_strength?: AuthState["settings"]["review_strength"];
      };
      if (body.ui_language) state.locale = body.ui_language;
      if (body.daily_word_count !== undefined) {
        if (
          !Number.isInteger(body.daily_word_count) ||
          body.daily_word_count < 1 ||
          body.daily_word_count > 50
        ) {
          state.invalidDailyWordCountRequests += 1;
          await route.fulfill({
            status: 400,
            json: {
              detail: {
                error: "SETTINGS_INVALID",
                detail: "daily_word_count must be an integer between 1 and 50",
              },
            },
          });
          return;
        }
        state.settings.daily_word_count = body.daily_word_count;
      }
      if (body.review_strength) state.settings.review_strength = body.review_strength;
    }
    await route.fulfill({ json: settingsResponse(state) });
    return;
  }

  if (path === "/today") {
    await route.fulfill({ json: todayResponse() });
    return;
  }

  await route.fulfill({ status: 404, json: { detail: `Unhandled ${path}` } });
}

test.describe("M12 localized auth UX", () => {
  test("zh-CN login, current-user display, and logout use localized copy", async ({ page }) => {
    const state = await setupAuthApi(page, "zh-CN");
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "登录后开始练习" })).toBeVisible();
    await page.getByLabel("用户名").fill("owner");
    await page.getByLabel("密码").fill("wrong");
    await page.getByRole("button", { name: "登录" }).click();
    await expect(page.getByText("用户名或密码不正确。")).toBeVisible();

    await page.getByLabel("密码").fill("secret");
    await page.getByRole("button", { name: "登录" }).click();
    await expect(page.locator(".account-menu")).toContainText("当前用户");
    await expect(page.locator(".account-menu")).toContainText("owner");

    await page.getByRole("button", { name: "设置" }).click();
    await expect(page.getByText("已登录为 owner。练习、进度和设置只属于当前用户。")).toBeVisible();
    await expect(page.getByText("保存 1 到 50 之间的整数。只影响之后新建的常规练习组；今日已经进行中的组会保持原来的词数。")).toBeVisible();
    await expect(page.getByText("关闭后，练习卡片不显示中文释义；重新开启后，下一次渲染会显示可用释义。")).toBeVisible();
    await expect(page.getByText("只影响之后新建的常规练习组；已经进行中的练习组不会改变。需要已有薄弱音或错题信号时，差异才会明显。")).toBeVisible();
    await expect(page.getByText("快速：下一组常规练习会减少薄弱音和错题占用的空间，更偏向轻量练习。")).toBeVisible();
    await expect(page.getByText("标准：下一组常规练习保持新词和薄弱音复习的平衡。")).toBeVisible();
    await expect(page.getByText("加强复习：下一组常规练习会在有薄弱音或近期错题时，更优先安排这些声音。")).toBeVisible();

    const wordCountInput = page.getByLabel(/每组词数/);
    await wordCountInput.fill("");
    await wordCountInput.blur();
    await expect(page.getByText("请输入 1 到 50 之间的整数。已进行中的练习组不会改变；下一组新建的常规练习会使用保存后的设置。")).toBeVisible();
    await expect(page.locator("body")).not.toContainText("SETTINGS_INVALID");
    await wordCountInput.fill("0");
    await wordCountInput.press("Enter");
    await expect(page.getByText("请输入 1 到 50 之间的整数。已进行中的练习组不会改变；下一组新建的常规练习会使用保存后的设置。")).toBeVisible();
    await wordCountInput.fill("4");
    await wordCountInput.press("Enter");
    await expect(page.getByText("已保存")).toBeVisible();
    await expect(wordCountInput).toHaveValue("4");
    expect(state.invalidDailyWordCountRequests).toBe(0);

    await page.getByRole("button", { name: "退出" }).click();
    await expect(page.getByRole("heading", { name: "登录后开始练习" })).toBeVisible();
  });

  test("en-US login and logout use English copy", async ({ page }) => {
    await setupAuthApi(page, "en-US");
    await page.goto("/");

    await page.getByLabel("界面语言").selectOption("en-US");
    await expect(page.getByRole("heading", { name: "Sign in to practice" })).toBeVisible();
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password").fill("secret");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.locator(".account-menu")).toContainText("Current user");
    await expect(page.locator(".account-menu")).toContainText("owner");

    await page.getByRole("button", { name: "Settings" }).click();
    await expect(page.getByText("Signed in as owner. Practice, progress, and settings belong to this user only.")).toBeVisible();
    await expect(page.getByText("Save a whole number from 1 to 50. It affects future regular groups only; today's active group keeps its original item count.")).toBeVisible();
    await expect(page.getByText("When off, practice cards hide Chinese meanings; turning it back on shows available meanings on the next render.")).toBeVisible();
    await expect(page.getByText("Affects future regular practice groups only; existing active groups stay unchanged. The difference is visible when weak sounds or mistake history exist.")).toBeVisible();
    await expect(page.getByText("Quick: future regular groups spend less room on weak or mistaken sounds for lighter practice.")).toBeVisible();
    await expect(page.getByText("Standard: future regular groups keep a balanced mix of new words and weak-sound review.")).toBeVisible();
    await expect(page.getByText("Extra review: future regular groups give weak sounds or recent mistakes more priority when that evidence exists.")).toBeVisible();

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in to practice" })).toBeVisible();
  });
});
