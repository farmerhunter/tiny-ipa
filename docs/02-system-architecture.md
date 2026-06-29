# 系统架构与边界

## 总体架构

推荐架构：

```text
Content Sources
  wordfreq / SUBTLEX-US / ipa-dict / manual blocklists
        |
        v
Content Build Layer
  select_candidates.py
  validate_content.py
  generate_tts_audio.py
  import_words.py
        |
        v
Runtime Assets
  SQLite database
  /audio static files
        |
        v
FastAPI Backend
  auth/session/current user
  practice
  grading
  progress
  settings
  content reports
        |
        v
React PWA Client
```

部署时：

```text
Mobile Browser / PWA
        |
      HTTPS
        |
      Nginx
   /static     /api        /audio
 frontend   FastAPI   static mp3 files
              |
           SQLite
```

## 边界说明

### Content Source Layer

维护人工可读、可版本管理的源数据：

```text
content/sources/
content/phonemes.json
content/blocklists.json
content/selection_config.json
content/manual_overrides.json
```

它是长期资产。SQLite 不是源事实，只是运行时导入结果。

### Content Build Layer

负责把外部数据和项目规则变成可运行内容：

```text
select_candidates.py
validate_content.py
generate_tts_audio.py
import_words.py
```

这些脚本应输出可审查报告，例如：

```text
candidate_count
rejection_reasons
phoneme_coverage_us
phoneme_coverage_uk
missing_audio
unknown_ipa_symbols
license_summary
```

### Runtime Backend

FastAPI 只面向运行时用户体验。它不在请求路径中做大规模内容抓取、实时词典查询或实时 TTS。

后端拥有：

```text
current-user resolution
minimal auth/session boundary
session generation
question generation
server-side grading
phoneme stat update
progress summary
settings validation
```

### Frontend

React PWA 消费领域摘要，不自行计算掌握度或决定调度逻辑。

前端可以有本地 UI 状态，例如当前卡片是否 reveal，但不拥有学习记录事实。

### Localization

UI language is a product/runtime preference, not content-source data.

Learner-facing UI copy should live behind a locale boundary so the app can
support:

```text
zh-CN default learner-facing copy
en-US selectable UI copy
stable IPA, phoneme, accent, and content semantics
```

Localization should not translate source word records or `meaning_zh`. IPA
symbols, phoneme tags, accent identifiers, and grading semantics remain domain
data. Locale resources own button labels, state descriptions, error copy, and
help text.

### Auth and User Data Boundary

Tiny IPA starts as a local single-user app, but runtime learning data is already
modeled around `user_id`. Before deployment, the system needs an explicit
current-user boundary:

```text
users / owner bootstrap
login / logout / current user
settings scoped by user
daily_sessions scoped by user
attempts scoped by user
phoneme_stats scoped by user
review/focus state scoped by user
```

Content tables remain global and source-driven. User runtime tables are private
learning state and must be backed up and restored with the authenticated user
boundary intact.

Minimal auth should avoid broad SaaS features. OAuth, social login, family
dashboards, complex role matrices, and account administration are separate
future product decisions.

### Audio Assets

音频是静态资产：

```text
/audio/us/ship.mp3
/audio/uk/ship.mp3
```

数据库保存 URL 或 asset key。前端只播放 URL，不关心音频来自浏览器 TTS、edge-tts、云 TTS 还是人工录音。

## 技术选择

建议：

```text
Backend: Python FastAPI
DB: SQLite
ORM: SQLModel or SQLAlchemy
Frontend: Vite + React + TypeScript
Deployment: VPS + Nginx + systemd
Content scripts: Python
```

这些是边界实现，不是架构本身。若未来改成 PostgreSQL、Vue 或小程序，内容层、API 语义和音频资产边界仍应保持。

## 目录建议

```text
tiny-ipa/
  docs/
  content/
    phonemes.json
    selection_config.json
    blocklists.json
    manual_overrides.json
    generated/
      candidate_words.json
      core_words.json
      content_report.json
  audio/
    us/
    uk/
  backend/
    app/
      main.py
      config.py
      db.py
      models.py
      schemas.py
      routes/
      services/
    scripts/
      select_candidates.py
      validate_content.py
      generate_tts_audio.py
      import_words.py
    tests/
  frontend/
```

## 替换测试

架构应通过以下替换测试：

1. 如果浏览器 TTS 换成预生成 mp3，前端练习流程不变。
2. 如果 edge-tts 换成云 TTS，只改构建脚本，不改 API。
3. 如果 SQLite 换成 PostgreSQL，内容源文件和 API 合同不变。
4. 如果 React PWA 后面换微信小程序，后端领域服务不变。
5. 如果 IPA 来源换掉，`WordEntry` 的运行时字段不变，只改变内容构建层。

## 明确失败状态

系统应显式表示这些失败，而不是只抛异常：

```text
content_source_unavailable
auth_required
current_user_missing
user_data_scope_violation
ipa_missing_us
ipa_missing_uk
ipa_parse_failed
unknown_phoneme_symbol
candidate_rejected
audio_missing
audio_generation_failed
session_generation_failed
attempt_invalid
settings_invalid
```

内容构建失败应生成报告；运行时失败应返回稳定错误码和用户可理解提示。
