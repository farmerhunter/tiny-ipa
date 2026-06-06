import { useCallback, useEffect, useState } from "react";
import AudioButton from "../components/AudioButton";
import ChoiceQuestion from "../components/ChoiceQuestion";
import IpaCard from "../components/IpaCard";
import { fetchToday } from "../api";
import type { TodayItem } from "../api";

/** Explicit interaction states for the practice flow. */
type PracticeState =
  | "loading"
  | "error"
  | "empty"
  | "ipa_only"
  | "revealed"
  | "answering"
  | "feedback"
  | "completed";

export default function TodayPractice() {
  const [state, setState] = useState<PracticeState>("loading");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [items, setItems] = useState<TodayItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [feedbackType, setFeedbackType] = useState<"idle" | "correct" | "wrong">("idle");
  const [correctCount, setCorrectCount] = useState(0);

  // Load today's session on mount
  useEffect(() => {
    let cancelled = false;
    fetchToday({ daily_word_count: 10 })
      .then((data) => {
        if (cancelled) return;
        if (data.items.length === 0) {
          setState("empty");
          return;
        }
        setItems(data.items);
        setState("ipa_only");
      })
      .catch((err) => {
        if (cancelled) return;
        setErrorMsg(err.message);
        setState("error");
      });
    return () => { cancelled = true; };
  }, []);

  const currentItem = items[currentIndex] ?? null;
  const correctAnswer = currentItem?.display_ipa ?? "";
  const isLastItem = currentIndex >= items.length - 1;

  // ---- state transitions ----

  const handleReveal = useCallback(() => {
    setState("answering");
  }, []);

  const handleSelectAnswer = useCallback((choice: string) => {
    setSelectedAnswer(choice);
    const isCorrect = choice === correctAnswer;
    if (isCorrect) setCorrectCount((c) => c + 1);
    setFeedbackType(isCorrect ? "correct" : "wrong");
    setState("feedback");
  }, [correctAnswer]);

  const handleNext = useCallback(() => {
    if (isLastItem) {
      setState("completed");
    } else {
      setSelectedAnswer(null);
      setFeedbackType("idle");
      setCurrentIndex((i) => i + 1);
      setState("ipa_only");
    }
  }, [isLastItem]);

  const handleRetry = useCallback(() => {
    setErrorMsg(null);
    setState("loading");
    fetchToday({ daily_word_count: 10 })
      .then((data) => {
        setItems(data.items);
        setCurrentIndex(0);
        setSelectedAnswer(null);
        setFeedbackType("idle");
        setCorrectCount(0);
        setState(data.items.length === 0 ? "empty" : "ipa_only");
      })
      .catch((err) => {
        setErrorMsg(err.message);
        setState("error");
      });
  }, []);

  // ---- render states ----

  if (state === "loading") {
    return <p className="state-message">Loading today's practice…</p>;
  }

  if (state === "error") {
    return (
      <div className="state-message state-error">
        <p>Something went wrong: {errorMsg}</p>
        <button className="btn btn-primary" onClick={handleRetry}>Try again</button>
      </div>
    );
  }

  if (state === "empty") {
    return <p className="state-message">No practice words available today. Check back later!</p>;
  }

  if (state === "completed") {
    return (
      <div className="state-message state-completed">
        <h2>Great work!</h2>
        <p>
          You answered {correctCount} of {items.length} correctly.
        </p>
        <button className="btn btn-primary" onClick={handleRetry}>
          Practice again
        </button>
      </div>
    );
  }

  // Active practice states
  return (
    <div className="today-practice">
      {/* Progress indicator */}
      <div className="progress-bar">
        {currentIndex + 1} / {items.length}
      </div>

      {/* IPA card — hidden until revealed */}
      <IpaCard
        ipa={currentItem!.display_ipa}
        revealed={state !== "ipa_only"}
        word={currentItem!.word}
        meaningZh={currentItem!.meaning_zh}
        onReveal={handleReveal}
      />

      {/* Audio button — visible after reveal */}
      {state !== "ipa_only" && (
        <AudioButton audioUrl={currentItem!.audio_url} word={currentItem!.word} />
      )}

      {/* Question — visible while answering or in feedback */}
      {(state === "answering" || state === "feedback") && (
        <ChoiceQuestion
          prompt="Which IPA matches this word?"
          choices={currentItem!.question.choices}
          selectedAnswer={selectedAnswer}
          correctAnswer={correctAnswer}
          feedback={feedbackType}
          onSelect={handleSelectAnswer}
        />
      )}

      {/* Next button — visible during feedback */}
      {state === "feedback" && (
        <button className="btn btn-primary btn-next" onClick={handleNext}>
          {isLastItem ? "See results" : "Next"}
        </button>
      )}
    </div>
  );
}
