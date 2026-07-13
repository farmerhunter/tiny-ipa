# 数据模型与 API 合同

## 源内容与运行时数据库

Tiny IPA 有两类数据：

```text
Source Content
  人工可读、可版本管理、可重新导入

Runtime Data
  SQLite 中的 session、attempt、stats、settings
```

源内容是事实来源。SQLite 可以删除重建，但用户学习记录需要备份。

## Deployment Prerequisite Roadmap Boundary

M11, M12, and M13 are deployment prerequisites before M14 VPS work:

```text
M11 Localization and Configurable UI Language (#209)
M12 Minimal Auth and Multi-user Data Isolation (#210)
M13 Expand Practice Modes: Choose Word and Type Word (#256)
```

Localization is a UI/runtime contract. It should make learner-facing copy
configurable without changing IPA/content/grading semantics. Auth is a runtime
identity contract. It should make existing `user_id` fields meaningful before
the app is exposed through VPS deployment. Practice modes are a practice-runtime
contract. They should keep question mode, grading, distractor quality, and
mode-specific UI behavior testable before deployment smoke and restore checks.

M14 deployment and backup (#27) is now decomposed. #276 owns the deployment
target/runtime config contract. Later M14 work must not mutate real VPS, DNS,
TLS, secrets, deployment config, or private SQLite data without an explicit
Human gate.

These Epics must preserve the existing content boundary:

```text
global source/runtime content:
  words
  phonemes
  static audio assets
  source reports

per-user runtime learning data:
  settings
  daily_sessions
  session ownership
  attempts
  phoneme_stats
  review/focus state
```

The old `default` user is a migration concern. Any real migration of existing
SQLite data requires backup guidance, dry-run evidence, and explicit Human
approval before mutating real/private data.

## 源词条字段

推荐源内容字段：

```json
{
  "word_id": "ship",
  "word": "ship",
  "level": "beginner",
  "ipa_us": "/ʃɪp/",
  "ipa_uk": "/ʃɪp/",
  "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
  "phoneme_tags_uk": ["/ʃ/", "/ɪ/", "/p/"],
  "meaning_zh": "船；大船",
  "example": "A ship is on the sea.",
  "difficulty_tags": ["sh", "short_i"],
  "minimal_pair_group": "ship_sheep",
  "frequency_zipf": 4.5,
  "candidate_score": 82.4,
  "audio_us": "/audio/us/ship.mp3",
  "audio_uk": null,
  "source_ipa_us": "open-dict-data/ipa-dict en_US",
  "source_ipa_uk": "open-dict-data/ipa-dict en_UK",
  "source_frequency": "wordfreq",
  "license_notes": "see content report",
  "content_status": "core_selected",
  "review_status_us": "auto_checked",
  "review_status_uk": "auto_checked"
}
```

## SQLite 表

MVP 到 Epic M2 建议：

```sql
words(
  id TEXT PRIMARY KEY,
  word TEXT NOT NULL,
  level TEXT NOT NULL,
  ipa_us TEXT NOT NULL,
  ipa_uk TEXT,
  phoneme_tags_us TEXT NOT NULL,
  phoneme_tags_uk TEXT,
  meaning_zh TEXT,
  audio_us TEXT,
  audio_uk TEXT,
  difficulty_tags TEXT,
  minimal_pair_group TEXT,
  content_status TEXT NOT NULL
)

phonemes(
  id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  accent_scope TEXT NOT NULL,
  category TEXT NOT NULL,
  example_word TEXT,
  priority INTEGER NOT NULL,
  description_zh TEXT
)

users(
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  is_owner INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

auth_sessions(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
)

settings(
  user_id TEXT PRIMARY KEY,
  primary_accent TEXT NOT NULL,
  daily_word_count INTEGER NOT NULL,
  show_translation INTEGER NOT NULL,
  show_accent_compare INTEGER NOT NULL,
  practice_mode TEXT NOT NULL,
  review_strength TEXT NOT NULL,
  learner_level TEXT NOT NULL DEFAULT 'entry',
  ui_language TEXT NOT NULL DEFAULT 'zh-CN',
  focus_phonemes TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL
)

daily_sessions(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_date TEXT NOT NULL,
  primary_accent TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  group_index INTEGER NOT NULL DEFAULT 1,
  group_type TEXT NOT NULL DEFAULT 'normal',
  learner_level TEXT NOT NULL DEFAULT 'entry',
  source_session_item_ids TEXT NOT NULL DEFAULT '[]'
)

session_items(
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  word_id TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  target_phonemes TEXT NOT NULL,
  question_type TEXT NOT NULL,
  status TEXT NOT NULL
)

attempts(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_item_id TEXT NOT NULL,
  word_id TEXT NOT NULL,
  primary_accent TEXT NOT NULL,
  question_type TEXT NOT NULL,
  target_phoneme TEXT,
  selected_answer TEXT,
  correct_answer TEXT NOT NULL,
  is_correct INTEGER NOT NULL,
  created_at TEXT NOT NULL
)

phoneme_stats(
  user_id TEXT NOT NULL,
  primary_accent TEXT NOT NULL,
  phoneme_id TEXT NOT NULL,
  attempt_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  last_attempt_at TEXT,
  last_wrong_at TEXT,
  mastery_status TEXT NOT NULL,
  PRIMARY KEY(user_id, primary_accent, phoneme_id)
)
```

`primary_accent` 必须进入 session、attempt 和 stats，否则未来 UK 对照会污染 US 统计。

## API 合同

### Current user and auth boundary

M12 treats auth as a personal-VPS data-isolation boundary, not as broad account
management. The deployment target is a private Tiny IPA instance reached through
an HTTPS reverse proxy by a small known learner set. The contract must protect
runtime learning data from cross-user reads/writes, avoid silent fallback to the
old `default` user in deployed mode, and keep local development simple enough to
run without OAuth or an external identity provider.

Explicit non-goals for M12:

```text
OAuth or social login
email verification or password reset
family dashboard, billing, analytics, or broad admin/account UX
provider-specific VPS, DNS, reverse-proxy, or backup automation
real/private SQLite migration without Human-gated dry-run evidence
```

Runtime endpoints that read or mutate learner data must resolve the current
user before touching user-scoped tables. The deployed runtime current-user
source is the authenticated session cookie. The local-dev current-user source
may be an explicit documented dev user only when dev mode is enabled.

Resolution order:

```text
1. Parse and validate the server-side session cookie.
2. Resolve the session to an active user record.
3. Set current_user.id for the request.
4. Reject learner-data requests with AUTH_REQUIRED when no current user exists.
```

Production learner-data endpoints cannot silently use `default`. The only
allowed `default` behavior is an explicit local-dev bootstrap path that is
disabled or fail-closed in deployed mode. Any endpoint that detects a missing
current user after auth middleware must return a structured error such as:

```json
{
  "error": "AUTH_REQUIRED",
  "detail": "Sign in required."
}
```

#### Session, cookie, secret, CORS, and CSRF policy

M12 implementation issues should use a server-side opaque session identifier in
an `HttpOnly` cookie. Session identity must not be stored in frontend
`localStorage` or sent as a long-lived bearer token by the SPA.

Required deployed cookie/secret behavior:

```text
HttpOnly cookie
Secure cookie when served over HTTPS
SameSite=Lax or stricter unless a later explicit cross-site flow requires more
Path=/
bounded session lifetime
logout invalidates the server-side session and clears the cookie
login rotates or replaces any existing session id
deployed session secret is required and must not have an insecure built-in default
local-dev secret/bootstrap behavior is documented and visibly non-production
```

The #239 bootstrap foundation provides a CLI setup path without enabling route
behavior:

```bash
cd backend
python scripts/bootstrap_auth.py --db-url /path/to/tiny_ipa.sqlite owner \
  --username owner --password 'change-me-long-password'

python scripts/bootstrap_auth.py --db-url /tmp/tiny_ipa_dev.sqlite dev-user \
  --enable-local-dev --environment development \
  --username local-dev --password 'local-dev-password'
```

Owner bootstrap creates the first owner and fails closed if an owner already
exists. Local dev bootstrap is explicit, creates a normal user instead of an
auth bypass, and refuses `production`, `prod`, `deployed`, or `deploy`
environments. Password hashes use Argon2 via `argon2-cffi`; auth session rows
store a hash of the opaque session token, not the raw token.

Same-origin SPA/API deployment is the default. If a split origin is introduced,
the CORS allowlist must be exact and credentials-aware; wildcard origins are not
allowed with cookies. Unsafe requests such as `POST`, `PUT`, `PATCH`, and
`DELETE` must pass an Origin/Referer check against the configured app origin.
SameSite cookies plus Origin validation are the minimum CSRF boundary for M12;
if future cross-site credentialed requests are needed, a CSRF token contract must
be added before release.

#### User-scoped and global data matrix

```text
Data / behavior                         Scope
settings                                user-scoped by user_id
daily_sessions                          user-scoped by user_id
session_items                           scoped through owning daily_session
attempts                                user-scoped by user_id and session item ownership
phoneme_stats                           user-scoped by user_id + accent + phoneme
review/focus state                      user-scoped through settings/sessions/attempts
progress summaries                      user-scoped aggregation over attempts/stats/sessions
auth sessions                           user-scoped session records
owner/admin bootstrap record            global setup state, not broad admin UX
words                                   global shared source/runtime content
phonemes                                global shared source/runtime content
static audio assets                     global shared source/runtime content
source reports and curation artifacts   global versioned artifacts
health/content readiness                global and must not expose learner data
```

Shared content may remain global, but content reads must not leak another user's
runtime attempts, settings, sessions, review/focus state, or stats.

#### Endpoint auth-required matrix

```text
GET /api/health                                  no learner auth; no user data
POST /api/auth/login                             no prior auth; creates/rotates session
POST /api/auth/logout                            clears session; idempotent if already anonymous
GET /api/auth/me                                 no prior auth; reports anonymous or current user
GET /api/today                                   auth required
POST /api/practice/next-normal                   auth required
POST /api/practice/abandon-current-and-next      auth required
POST /api/practice/focus                         auth required
POST /api/practice/clear-focus                   auth required
POST /api/review/current-group                   auth required
POST /api/review/recent-mistakes                 auth required
POST /api/attempt                                auth required
GET /api/progress                                auth required
GET /api/settings                                auth required
PUT /api/settings                                auth required
```

Auth failures must use stable structured errors, preferably `AUTH_REQUIRED` for
anonymous requests and `CURRENT_USER_MISSING` only for internal invariant
failures after auth middleware has already run. User-scoped endpoints must never
return another user's rows; test failures for that class should use or assert
`USER_DATA_SCOPE_VIOLATION` where an explicit guard detects it.

Runtime endpoints that must resolve current user:

```text
GET /api/today
POST /api/practice/next-normal
POST /api/practice/abandon-current-and-next
POST /api/practice/focus
POST /api/practice/clear-focus
POST /api/review/current-group
POST /api/review/recent-mistakes
POST /api/attempt
GET /api/progress
GET/PUT /api/settings
```

#### Default-data owner-claim and migration gate

Existing rows for the old `default` user are not automatically owned by the
first authenticated user. Any real/private SQLite owner claim or migration is
Human-gated and must start with a dry-run report.

The dry-run must report:

```text
database path and backup guidance
whether a backup exists or the command to create one
target owner user id
tables and row counts currently owned by default
conflicts with existing target-user rows
rows that would be updated, skipped, or left global
irreversible or manual-review risks
exact apply command, if an apply mode is later accepted
```

Apply mode, if introduced by a later issue, must require an explicit flag and
must not run against a real/private DB without backup evidence and explicit
Human approval. Source content imports remain global and are not part of the
owner-claim mutation.

#### M12 child issue test matrix

```text
#239 User model, session storage, owner bootstrap
  - user table/session storage schema tests
  - owner bootstrap creates exactly one personal owner path
  - deployed mode fails closed without a configured session secret
  - dev bootstrap path is explicit and marked non-production

#240 Auth endpoints and current-user dependency
  - login success/failure, logout invalidation, session rotation
  - /api/auth/me anonymous and authenticated responses
  - learner-data endpoints return AUTH_REQUIRED when anonymous
  - current-user dependency never falls back to default in deployed mode

#241 User data isolation across runtime endpoints
  - two users cannot read/write each other's settings
  - Today normal/review/focus sessions are scoped by user
  - attempts and phoneme_stats aggregate only current user's rows
  - progress summaries and unfinished-practice callouts are user-scoped

#242 Default-user owner claim dry-run
  - dry-run reports default row counts by table and backup guidance
  - dry-run detects target-user conflicts and does not mutate DB
  - apply mode, if added, is explicit and refuses missing backup evidence
  - source content tables remain global and are not owner-claimed

#243 Localized login/logout/current-user frontend UX
  - unauthenticated learner sees localized auth gate before protected practice data
  - login/logout/current-user states use M11 locale resources
  - authenticated UI does not render raw backend auth errors
  - no auth UI changes IPA/content/grading semantics

#244 M12 isolation/readiness review
  - full backend auth/isolation regression suite passes
  - real-backend browser walkthrough covers login, practice, logout, re-login isolation
  - cookie flags, Origin/CSRF checks, and CORS allowlist behavior are evidenced
  - default-data dry-run evidence is linked for any existing private DB

#27 / M14 VPS deployment prerequisite evidence
  - M12 readiness comment links auth/session/cookie/origin evidence
  - user-isolation tests and real-backend walkthrough evidence are accepted
  - M13 practice-mode readiness evidence is accepted
  - backup and owner-claim dry-run guidance exists before deployment release
  - #276 deployment target/runtime config contract is accepted before #277-#281
  - local dev remains runnable without VPS-specific assumptions
```

Normal practice responses from `GET /api/today` and
`POST /api/practice/next-normal` expose backend-authoritative resume metadata:

```json
{
  "resume_index": 2,
  "completed_item_count": 2,
  "items": [
    {
      "status": "completed",
      "last_attempt": {
        "selected_answer": "/ʃɪp/",
        "correct_answer": "/ʃɪp/",
        "is_correct": true
      }
    },
    {
      "status": "pending"
    }
  ]
}
```

`resume_index` is zero-based and points at the first pending item. The frontend
must treat it as authoritative when resuming a normal group, so answered items
are not presented as unanswered.

Shared content reads may remain global, but must not leak another user's
runtime attempts, settings, sessions, or stats.

### Health

```http
GET /api/health
```

返回：

```json
{
  "status": "ok",
  "content_version": "2026-06-06-core100",
  "db_ready": true
}
```

## M7 v2 learner workflow contract

M7 v2 defines the practice loop from the learner's point of view before adding
more endpoints or UI buttons. The app should make the next action obvious:

```text
Start normal group
-> answer all items
-> read current group result
-> choose next normal group, review current misses, review recent mistakes,
   choose focus, or stop
```

The learner goal is to complete multiple short groups in one sitting, use wrong
answers immediately, and optionally focus a weak sound without typing raw IPA.
The backend may still use `session_items`, `attempts`, and `phoneme_stats` as
the source of truth; the UI and API must expose enough group metadata to explain
why the learner is seeing a group.

### User-facing states

| State | Meaning | Primary visible actions |
| --- | --- | --- |
| Entry/home | No active card is being answered. The app can resume an active group or start today's first normal group. | Start/resume practice, Progress, Settings |
| Active normal group | Learner is answering a standard 10-word group. | Answer item, listen/replay where available |
| Group completed | All items in the current group are answered. Current-group results remain visible while follow-up actions run. | Start next 10-word group, review misses from this group, review recent mistakes, choose focus, stop |
| Current-group review | Learner is reviewing words missed in the just-finished group. | Answer review items, return to summary when done |
| Recent-mistake review | Learner is reviewing recent missed words across earlier groups. | Answer review items, handle empty queue |
| Choose focus | Learner selects a weak phoneme from Progress or another guided list. | Start focused group, clear focus, return |
| Focused group | Learner practices words weighted toward selected phoneme(s). | Answer items, clear focus after completion |
| Stopped/returning | Learner intentionally leaves practice. Returning should resume an active group or show a clear start action. | Resume group, start next group, Progress |
| Empty review | No reviewable mistakes exist for the selected review scope. | Return to summary, start next group |
| Error/retry | A backend or network action failed. The previous meaningful state stays visible. | Retry action, return, start next group if safe |

### Action semantics

| Action | Scope | Required behavior | Copy obligation |
| --- | --- | --- | --- |
| Start/resume practice | Active normal group or first normal group for today | Resume an unfinished normal group; otherwise create the first normal group. | Say whether the learner is resuming or starting. |
| Start next 10-word group | Next normal group after a completed normal group | Create the next normal group if no active normal group exists; if one exists, resume it and say so. | Do not label this only as `Continue`; name it as next group/resume. |
| Review misses from this group | Current completed group | Create a review group from the current group's wrong answers only. Empty state is non-error. | Label as current-group review, not global review. |
| Review recent mistakes | Global recent history | Create a review group from recent wrong attempts across groups. Empty state is non-error. | Label as recent mistakes and keep it distinct from current-group misses. |
| Focus weak phoneme | Selected phoneme(s) | Store or pass the selected focus and offer focused practice. M7 v2 primary behavior is to start a dedicated focused group from this action. | Explain which phoneme is selected and that the next group focuses on it. |
| Start focused group | Selected focus | Create or resume a `weak_focus` group using scheduler focus weighting. | Name the group as focused and show focus chips. |
| Clear focus | Current selected focus | Remove selected focus and return future practice to normal weighting. | Make return to normal practice explicit. |
| Stop | Current known state | Leave practice without losing a resumable active group. | Prefer `Back to Progress` or `Return home` over generic `Stop` when possible. |
| Settings | User preferences | Keep raw IPA focus input out of the primary learner path; if retained, mark it advanced/debug. | Words count is `words per group`, not words per day. |

### State transition table

| Current UI state | Domain state | User action | Command/query | Next domain state | Next UI state | User-facing copy | Failure/empty state |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Entry/home | No active group | Start practice | `POST /api/practice/next-normal` | Active normal group | Active normal group | `Start Entry group` / `Start Mid group` | Show setup/import error with retry |
| Entry/home | Active normal group exists | Resume practice | `GET /api/today` | Same active normal group | Active normal group | `Resume Group N` | Keep entry/home actions visible |
| Active normal group | Pending items remain | Submit answer | `POST /api/attempt` | Attempt recorded; next item pending | Active normal group | Feedback on current answer | Keep item visible with retry |
| Active normal group | Last item answered | Submit answer | `POST /api/attempt` | Group completed | Group completed | Score, current misses, target sounds, next choices | Keep summary if follow-up load fails |
| Group completed | Completed normal group with misses | Review this group | #136 current-group review action | Review group sourced from current group | Current-group review | `Review misses from Group N` | `No misses in this group` |
| Group completed | Completed normal group | Review recent mistakes | `POST /api/review/recent-mistakes` or #136 replacement | Recent-mistake review group | Recent-mistake review | `Review recent mistakes` | `No recent mistakes ready` |
| Group completed | Completed normal group | Start next group | #136 next-normal action | Next normal group or resumed intended active group | Active normal group | `Start Group N+1` or `Resume Group N+1` | Keep completion summary with retry |
| Group completed or Progress | Weak phoneme selected | Start focused practice | #136 focus action | Active `weak_focus` group | Focused group | `Focused group: /.../` | Keep focus choice visible with retry |
| Focused group completed | Focus remains selected | Clear focus | #136 clear-focus action or settings update | No active focus | Group completed or Progress | `Back to normal practice` | Show clear failure without losing summary |
| Any review/focused group | Learner leaves practice | Stop/return | UI navigation only | Active group may remain resumable | Progress or home | `Return to Progress` / `Resume later` | N/A |
| Any action state | Request fails | Retry | Same command/query | Prior domain state preserved | Prior meaningful UI state | Inline failure near action | Do not replace summary with generic unavailable state |

### Walkthrough scenarios for M7 v2

#135 must automate these scenarios with Playwright in a mobile viewport:

1. Start a normal group, answer all items, and reach a completion summary that
   names the group, score, current misses, and next actions.
2. Start the next normal group from the summary and verify the UI shows a new or
   explicitly resumed intended group, not an ambiguous repeat.
3. Miss at least one answer, choose current-group review, and verify the review
   items come from that completed group.
4. Choose recent-mistake review and verify it is labeled separately from
   current-group review, including the empty state.
5. Select a weak phoneme without raw IPA typing, start a focused group, verify
   focus visibility, then clear focus and return to normal practice.
6. Trigger a follow-up action failure in a controlled fixture and verify the
   completion summary remains visible with an inline retry/error message.

The final M7 v2 readiness review (#139) must prove these walkthroughs pass
against the M7 v2 integration branch, not only route-mocked fixtures.

### Today

```http
GET /api/today
```

查询 Today hub 状态，不创建新的普通练习组。M7 起，Tiny IPA 将“每日练习”
收窄为“当天可重复创建的 practice group”，group creation 必须来自显式
user command：

- active group response 中，`session_id` 仍是 attempt 提交使用的持久 session id；
- active group response 中，`group_id` 是 `session_id` 的语义别名，供 UI 用
  group 语言表达；
- active group response 中，`group_index` 是同一
  `user_id`/`date`/`primary_accent` 下的递增序号；
- `group_type` 当前实现 `normal`、`mistake_review` 和 `weak_focus`，均复用
  同一 session_items/attempts/phoneme_stats 路径；
- `learner_level` 和 `learner_level_label` 记录创建该 group 时使用的
  learner-facing level，active group 恢复时不随 settings 切换而改写；
- `selected_learner_level` 和 `selected_learner_level_label` 记录 Settings
  当前选择，用于 Today hub 说明“已选择的未来练习 level”；
- `pending_level_change` 在 active normal group 的 level 与 Settings level
  不一致时为 true；
- `completed_normal_groups_today` 按 Entry/Mid/total 统计当天已完成的 normal
  practice group，不包含 review/focus group；
- `origin` 说明 action reason，例如 `normal_empty`、`normal_resume`、
  `normal_next`、`normal_abandon_next`、`current_group_review_start`、
  `recent_review_start`、`focus_start`、`focus_clear`；
- `source_scope` 说明数据来源范围，例如 `normal_none`、`normal_current`、
  `normal_next`、`current_group`、`recent_global`、`focus_selection`；
- `source_group_id` 仅 current-group review 使用，指向被复习的 source group；
- `focus_phonemes` 在 focus 影响选词或清除 focus 时返回；
- `action_label` 是后端状态驱动的短文案提示，前端可按产品语气改写；
- `daily_word_count` 保留为兼容字段，M7 UI 文案应理解为 words per group；
- `word_count` 是本响应实际返回的 item 数；
- `source_session_item_ids` 仅 review group 使用，用于追踪错题来源。

重复调用 `GET /api/today` 时，如果存在当天同 accent 的 `normal`
`in_progress` group，则恢复它；如果没有 active normal group，则返回
`status = "idle"`、`origin = "normal_empty"`、`source_scope = "normal_none"`、
`items = []` 的 hub response，不写入 `daily_sessions`。不同 group 共用
`session_items`、`attempts` 和 `phoneme_stats`，不引入第二套判题或统计来源。

No-active hub response 示例：

```json
{
  "group_type": "normal",
  "learner_level": "entry",
  "learner_level_label": "Entry",
  "selected_learner_level": "entry",
  "selected_learner_level_label": "Entry",
  "pending_level_change": false,
  "completed_normal_groups_today": {"entry": 0, "mid": 0, "total": 0},
  "date": "2026-06-06",
  "primary_accent": "US",
  "origin": "normal_empty",
  "source_scope": "normal_none",
  "action_label": "Start Entry group",
  "daily_word_count": 10,
  "word_count": 0,
  "status": "idle",
  "source_session_item_ids": [],
  "items": []
}
```

Active group response 返回领域摘要，不返回原始调度内部状态：

```json
{
  "session_id": "2026-06-06-default-g001-normal",
  "group_id": "2026-06-06-default-g001-normal",
  "group_index": 1,
  "group_type": "normal",
  "learner_level": "entry",
  "learner_level_label": "Entry",
  "selected_learner_level": "entry",
  "selected_learner_level_label": "Entry",
  "pending_level_change": false,
  "completed_normal_groups_today": {"entry": 0, "mid": 0, "total": 0},
  "date": "2026-06-06",
  "primary_accent": "US",
  "origin": "normal_next",
  "source_scope": "normal_current",
  "action_label": "Start Entry Group 1",
  "daily_word_count": 10,
  "word_count": 10,
  "status": "in_progress",
  "source_session_item_ids": [],
  "items": [
    {
      "session_item_id": "item_001",
      "word_id": "ship",
      "display_ipa": "/ʃɪp/",
      "word": "ship",
      "meaning_zh": "船；大船",
      "audio_url": "/audio/us/ship.mp3",
      "target_phonemes": ["/ʃ/", "/ɪ/"],
      "question": {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": ["/ʃɪp/", "/ʃiːp/", "/sɪp/"]
      }
    }
  ]
}
```

推荐服务端判题，不在生产响应中返回 `answer`。

## M13 practice question contract

M13 expands practice question modes without changing the authoritative
session/attempt/statistics path. `choose_ipa` remains the compatibility
baseline. `choose_word` is the first reverse-recognition expansion. `type_word`
is deferred until accepted-answer and same-IPA ambiguity semantics are accepted.

The backend is authoritative for question generation and grading. The frontend
renders the discriminated `question` payload, submits `selected_answer` to
`POST /api/attempt`, and never decides correctness from local prompt text.
`phoneme_stats` continuity is preserved across supported modes: attempts update
stats from the session item's persisted `target_phonemes`, not from the
frontend-visible answer string.

### Question mode taxonomy

| `question.type` | Prompt surface | Choice/input surface | Correct-answer representation | Launch status |
| --- | --- | --- | --- | --- |
| `choose_ipa` | Show `word`, optional `meaning_zh`, audio, and target copy. | Multiple IPA choices. | IPA string for the active accent, e.g. `word.ipa_us` for US sessions. | Existing compatibility baseline. |
| `choose_word` | Show IPA for the active accent plus question-specific prompt copy. | Multiple word choices. | Canonical `word.word` string for the target row. | First M13 implementation slice after this contract is accepted. |
| `type_word` | Show IPA for the active accent plus typed-answer instructions. | Text input. | Accepted-answer set, not a single frontend string. | Deferred; not production-visible until same-IPA/homophone policy is implemented. |

`choose_ipa` payload remains backward-compatible:

```json
{
  "type": "choose_ipa",
  "prompt": "Which IPA matches this word?",
  "choices": ["/ʃɪp/", "/ʃiːp/", "/sɪp/"]
}
```

`choose_word` uses the same multiple-choice renderer boundary but reverses the
prompt and answers:

```json
{
  "type": "choose_word",
  "prompt": "Which word matches this IPA?",
  "display_ipa": "/ʃɪp/",
  "choices": ["ship", "sheep", "sip", "chip"]
}
```

For `choose_word`, choices are learner-facing word strings, but grading still
looks up the persisted `session_item_id`, `question_type`, word row, and active
accent server-side. The client-submitted `selected_answer` is an answer token,
not proof of correctness.

`type_word` must not share the `choose_word` grading path until it has an
accepted-answer contract:

```json
{
  "type": "type_word",
  "prompt": "Type the word that matches this IPA.",
  "display_ipa": "/ˈnju/",
  "input": {"kind": "text", "autocapitalize": "none"}
}
```

### `/api/attempt` grading boundary

`POST /api/attempt` remains the only production grading endpoint for practice
answers. The request shape stays stable:

```json
{
  "session_item_id": "item_001",
  "selected_answer": "ship"
}
```

Server grading dispatches by persisted `session_items.question_type`:

```text
choose_ipa   -> compare selected IPA token with active-accent IPA
choose_word  -> compare selected word token with target word row
type_word    -> deferred; compare normalized input against accepted answers
```

The response continues to return `is_correct`, `correct_answer`, and
`updated_phonemes`. `correct_answer` is the server-side canonical answer for
feedback, not a value trusted from the client. Unsupported `question_type`
values fail closed with `INVALID_ATTEMPT` or an equivalent stable structured
attempt error; they must not silently grade as `choose_ipa`.

### Same-IPA and homophone policy

`choose_word` distractors should avoid exact same active-accent IPA unless the
question explicitly supports multiple correct answers. This keeps a learner
from seeing two visually different words that are both correct for the same
displayed IPA.

`type_word` remains gated for production until accepted answers are generated
and persisted by the backend. The first safe implementation path is not
"compare the typed string with `word.word`"; it is "compare the normalized typed
string with a server-side accepted-answer snapshot for the session item."

Current content already has same-IPA and spelling-variant ambiguity. A
2026-07-03 probe over `content/core_300_words.json` and
`content/core_1000_words.json` found:

| Scope | US exact same-IPA groups | UK exact same-IPA groups | Examples |
| --- | ---: | ---: | --- |
| Same learner level | 11 | 7 | `knew` / `new`, `buy` / `bye`, `see` / `sea`, `ads` / `adds`, `color` / `colour`, `favor` / `favour`, `honor` / `honour`, `labor` / `labour` |
| Cross learner level | 3 | 2 | Entry `sun` / Mid `son`, Entry `new` / Mid `new`, Entry `feb` / `february` / Mid `february` |

Legacy ambiguity examples include `new` / `knew`, `sun` / `son`, and `see` /
`sea`. The spelling variant policy must be explicit before `type_word` can move
from contract fixture to learner-facing runtime.

Because learners may type a valid homophone or spelling variant that is not the
target row, a future `type_word` implementation must add explicit accepted
answers before exposure. The accepted-answer snapshot must be created
server-side when the session item is created or first materialized, and it must
be stable for grading and feedback even if content files change later.

Minimal safe `type_word` contract for a follow-up implementation:

```text
accepted_answers source:
  - canonical target word
  - all enabled runtime words sharing the active-accent IPA
  - explicit spelling variants or aliases if a future curation file adds them
  - no frontend-provided answers

accepted_answers storage:
  - persisted session-item answer metadata or persisted question payload
  - response may expose display-safe accepted answer labels only after grading
  - /api/attempt must grade against the persisted snapshot

normalization rules:
  - Unicode NFKC normalization
  - trim leading/trailing whitespace
  - collapse repeated internal whitespace
  - case-insensitive comparison
  - normalize curly apostrophes to ASCII apostrophe
  - strip surrounding sentence punctuation such as ., ,, !, ?
  - hyphen/space variants and omitted apostrophes are accepted only when an
    explicit accepted-answer entry or generated alias exists
  - no fuzzy typo matching in the MVP

same-IPA behavior:
  - if typed answer matches any accepted answer, mark correct
  - if it matches an accepted alternate, feedback says the typed answer is also
    accepted for this IPA and shows the target word separately
  - if same-IPA accepted answers are unavailable, exclude that row from
    type_word candidate generation rather than marking homophones wrong

feedback copy:
  - exact target: "Correct."
  - accepted alternate: "Accepted: {typedAnswer} also matches this IPA. Target
    word: {targetWord}."
  - incorrect: "Not quite. You typed {typedAnswer}. Accepted answer:
    {targetWord}."
  - ambiguous unavailable: "This IPA has multiple valid spellings, so this item
    is not used for typed-answer practice yet."
  - partial mismatch: no "almost" or edit-distance hint until a later contract
    defines typo tolerance

launch recommendation:
  - no production type_word exposure in the current M13 MVP
  - safe follow-up may implement normal-only type_word behind an explicit
    challenge-mode selector after accepted-answer metadata, row exclusion, and
    feedback copy tests are accepted
  - review, focus, and specialty groups stay non-typed until separate
    walkthrough evidence accepts those flows
```

Until then, `type_word` may appear only in docs/test fixtures that assert it is
deferred or fail-closed; it must not be exposed as a learner-selectable runtime
mode.

### Review and focus behavior for the first M13 slice

The first implementation slice should keep review/focus behavior conservative:

```text
normal groups      -> may use selected supported question mode once implemented
mistake_review     -> stays choose_ipa until choose_word review semantics are accepted
weak_focus         -> stays choose_ipa until choose_word focus semantics are accepted
minimal/sound compare -> unchanged specialty behavior
```

This avoids mixing reverse-recognition distractor quality questions into
current-group review, recent-mistake review, and weak-focus recovery before
normal `choose_word` has backend/frontend evidence. If a later child issue wants
review/focus to inherit the selected question mode, it must update this contract
and provide route-mocked plus real-backend walkthrough evidence.

### API and frontend renderer boundary

The API shape is a discriminated question payload keyed by `question.type`.
Shared item fields remain outside the question object:

```text
TodayItem.word
TodayItem.display_ipa
TodayItem.meaning_zh
TodayItem.audio_url
TodayItem.target_phonemes
TodayItem.question
```

Frontend rendering should branch on `question.type`, not infer mode from prompt
strings. `choose_ipa` and `choose_word` may share a generic multiple-choice
renderer only if labels, accessible names, feedback copy, and selected-answer
tokens stay mode-aware. `type_word` requires a separate text-input renderer and
must stay hidden until accepted-answer semantics are complete.

Normal practice responses expose mode metadata so the UI can distinguish the
current active group from the setting for the next new group:

```json
{
  "practice_mode": "ipa_first",
  "selected_practice_mode": "choose_word",
  "pending_practice_mode_change": true
}
```

`practice_mode` is the active group mode, derived from persisted session item
`question_type` when a group exists. `selected_practice_mode` is the current
Settings value for the next new normal group. Review, focus, and specialty
groups stay `ipa_first` for the first M13 slice even when
`selected_practice_mode` is `choose_word`.

Question-specific localization must use dedicated prompt/feedback keys, for
example:

```text
practice.question.prompt.choose_ipa
practice.question.prompt.choose_word
practice.question.prompt.type_word
practice.feedback.correct_answer.ipa
practice.feedback.correct_answer.word
```

Mobile text-fit expectations:

- prompt copy must fit within the practice card without relying on raw enum
  values;
- choice buttons may contain IPA or word strings, but labels must not overflow
  the mobile viewport;
- feedback must name what the learner selected and what the server accepted in
  mode-specific terms;
- unresolved localization placeholders are blocker failures for M13 UI work.

### M13 test matrix

Later M13 child issues should reuse this matrix instead of redefining question
semantics:

| Issue | Required evidence |
| --- | --- |
| #261 backend choose-word generation/grading | Unit/integration tests for `choose_ipa` compatibility, `choose_word` payload generation, `/api/attempt` grading dispatch, fail-closed unknown `question_type`, and `phoneme_stats` updates from `target_phonemes`. |
| #260 distractor scorer/report | Deterministic scorer tests and quality report evidence that `choose_word` distractors avoid exact same active-accent IPA unless a future multi-answer policy exists. |
| #259 frontend generic renderer | Component/E2E tests for discriminated rendering, accessible choice labels, localized prompt/feedback copy, mobile text fit, and no `type_word` production exposure. |
| #262 mode selection workflow | Route-mocked and real-backend walkthroughs for normal `choose_word` entry, active group resume, Settings/Today/Progress copy, review/focus remaining `choose_ipa`, and stats continuity. |
| #264 type-word accepted-answer contract | Contract-only evidence for accepted answers, normalization, homophones, spelling variants, fail-closed unsupported runtime exposure, and future walkthrough criteria. |
| #263 readiness review | User-facing summary, residual distractor/type-word risks, route-mocked and real-backend evidence, and final human-gated main integration decision. |

### Next normal group

```http
POST /api/practice/next-normal
```

显式从 Today hub 或完成摘要进入第一个/下一个 normal group。若当天已经有
active normal group，返回该 group 并标记 `origin = "normal_resume"`；
否则按 Settings 当前 `learner_level` 创建递增 `group_index` 的 normal group，
并标记 `origin = "normal_next"`、`source_scope = "normal_next"`。该 endpoint
用于避免 UI 把打开 Today 或“继续”误解为自动分配/重复当前 group。

### Abandon current and start selected level

```http
POST /api/practice/abandon-current-and-next
```

显式结束当天 active normal group，并创建 Settings 当前 `learner_level` 对应的
new normal group。旧 group 标记为 `status = "abandoned"`，保留已有 attempts，
但不计入 completed normal group。该 endpoint 用于 Today hub 的 intentional
restart / level-switch path，例如 `End this Entry group and start Mid`。

如果没有 active normal group，该 endpoint 退化为 next normal group creation。

### Current-group review

```http
POST /api/review/current-group
Content-Type: application/json

{"group_id": "2026-06-06-default-g001-normal"}
```

从指定 source group 中的 wrong attempts 创建 `mistake_review` group。它只使用
该 group 的错题，返回 `source_scope = "current_group"`、
`source_group_id = <group_id>` 和 `source_session_item_ids`。没有错题时返回
stable empty response，不视为错误；未知 group id 返回 `GROUP_NOT_FOUND`。

### Recent mistake review group

```http
POST /api/review/recent-mistakes
```

显式创建或恢复当天的 recent mistake review group。该 API 从最近的错误
attempt 查询错词，去重后映射回 `words`/`session_items`，并创建
`group_type = "mistake_review"` 的普通 session_items。之后前端继续用
`POST /api/attempt` 提交答案，`phoneme_stats` 仍是复习强度和弱项判断的唯一
统计来源。

空队列是稳定非错误状态：

```json
{
  "group_type": "mistake_review",
  "status": "empty",
  "items": [],
  "source_count": 0,
  "origin": "recent_review_empty",
  "source_scope": "recent_global",
  "detail": "No recent incorrect attempts are available for review."
}
```

有错题时返回与 `/api/today` 相同的 group response，并额外包含
`source_count`。同一天重复调用会恢复 active `mistake_review` group，而不是
创建重复 active work。

### Weak phoneme focused group

M7 P1 的 Progress 入口可以创建 `group_type = "weak_focus"` 的 practice group。
`POST /api/practice/focus` 接收 `{"focus_phonemes": [...]}`，保存 focus selection
并调用现有 scheduler focus weighting；
不应新建复习统计表，也不应绕开 `phoneme_stats`。若当天已有 active
`weak_focus` group 且 focus selection 相同，API 应恢复该 group；不同 focus
selection 会创建新的 clearly scoped `weak_focus` group，避免把旧 focus group
误报成新的 selection。完成后下一次显式 action 才创建新 focused group。
`POST /api/practice/clear-focus` 清空 selection，并返回当前 normal practice
state，标记 `origin = "focus_clear"`、`focus_phonemes = []`。

### M7 minimum smoke path

M7 的用户可见 smoke path 至少覆盖：

1. Learner loads `/api/today`, completes one `normal` group through
   `POST /api/attempt`, then requests another same-day `normal` group.
2. Learner answers at least one item incorrectly, starts
   `POST /api/review/recent-mistakes`, and submits the review item through the
   same `POST /api/attempt` path.
3. Progress continues to derive weak/strong phonemes from `phoneme_stats`; no
   review-specific correctness store is introduced.

### Attempt

```http
POST /api/attempt
```

请求：

```json
{
  "session_item_id": "item_001",
  "selected_answer": "/ʃɪp/"
}
```

响应：

```json
{
  "is_correct": true,
  "correct_answer": "/ʃɪp/",
  "updated_phonemes": [
    {
      "phoneme": "/ɪ/",
      "attempt_count": 4,
      "correct_count": 3,
      "mastery_status": "learning"
    }
  ],
  "next_action": "next_item"
}
```

客户端不需要提交 `correct_answer`。后端根据 session item 和 question definition 判题。

### Progress

```http
GET /api/progress
```

返回：

```json
{
  "today_completed": true,
  "streak_days": 5,
  "total_attempts": 120,
  "total_sessions": 12,
  "total_normal_groups": 9,
  "resumable_normal_groups": 1,
  "stat_scope": "global",
  "level_stats": {
    "entry": {
      "learner_level": "entry",
      "label": "Entry",
      "attempts": 60,
      "correct_attempts": 44,
      "accuracy": 0.73,
      "normal_groups": 5,
      "completed_normal_groups": 4,
      "completed_normal_groups_today": 1,
      "resumable_normal_groups": 1,
      "weak_phonemes": [],
      "strong_phonemes": []
    },
    "mid": {
      "learner_level": "mid",
      "label": "Mid",
      "attempts": 40,
      "correct_attempts": 30,
      "accuracy": 0.75,
      "normal_groups": 4,
      "completed_normal_groups": 3,
      "completed_normal_groups_today": 0,
      "resumable_normal_groups": 0,
      "weak_phonemes": [],
      "strong_phonemes": []
    }
  },
  "weak_phonemes": [
    {"phoneme": "/ɪ/", "accuracy": 0.62, "attempt_count": 13}
  ],
  "strong_phonemes": [
    {"phoneme": "/ʃ/", "accuracy": 0.92, "attempt_count": 12}
  ]
}
```

`resumable_normal_groups` is the only Progress field that should drive an
unfinished-practice resume affordance. It counts current-day regular practice
groups that are still `in_progress` and therefore can be resumed by Today.
It must not be inferred from `normal_groups - completed_normal_groups`, because
that historical difference can include abandoned or otherwise non-resumable
groups.

### Settings

```http
GET /api/settings
PUT /api/settings
```

MVP 默认：

```json
{
  "primary_accent": "US",
  "daily_word_count": 10,
  "show_translation": true,
  "show_accent_compare": false,
  "practice_mode": "ipa_first",
  "review_strength": "normal",
  "ui_language": "zh-CN",
  "learner_level": "entry"
}
```

`primary_accent = UK` 可以先不在 UI 开放，但字段应存在。

### M8 learner levels

M8 introduces a learner-facing level setting for future practice groups:

```text
learner_level = entry | mid
```

This is separate from `words.level`, which remains word-level difficulty metadata
from the content source. Runtime scheduling must use `settings.learner_level`
plus content-set readiness, not infer the user's selected level from
`words.level`.

User-facing labels:

```text
entry = Entry
mid = Mid
```

Level meanings:

```text
Entry:
  uses the existing Core 300 runtime set
  is the default for existing and new users
  must not overwrite, delete, or reshuffle the current Core 300 source file

Mid:
  uses a newly curated Core 1000 runtime set
  should increase two-syllable and multi-syllable word ratio versus Core 300
  must not become selectable as a working practice path until Core 1000 is imported and validated
```

Content readiness and import contract:

```text
Entry source: content/core_300_words.json
Mid source:   content/core_1000_words.json

Entry validation:
  backend/scripts/validate_content.py content/core_300_words.json --content-level entry

Mid validation:
  backend/scripts/validate_content.py content/core_1000_words.json --content-level mid
```

Mid/Core1000 word IDs use a `mid_` namespace while preserving
`source_word_id`, so a selected-level import can load Mid rows into the same
SQLite database without replacing Entry/Core300 rows that share the same word
string. `import_words.py --content-level entry|mid|auto` applies the matching
readiness profile before import. Mid readiness reports Core1000 count, level
counts, content statuses, syllable buckets, and multisyllable percentage.

#125 promoted `content/core_1000_words.json` with the accepted #124 target split
of 250 one-syllable, 500 two-syllable, and 250 three-plus-syllable words. The
file includes `meaning_zh` values for runtime compatibility; entries marked
`meaning_zh_review_status = inherited_core300` reuse accepted Entry meanings,
while `meaning_zh_review_status = curated_mid` comes from
`content/core_1000_meanings_zh.json`. Mid validation fails closed if placeholder
meanings remain. The curation script also reuses the accepted Core100
STRUT/r-colored phoneme overrides where matching words appear.

Settings API contract:

```json
{
  "primary_accent": "US",
  "daily_word_count": 10,
  "show_translation": true,
  "show_accent_compare": false,
  "practice_mode": "ipa_first",
  "review_strength": "normal",
  "focus_phonemes": [],
  "ui_language": "zh-CN",
  "learner_level": "entry"
}
```

`PUT /api/settings` accepts partial updates. `learner_level` validation:

```text
entry | mid      accepted values
other values     400 SETTINGS_INVALID
```

M11 adds `ui_language` as a learner-facing UI preference. Initial accepted
values should be:

```text
zh-CN | en-US     accepted values
other values      400 SETTINGS_INVALID
```

`ui_language` controls interface copy only. It must not translate IPA strings,
phoneme symbols, accent identifiers, source word content, `meaning_zh`, grading
logic, or scheduler behavior.

`review_strength` is a scheduling preference for future newly created regular
practice groups. Updating it persists through `GET /api/settings`, but it does
not mutate an already active regular group.

If the UI exposes `mid` before the Mid content set is ready, the action must fail
with a clear disabled/hold state or a structured backend error. Final M8
acceptance requires Mid to be selectable and usable, so the preferred completed
state is not fallback-to-Entry but verified Core 1000 readiness.

Practice generation contract:

```text
Changing learner_level affects future generated regular practice groups.
Changing review_strength affects future generated regular practice groups.
An already active regular group remains resumable until completed.
Entry regular groups select only Entry/Core 300 runtime content.
Mid regular groups select only Mid/Core 1000 runtime content.
Current-group review reuses the source group's items regardless of later level changes.
Recent-mistake review may include previously missed words from the user's history,
but its UI must label it as review rather than as a fresh Entry/Mid group.
Focused practice uses the active learner_level pool; the same focus selection
resumes only an active focused group with the same learner_level.
```

Frontend workflow contract:

```text
Settings shows a Practice level control with Entry and Mid options.
Today Practice displays the active level for regular practice groups.
Regular practice wording must not imply Mid is only a larger daily quota; it is
a different content pool.
Review/focus groups remain visually distinct from regular Entry/Mid practice.
If Mid is unavailable in a developer or partial-import state, the UI explains
the hold instead of silently starting Entry practice.
```

Walkthrough gate:

```text
Entry smoke:
  default settings show learner_level=entry
  a regular group starts from Core 300 content
  completing a group keeps M7 next/review/focus actions coherent

Mid smoke:
  switching to Mid is visible in Settings and Today Practice
  the next regular group uses Core 1000 content
  sample Mid words include visibly more two-syllable or multi-syllable items
  switching levels does not corrupt Entry progress or current-group review

Closure:
  M8 cannot close without a final-user note or trial path describing Entry,
  Mid, how to switch, what changed, verification evidence, exclusions, and
  whether human trial is required.

Route-mocked browser command:

```text
cd frontend && pnpm test:e2e:m8
```
```

## M12 default-owner claim dry-run

Existing local data may still be owned by the legacy `default` user id. Before
any real/private SQLite data is claimed by an authenticated owner, the project
must produce a dry-run report and preserve a restorable backup.

Dry-run command:

```text
cd backend
python scripts/default_owner_claim.py --db-url path/to/tiny_ipa.sqlite
```

Report contract:

```text
dry_run = true
mutation_authorized = false
apply_mode_available = false

row_counts includes:
  users_default
  settings_default
  daily_sessions_default
  session_items_owned_by_default_sessions
  attempts_default_user
  attempts_on_default_session_items
  phoneme_stats_default
  auth_sessions_default

breakdown includes:
  daily_sessions_by_status
  daily_sessions_by_group_type
  session_items_by_session_status
  session_items_by_group_type
```

Backup guidance before any future real apply mode:

```text
Stop the backend.
Copy the SQLite database file and sibling -wal / -shm files to a timestamped
backup path.
Run the dry-run report against both backup and source database.
Do not mutate real/private data until a separate Human Decision Contract
authorizes the exact apply operation and rollback evidence.
```

The #242 artifact intentionally has no apply mode. Temp DB tests may describe
the owner-claim sequence, but real/private mutation remains Human-gated.

## 服务端领域规则

后端负责：

```text
选择每组练习词
创建或恢复当天 practice group
生成 question choices
判题
更新 phoneme_stats
计算 weak/strong/mastered
根据 settings 影响 words per group 和调度
```

前端负责：

```text
展示 IPA first 状态
播放 audio_url 或浏览器 TTS fallback
提交 selected_answer
展示 feedback 和进度摘要
```

## 错误码

建议稳定错误码：

```text
CONTENT_NOT_READY
AUDIO_MISSING
AUTH_REQUIRED
CURRENT_USER_MISSING
USER_DATA_SCOPE_VIOLATION
SESSION_NOT_FOUND
SESSION_ALREADY_COMPLETED
ITEM_NOT_FOUND
INVALID_ATTEMPT
SETTINGS_INVALID
```

这些错误码应该被测试覆盖，尤其是 session 和 attempt 的连接路径。
