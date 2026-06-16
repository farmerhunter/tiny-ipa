/**
 * ProgressPage — displays learner progress summary.
 *
 * Shows streak, total stats, and weak/strong phoneme lists.
 */

import { useEffect, useState } from "react";
import type { ProgressResponse, SettingsData } from "../api";
import { fetchProgress, fetchSettings, saveSettings } from "../api";

interface Props {
  onBack: () => void;
  focusPhonemes: string[];
  onFocusChange: (focusPhonemes: string[]) => void;
}

export default function ProgressPage({
  onBack,
  focusPhonemes,
  onFocusChange,
}: Props) {
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingFocus, setSavingFocus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeFocus = settings?.focus_phonemes ?? focusPhonemes;

  useEffect(() => {
    Promise.all([fetchProgress(), fetchSettings()])
      .then(([progressData, settingsData]) => {
        setData(progressData);
        setSettings(settingsData);
        onFocusChange(settingsData.focus_phonemes);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [onFocusChange]);

  const updateFocus = async (nextFocus: string[], navigateAfter = false) => {
    setSavingFocus(nextFocus.join(",") || "clear");
    setError(null);
    try {
      const updated = await saveSettings({ focus_phonemes: nextFocus });
      setSettings(updated);
      onFocusChange(updated.focus_phonemes);
      if (navigateAfter) onBack();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update focus");
    } finally {
      setSavingFocus(null);
    }
  };

  const focusOne = (phoneme: string) => {
    const next = [phoneme, ...activeFocus.filter((item) => item !== phoneme)];
    void updateFocus(next, true);
  };

  const clearFocus = () => {
    void updateFocus([]);
  };

  if (loading) return <main className="practice-container"><p>Loading progress…</p></main>;
  if (error && !data) return <main className="practice-container"><p className="error">Failed: {error}</p></main>;
  if (!data) return null;

  return (
    <main className="practice-container">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>← Today</button>
        <h1>Progress</h1>
      </div>
      {error && <p className="save-error">{error}</p>}

      {activeFocus.length > 0 && (
        <div className="focus-panel">
          <span className="focus-panel-label">Next group focus</span>
          <div className="phoneme-chip-list">
            {activeFocus.map((phoneme) => (
              <span className="phoneme-chip" key={phoneme}>{phoneme}</span>
            ))}
          </div>
          <button
            className="secondary-action-btn compact"
            onClick={clearFocus}
            disabled={savingFocus !== null}
          >
            Clear focus
          </button>
        </div>
      )}

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
                <button
                  className="focus-action-btn"
                  onClick={() => focusOne(p.phoneme)}
                  disabled={savingFocus !== null}
                >
                  {activeFocus.includes(p.phoneme) ? "Focused" : "Focus"}
                </button>
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
