import { expect, test, type Page, type Route } from "@playwright/test";

type Locale = "zh-CN" | "en-US";

interface AuthState {
  authenticated: boolean;
  locale: Locale;
  username: string | null;
}

function settingsResponse(locale: Locale) {
  return {
    primary_accent: "US",
    daily_word_count: 3,
    show_translation: true,
    show_accent_compare: false,
    practice_mode: "normal",
    review_strength: "normal",
    learner_level: "entry",
    ui_language: locale,
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
      const body = request.postDataJSON() as { ui_language?: Locale };
      if (body.ui_language) state.locale = body.ui_language;
    }
    await route.fulfill({ json: settingsResponse(state.locale) });
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
    await setupAuthApi(page, "zh-CN");
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
    await expect(page.getByText("只影响之后新建的常规练习组；已进行中的练习组词数不变。")).toBeVisible();
    await expect(page.getByText("关闭后，练习卡片不显示中文释义；重新开启后，下一次渲染会显示可用释义。")).toBeVisible();
    await expect(page.getByText("只影响之后新建的常规练习组，并且需要已有薄弱音或错题信号才会明显改变选词。已经进行中的练习组不会改变。")).toBeVisible();

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
    await expect(page.getByText("Affects future regular groups only; active groups keep their existing item count.")).toBeVisible();
    await expect(page.getByText("When off, practice cards hide Chinese meanings; turning it back on shows available meanings on the next render.")).toBeVisible();
    await expect(page.getByText("Affects future regular practice groups only, and becomes visible when weak sounds or mistake history exist. Existing active groups stay unchanged.")).toBeVisible();

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in to practice" })).toBeVisible();
  });
});
