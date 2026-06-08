/**
 * AudioButton — plays static mp3 when audio_url is present,
 * falls back to browser speechSynthesis otherwise.
 *
 * Finger-friendly, no layout shift, handles overlapping taps.
 * Shows a visible indicator when TTS fallback is active.
 */

import { useState, useEffect } from "react";

type PlayStatus = "idle" | "playing" | "fallback" | "error";

interface Props {
  audioUrl: string | null;
  word: string;
  disabled?: boolean;
}

export function AudioButton({ audioUrl, word, disabled = false }: Props) {
  const [status, setStatus] = useState<PlayStatus>("idle");

  // Cleanup on unmount — guard for browsers without speechSynthesis
  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const handleClick = () => {
    if (disabled || status === "playing" || status === "fallback") return;

    if (audioUrl) {
      // Try static mp3 first; fall back to TTS on failure
      playStatic(
        audioUrl,
        () => playTTS(word, () => setStatus("fallback"), setStatus),
        setStatus,
      );
    } else {
      playTTS(word, () => setStatus("idle"), setStatus);
    }
  };

  const disabled_ = disabled || status === "playing" || status === "fallback";

  const icon =
    status === "playing" ? "🔊" :
    status === "fallback" ? "🔈" :
    status === "error" ? "⚠️" :
    "🔈";

  const ttsLabel = audioUrl
    ? (status === "fallback" ? "Static audio unavailable — using TTS" : "Play audio")
    : "Play pronunciation (TTS)";

  return (
    <span className="audio-btn-wrapper">
      <button
        className="audio-btn"
        onClick={handleClick}
        disabled={disabled_}
        aria-label={ttsLabel}
        title={ttsLabel}
      >
        {icon}
      </button>
      {status === "fallback" && (
        <span className="audio-fallback-badge" aria-live="polite">TTS</span>
      )}
      {status === "error" && (
        <span className="audio-error-badge" aria-live="polite">!</span>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Static mp3 playback — singleton to prevent overlap
// ---------------------------------------------------------------------------

let _currentAudio: HTMLAudioElement | null = null;

function playStatic(
  url: string,
  onFallback: () => void,
  setStatus: (s: PlayStatus) => void,
) {
  if (_currentAudio) {
    _currentAudio.pause();
  }
  const audio = new Audio(url);
  _currentAudio = audio;
  setStatus("playing");

  audio.onended = () => setStatus("idle");

  const handleFailure = () => {
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
  onStart: () => void,
  setStatus: (s: PlayStatus) => void,
) {
  if (!window.speechSynthesis) {
    setStatus("error");
    setTimeout(() => setStatus("idle"), 2000);
    return;
  }

  speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = "en-US";
  utterance.rate = 0.85;

  onStart(); // signal fallback mode to UI

  utterance.onend = () => setStatus("idle");
  utterance.onerror = () => {
    setStatus("error");
    setTimeout(() => setStatus("idle"), 2000);
  };

  speechSynthesis.speak(utterance);
}
