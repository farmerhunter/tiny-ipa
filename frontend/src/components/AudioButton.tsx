/**
 * AudioButton — plays static mp3 when audio_url is present,
 * falls back to browser speechSynthesis otherwise.
 *
 * Finger-friendly, no layout shift, handles overlapping taps.
 * Shows learner-visible audio source and fallback state.
 */

import { useState, useEffect } from "react";
import type { Translator } from "../locales";

type PlayStatus = "idle" | "playing" | "tts" | "fallback" | "error";

interface Props {
  audioUrl: string | null;
  word: string;
  t: Translator;
  disabled?: boolean;
}

export function AudioButton({ audioUrl, word, t, disabled = false }: Props) {
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

  const sourceLabel = getSourceLabel(audioUrl, status, t);
  const actionLabel = getActionLabel(audioUrl, status, t);

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

function getActionLabel(audioUrl: string | null, status: PlayStatus, t: Translator) {
  if (status === "error") return t("audio.status.unavailable");
  if (audioUrl) {
    return status === "fallback"
      ? t("audio.status.fallback")
      : t("audio.action.play_recorded");
  }
  return status === "tts"
    ? t("audio.status.browser_voice.playing")
    : t("audio.action.play_browser_voice");
}

function getSourceLabel(audioUrl: string | null, status: PlayStatus, t: Translator) {
  if (status === "error") return t("audio.status.unavailable");
  if (audioUrl) {
    if (status === "playing") return t("audio.status.recorded.playing");
    if (status === "fallback") return t("audio.status.fallback");
    return t("audio.status.recorded.idle");
  }
  return status === "tts"
    ? t("audio.status.browser_voice.playing")
    : t("audio.status.browser_voice.idle");
}
