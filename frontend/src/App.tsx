import { fetchHealth } from "./api";
import { useEffect, useState } from "react";

function App() {
  const [health, setHealth] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => setHealth(JSON.stringify(data, null, 2)))
      .catch((err) => setError(err.message));
  }, []);

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
      <p>Daily IPA practice with small beginner word sets.</p>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      {health ? (
        <pre style={{ background: "#f5f5f5", padding: 12, borderRadius: 8 }}>
          {health}
        </pre>
      ) : (
        !error && <p>Connecting to backend…</p>
      )}
    </main>
  );
}

export default App;
