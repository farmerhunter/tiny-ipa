/** Large IPA display card. */

interface IpaCardProps {
  ipa: string;
  revealed: boolean;
  word: string;
  meaningZh: string | null;
  onReveal: () => void;
}

export default function IpaCard({ ipa, revealed, word, meaningZh, onReveal }: IpaCardProps) {
  return (
    <div className="ipa-card">
      <div className="ipa-display">{ipa}</div>

      {!revealed ? (
        <button
          className="btn btn-primary btn-reveal"
          onClick={onReveal}
          aria-label="Reveal word"
        >
          Show word
        </button>
      ) : (
        <div className="ipa-revealed">
          <div className="ipa-word">{word}</div>
          {meaningZh && <div className="ipa-meaning">{meaningZh}</div>}
        </div>
      )}
    </div>
  );
}
