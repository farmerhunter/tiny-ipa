/**
 * Tiny IPA API client.
 * Base URL can be overridden via VITE_API_BASE environment variable.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Today practice
// ---------------------------------------------------------------------------

export interface TodayItem {
  session_item_id: string;
  word_id: string;
  display_ipa: string;
  word: string;
  meaning_zh: string | null;
  audio_url: string | null;
  target_phonemes: string[];
  question: {
    type: string;
    prompt: string;
    choices: string[];
  };
}

export interface TodayResponse {
  session_id: string;
  date: string;
  primary_accent: string;
  daily_word_count: number;
  status: string;
  items: TodayItem[];
  error?: string;
  detail?: string;
}

export async function fetchToday(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/today`);
  if (!res.ok) {
    throw new Error(`GET /api/today failed: ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Attempt submission
// ---------------------------------------------------------------------------

export interface UpdatedPhoneme {
  phoneme: string;
  attempt_count: number;
  correct_count: number;
  mastery_status: string;
}

export interface AttemptResponse {
  is_correct: boolean;
  correct_answer: string;
  updated_phonemes: UpdatedPhoneme[];
  next_action: string;
}

export interface AttemptError {
  error: string;
  detail: string;
}

export async function submitAttempt(
  sessionItemId: string,
  selectedAnswer: string,
): Promise<AttemptResponse> {
  const res = await fetch(`${API_BASE}/attempt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_item_id: sessionItemId,
      selected_answer: selectedAnswer,
    }),
  });
  if (!res.ok) {
    const body: AttemptError = await res.json().catch(() => ({
      error: "NETWORK_ERROR",
      detail: `HTTP ${res.status}`,
    }));
    throw body;
  }
  return res.json();
}
