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

settings(
  user_id TEXT PRIMARY KEY,
  primary_accent TEXT NOT NULL,
  daily_word_count INTEGER NOT NULL,
  show_translation INTEGER NOT NULL,
  show_accent_compare INTEGER NOT NULL,
  practice_mode TEXT NOT NULL,
  review_strength TEXT NOT NULL,
  learner_level TEXT NOT NULL DEFAULT 'entry',
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
| Entry/home | No active group or unknown | Start practice | `GET /api/today` or future explicit start query | Active normal group | Active normal group | `Group 1`, `10 words` | Show setup/import error with retry |
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

创建或恢复当天的普通练习组。M7 起，Tiny IPA 将“每日练习”收窄为
“当天可重复创建的 10 词 practice group”：

- `session_id` 仍是 attempt 提交使用的持久 session id；
- `group_id` 是 `session_id` 的语义别名，供 UI 用 group 语言表达；
- `group_index` 是同一 `user_id`/`date`/`primary_accent` 下的递增序号；
- `group_type` 当前实现 `normal`、`mistake_review` 和 `weak_focus`，均复用
  同一 session_items/attempts/phoneme_stats 路径；
- `learner_level` 和 `learner_level_label` 记录创建该 group 时使用的
  learner-facing level，active group 恢复时不随 settings 切换而改写；
- `origin` 说明 action reason，例如 `normal_start`、`normal_resume`、
  `normal_next`、`current_group_review_start`、`recent_review_start`、
  `focus_start`、`focus_clear`；
- `source_scope` 说明数据来源范围，例如 `normal_current`、`normal_next`、
  `current_group`、`recent_global`、`focus_selection`；
- `source_group_id` 仅 current-group review 使用，指向被复习的 source group；
- `focus_phonemes` 在 focus 影响选词或清除 focus 时返回；
- `action_label` 是后端状态驱动的短文案提示，前端可按产品语气改写；
- `daily_word_count` 保留为兼容字段，M7 UI 文案应理解为 words per group；
- `word_count` 是本响应实际返回的 item 数；
- `source_session_item_ids` 仅 review group 使用，用于追踪错题来源。

重复调用 `GET /api/today` 时，如果存在当天同 accent 的 `normal`
`in_progress` group，则恢复它；如果当天已有 completed normal group 且没有
active normal group，则创建下一个 normal group。不同 group 共用
`session_items`、`attempts` 和 `phoneme_stats`，不引入第二套判题或统计来源。

返回领域摘要，不返回原始调度内部状态：

```json
{
  "session_id": "2026-06-06-default-g001-normal",
  "group_id": "2026-06-06-default-g001-normal",
  "group_index": 1,
  "group_type": "normal",
  "learner_level": "entry",
  "learner_level_label": "Entry",
  "date": "2026-06-06",
  "primary_accent": "US",
  "origin": "normal_start",
  "source_scope": "normal_current",
  "action_label": "Start Group 1",
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

### Next normal group

```http
POST /api/practice/next-normal
```

显式从完成摘要进入下一个 normal group。若当天已经有 active normal group，
返回该 group 并标记 `origin = "normal_resume"`；否则创建递增
`group_index` 的 normal group 并标记 `origin = "normal_next"`、
`source_scope = "normal_next"`。该 endpoint 用于避免 UI 把“继续”误解为重复
当前 group。

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
  "weak_phonemes": [
    {"phoneme": "/ɪ/", "accuracy": 0.62, "attempt_count": 13}
  ],
  "strong_phonemes": [
    {"phoneme": "/ʃ/", "accuracy": 0.92, "attempt_count": 12}
  ]
}
```

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
`meaning_zh_review_status = placeholder` remain a human/Architect content
acceptance risk before learner exposure. The curation script also reuses the
accepted Core100 STRUT/r-colored phoneme overrides where matching words appear.

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
  "learner_level": "entry"
}
```

`PUT /api/settings` accepts partial updates. `learner_level` validation:

```text
entry | mid      accepted values
other values     400 SETTINGS_INVALID
```

If the UI exposes `mid` before the Mid content set is ready, the action must fail
with a clear disabled/hold state or a structured backend error. Final M8
acceptance requires Mid to be selectable and usable, so the preferred completed
state is not fallback-to-Entry but verified Core 1000 readiness.

Practice generation contract:

```text
Changing learner_level affects future generated normal practice groups.
An already active normal group remains resumable until completed.
Entry normal groups select only Entry/Core 300 runtime content.
Mid normal groups select only Mid/Core 1000 runtime content.
Current-group review reuses the source group's items regardless of later level changes.
Recent-mistake review may include previously missed words from the user's history,
but its UI must label it as review rather than as a fresh Entry/Mid group.
Focused practice uses the active learner_level pool; the same focus selection
resumes only an active focused group with the same learner_level.
```

Frontend workflow contract:

```text
Settings shows a Practice level control with Entry and Mid options.
Today Practice displays the active level for normal practice groups.
Normal practice wording must not imply Mid is only a larger daily quota; it is a
different content pool.
Review/focus groups remain visually distinct from normal Entry/Mid practice.
If Mid is unavailable in a developer or partial-import state, the UI explains
the hold instead of silently starting Entry practice.
```

Walkthrough gate:

```text
Entry smoke:
  default settings show learner_level=entry
  a normal group starts from Core 300 content
  completing a group keeps M7 next/review/focus actions coherent

Mid smoke:
  switching to Mid is visible in Settings and Today Practice
  the next normal group uses Core 1000 content
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
SESSION_NOT_FOUND
SESSION_ALREADY_COMPLETED
ITEM_NOT_FOUND
INVALID_ATTEMPT
SETTINGS_INVALID
```

这些错误码应该被测试覆盖，尤其是 session 和 attempt 的连接路径。
