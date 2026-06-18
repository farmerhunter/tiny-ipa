/**
 * TodayPractice page.
 *
 * Loads /api/today, renders a sequence of practice items, and submits
 * answers to /api/attempt for server-side grading. The page is
 * refresh-safe: reloading on the same date resumes the same session.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { SettingsData, TodayItem, TodayResponse } from "../api";
import {
  clearPracticeFocus,
  fetchSettings,
  fetchToday,
  startCurrentGroupReview,
  startFocusedPractice,
  startNextNormalGroup,
  startRecentMistakeReview,
} from "../api";
import type { ChoiceResult } from "../components/ChoiceQuestion";
import { ChoiceQuestion } from "../components/ChoiceQuestion";

interface Props {
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

function groupLabel(session: TodayResponse): string {
  if (session.group_type === "weak_focus") return "Focused group";
  if (session.source_scope === "current_group") return "Current-group review";
  if (session.source_scope === "recent_global") return "Recent mistake review";
  if (session.group_type === "mistake_review") return "Mistake review";
  return "Practice group";
}

function learnerLevelLabel(session: TodayResponse): string {
  return session.learner_level_label ?? (session.learner_level === "mid" ? "Mid" : "Entry");
}

function groupReason(session: TodayResponse): string {
  if (session.group_type === "weak_focus") {
    const focus = session.focus_phonemes?.join(" ") || "selected sounds";
    return `${learnerLevelLabel(session)} focused practice for ${focus}.`;
  }
  if (session.source_scope === "current_group") {
    return "Reviewing misses from the group you just finished.";
  }
  if (session.source_scope === "recent_global") {
    return "Reviewing recent mistakes from earlier practice.";
  }
  if (session.source_scope === "normal_next") {
    return `A new ${learnerLevelLabel(session)} practice group.`;
  }
  if (session.origin === "normal_resume") {
    return `Resuming your current ${learnerLevelLabel(session)} group.`;
  }
  return `${learnerLevelLabel(session)} practice group.`;
}

function buildFocusHint(targetPhonemes: string[]): string {
  if (targetPhonemes.length === 0) {
    return "Focus on the IPA difference, then listen again.";
  }
  return `Focus on ${targetPhonemes.join(" ")} before choosing.`;
}

function currentReviewActionLabel(session: TodayResponse): string {
  if (session.group_type === "mistake_review") {
    return "Review misses from this review";
  }
  return "Review misses from this group";
}

function nextNormalActionLabel(session: TodayResponse): string {
  const level = learnerLevelLabel(session);
  return `Start next ${level} group`;
}

export default function TodayPractice({
  focusPhonemes,
  onFocusChange,
  onOpenProgress,
  initialSession,
  onInitialSessionConsumed,
}: Props) {
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
  const [lastSummarySession, setLastSummarySession] = useState<TodayResponse | null>(null);

  const resetPractice = useCallback((data: TodayResponse, settings?: SettingsData) => {
    if (data.error) {
      setError(data.detail ?? data.error);
      return;
    }
    setSession(data);
    setCurrentIndex(0);
    setResults([]);
    setFinished(data.items.length === 0);
    setLastSummarySession(null);
    setNotice(null);
    if (data.focus_phonemes) onFocusChange(data.focus_phonemes);
    else if (settings) onFocusChange(settings.focus_phonemes);
  }, [onFocusChange]);

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
        resetPractice(today, settings);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load practice");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [initialSession, resetPractice]);

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
      setError(err instanceof Error ? err.message : "Failed to load another group");
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
        setNotice(data.detail ?? "No misses in this group are ready for review.");
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start review");
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
        setNotice(data.detail ?? "No recent mistakes are ready for review.");
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start recent review");
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
      setError(err instanceof Error ? err.message : "Failed to start focused practice");
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
      resetPractice(data);
      setNotice("Focus cleared. Back to normal practice.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear focus");
    } finally {
      setActionLoading(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <main className="practice-container">
        <p>Loading today's practice…</p>
      </main>
    );
  }

  // Error state
  if (!session) {
    return (
      <main className="practice-container">
        <div className="practice-error">
          <h2>Practice unavailable</h2>
          <p>{error || "Unknown error"}</p>
          <p className="hint">
            Make sure you've run <code>import_words.py</code> and the backend
            is running.
          </p>
        </div>
      </main>
    );
  }

  if (!finished && (error || session.error)) {
    return (
      <main className="practice-container">
        <div className="practice-error">
          <h2>Practice unavailable</h2>
          <p>{error || session?.detail || "Unknown error"}</p>
          <p className="hint">
            Make sure you've run <code>import_words.py</code> and the backend
            is running.
          </p>
        </div>
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
    const focusSuggestions = canonicalFocus(
      wrongResults.flatMap((result) => result.targetPhonemes),
    ).slice(0, 3);
    return (
      <main className="practice-container">
        <div className="practice-summary">
          <p className="workflow-kicker">{groupReason(summarySession)}</p>
          <h2>{groupLabel(summarySession)} complete</h2>
          <p className="summary-score">
            {correctCount} / {total} correct
          </p>
          {wrongResults.length > 0 ? (
            <section className="summary-section">
              <h3>Misses from this group</h3>
              <ul className="summary-list">
                {wrongResults.map((r) => (
                  <li key={r.sessionItemId} className="summary-wrong">
                    <span>
                      <strong>{r.word}</strong>
                      <span className="summary-answer">
                        picked <code>{r.selectedAnswer}</code>, correct{" "}
                        <code>{r.correctAnswer}</code>
                      </span>
                    </span>
                    <span className="summary-phonemes">
                      Target sound: {r.targetPhonemes.join(" ") || "IPA contrast"}
                    </span>
                    <span className="summary-hint">
                      {buildFocusHint(r.targetPhonemes)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <p className="summary-perfect">No misses in this group.</p>
          )}
          {focusSuggestions.length > 0 && (
            <section className="summary-section focus-choice-panel">
              <h3>Focus a weak sound next</h3>
              <p className="section-copy">
                Start a focused group weighted toward one of the sounds missed here.
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
                    Focus {phoneme}
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
              {actionLoading === "continue" ? "Loading…" : nextNormalActionLabel(summarySession)}
            </button>
            {hasCurrentGroupMisses && (
              <button
                className="secondary-action-btn"
                onClick={handleCurrentGroupReview}
                disabled={actionLoading !== null}
              >
                {actionLoading === "current-review"
                  ? "Loading…"
                  : currentReviewActionLabel(summarySession)}
              </button>
            )}
            <button
              className="secondary-action-btn"
              onClick={handleRecentReview}
              disabled={actionLoading !== null}
            >
              {actionLoading === "recent-review" ? "Loading…" : "Review recent mistakes"}
            </button>
            <button className="secondary-action-btn" onClick={onOpenProgress}>
              Return to Progress
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
        <span className="progress-label">{groupLabel(session)}: {progress}</span>
        <span className="practice-context">
          <span className="level-label">{learnerLevelLabel(session)}</span>
          <span className="accent-label">{session.primary_accent}</span>
        </span>
      </div>
      <div className="mode-panel">
        <strong>{groupLabel(session)}</strong>
        <span>{groupReason(session)}</span>
      </div>
      {(session.focus_phonemes?.length || focusPhonemes.length > 0) && (
        <div className="active-focus-banner">
          <span>Current focus</span>
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
              Clear focus
            </button>
          )}
        </div>
      )}
      {notice && <p className="empty-hint">{notice}</p>}
      {error && <p className="save-error">{error}</p>}

      <ChoiceQuestion
        key={currentItem.session_item_id}
        item={currentItem}
        onResult={(result) => {
          handleResult(currentItem, result);
          // Auto-advance after a short delay so the user can read feedback.
          setTimeout(() => handleNext(), 1500);
        }}
      />
    </main>
  );
}
