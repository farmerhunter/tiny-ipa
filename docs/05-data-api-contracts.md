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

### Today

```http
GET /api/today
```

创建或恢复当天的普通练习组。M7 起，Tiny IPA 将“每日练习”收窄为
“当天可重复创建的 10 词 practice group”：

- `session_id` 仍是 attempt 提交使用的持久 session id；
- `group_id` 是 `session_id` 的语义别名，供 UI 用 group 语言表达；
- `group_index` 是同一 `user_id`/`date`/`primary_accent` 下的递增序号；
- `group_type` 当前实现 `normal` 和 `mistake_review`；后续弱音素入口使用
  `weak_focus`，但仍复用同一 session_items/attempts/phoneme_stats 路径；
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
  "date": "2026-06-06",
  "primary_accent": "US",
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
  "detail": "No recent incorrect attempts are available for review."
}
```

有错题时返回与 `/api/today` 相同的 group response，并额外包含
`source_count`。同一天重复调用会恢复 active `mistake_review` group，而不是
创建重复 active work。

### Weak phoneme focused group

M7 P1 的 Progress 入口可以创建 `group_type = "weak_focus"` 的 practice group。
它应接收用户选择的 phoneme symbols/ids，并调用现有 scheduler focus weighting；
不应新建复习统计表，也不应绕开 `phoneme_stats`。若当天已有 active
`weak_focus` group，API 应恢复该 group；完成后下一次显式 action 才创建新
focused group。

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
  "review_strength": "normal"
}
```

`primary_accent = UK` 可以先不在 UI 开放，但字段应存在。

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
