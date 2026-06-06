import { fetchHealth } from "./api";
import { useEffect, useState } from "react";
import TodayPractice from "./pages/TodayPractice";

function App() {
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    fetchHealth()
      .then(() => setBackendReady(true))
      .catch(() => setBackendReady(false))
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <main
        style={{
          maxWidth: 480,
          margin: "0 auto",
          padding: "24px 16px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1>Tiny IPA</h1>
        <p>Connecting to backend…</p>
      </main>
    );
  }

  if (!backendReady) {
    return (
      <main
        style={{
          maxWidth: 480,
          margin: "0 auto",
          padding: "24px 16px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1>Tiny IPA</h1>
        <p style={{ color: "#c00" }}>
          Cannot reach the backend. Make sure it is running on port 8010.
        </p>
      </main>
    );
  }

  return <TodayPractice />;
}

export default App;
