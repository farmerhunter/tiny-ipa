/**
 * TodayPractice page.
 *
 * Loads /api/today, renders a sequence of practice items, and submits
 * answers to /api/attempt for server-side grading. The page is
 * refresh-safe: reloading on the same date resumes the same session.
 */

import { useCallback, useEffect, useState } from "react";
import type { SettingsData, TodayItem, TodayResponse } from "../api";
import { fetchSettings, fetchToday, startRecentMistakeReview } from "../api";
import type { ChoiceResult } from "../components/ChoiceQuestion";
import { ChoiceQuestion } from "../components/ChoiceQuestion";

interface Props {
  focusPhonemes: string[];
  onFocusChange: (focusPhonemes: string[]) => void;
  onOpenProgress: () => void;
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

function groupLabel(session: TodayResponse): string {
  if (session.group_type === "mistake_review") return "Mistake review";
  return `Group ${session.group_index ?? 1}`;
}

export default function TodayPractice({
  focusPhonemes,
  onFocusChange,
  onOpenProgress,
}: Props) {
  const [session, setSession] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [results, setResults] = useState<PracticeResult[]>([]);
  const [finished, setFinished] = useState(false);

  const resetPractice = useCallback((data: TodayResponse, settings?: SettingsData) => {
    if (data.error) {
      setError(data.detail ?? data.error);
      return;
    }
    setSession(data);
    setCurrentIndex(0);
    setResults([]);
    setFinished(data.items.length === 0);
    setNotice(null);
    if (settings) onFocusChange(settings.focus_phonemes);
  }, [onFocusChange]);

  // Load today's session on mount.
  useEffect(() => {
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
  }, [resetPractice]);

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
      setFinished(true);
    } else {
      setCurrentIndex(nextIndex);
    }
  };

  const handleContinue = async () => {
    setActionLoading("continue");
    setError(null);
    try {
      const data = await fetchToday();
      resetPractice(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load another group");
    } finally {
      setActionLoading(null);
    }
  };

  const handleMistakeReview = async () => {
    setActionLoading("review");
    setError(null);
    try {
      const data = await startRecentMistakeReview();
      if (data.status === "empty" || data.items.length === 0) {
        setNotice(data.detail ?? "No recent mistakes are ready for review.");
      } else {
        resetPractice(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start review");
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
  if (error || !session || session.error) {
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
    const hasMistakes = wrongResults.length > 0;
    return (
      <main className="practice-container">
        <div className="practice-summary">
          <h2>{groupLabel(session)} complete</h2>
          <p className="summary-score">
            {correctCount} / {total} correct
          </p>
          {wrongResults.length > 0 ? (
            <section className="summary-section">
              <h3>Review these</h3>
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
                      {r.targetPhonemes.join(" ")}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <p className="summary-perfect">No misses in this group.</p>
          )}
          {error && <p className="save-error">{error}</p>}
          {notice && <p className="empty-hint">{notice}</p>}
          <div className="summary-actions">
            <button
              className="primary-action-btn"
              onClick={handleContinue}
              disabled={actionLoading !== null}
            >
              {actionLoading === "continue" ? "Loading…" : "Continue"}
            </button>
            <button
              className="secondary-action-btn"
              onClick={handleMistakeReview}
              disabled={!hasMistakes || actionLoading !== null}
            >
              {actionLoading === "review" ? "Loading…" : "Review mistakes"}
            </button>
            <button className="secondary-action-btn" onClick={onOpenProgress}>
              Stop
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
        <span className="accent-label">{session.primary_accent}</span>
      </div>
      {focusPhonemes.length > 0 && (
        <div className="active-focus-banner">
          <span>Focus</span>
          {focusPhonemes.map((phoneme) => (
            <span className="phoneme-chip" key={phoneme}>{phoneme}</span>
          ))}
        </div>
      )}

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
