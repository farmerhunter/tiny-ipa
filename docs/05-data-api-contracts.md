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
  completed_at TEXT
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

返回领域摘要，不返回原始调度内部状态：

```json
{
  "session_id": "2026-06-06-default",
  "date": "2026-06-06",
  "primary_accent": "US",
  "daily_word_count": 10,
  "status": "in_progress",
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
选择今日词
创建或恢复当天 session
生成 question choices
判题
更新 phoneme_stats
计算 weak/strong/mastered
根据 settings 影响 daily_word_count 和调度
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
