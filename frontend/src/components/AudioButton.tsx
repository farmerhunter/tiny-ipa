/** Audio playback button. Uses browser TTS as fallback when no audio_url. */

interface AudioButtonProps {
  audioUrl: string | null;
  word: string;
}

export default function AudioButton({ audioUrl, word }: AudioButtonProps) {
  const handleClick = () => {
    if (audioUrl) {
      const audio = new Audio(audioUrl);
      audio.play().catch(() => {
        // Fallback to TTS on play failure
        speakWord(word);
      });
    } else {
      speakWord(word);
    }
  };

  return (
    <button
      className="btn btn-audio"
      onClick={handleClick}
      aria-label={`Play pronunciation of ${word}`}
    >
      <span className="audio-icon">🔊</span> Play
    </button>
  );
}

function speakWord(text: string) {
  if ("speechSynthesis" in window) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.8;
    window.speechSynthesis.speak(utterance);
  }
}
