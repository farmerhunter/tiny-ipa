/**
 * AudioButton — plays static mp3 when audio_url is present,
 * falls back to browser speechSynthesis otherwise.
 *
 * Finger-friendly, no layout shift, handles overlapping taps.
 */

import { useState, useEffect } from "react";

interface Props {
  audioUrl: string | null;
  word: string;
  disabled?: boolean;
}

export function AudioButton({ audioUrl, word, disabled = false }: Props) {
  const [status, setStatus] = useState<"idle" | "playing" | "error">("idle");

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      speechSynthesis.cancel();
    };
  }, []);

  const handleClick = () => {
    if (disabled || status === "playing") return;

    if (audioUrl) {
      // Try static mp3 first; fall back to TTS on failure
      playStatic(audioUrl, () => playTTS(word, setStatus), setStatus);
    } else {
      playTTS(word, setStatus);
    }
  };

  const icon = status === "playing" ? "🔊" : status === "error" ? "⚠️" : "🔈";

  return (
    <button
      className="audio-btn"
      onClick={handleClick}
      disabled={disabled || status === "playing"}
      aria-label={audioUrl ? "Play audio" : "Play pronunciation (TTS)"}
      title={audioUrl ? "Play audio" : "Play pronunciation (TTS)"}
    >
      {icon}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Static mp3 playback — singleton to prevent overlap
// ---------------------------------------------------------------------------

let _currentAudio: HTMLAudioElement | null = null;

function playStatic(
  url: string,
  onFallback: () => void,
  setStatus: (s: "idle" | "playing" | "error") => void,
) {
  if (_currentAudio) {
    _currentAudio.pause();
  }
  const audio = new Audio(url);
  _currentAudio = audio;
  setStatus("playing");

  audio.onended = () => setStatus("idle");

  const handleFailure = () => {
    // Fall back to TTS if static audio fails
    onFallback();
  };

  audio.onerror = handleFailure;
  audio.play().catch(handleFailure);
}

// ---------------------------------------------------------------------------
// Browser TTS fallback
// ---------------------------------------------------------------------------

function playTTS(
  word: string,
  setStatus: (s: "idle" | "playing" | "error") => void,
) {
  if (!window.speechSynthesis) {
    setStatus("error");
    setTimeout(() => setStatus("idle"), 2000);
    return;
  }

  speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = "en-US";
  utterance.rate = 0.85; // slightly slower for learners
  setStatus("playing");

  utterance.onend = () => setStatus("idle");
  utterance.onerror = () => {
    setStatus("error");
    setTimeout(() => setStatus("idle"), 2000);
  };

  speechSynthesis.speak(utterance);
}
