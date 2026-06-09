/**
 * ProgressPage — displays learner progress summary.
 *
 * Shows streak, total stats, and weak/strong phoneme lists.
 */

import { useEffect, useState } from "react";
import type { ProgressResponse } from "../api";
import { fetchProgress } from "../api";

interface Props {
  onBack: () => void;
}

export default function ProgressPage({ onBack }: Props) {
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProgress()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="practice-container"><p>Loading progress…</p></main>;
  if (error) return <main className="practice-container"><p className="error">Failed: {error}</p></main>;
  if (!data) return null;

  return (
    <main className="practice-container">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>← Today</button>
        <h1>Progress</h1>
      </div>

      <div className="progress-stats">
        <div className="stat-card">
          <span className="stat-number">{data.streak_days}</span>
          <span className="stat-label">day streak</span>
        </div>
        <div className="stat-card">
          <span className="stat-number">{data.total_attempts}</span>
          <span className="stat-label">attempts</span>
        </div>
        <div className="stat-card">
          <span className="stat-number">{data.total_sessions}</span>
          <span className="stat-label">sessions</span>
        </div>
      </div>

      {data.weak_phonemes.length > 0 && (
        <section className="phoneme-section">
          <h2>Needs practice</h2>
          <ul className="phoneme-list">
            {data.weak_phonemes.map((p) => (
              <li key={p.phoneme} className="phoneme-item weak">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">{Math.round(p.accuracy * 100)}%</span>
                <span className="phoneme-count">{p.attempt_count} att.</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.strong_phonemes.length > 0 && (
        <section className="phoneme-section">
          <h2>Strong</h2>
          <ul className="phoneme-list">
            {data.strong_phonemes.map((p) => (
              <li key={p.phoneme} className="phoneme-item strong">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">{Math.round(p.accuracy * 100)}%</span>
                <span className="phoneme-count">{p.attempt_count} att.</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.weak_phonemes.length === 0 && data.strong_phonemes.length === 0 && (
        <p className="empty-hint">Complete some practice to see your phoneme stats.</p>
      )}
    </main>
  );
}
