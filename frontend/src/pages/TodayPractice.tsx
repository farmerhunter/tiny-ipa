/**
 * TodayPractice page.
 *
 * Loads /api/today, renders a sequence of practice items, and submits
 * answers to /api/attempt for server-side grading. The page is
 * refresh-safe: reloading on the same date resumes the same session.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SettingsData, TodayItem, TodayResponse } from "../api";
import {
  abandonCurrentAndStartNext,
  clearPracticeFocus,
  fetchSettings,
  fetchToday,
  startCurrentGroupReview,
  startFocusedPractice,
  startMinimalPairPractice,
  startNextNormalGroup,
  startRecentMistakeReview,
  startTargetPhonemePractice,
} from "../api";
import type { ChoiceResult } from "../components/ChoiceQuestion";
import { ChoiceQuestion } from "../components/ChoiceQuestion";
import {
  createTranslator,
  learnerLevelLabel as localizedLearnerLevelLabel,
  type Locale,
  type Translator,
} from "../locales";

interface Props {
  uiLanguage: Locale;
  focusPhonemes: string[];
  onFocusChange: (focusPhonemes: string[]) => void;
  onOpenProgress: () => void;
  initialSession?: TodayResponse | null;
  onInitialSessionConsumed?: () => void;
}

interface PracticeResult {
  sessionItemId: string;
  wordId: string;
  word: string;
  targetPhonemes: string[];
  selectedAnswer: string;
  correctAnswer: string;
  isCorrect: boolean;
}

function canonicalFocus(phonemes: string[]): string[] {
  return Array.from(new Set(phonemes.map((item) => item.trim()).filter(Boolean))).sort();
}

function groupLabel(session: TodayResponse, t: Translator): string {
  if (session.group_type === "minimal_pair") return t("today.group.label.sound_compare");
  if (session.group_type === "target_phoneme") return t("today.group.label.sound_practice");
  if (session.group_type === "weak_focus") return t("today.group.label.focused");
  if (session.source_scope === "current_group") return t("today.group.label.current_review");
  if (session.source_scope === "recent_global") return t("today.group.label.recent_review");
  if (session.group_type === "mistake_review") return t("today.group.label.mistake_review");
  return t("today.group.label.practice");
}

function learnerLevelLabel(session: TodayResponse, t: Translator): string {
  return localizedLearnerLevelLabel(session.learner_level, t);
}

function selectedLevelLabel(session: TodayResponse, t: Translator): string {
  return localizedLearnerLevelLabel(session.selected_learner_level, t);
}

function groupReason(session: TodayResponse, t: Translator): string {
  if (session.group_type === "minimal_pair") {
    return t("specialty.sound_compare.description");
  }
  if (session.group_type === "target_phoneme") {
    const phoneme = session.focus_phonemes?.[0] ?? t("today.group.reason.chosen_sound");
    return t("today.group.reason.target_phoneme", { phoneme });
  }
  if (session.group_type === "weak_focus") {
    const phonemes = session.focus_phonemes?.join(" ") || t("today.group.reason.selected_sounds");
    return t("today.group.reason.weak_focus", {
      level: learnerLevelLabel(session, t),
      phonemes,
    });
  }
  if (session.source_scope === "current_group") {
    return t("today.group.reason.current_group");
  }
  if (session.source_scope === "recent_global") {
    return t("today.group.reason.recent_global");
  }
  if (session.source_scope === "normal_next") {
    return t("today.group.reason.normal_next", { level: learnerLevelLabel(session, t) });
  }
  if (session.origin === "normal_resume") {
    return t("today.group.reason.normal_resume", { level: learnerLevelLabel(session, t) });
  }
  return t("today.group.reason.default", { level: learnerLevelLabel(session, t) });
}

function buildFocusHint(targetPhonemes: string[], t: Translator): string {
  if (targetPhonemes.length === 0) {
    return t("practice.feedback.focus_hint.default");
  }
  return t("practice.feedback.focus_hint.phonemes", { phonemes: targetPhonemes.join(" ") });
}

function currentReviewActionLabel(session: TodayResponse, t: Translator): string {
  if (session.group_type === "mistake_review") {
    return t("review.current.action.review_misses");
  }
  return t("review.current.action.group_misses");
}

function nextNormalActionLabel(session: TodayResponse, t: Translator): string {
  const level = selectedLevelLabel(session, t);
  return t("today.action.start_next_group", { level });
}

function resumeActionLabel(session: TodayResponse, t: Translator): string {
  const level = learnerLevelLabel(session, t);
  return t("today.action.resume_group.short", { level });
}

function completedGroupsCopy(session: TodayResponse, t: Translator): string {
  const counts = session.completed_normal_groups_today ?? { entry: 0, mid: 0, total: 0 };
  return t("today.hub.completed_today", {
    entryCount: counts.entry,
    midCount: counts.mid,
  });
}

function completedGroupCount(session: TodayResponse): number {
  return session.completed_normal_groups_today?.total ?? 0;
}

function todayHubHeading(session: TodayResponse, hasActiveGroup: boolean, t: Translator): string {
  if (hasActiveGroup) {
    return t("today.hub.heading.active", { level: learnerLevelLabel(session, t) });
  }
  return t("today.hub.heading.start", { selectedLevel: selectedLevelLabel(session, t) });
}

function todayHubCopy(hasActiveGroup: boolean, t: Translator): string {
  if (hasActiveGroup) {
    return t("today.hub.copy.active");
  }
  return t("today.hub.copy.empty");
}

function recentReviewLabel(session: TodayResponse, t: Translator): string {
  const count = session.recent_mistake_count ?? 0;
  if (count <= 0) return t("review.recent.none");
  return t("review.recent.action.count", { count });
}

export default function TodayPractice({
  uiLanguage,
  focusPhonemes,
  onFocusChange,
  onOpenProgress,
  initialSession,
  onInitialSessionConsumed,
}: Props) {
  const t = useMemo(() => createTranslator(uiLanguage), [uiLanguage]);
  const adoptedInitialSession = useRef(Boolean(initialSession));
  const [session, setSession] = useState<TodayResponse | null>(() => initialSession ?? null);
  const [loading, setLoading] = useState(() => !initialSession);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [results, setResults] = useState<PracticeResult[]>([]);
  const [finished, setFinished] = useState(() =>
    Boolean(initialSession && initialSession.items.length === 0),
  );
  const [showHub, setShowHub] = useState(() => !initialSession);
  const [lastSummarySession, setLastSummarySession] = useState<TodayResponse | null>(null);

  const resetPractice = useCallback((
    data: TodayResponse,
    settings?: SettingsData,
    options: { showHub?: boolean } = {},
  ) => {
    if (data.error) {
      setError(t("error.generic.failed", { error: data.error }));
      return;
    }
    setSession(data);
    setCurrentIndex(0);
    setResults([]);
    setFinished(data.items.length === 0);
    setShowHub(options.showHub ?? false);
    setLastSummarySession(null);
    setNotice(null);
    if (data.focus_phonemes) onFocusChange(data.focus_phonemes);
    else if (settings) onFocusChange(settings.focus_phonemes);
  }, [onFocusChange, t]);

  useEffect(() => {
    if (initialSession) {
      onInitialSessionConsumed?.();
    }
  }, [initialSession, onInitialSessionConsumed]);

  // Load today's session on mount.
  useEffect(() => {
    if (initialSession || adoptedInitialSession.current) return;

    let cancelled = false;
    Promise.all([fetchToday(), fetchSettings()])
      .then(([today, settings]) => {
        if (cancelled) return;
        setError(null);
        resetPractice(today, settings, { showHub: true });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("error.practice.load_failed"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [initialSession, resetPractice, t]);

  const handleResult = (item: TodayItem, result: ChoiceResult) => {
    setResults((prev) => [
      ...prev,
      {
        sessionItemId: result.sessionItemId,
        wordId: item.word_id,
        word: item.word,
        targetPhonemes: item.target_phonemes,
        selectedAnswer: result.selectedAnswer,
        correctAnswer: result.correctAnswer,
        isCorrect: result.isCorrect,
      },
    ]);
  };

  const handleNext = () => {
    if (!session) return;
    const nextIndex = currentIndex + 1;
    if (nextIndex >= session.items.length) {
      setLastSummarySession(session);
      setFinished(true);
    } else {
      setCurrentIndex(nextIndex);
    }
  };

  const handleNextNormal = async () => {
    setActionLoading("continue");
    setError(null);
    try {
      const data = await startNextNormalGroup();
      resetPractice(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.load_next_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleAbandonAndNext = async () => {
    if (!session) return;
    const isPending = Boolean(session.pending_level_change);
    const ok = window.confirm(
      isPending
        ? t("today.confirm.abandon_pending", {
            currentLevel: learnerLevelLabel(session, t),
            selectedLevel: selectedLevelLabel(session, t),
          })
        : t("today.confirm.abandon_same_level", {
            currentLevel: learnerLevelLabel(session, t),
            selectedLevel: selectedLevelLabel(session, t),
          }),
    );
    if (!ok) return;
    setActionLoading("abandon-next");
    setError(null);
    try {
      const data = await abandonCurrentAndStartNext();
      resetPractice(data);
      setNotice(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.switch_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleCurrentGroupReview = async () => {
    const sourceGroupId = lastSummarySession?.group_id ?? session?.group_id;
    if (!sourceGroupId) return;
    setActionLoading("current-review");
    setError(null);
    try {
      const data = await startCurrentGroupReview(sourceGroupId);
      if (data.status === "empty" || data.items.length === 0) {
        setNotice(t("review.current.empty"));
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.review_start_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleRecentReview = async () => {
    setActionLoading("recent-review");
    setError(null);
    try {
      const data = await startRecentMistakeReview();
      if (data.status === "empty" || data.items.length === 0) {
        setNotice(t("review.recent.empty"));
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.recent_review_start_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleMinimalPairPractice = async () => {
    setActionLoading("minimal-pair");
    setError(null);
    try {
      const data = await startMinimalPairPractice();
      if (data.status === "empty" || data.items.length === 0) {
        setNotice(t("specialty.sound_compare.empty"));
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.sound_compare_start_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleTargetPhonemePractice = async (phoneme: string) => {
    setActionLoading(`target-${phoneme}`);
    setError(null);
    try {
      const data = await startTargetPhonemePractice(phoneme);
      if (data.status === "empty" || data.items.length === 0) {
        setNotice(t("specialty.sound_practice.empty"));
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.sound_practice_start_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleFocusPractice = async (phonemes: string[]) => {
    const nextFocus = canonicalFocus(phonemes);
    if (nextFocus.length === 0) return;
    setActionLoading("focus");
    setError(null);
    try {
      const data = await startFocusedPractice(nextFocus);
      resetPractice(data);
      onFocusChange(data.focus_phonemes ?? nextFocus);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.focus_start_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearFocus = async () => {
    setActionLoading("clear-focus");
    setError(null);
    try {
      const data = await clearPracticeFocus();
      onFocusChange([]);
      resetPractice(data, undefined, { showHub: true });
      setNotice(t("focus.action.clear.notice"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error.practice.clear_focus_failed"));
    } finally {
      setActionLoading(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <main className="practice-container">
        <p>{t("today.loading")}</p>
      </main>
    );
  }

  // Error state
  if (!session) {
    return (
      <main className="practice-container">
        <div className="practice-error">
          <h2>{t("today.error.title")}</h2>
          <p>{error || t("error.generic.unknown")}</p>
          <p className="hint">
            {t("today.error.import_hint_before")} <code>import_words.py</code>{" "}
            {t("today.error.import_hint_after")}
          </p>
        </div>
      </main>
    );
  }

  if (!finished && (error || session.error)) {
    return (
      <main className="practice-container">
        <div className="practice-error">
          <h2>{t("today.error.title")}</h2>
          <p>{error || t("error.generic.unknown")}</p>
          <p className="hint">
            {t("today.error.import_hint_before")} <code>import_words.py</code>{" "}
            {t("today.error.import_hint_after")}
          </p>
        </div>
      </main>
    );
  }

  if (showHub && session.group_type === "normal") {
    const hasActiveGroup = Boolean(
      session.group_id && session.items.length > 0 && session.status !== "idle",
    );
    const pendingLevelChange = hasActiveGroup && Boolean(session.pending_level_change);
    const showSwitchAction = hasActiveGroup && pendingLevelChange;
    return (
      <main className="practice-container">
        <section className="today-hub">
          <p className="workflow-kicker">{t("today.hub.kicker")}</p>
          <h1>{todayHubHeading(session, hasActiveGroup, t)}</h1>
          <p className="section-copy">
            {todayHubCopy(hasActiveGroup, t)}
          </p>

          <div className={`hub-status-card ${pendingLevelChange ? "pending" : ""}`}>
            {hasActiveGroup ? (
              <>
                <span className="focus-panel-label">{t("today.hub.status.active.label")}</span>
                <strong>
                  {t("today.hub.status.active.title", { level: learnerLevelLabel(session, t) })}
                </strong>
                <span>
                  {t("today.hub.status.active.meta", {
                    wordCount: session.word_count ?? session.items.length,
                  })} · {session.primary_accent}
                </span>
                {pendingLevelChange && (
                  <p className="pending-copy">
                    {t("today.hub.pending_level_change", {
                      selectedLevel: selectedLevelLabel(session, t),
                      currentLevel: learnerLevelLabel(session, t),
                    })}
                  </p>
                )}
              </>
            ) : (
              <>
                <span className="focus-panel-label">{t("today.hub.status.ready.label")}</span>
                <strong>
                  {t("today.hub.status.ready.title", {
                    selectedLevel: selectedLevelLabel(session, t),
                  })}
                </strong>
                <span>
                  {t("today.hub.status.ready.meta", { count: session.daily_word_count })} · {session.primary_accent}
                </span>
              </>
            )}
          </div>

          {completedGroupCount(session) > 0 && (
            <p className="empty-hint">{completedGroupsCopy(session, t)}</p>
          )}

          <div className="specialty-panel">
            <div>
              <span className="focus-panel-label">{t("specialty.label")}</span>
              <strong>{t("specialty.sound_compare.title")}</strong>
              <span>
                {t("specialty.sound_compare.description")}
              </span>
            </div>
            <button
              className="secondary-action-btn"
              onClick={() => void handleMinimalPairPractice()}
              disabled={actionLoading !== null}
              type="button"
            >
              {actionLoading === "minimal-pair"
                ? t("action.loading")
                : t("specialty.sound_compare.start")}
            </button>
          </div>

          <div className="specialty-panel target-phoneme-panel">
            <div>
              <span className="focus-panel-label">{t("specialty.label")}</span>
              <strong>{t("specialty.sound_practice.title")}</strong>
              <span>
                {t("specialty.sound_practice.description")}
              </span>
            </div>
            <div className="phoneme-chip-list">
              {(session.target_phoneme_options ?? []).slice(0, 6).map((option) => (
                <button
                  className="phoneme-chip selectable"
                  key={option.phoneme}
                  onClick={() => void handleTargetPhonemePractice(option.phoneme)}
                  disabled={actionLoading !== null}
                  type="button"
                >
                  {actionLoading === `target-${option.phoneme}`
                    ? t("action.loading")
                    : t("specialty.sound_practice.practice", { phoneme: option.phoneme })}
                </button>
              ))}
              {(session.target_phoneme_options ?? []).length === 0 && (
                <span className="empty-hint">
                  {t("specialty.sound_practice.no_options")}
                </span>
              )}
            </div>
          </div>

          {notice && <p className="empty-hint">{notice}</p>}
          {error && <p className="save-error">{error}</p>}

          <div className="summary-actions">
            <button
              className="primary-action-btn"
              onClick={() => {
                if (hasActiveGroup) {
                  setShowHub(false);
                  setNotice(null);
                } else {
                  void handleNextNormal();
                }
              }}
              disabled={actionLoading !== null}
            >
              {actionLoading === "continue"
                ? t("action.loading")
                : hasActiveGroup
                  ? resumeActionLabel(session, t)
                  : t("today.action.start_group.short", {
                      level: selectedLevelLabel(session, t),
                    })}
            </button>
            {showSwitchAction && (
              <button
                className="secondary-action-btn"
                onClick={() => void handleAbandonAndNext()}
                disabled={actionLoading !== null}
              >
                {actionLoading === "abandon-next"
                  ? t("action.loading")
                  : t("today.action.switch_now", {
                      selectedLevel: selectedLevelLabel(session, t),
                    })}
              </button>
            )}
            <button
              className="secondary-action-btn"
              onClick={handleRecentReview}
              disabled={actionLoading !== null || (session.recent_mistake_count ?? 0) <= 0}
            >
              {actionLoading === "recent-review" ? t("action.loading") : recentReviewLabel(session, t)}
            </button>
            <button className="secondary-action-btn" onClick={onOpenProgress}>
              {t("today.action.view_progress")}
            </button>
          </div>
        </section>
      </main>
    );
  }

  // Finished state — show summary
  if (finished) {
    const correctCount = results.filter((r) => r.isCorrect).length;
    const total = results.length;
    const wrongResults = results.filter((r) => !r.isCorrect);
    const summarySession = lastSummarySession ?? session;
    const hasCurrentGroupMisses = wrongResults.length > 0;
    const summaryRecentMistakeCount = Math.max(
      summarySession.recent_mistake_count ?? 0,
      wrongResults.length,
    );
    const focusSuggestions = canonicalFocus(
      wrongResults.flatMap((result) => result.targetPhonemes),
    ).slice(0, 3);
    return (
      <main className="practice-container">
        <div className="practice-summary">
          <p className="workflow-kicker">{groupReason(summarySession, t)}</p>
          <h2>
            {t("practice.summary.complete_title", {
              groupLabel: groupLabel(summarySession, t),
            })}
          </h2>
          <p className="summary-score">
            {t("practice.summary.score", {
              correctCount,
              totalCount: total,
            })}
          </p>
          {wrongResults.length > 0 ? (
            <section className="summary-section">
              <h3>{t("practice.summary.current_misses")}</h3>
              <ul className="summary-list">
                {wrongResults.map((r) => (
                  <li key={r.sessionItemId} className="summary-wrong">
                    <span>
                      <strong>{r.word}</strong>
                      <span className="summary-answer">
                        {t("practice.summary.picked_before")} <code>{r.selectedAnswer}</code>
                        {", "}
                        {t("practice.summary.correct_before")} <code>{r.correctAnswer}</code>
                      </span>
                    </span>
                    <span className="summary-phonemes">
                      {t("practice.feedback.label.target_sound")}:{" "}
                      {r.targetPhonemes.join(" ") || t("practice.feedback.target_sound.default")}
                    </span>
                    <span className="summary-hint">
                      {buildFocusHint(r.targetPhonemes, t)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <p className="summary-perfect">{t("practice.summary.no_misses")}</p>
          )}
          {focusSuggestions.length > 0 && (
            <section className="summary-section focus-choice-panel">
              <h3>{t("practice.summary.focus_next.title")}</h3>
              <p className="section-copy">
                {t("practice.summary.focus_next.description")}
              </p>
              <div className="phoneme-chip-list">
                {focusSuggestions.map((phoneme) => (
                  <button
                    className="phoneme-chip selectable"
                    key={phoneme}
                    onClick={() => void handleFocusPractice([phoneme])}
                    disabled={actionLoading !== null}
                    type="button"
                  >
                    {t("focus.action.start_phoneme", { phoneme })}
                  </button>
                ))}
              </div>
            </section>
          )}
          {error && <p className="save-error">{error}</p>}
          {notice && <p className="empty-hint">{notice}</p>}
          <div className="summary-actions">
            <button
              className="primary-action-btn"
              onClick={handleNextNormal}
              disabled={actionLoading !== null}
            >
              {actionLoading === "continue"
                ? t("action.loading")
                : nextNormalActionLabel(summarySession, t)}
            </button>
            {hasCurrentGroupMisses && (
              <button
                className="secondary-action-btn"
                onClick={handleCurrentGroupReview}
                disabled={actionLoading !== null}
              >
                {actionLoading === "current-review"
                  ? t("action.loading")
                  : currentReviewActionLabel(summarySession, t)}
              </button>
            )}
            <button
              className="secondary-action-btn"
              onClick={handleRecentReview}
              disabled={actionLoading !== null}
            >
              {actionLoading === "recent-review"
                ? t("action.loading")
                : recentReviewLabel({
                    ...summarySession,
                    recent_mistake_count: summaryRecentMistakeCount,
                  }, t)}
            </button>
            <button className="secondary-action-btn" onClick={onOpenProgress}>
              {t("today.action.return_to_progress")}
            </button>
          </div>
        </div>
      </main>
    );
  }

  // Active practice — show current item
  const currentItem = session.items[currentIndex];
  const progress = `${currentIndex + 1} / ${session.items.length}`;

  return (
    <main className="practice-container">
      <div className="practice-header">
        <span className="progress-label">{groupLabel(session, t)}: {progress}</span>
        <span className="practice-context">
          <span className="level-label">{learnerLevelLabel(session, t)}</span>
          <span className="accent-label">{session.primary_accent}</span>
        </span>
      </div>
      <div className="mode-panel">
        <strong>{groupLabel(session, t)}</strong>
        <span>{groupReason(session, t)}</span>
      </div>
      {(session.focus_phonemes?.length || focusPhonemes.length > 0) && (
        <div className="active-focus-banner">
          <span>
            {session.group_type === "target_phoneme"
              ? t("focus.chosen_sound.label")
              : t("focus.current.label")}
          </span>
          {(session.focus_phonemes ?? focusPhonemes).map((phoneme) => (
            <span className="phoneme-chip" key={phoneme}>{phoneme}</span>
          ))}
          {session.group_type === "weak_focus" && (
            <button
              className="secondary-action-btn compact"
              onClick={() => void handleClearFocus()}
              disabled={actionLoading !== null}
              type="button"
            >
              {t("focus.action.clear_button")}
            </button>
          )}
        </div>
      )}
      {notice && <p className="empty-hint">{notice}</p>}
      {error && <p className="save-error">{error}</p>}

      <ChoiceQuestion
        key={currentItem.session_item_id}
        item={currentItem}
        t={t}
        onResult={(result) => {
          handleResult(currentItem, result);
          if (result.isCorrect) {
            // Correct answers keep the quick flow; misses stay visible until acknowledged.
            setTimeout(() => handleNext(), 1500);
          }
        }}
        onContinue={handleNext}
      />
    </main>
  );
}
