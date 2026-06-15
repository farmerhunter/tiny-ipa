/**
 * Tiny IPA API client.
 * Base URL can be overridden via VITE_API_BASE environment variable.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

/**
 * Normalises FastAPI structured errors into a user-friendly string.
 * Handles { detail: string | { error, detail } } and bare string bodies,
 * falling back to `Request failed (HTTP <status>)` on parse failure.
 */
async function normalizeApiError(res: Response): Promise<string> {
  let message = `Request failed (HTTP ${res.status})`;
  try {
    const body = await res.json();
    // FastAPI wraps HTTPException detail at top-level "detail"
    const inner = body.detail ?? body;
    if (typeof inner === "object" && inner !== null) {
      // Prefer {error, detail} shape → "ERROR_CODE: detail"
      const code = inner.error ?? "";
      const text = inner.detail ?? JSON.stringify(inner);
      message = code ? `${code}: ${text}` : String(text);
    } else if (typeof inner === "string") {
      message = inner;
    }
  } catch {
    // Fall through with the default message.
  }
  return message;
}

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

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

export interface PhonemeStat {
  phoneme: string;
  accuracy: number;
  attempt_count: number;
  correct_count: number;
  mastery_status: string;
}

export interface ProgressResponse {
  today_completed: boolean;
  today_status: string;
  streak_days: number;
  total_attempts: number;
  total_sessions: number;
  weak_phonemes: PhonemeStat[];
  strong_phonemes: PhonemeStat[];
}

export async function fetchProgress(): Promise<ProgressResponse> {
  const res = await fetch(`${API_BASE}/progress`);
  if (!res.ok) {
    throw new Error(`GET /api/progress failed: ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Attempt submission
// ---------------------------------------------------------------------------

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
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface SettingsData {
  primary_accent: string;
  daily_word_count: number;
  show_translation: boolean;
  show_accent_compare: boolean;
  practice_mode: string;
  review_strength: string;
  focus_phonemes: string[];
}

export async function fetchSettings(): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) {
    throw new Error(`GET /api/settings failed: ${res.status}`);
  }
  return res.json();
}

export async function saveSettings(
  data: Partial<SettingsData>,
): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}
