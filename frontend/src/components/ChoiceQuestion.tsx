/**
 * ChoiceQuestion component.
 *
 * Displays a word and a set of IPA choices. The user selects one — it is
 * submitted to the server for grading. Feedback is shown after the server
 * responds.
 */

import { useState } from "react";
import type { TodayItem } from "../api";
import { submitAttempt } from "../api";
import { AudioButton } from "./AudioButton";

export interface ChoiceResult {
  sessionItemId: string;
  selectedAnswer: string;
  isCorrect: boolean;
  correctAnswer: string;
}

function buildFocusHint(targetPhonemes: string[]): string {
  if (targetPhonemes.length === 0) {
    return "Focus on the IPA difference, then listen again.";
  }
  return `Focus on ${targetPhonemes.join(" ")} before choosing.`;
}

interface Props {
  item: TodayItem;
  onResult: (result: ChoiceResult) => void;
  onContinue?: () => void;
}

export function ChoiceQuestion({ item, onResult, onContinue }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{
    isCorrect: boolean;
    selectedAnswer: string;
    correctAnswer: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = async (choice: string) => {
    if (submitting || feedback) return; // Already answered
    setSelected(choice);
    setSubmitting(true);
    setError(null);

    try {
      const result = await submitAttempt(item.session_item_id, choice);
      setFeedback({
        isCorrect: result.is_correct,
        selectedAnswer: choice,
        correctAnswer: result.correct_answer,
      });
      onResult({
        sessionItemId: item.session_item_id,
        selectedAnswer: choice,
        isCorrect: result.is_correct,
        correctAnswer: result.correct_answer,
      });
    } catch (err: unknown) {
      // submitAttempt normalises errors into Error with .message
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const isAnswered = feedback !== null;
  const isError = error !== null;

  return (
    <div className="choice-question">
      {/* Word display — IPA-first: word is shown, user picks matching IPA */}
      <div className="word-display">
        <span className="word-text">
          {item.word}
          <AudioButton
            audioUrl={item.audio_url}
            word={item.word}
            disabled={submitting}
          />
        </span>
        {item.meaning_zh && (
          <span className="word-meaning">{item.meaning_zh}</span>
        )}
      </div>

      <p className="question-prompt">{item.question.prompt}</p>

      <div className="choices-list">
        {item.question.choices.map((choice) => {
          let className = "choice-btn";
          if (isAnswered && choice === feedback.correctAnswer) {
            className += " choice-correct";
          } else if (
            isAnswered &&
            choice === selected &&
            !feedback.isCorrect
          ) {
            className += " choice-wrong";
          }

          return (
            <button
              key={choice}
              className={className}
              onClick={() => handleSelect(choice)}
              disabled={submitting || isAnswered}
              aria-label={`Select ${choice}`}
            >
              {choice}
            </button>
          );
        })}
      </div>

      {submitting && <p className="submit-status">Submitting…</p>}

      {isAnswered && (
        <div
          className={`feedback ${feedback.isCorrect ? "feedback-correct" : "feedback-wrong"}`}
          role="alert"
        >
          {feedback.isCorrect ? (
            <p>✅ Correct!</p>
          ) : (
            <div className="missed-answer-explanation">
              <p>❌ Not quite.</p>
              <div className="explanation-grid">
                <span>You picked</span>
                <code>{feedback.selectedAnswer}</code>
                <span>Correct IPA</span>
                <code>{feedback.correctAnswer}</code>
                <span>Target sound</span>
                <strong>{item.target_phonemes.join(" ") || "IPA contrast"}</strong>
              </div>
              <p className="focus-hint">{buildFocusHint(item.target_phonemes)}</p>
              {onContinue && (
                <button
                  className="feedback-continue-btn"
                  onClick={onContinue}
                  type="button"
                >
                  Continue
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {isAnswered && item.accent_compare && (
        <aside className="accent-compare-note" aria-label="Accent comparison">
          <span>{item.accent_compare.primary.label}</span>
          <code>{item.accent_compare.primary.ipa}</code>
          <span>{item.accent_compare.comparison.label}</span>
          <code>{item.accent_compare.comparison.ipa}</code>
          <p>{item.accent_compare.comparison.review_note}</p>
        </aside>
      )}

      {isError && (
        <div className="feedback feedback-error" role="alert">
          <p>⚠️ Failed to submit: {error}</p>
        </div>
      )}
    </div>
  );
}
