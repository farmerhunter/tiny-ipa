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
  if (value === null) return "Accuracy appears after answers";
  return `${Math.round(value * 100)}% accuracy`;
}

function todayMotivation(data: ProgressResponse): { value: string; label: string } {
  if (data.today_completed) {
    return { value: "Done", label: "practice completed today" };
  }
  if (data.today_status !== "none" || data.total_attempts > 0) {
    return { value: "Started", label: "practice underway today" };
  }
  if (data.streak_days > 0) {
    return { value: String(data.streak_days), label: "day streak" };
  }
  return { value: "Ready", label: "start today's practice" };
}

function activeGroupCount(stats: LevelProgressStats): number {
  return Math.max(0, stats.normal_groups - stats.completed_normal_groups);
}

function levelProgressHint(stats: LevelProgressStats): string {
  const activeGroups = activeGroupCount(stats);
  if (stats.attempts === 0 && activeGroups > 0) {
    return `${stats.label} has an active group. Answer a few items to unlock accuracy and sound signals.`;
  }
  if (stats.attempts === 0) {
    return `${stats.label} has no answered items yet. Start a group when this level is selected.`;
  }
  if (stats.weak_phonemes.length > 0) {
    return `${stats.label} has sounds ready for focused practice.`;
  }
  return `${stats.label} is looking steady so far. Keep practicing to confirm strong sounds.`;
}

function levelWeakEmptyCopy(stats: LevelProgressStats): string {
  if (stats.attempts === 0) {
    return `No weak sound signal yet for ${stats.label}; it appears after answered items.`;
  }
  return `No weak sound signal right now for ${stats.label}.`;
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
        <h2>{stats.label} progress</h2>
        <span className="level-scope-label">{stats.label}</span>
      </div>
      <p className="section-copy">{levelProgressHint(stats)}</p>
      <div className="level-stat-grid">
        <span>{stats.completed_normal_groups_today} completed today</span>
        <span>{stats.completed_normal_groups} completed groups</span>
        <span>{activeGroupCount(stats)} active groups</span>
        <span>{stats.attempts} answered items</span>
        <span>{formatAccuracy(stats.accuracy)}</span>
      </div>
      {stats.weak_phonemes.length > 0 ? (
        <>
          <h3>Sounds to revisit in {stats.label}</h3>
          <ul className="phoneme-list">
            {stats.weak_phonemes.map((p) => (
              <li key={`${stats.learner_level}-${p.phoneme}`} className="phoneme-item weak">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">
                  {Math.round(p.accuracy * 100)}% accuracy
                </span>
                <span className="phoneme-count">{p.attempt_count} answered</span>
                <button
                  className="focus-action-btn"
                  onClick={() => onFocus(p.phoneme)}
                  disabled={savingFocus !== null}
                >
                  {activeFocus.includes(p.phoneme) ? "Resume focus" : `Focus ${p.phoneme}`}
                </button>
                <span className="phoneme-help">
                  Focused practice uses the level selected in Settings.
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="section-copy">{levelWeakEmptyCopy(stats)}</p>
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
  const todayCard = todayMotivation(data);
  const completedGroups = data.level_stats
    ? data.level_stats.entry.completed_normal_groups + data.level_stats.mid.completed_normal_groups
    : data.total_normal_groups;
  const activeGroups = data.level_stats
    ? activeGroupCount(data.level_stats.entry) + activeGroupCount(data.level_stats.mid)
    : 0;

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
          <span className="stat-number stat-word">{todayCard.value}</span>
          <span className="stat-label">{todayCard.label}</span>
        </div>
        <div className="stat-card">
          <span className="stat-number">{data.total_attempts}</span>
          <span className="stat-label">answered items</span>
        </div>
        <div className="stat-card">
          <span className="stat-number">{completedGroups}</span>
          <span className="stat-label">completed groups</span>
          {activeGroups > 0 && (
            <span className="stat-subtext">{activeGroups} active</span>
          )}
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
          <h2>Sounds to revisit overall</h2>
          <p className="section-copy">
            Sounds that need more reps across your complete history. Use the Entry/Mid
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
                  {p.attempt_count} answered
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
          <h2>Sounds going well overall</h2>
          <ul className="phoneme-list">
            {data.strong_phonemes.map((p) => (
              <li key={p.phoneme} className="phoneme-item strong">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">{Math.round(p.accuracy * 100)}%</span>
                <span className="phoneme-count">{p.attempt_count} answered</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.weak_phonemes.length === 0 && data.strong_phonemes.length === 0 && (
        <p className="empty-hint">Answer a few items to see sound-level progress.</p>
      )}
    </main>
  );
}
