/**
 * ProgressPage — displays learner progress summary.
 *
 * Shows streak, total stats, and weak/strong phoneme lists.
 */

import { useEffect, useState } from "react";
import type {
  LevelProgressStats,
  ProgressResponse,
  SettingsData,
  TodayResponse,
} from "../api";
import {
  clearPracticeFocus,
  fetchProgress,
  fetchSettings,
  startFocusedPractice,
} from "../api";

interface Props {
  onBack: () => void;
  focusPhonemes: string[];
  onFocusChange: (focusPhonemes: string[]) => void;
  onStartPractice: (session: TodayResponse) => void;
}

function formatAccuracy(value: number | null): string {
  if (value === null) return "No attempts";
  return `${Math.round(value * 100)}% accuracy`;
}

function LevelStatsSection({
  stats,
  onFocus,
  activeFocus,
  savingFocus,
}: {
  stats: LevelProgressStats;
  onFocus: (phoneme: string) => void;
  activeFocus: string[];
  savingFocus: string | null;
}) {
  return (
    <section className="level-progress-panel">
      <div className="level-progress-header">
        <h2>{stats.label} stats</h2>
        <span className="level-scope-label">{stats.label}</span>
      </div>
      <div className="level-stat-grid">
        <span>{stats.completed_normal_groups_today} completed today</span>
        <span>{stats.normal_groups} normal groups</span>
        <span>{stats.attempts} attempts</span>
        <span>{formatAccuracy(stats.accuracy)}</span>
      </div>
      {stats.weak_phonemes.length > 0 ? (
        <>
          <h3>Needs practice in {stats.label}</h3>
          <ul className="phoneme-list">
            {stats.weak_phonemes.map((p) => (
              <li key={`${stats.learner_level}-${p.phoneme}`} className="phoneme-item weak">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">
                  {Math.round(p.accuracy * 100)}% accuracy
                </span>
                <span className="phoneme-count">{p.attempt_count} attempts</span>
                <button
                  className="focus-action-btn"
                  onClick={() => onFocus(p.phoneme)}
                  disabled={savingFocus !== null}
                >
                  {activeFocus.includes(p.phoneme) ? "Resume focus" : `Focus ${p.phoneme}`}
                </button>
                <span className="phoneme-help">
                  Focused practice starts at the selected level in Settings.
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="section-copy">No weak phoneme signal yet for {stats.label}.</p>
      )}
    </section>
  );
}

export default function ProgressPage({
  onBack,
  focusPhonemes,
  onFocusChange,
  onStartPractice,
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

  const canonicalFocus = (nextFocus: string[]) =>
    Array.from(new Set(nextFocus.map((item) => item.trim()).filter(Boolean))).sort();

  const startFocus = async (nextFocus: string[]) => {
    const focus = canonicalFocus(nextFocus);
    setSavingFocus(nextFocus.join(",") || "clear");
    setError(null);
    try {
      const focusedSession = await startFocusedPractice(focus);
      const appliedFocus = focusedSession.focus_phonemes ?? focus;
      setSettings((prev) => prev ? { ...prev, focus_phonemes: appliedFocus } : prev);
      onFocusChange(appliedFocus);
      onStartPractice(focusedSession);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start focused practice");
    } finally {
      setSavingFocus(null);
    }
  };

  const focusOne = (phoneme: string) => {
    void startFocus([phoneme]);
  };

  const clearFocus = () => {
    setSavingFocus("clear");
    setError(null);
    clearPracticeFocus()
      .then((normalSession) => {
        setSettings((prev) => prev ? { ...prev, focus_phonemes: [] } : prev);
        onFocusChange([]);
        onStartPractice(normalSession);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to clear focus"))
      .finally(() => setSavingFocus(null));
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
          <span className="focus-panel-label">Current focus</span>
          <p className="section-copy">
            Focus changes the next focused practice group. Clear it to return to normal practice.
          </p>
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
          <span className="stat-label">global attempts</span>
        </div>
        <div className="stat-card">
          <span className="stat-number">{data.total_normal_groups}</span>
          <span className="stat-label">normal groups</span>
        </div>
      </div>

      {data.level_stats && (
        <div className="level-progress-list">
          <LevelStatsSection
            stats={data.level_stats.entry}
            onFocus={focusOne}
            activeFocus={activeFocus}
            savingFocus={savingFocus}
          />
          <LevelStatsSection
            stats={data.level_stats.mid}
            onFocus={focusOne}
            activeFocus={activeFocus}
            savingFocus={savingFocus}
          />
        </div>
      )}

      {data.weak_phonemes.length > 0 && (
        <section className="phoneme-section">
          <h2>Global needs practice</h2>
          <p className="section-copy">
            All-level weak sounds from your complete history. Use the Entry/Mid
            sections above when level context matters.
          </p>
          <ul className="phoneme-list">
            {data.weak_phonemes.map((p) => (
              <li key={p.phoneme} className="phoneme-item weak">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">
                  {Math.round(p.accuracy * 100)}% accuracy
                </span>
                <span className="phoneme-count">
                  {p.attempt_count} attempts
                </span>
                <button
                  className="focus-action-btn"
                  onClick={() => focusOne(p.phoneme)}
                  disabled={savingFocus !== null}
                >
                  {activeFocus.includes(p.phoneme) ? "Resume focus" : `Focus ${p.phoneme}`}
                </button>
                <span className="phoneme-help">
                  Focused practice will choose words weighted toward {p.phoneme}.
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.strong_phonemes.length > 0 && (
        <section className="phoneme-section">
          <h2>Global strong sounds</h2>
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
