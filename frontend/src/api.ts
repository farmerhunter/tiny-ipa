/**
 * Tiny IPA API client.
 * Base URL can be overridden via VITE_API_BASE environment variable.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

// ---- health ----

export interface HealthResponse {
  status: string;
  content_version: string;
  db_ready: boolean;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}

// ---- today ----

export interface Question {
  type: string;
  prompt: string;
  choices: string[];
}

export interface TodayItem {
  session_item_id: string;
  word_id: string;
  display_ipa: string;
  word: string;
  meaning_zh: string | null;
  audio_url: string | null;
  target_phonemes: string[];
  question: Question;
}

export interface TodayResponse {
  session_id: string;
  date: string;
  primary_accent: string;
  daily_word_count: number;
  status: string;
  items: TodayItem[];
}

export async function fetchToday(params?: {
  daily_word_count?: number;
  primary_accent?: string;
}): Promise<TodayResponse> {
  const searchParams = new URLSearchParams();
  if (params?.daily_word_count) {
    searchParams.set("daily_word_count", String(params.daily_word_count));
  }
  if (params?.primary_accent) {
    searchParams.set("primary_accent", params.primary_accent);
  }
  const qs = searchParams.toString();
  const url = `${API_BASE}/today${qs ? "?" + qs : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load today's practice: ${res.status}`);
  }
  return res.json();
}
