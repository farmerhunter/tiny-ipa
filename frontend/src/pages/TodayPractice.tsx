/**
 * TodayPractice page.
 *
 * Loads /api/today, renders a sequence of practice items, and submits
 * answers to /api/attempt for server-side grading. The page is
 * refresh-safe: reloading on the same date resumes the same session.
 */

import { useEffect, useState } from "react";
import type { TodayItem, TodayResponse } from "../api";
import { fetchToday } from "../api";
import type { ChoiceResult } from "../components/ChoiceQuestion";
import { ChoiceQuestion } from "../components/ChoiceQuestion";

interface PracticeResult {
  sessionItemId: string;
  wordId: string;
  word: string;
  selectedAnswer: string;
  correctAnswer: string;
  isCorrect: boolean;
}

export default function TodayPractice() {
  const [session, setSession] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [results, setResults] = useState<PracticeResult[]>([]);
  const [finished, setFinished] = useState(false);

  // Load today's session on mount.
  useEffect(() => {
    fetchToday()
      .then((data) => {
        if (data.error) {
          setError(data.detail ?? data.error);
        } else {
          setSession(data);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleResult = (item: TodayItem, result: ChoiceResult) => {
    setResults((prev) => [
      ...prev,
      {
        sessionItemId: result.sessionItemId,
        wordId: item.word_id,
        word: item.word,
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
    return (
      <main className="practice-container">
        <div className="practice-summary">
          <h2>Practice complete!</h2>
          <p className="summary-score">
            {correctCount} / {total} correct
          </p>
          <ul className="summary-list">
            {results.map((r, i) => (
              <li key={i} className={r.isCorrect ? "summary-correct" : "summary-wrong"}>
                <strong>{r.word}</strong> — you picked{" "}
                <code>{r.selectedAnswer}</code>
                {r.isCorrect ? " ✅" : ` ❌ (correct: ${r.correctAnswer})`}
              </li>
            ))}
          </ul>
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
        <span className="progress-label">Progress: {progress}</span>
        <span className="accent-label">{session.primary_accent} practice</span>
      </div>

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
