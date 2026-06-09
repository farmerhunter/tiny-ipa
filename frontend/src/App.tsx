import { fetchHealth } from "./api";
import { useEffect, useState } from "react";
import TodayPractice from "./pages/TodayPractice";
import ProgressPage from "./pages/ProgressPage";

function App() {
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [checking, setChecking] = useState(true);
  const [page, setPage] = useState<"today" | "progress">("today");

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
      </nav>
      {page === "progress"
        ? <ProgressPage onBack={() => setPage("today")} />
        : <TodayPractice />
      }
    </div>
  );
}

export default App;
