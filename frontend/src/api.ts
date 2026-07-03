/**
 * Tiny IPA API client.
 * Base URL can be overridden via VITE_API_BASE environment variable.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const AUTH_CREDENTIALS: RequestCredentials = "include";

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

export function isAuthRequiredError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("AUTH_REQUIRED");
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
// Auth
// ---------------------------------------------------------------------------

export interface CurrentUser {
  id: string;
  username: string;
  is_owner: boolean;
}

export interface AuthState {
  authenticated: boolean;
  user: CurrentUser | null;
}

export async function fetchAuthState(): Promise<AuthState> {
  const res = await fetch(`${API_BASE}/auth/me`, { credentials: AUTH_CREDENTIALS });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function login(username: string, password: string): Promise<AuthState> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function logout(): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
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
  status?: "pending" | "completed";
  last_attempt?: {
    selected_answer: string | null;
    correct_answer: string;
    is_correct: boolean;
  };
  question: {
    type: "choose_ipa" | "choose_word" | string;
    prompt: string;
    display_ipa?: string;
    choices: string[];
  };
  accent_compare?: {
    enabled: boolean;
    primary: {
      accent: "US";
      label: string;
      ipa: string;
    };
    comparison: {
      accent: "UK";
      label: string;
      ipa: string;
      phoneme_tags: string[];
      review_note: string;
    };
  };
}

export interface TodayResponse {
  session_id?: string;
  group_id?: string;
  group_index?: number;
  group_type?: string;
  learner_level?: "entry" | "mid";
  learner_level_label?: string;
  selected_learner_level?: "entry" | "mid";
  selected_learner_level_label?: string;
  pending_level_change?: boolean;
  completed_normal_groups_today?: {
    entry: number;
    mid: number;
    total: number;
  };
  origin?: string;
  source_scope?: string;
  source_group_id?: string;
  focus_phonemes?: string[];
  action_label?: string;
  date: string;
  primary_accent: string;
  daily_word_count: number;
  recent_mistake_count?: number;
  word_count?: number;
  resume_index?: number;
  completed_item_count?: number;
  status: string;
  source_session_item_ids?: string[];
  target_phoneme_options?: {
    phoneme: string;
    symbol: string;
    example_word: string | null;
    candidate_count: number;
  }[];
  items: TodayItem[];
  source_count?: number;
  error?: string;
  detail?: string;
}

export async function fetchToday(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/today`, { credentials: AUTH_CREDENTIALS });
  if (!res.ok) {
    throw new Error(`GET /api/today failed: ${res.status}`);
  }
  return res.json();
}

export async function startNextNormalGroup(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/practice/next-normal`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function abandonCurrentAndStartNext(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/practice/abandon-current-and-next`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function startCurrentGroupReview(
  groupId: string,
): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/review/current-group`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group_id: groupId }),
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function startRecentMistakeReview(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/review/recent-mistakes`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function startMinimalPairPractice(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/practice/minimal-pairs`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function startTargetPhonemePractice(
  phoneme: string,
): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/practice/target-phoneme`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phoneme }),
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function startFocusedPractice(
  focusPhonemes: string[],
): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/practice/focus`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ focus_phonemes: focusPhonemes }),
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}

export async function clearPracticeFocus(): Promise<TodayResponse> {
  const res = await fetch(`${API_BASE}/practice/clear-focus`, {
    method: "POST",
    credentials: AUTH_CREDENTIALS,
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
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

export interface LevelProgressStats {
  learner_level: "entry" | "mid";
  label: string;
  attempts: number;
  correct_attempts: number;
  accuracy: number | null;
  normal_groups: number;
  completed_normal_groups: number;
  completed_normal_groups_today: number;
  resumable_normal_groups: number;
  weak_phonemes: PhonemeStat[];
  strong_phonemes: PhonemeStat[];
}

export interface ProgressResponse {
  today_completed: boolean;
  today_status: string;
  streak_days: number;
  total_attempts: number;
  total_sessions: number;
  total_normal_groups: number;
  resumable_normal_groups: number;
  weak_phonemes: PhonemeStat[];
  strong_phonemes: PhonemeStat[];
  stat_scope?: "global";
  level_stats?: Record<"entry" | "mid", LevelProgressStats>;
}

export async function fetchProgress(): Promise<ProgressResponse> {
  const res = await fetch(`${API_BASE}/progress`, { credentials: AUTH_CREDENTIALS });
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
    credentials: AUTH_CREDENTIALS,
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
  learner_level: "entry" | "mid";
  ui_language: "zh-CN" | "en-US";
  focus_phonemes: string[];
}

export async function fetchSettings(): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`, { credentials: AUTH_CREDENTIALS });
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
    credentials: AUTH_CREDENTIALS,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(await normalizeApiError(res));
  }
  return res.json();
}
