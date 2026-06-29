import { fetchHealth, type TodayResponse } from "./api";
import { useEffect, useState } from "react";
import TodayPractice from "./pages/TodayPractice";
import ProgressPage from "./pages/ProgressPage";
import SettingsPage from "./pages/SettingsPage";
import { DEFAULT_LOCALE, createTranslator } from "./locales";

function App() {
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [checking, setChecking] = useState(true);
  const [page, setPage] = useState<"today" | "progress" | "settings">("today");
  const [focusPhonemes, setFocusPhonemes] = useState<string[]>([]);
  const [practiceSession, setPracticeSession] = useState<TodayResponse | null>(null);
  const t = createTranslator(DEFAULT_LOCALE);

  useEffect(() => {
    fetchHealth()
      .then(() => setBackendReady(true))
      .catch(() => setBackendReady(false))
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
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

  return (
    <div className="app-shell">
      <header className="app-brand" aria-label={t("app.brand.name")}>
        <div className="brand-mark" aria-hidden="true">小</div>
        <div className="brand-copy">
          <strong>{t("app.brand.name")}</strong>
          <span>{t("app.brand.tagline")}</span>
        </div>
        <button className="login-placeholder" type="button" disabled>
          {t("app.login.disabled").split(" / ")[0]}
        </button>
      </header>
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
            onBack={() => setPage("today")}
            onFocusChange={setFocusPhonemes}
            onStartPractice={(session) => {
              setPracticeSession(session);
              setPage("today");
            }}
          />
        : <TodayPractice
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

export default App;
