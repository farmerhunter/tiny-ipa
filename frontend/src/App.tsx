import { fetchHealth, type TodayResponse } from "./api";
import { useEffect, useState } from "react";
import TodayPractice from "./pages/TodayPractice";
import ProgressPage from "./pages/ProgressPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [checking, setChecking] = useState(true);
  const [page, setPage] = useState<"today" | "progress" | "settings">("today");
  const [focusPhonemes, setFocusPhonemes] = useState<string[]>([]);
  const [practiceSession, setPracticeSession] = useState<TodayResponse | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(() => setBackendReady(true))
      .catch(() => setBackendReady(false))
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <main className="practice-container">
        <h1>Tiny IPA</h1>
        <p>Connecting to backend…</p>
      </main>
    );
  }

  if (!backendReady) {
    return (
      <main className="practice-container">
        <h1>Tiny IPA</h1>
        <p style={{ color: "#c00" }}>
          Cannot reach backend. Make sure it is running on port 8010.
        </p>
      </main>
    );
  }

  return (
    <div>
      <nav className="nav-bar">
        <button className={`nav-tab ${page === "today" ? "nav-active" : ""}`}
          onClick={() => setPage("today")}>Today</button>
        <button className={`nav-tab ${page === "progress" ? "nav-active" : ""}`}
          onClick={() => setPage("progress")}>Progress</button>
        <button className={`nav-tab ${page === "settings" ? "nav-active" : ""}`}
          onClick={() => setPage("settings")}>Settings</button>
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
