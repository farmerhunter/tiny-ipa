import {
  fetchAuthState,
  fetchHealth,
  fetchSettings,
  isAuthRequiredError,
  login,
  logout,
  type CurrentUser,
  type TodayResponse,
} from "./api";
import { type FormEvent, useEffect, useState } from "react";
import TodayPractice from "./pages/TodayPractice";
import ProgressPage from "./pages/ProgressPage";
import SettingsPage from "./pages/SettingsPage";
import { DEFAULT_LOCALE, createTranslator, type Locale } from "./locales";

function App() {
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [checking, setChecking] = useState(true);
  const [authChecking, setAuthChecking] = useState(true);
  const [authUser, setAuthUser] = useState<CurrentUser | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [page, setPage] = useState<"today" | "progress" | "settings">("today");
  const [uiLanguage, setUiLanguage] = useState<Locale>(DEFAULT_LOCALE);
  const [focusPhonemes, setFocusPhonemes] = useState<string[]>([]);
  const [practiceSession, setPracticeSession] = useState<TodayResponse | null>(null);
  const t = createTranslator(uiLanguage);

  useEffect(() => {
    fetchHealth()
      .then(() => {
        setBackendReady(true);
        return fetchAuthState()
          .then((auth) => {
            setAuthUser(auth.user);
            if (!auth.authenticated) return undefined;
            return fetchSettings()
              .then((settings) => setUiLanguage(settings.ui_language))
              .catch((error) => {
                if (isAuthRequiredError(error)) setAuthUser(null);
              });
          })
          .catch((error) => {
            setAuthError(
              error instanceof Error
                ? error.message
                : createTranslator(DEFAULT_LOCALE)("auth.error.session_check_failed"),
            );
          });
      })
      .catch(() => setBackendReady(false))
      .finally(() => {
        setChecking(false);
        setAuthChecking(false);
      });
  }, []);

  const handleLogin = (user: CurrentUser) => {
    setAuthUser(user);
    setAuthError(null);
    setPage("today");
    fetchSettings()
      .then((settings) => setUiLanguage(settings.ui_language))
      .catch(() => undefined);
  };

  const handleLogout = async () => {
    setAuthError(null);
    try {
      await logout();
    } catch (error: unknown) {
      setAuthError(error instanceof Error ? error.message : t("auth.error.logout_failed"));
    } finally {
      setAuthUser(null);
      setFocusPhonemes([]);
      setPracticeSession(null);
      setPage("today");
    }
  };

  if (checking || authChecking) {
    return (
      <main className="practice-container">
        <h1>{t("app.brand.name")}</h1>
        <p>{t("app.backend.connecting")}</p>
      </main>
    );
  }

  if (!backendReady) {
    return (
      <main className="practice-container">
        <h1>{t("app.brand.name")}</h1>
        <p style={{ color: "#c00" }}>
          {t("app.backend.unreachable")}
        </p>
      </main>
    );
  }

  if (!authUser) {
    return (
      <LoginScreen
        error={authError}
        onLogin={handleLogin}
        onLanguageChange={setUiLanguage}
        t={t}
        uiLanguage={uiLanguage}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="app-brand" aria-label={t("app.brand.name")}>
        <div className="brand-mark" aria-hidden="true">小</div>
        <div className="brand-copy">
          <strong>{t("app.brand.name")}</strong>
          <span>{t("app.brand.tagline")}</span>
        </div>
        <div className="account-menu">
          <span>{t("auth.current_user", { username: authUser.username })}</span>
          <button className="account-action" type="button" onClick={() => void handleLogout()}>
            {t("auth.logout.action")}
          </button>
        </div>
      </header>
      {authError && <p className="shell-error">{authError}</p>}
      <nav className="nav-bar">
        <button className={`nav-tab ${page === "today" ? "nav-active" : ""}`}
          onClick={() => setPage("today")}>{t("app.nav.today")}</button>
        <button className={`nav-tab ${page === "progress" ? "nav-active" : ""}`}
          onClick={() => setPage("progress")}>{t("app.nav.progress")}</button>
        <button className={`nav-tab ${page === "settings" ? "nav-active" : ""}`}
          onClick={() => setPage("settings")}>{t("app.nav.settings")}</button>
      </nav>
      {page === "progress"
        ? <ProgressPage
            uiLanguage={uiLanguage}
            onBack={() => setPage("today")}
            focusPhonemes={focusPhonemes}
            onFocusChange={setFocusPhonemes}
            onStartPractice={(session) => {
              setPracticeSession(session);
              setPage("today");
            }}
          />
        : page === "settings"
        ? <SettingsPage
            uiLanguage={uiLanguage}
            currentUser={authUser}
            onBack={() => setPage("today")}
            onLanguageChange={setUiLanguage}
            onFocusChange={setFocusPhonemes}
            onStartPractice={(session) => {
              setPracticeSession(session);
              setPage("today");
            }}
          />
        : <TodayPractice
            uiLanguage={uiLanguage}
            focusPhonemes={focusPhonemes}
            onFocusChange={setFocusPhonemes}
            onOpenProgress={() => setPage("progress")}
            initialSession={practiceSession}
            onInitialSessionConsumed={() => setPracticeSession(null)}
          />
      }
    </div>
  );
}

function LoginScreen({
  error,
  onLogin,
  onLanguageChange,
  t,
  uiLanguage,
}: {
  error: string | null;
  onLogin: (user: CurrentUser) => void;
  onLanguageChange: (locale: Locale) => void;
  t: ReturnType<typeof createTranslator>;
  uiLanguage: Locale;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setLocalError(null);
    try {
      const auth = await login(username, password);
      if (auth.authenticated && auth.user) {
        onLogin(auth.user);
      } else {
        setLocalError(t("auth.error.invalid_credentials"));
      }
    } catch {
      setLocalError(t("auth.error.invalid_credentials"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="practice-container auth-screen">
      <div className="auth-brand">
        <div className="brand-mark" aria-hidden="true">小</div>
        <div>
          <h1>{t("app.brand.name")}</h1>
          <p>{t("app.brand.tagline")}</p>
        </div>
      </div>
      <form className="auth-form" onSubmit={submit}>
        <h2>{t("auth.login.title")}</h2>
        <p>{t("auth.login.description")}</p>
        <label>
          <span>{t("settings.ui_language.title")}</span>
          <select
            onChange={(event) => onLanguageChange(event.target.value as Locale)}
            value={uiLanguage}
          >
            <option value="zh-CN">{t("settings.ui_language.zh_cn")}</option>
            <option value="en-US">{t("settings.ui_language.en_us")}</option>
          </select>
        </label>
        <label>
          <span>{t("auth.login.username")}</span>
          <input
            autoComplete="username"
            name="username"
            onChange={(event) => setUsername(event.target.value)}
            required
            type="text"
            value={username}
          />
        </label>
        <label>
          <span>{t("auth.login.password")}</span>
          <input
            autoComplete="current-password"
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        {(localError || error) && <p className="save-error">{localError ?? error}</p>}
        <button className="primary-action-btn" disabled={submitting} type="submit">
          {submitting ? t("action.loading") : t("auth.login.action")}
        </button>
      </form>
    </main>
  );
}

export default App;
