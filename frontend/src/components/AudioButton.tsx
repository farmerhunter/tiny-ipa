/**
 * AudioButton — plays static mp3 when audio_url is present,
 * falls back to browser speechSynthesis otherwise.
 *
 * Finger-friendly, no layout shift, handles overlapping taps.
 * Shows learner-visible audio source and fallback state.
 */

import { useState, useEffect } from "react";

type PlayStatus = "idle" | "playing" | "tts" | "fallback" | "error";

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
    if (disabled || isBusy(status)) return;

    if (audioUrl) {
      // Try static mp3 first; fall back to TTS on failure
      playStatic(
        audioUrl,
        () => playTTS(word, () => setStatus("fallback"), setStatus),
        setStatus,
      );
    } else {
      playTTS(word, () => setStatus("tts"), setStatus);
    }
  };

  const disabled_ = disabled || isBusy(status);

  const icon =
    status === "playing" ? "🔊" :
    status === "fallback" || status === "tts" ? "🔈" :
    status === "error" ? "⚠️" :
    "🔈";

  const sourceLabel = getSourceLabel(audioUrl, status);
  const actionLabel = getActionLabel(audioUrl, status);

  return (
    <span className="audio-btn-wrapper">
      <button
        className="audio-btn"
        onClick={handleClick}
        disabled={disabled_}
        aria-label={actionLabel}
        title={actionLabel}
      >
        {icon}
      </button>
      <span
        className={`audio-source-label ${status === "error" ? "audio-source-label--error" : ""}`}
        aria-live="polite"
      >
        {sourceLabel}
      </span>
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

function isBusy(status: PlayStatus) {
  return status === "playing" || status === "fallback" || status === "tts";
}

function getActionLabel(audioUrl: string | null, status: PlayStatus) {
  if (status === "error") return "Audio unavailable";
  if (audioUrl) {
    return status === "fallback"
      ? "Static audio unavailable; using browser voice"
      : "Play recorded pronunciation";
  }
  return status === "tts" ? "Playing browser voice" : "Play pronunciation with browser voice";
}

function getSourceLabel(audioUrl: string | null, status: PlayStatus) {
  if (status === "error") return "Audio unavailable";
  if (audioUrl) {
    if (status === "playing") return "Playing recorded audio";
    if (status === "fallback") return "Recorded audio unavailable; using browser voice";
    return "Recorded audio";
  }
  return status === "tts" ? "Playing browser voice" : "Browser voice";
}
