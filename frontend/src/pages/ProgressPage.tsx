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
import { createTranslator, type Locale, type Translator } from "../locales";

interface Props {
  uiLanguage: Locale;
  onBack: () => void;
  focusPhonemes: string[];
  onFocusChange: (focusPhonemes: string[]) => void;
  onStartPractice: (session: TodayResponse) => void;
}

function formatAccuracy(value: number | null, t: Translator): string {
  if (value === null) return t("progress.stats.accuracy_pending");
  return t("progress.stats.accuracy", { accuracy: Math.round(value * 100) });
}

function todayMotivation(data: ProgressResponse, t: Translator): { value: string; label: string } {
  if (data.today_completed) {
    return { value: t("progress.today_status.done"), label: t("progress.today_status.done_label") };
  }
  if (data.today_status !== "none" || data.total_attempts > 0) {
    return {
      value: t("progress.today_status.started"),
      label: t("progress.today_status.started_label"),
    };
  }
  if (data.streak_days > 0) {
    return { value: String(data.streak_days), label: t("progress.today_status.streak_label") };
  }
  return { value: t("progress.today_status.ready"), label: t("progress.today_status.ready_label") };
}

function activeGroupCount(stats: LevelProgressStats): number {
  return Math.max(0, stats.normal_groups - stats.completed_normal_groups);
}

function levelProgressHint(stats: LevelProgressStats, t: Translator): string {
  const activeGroups = activeGroupCount(stats);
  if (stats.attempts === 0 && activeGroups > 0) {
    return t("progress.level.hint.active", { level: stats.label });
  }
  if (stats.attempts === 0) {
    return t("progress.level.hint.empty", { level: stats.label });
  }
  if (stats.weak_phonemes.length > 0) {
    return t("progress.level.hint.weak", { level: stats.label });
  }
  return t("progress.level.hint.steady", { level: stats.label });
}

function levelWeakEmptyCopy(stats: LevelProgressStats, t: Translator): string {
  if (stats.attempts === 0) {
    return t("progress.weak.level.empty_pending", { level: stats.label });
  }
  return t("progress.weak.level.empty", { level: stats.label });
}

function LevelStatsSection({
  stats,
  onFocus,
  activeFocus,
  savingFocus,
  t,
}: {
  stats: LevelProgressStats;
  onFocus: (phoneme: string) => void;
  activeFocus: string[];
  savingFocus: string | null;
  t: Translator;
}) {
  return (
    <section className="level-progress-panel">
      <div className="level-progress-header">
        <h2>{t("progress.level.title", { level: stats.label })}</h2>
        <span className="level-scope-label">{stats.label}</span>
      </div>
      <p className="section-copy">{levelProgressHint(stats, t)}</p>
      <div className="level-stat-grid">
        <span>{t("progress.stats.completed_today", { count: stats.completed_normal_groups_today })}</span>
        <span>{t("progress.stats.completed_groups", { count: stats.completed_normal_groups })}</span>
        <span>{t("progress.stats.active_groups", { count: activeGroupCount(stats) })}</span>
        <span>{t("progress.stats.answered_items", { count: stats.attempts })}</span>
        <span>{formatAccuracy(stats.accuracy, t)}</span>
      </div>
      {stats.weak_phonemes.length > 0 ? (
        <>
          <h3>{t("progress.weak.level.title", { level: stats.label })}</h3>
          <ul className="phoneme-list">
            {stats.weak_phonemes.map((p) => (
              <li key={`${stats.learner_level}-${p.phoneme}`} className="phoneme-item weak">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">
                  {t("progress.stats.accuracy", { accuracy: Math.round(p.accuracy * 100) })}
                </span>
                <span className="phoneme-count">
                  {t("progress.stats.answered_items", { count: p.attempt_count })}
                </span>
                <button
                  className="focus-action-btn"
                  onClick={() => onFocus(p.phoneme)}
                  disabled={savingFocus !== null}
                >
                  {activeFocus.includes(p.phoneme)
                    ? t("focus.action.resume")
                    : t("focus.action.start", { phoneme: p.phoneme })}
                </button>
                <span className="phoneme-help">
                  {t("progress.focus.uses_selected_level")}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="section-copy">{levelWeakEmptyCopy(stats, t)}</p>
      )}
    </section>
  );
}

export default function ProgressPage({
  uiLanguage,
  onBack,
  focusPhonemes,
  onFocusChange,
  onStartPractice,
}: Props) {
  const t = createTranslator(uiLanguage);
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
      setError(e instanceof Error ? e.message : t("error.practice.focus_start_failed"));
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
      .catch((e) => setError(e instanceof Error ? e.message : t("error.practice.clear_focus_failed")))
      .finally(() => setSavingFocus(null));
  };

  if (loading) return <main className="practice-container"><p>{t("progress.loading")}</p></main>;
  if (error && !data) return <main className="practice-container"><p className="error">{t("error.generic.failed", { error })}</p></main>;
  if (!data) return null;
  const todayCard = todayMotivation(data, t);
  const completedGroups = data.level_stats
    ? data.level_stats.entry.completed_normal_groups + data.level_stats.mid.completed_normal_groups
    : data.total_normal_groups;
  const activeGroups = data.level_stats
    ? activeGroupCount(data.level_stats.entry) + activeGroupCount(data.level_stats.mid)
    : 0;

  return (
    <main className="practice-container">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>{t("app.back.today")}</button>
        <h1>{t("app.nav.progress")}</h1>
      </div>
      {error && <p className="save-error">{error}</p>}

      {activeFocus.length > 0 && (
        <div className="focus-panel">
          <span className="focus-panel-label">{t("focus.current.label")}</span>
          <p className="section-copy">
            {t("focus.current.help")}
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
            {t("focus.action.clear_button")}
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
          <span className="stat-label">{t("progress.stats.answered_items.label")}</span>
        </div>
        <div className="stat-card">
          <span className="stat-number">{completedGroups}</span>
          <span className="stat-label">{t("progress.stats.completed_groups.label")}</span>
          {activeGroups > 0 && (
            <span className="stat-subtext">{t("progress.stats.active", { count: activeGroups })}</span>
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
            t={t}
          />
          <LevelStatsSection
            stats={data.level_stats.mid}
            onFocus={focusOne}
            activeFocus={activeFocus}
            savingFocus={savingFocus}
            t={t}
          />
        </div>
      )}

      {data.weak_phonemes.length > 0 && (
        <section className="phoneme-section">
          <h2>{t("progress.weak.global.title")}</h2>
          <p className="section-copy">
            {t("progress.weak.global.copy")}
          </p>
          <ul className="phoneme-list">
            {data.weak_phonemes.map((p) => (
              <li key={p.phoneme} className="phoneme-item weak">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">
                  {t("progress.stats.accuracy", { accuracy: Math.round(p.accuracy * 100) })}
                </span>
                <span className="phoneme-count">
                  {t("progress.stats.answered_items", { count: p.attempt_count })}
                </span>
                <button
                  className="focus-action-btn"
                  onClick={() => focusOne(p.phoneme)}
                  disabled={savingFocus !== null}
                >
                  {activeFocus.includes(p.phoneme)
                    ? t("focus.action.resume")
                    : t("focus.action.start", { phoneme: p.phoneme })}
                </button>
                <span className="phoneme-help">
                  {t("progress.focus.weighted", { phoneme: p.phoneme })}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.strong_phonemes.length > 0 && (
        <section className="phoneme-section">
          <h2>{t("progress.strong.global")}</h2>
          <ul className="phoneme-list">
            {data.strong_phonemes.map((p) => (
              <li key={p.phoneme} className="phoneme-item strong">
                <span className="phoneme-symbol">{p.phoneme}</span>
                <span className="phoneme-acc">
                  {t("progress.stats.percent", { value: Math.round(p.accuracy * 100) })}
                </span>
                <span className="phoneme-count">
                  {t("progress.stats.answered_items", { count: p.attempt_count })}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.weak_phonemes.length === 0 && data.strong_phonemes.length === 0 && (
        <p className="empty-hint">{t("progress.empty")}</p>
      )}
    </main>
  );
}
