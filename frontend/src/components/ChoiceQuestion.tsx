/** Choose-IPA question with multiple choice buttons. */

interface ChoiceQuestionProps {
  prompt: string;
  choices: string[];
  selectedAnswer: string | null;
  correctAnswer: string;
  feedback: "idle" | "correct" | "wrong";
  onSelect: (choice: string) => void;
}

export default function ChoiceQuestion({
  prompt,
  choices,
  selectedAnswer,
  correctAnswer,
  feedback,
  onSelect,
}: ChoiceQuestionProps) {
  const getButtonClass = (choice: string): string => {
    if (feedback === "idle") return "btn btn-choice";
    if (choice === correctAnswer) return "btn btn-choice btn-correct";
    if (choice === selectedAnswer && feedback === "wrong") return "btn btn-choice btn-wrong";
    return "btn btn-choice btn-dimmed";
  };

  return (
    <div className="choice-question">
      <p className="question-prompt">{prompt}</p>
      <div className="choice-grid">
        {choices.map((choice) => (
          <button
            key={choice}
            className={getButtonClass(choice)}
            onClick={() => feedback === "idle" && onSelect(choice)}
            disabled={feedback !== "idle"}
            aria-label={choice}
          >
            {choice}
          </button>
        ))}
      </div>
      {feedback !== "idle" && (
        <div className={`feedback feedback-${feedback}`}>
          {feedback === "correct" ? "✓ Correct!" : `✗ The answer is ${correctAnswer}`}
        </div>
      )}
    </div>
  );
}
