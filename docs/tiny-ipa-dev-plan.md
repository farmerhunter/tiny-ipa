# 小音标 Tiny IPA 开发计划

> 状态说明：本文是 Tiny IPA 的初始产品规划背景。后续架构、内容自动选词、TTS、数据/API 和里程碑实现合同，以 `docs/00-design-index.md` 所索引的设计文档集为准。尤其是 US/UK IPA 与 phoneme tags 的字段设计，已在新文档中调整为 accent-specific 字段。

## 1. 项目定位

“小音标 / Tiny IPA”是一个面向儿童和英语初学者的单用户音标练习应用。它不是背单词 App，也不是完整词典或家庭学习管理系统。它的核心目标是：通过有限规模的初级英语词库，让学习者每天看 IPA 音标读单词、听标准发音验证、完成少量音标辨识题，从而在一个阶段内掌握英语核心音位。

项目初期面向个人使用和开源自部署，不考虑商业化、不考虑应用商店发布、不考虑复杂版权商业授权、不考虑多家庭 SaaS 运营。系统应当尽量低成本、可本地或 VPS 部署、容易被 Codex/开发者继续迭代。

项目中文名：小音标。

项目英文名：Tiny IPA。

建议副标题：每天 10 个词，练会英语音标。

英文副标题：Daily IPA practice with small beginner word sets.

## 2. 核心设计原则

第一，围绕 phoneme mastery，而不是 vocabulary memorization。单词只是练习音标和音位辨识的载体。系统统计和复习调度应优先围绕 `/ɪ/`、`/iː/`、`/æ/`、`/θ/`、`/ʃ/` 等音位，而不是围绕“背了多少单词”。

第二，保持“小”。词库不追求大而全，目标是支撑一个阶段性的音标训练。MVP 可以从 300–500 个高质量初级词开始，长期也不必扩张成完整 learner’s dictionary。词条应当经过清洗和抽检，优先保证 IPA、音频、中文短释义和 phoneme tags 的准确性。

第三，主线先选一种口音。默认使用 US / General American 作为主线。UK IPA 和 UK audio 可以作为未来增强或可选对照，但不应在初期默认展示，避免增加儿童认知负担。

第四，先做 Web/PWA，不做 iOS 原生 App，也不先做微信小程序。Web/PWA 可部署在已有 VPS 上，手机浏览器或微信内置浏览器均可访问。以后如有必要，可以复用后端 API 做微信小程序前端。

第五，单用户自追踪。第一版不做家庭 dashboard、不做家长账号、不做教师后台、不做多租户 SaaS。可以保留一个轻量配置页，供家长或老师设置学习参数。数据模型可以保留 `user_id` 或默认 profile，避免未来扩展时重构。

第六，提醒系统后置。当前 Hermes 只连接一个微信账号，因此不把微信/Hermes 提醒作为 MVP 依赖。第一版靠用户主动打开应用练习。后续可加浏览器提醒、家长微信提醒或小程序订阅消息。

## 3. 明确非目标

MVP 不做以下内容：

1. 不做完整词典查询功能；
2. 不做大规模背单词功能；
3. 不做商业词典网页抓取；
4. 不做 Cambridge/Oxford 商业授权接入；
5. 不做原生 iOS/Android App；
6. 不做微信小程序第一版；
7. 不做多家庭、多租户、公开注册；
8. 不做家长 dashboard 或教师后台；
9. 不做复杂游戏化系统；
10. 不做录音自动评分第一版；
11. 不做社交、排行榜、班级管理；
12. 不做正式推送系统第一版。

## 4. 用户模型

第一版只有一个学习者。系统内部可以有一个默认用户：

```text
user_id = "default"
display_name = "Learner"
```

如果前端需要区分访问者，可以使用一个简单部署 token 或浏览器 localStorage 绑定默认 profile。第一版不需要登录注册流程。

家长/老师不是独立角色，只是配置页的使用者。配置页可以暂时无保护，或使用简单 PIN 保护。配置页不承担监督、统计报表、消息发送等管理功能。

## 5. MVP 用户流程

### 5.1 今日练习流程

学习者打开应用后直接进入“今日练习”。系统展示今日任务，例如 10 个词。每个练习项的默认顺序为：

1. 先显示 IPA，例如 `/ʃɪp/`；
2. 学习者尝试根据音标读出来；
3. 点击“显示单词 / 播放发音”；
4. 页面显示 `ship`、中文短释义、音频按钮；
5. 学习者完成一道简短题目；
6. 系统记录结果并进入下一个词。

这种流程的重点是让学习者从 IPA 到声音，再到单词和音频校验，而不是先看单词再记音标。

### 5.2 题型

第一版建议实现 3–4 种题型。

第一种：看 IPA 读词。展示 IPA，用户点击后揭示单词和音频。该题型主要记录是否完成，不强制判错。

第二种：看单词选 IPA。展示 `ship`，从 `/ʃɪp/`、`/ʃiːp/`、`/sɪp/` 中选择正确音标。

第三种：听音选 IPA。播放音频或 TTS，从多个 IPA 选项中选择。这个题型依赖音频质量，第一版可作为可选题型。

第四种：识别目标音。展示一个目标音 `/ɪ/`，让学习者从多个单词中选择包含该音的词，或展示一个词让学习者判断是否包含目标音。

MVP 应优先实现“看 IPA 读词”和“看单词选 IPA”。其他题型可逐步加入。

### 5.3 进度页

进度页只面向学习者本人，不是家长 dashboard。展示内容要简单：

1. 今日是否完成；
2. 连续练习天数；
3. 最近 7 天完成情况；
4. 最容易错的 3 个音位；
5. 掌握较好的 3 个音位；
6. 总完成词次和题次数。

进度统计应按 phoneme 聚合。例如 `/ɪ/` 的正确率、练习次数、最近错误时间，而不是只统计单词背诵数量。

### 5.4 配置页

配置页不是后台，只是 settings。建议第一版支持：

```text
primary_accent: "US" | "UK"，默认 "US"
daily_word_count: 默认 10
show_translation: 默认 true
show_accent_compare: 默认 false
practice_mode: "ipa_first" | "word_first"，默认 "ipa_first"
difficulty_level: "beginner"
focus_phonemes: 可为空；为空时系统按默认学习路径推送
review_strength: "low" | "normal" | "high"，默认 "normal"
```

可选：配置页简单 PIN。

## 6. 内容与数据策略

### 6.1 数据来源原则

初期不使用商业 learner’s dictionary 的网页抓取内容。优先使用开放数据和少量人工整理。

可选数据来源：

1. 词频或初级词候选：wordfreq、CEFR-J、手工精选儿童高频词；
2. IPA：open-dict-data/ipa-dict、Wiktionary、CMUdict 转 IPA；
3. 音频：浏览器 TTS、系统 TTS 预生成音频、开放音频资源；
4. 中文短释义：手工维护 MVP 词表，或用机器翻译生成后人工修订；
5. minimal pairs：手工维护核心对立组。

### 6.2 内容质量优先级

由于本项目定位为“小”，应优先做小而准的内容库。建议 MVP 词库分三层：

第一层：Core 100。高度人工审核，用于最初演示和真实使用。

第二层：Core 300。覆盖主要英语元音、常见辅音和中国学习者高频难点。

第三层：Core 500。支持一个阶段的每日练习和复习。

长期不必追求超过 1000–1500 词，除非产品目标发生变化。

### 6.3 词条数据结构

建议使用 JSON/CSV 作为源数据，构建时导入 SQLite。字段建议如下：

```json
{
  "word_id": "ship",
  "word": "ship",
  "level": "beginner",
  "frequency_rank": 1234,
  "ipa_us": "/ʃɪp/",
  "ipa_uk": "/ʃɪp/",
  "audio_us": "/audio/us/ship.mp3",
  "audio_uk": null,
  "meaning_zh": "船；大船",
  "example": "A ship is on the sea.",
  "phoneme_tags": ["/ʃ/", "/ɪ/"],
  "difficulty_tags": ["sh", "short_i"],
  "minimal_pair_group": "ship_sheep",
  "source": "manual/open",
  "license": "project-curated",
  "review_status": "reviewed"
}
```

`phoneme_tags` 是核心字段。所有调度和进度统计都应使用它。

### 6.4 音位表

系统应维护一张 phoneme 表。MVP 重点建议包括：

元音：

```text
/iː/ as in sheep
/ɪ/ as in ship
/e/ as in bed
/æ/ as in cat
/ʌ/ as in cup
/ɑ/ as in father, hot in many American accents
/ɔ/ as in thought in non-merged accents
/ʊ/ as in book
/uː/ as in food
/ə/ as in about
/eɪ/ as in face
/aɪ/ as in price
/oʊ/ as in go
/aʊ/ as in mouth
/ɔɪ/ as in choice
/ɝ/ as in bird
/ɚ/ as in teacher
```

辅音：

```text
/p/ /b/ /t/ /d/ /k/ /g/
/f/ /v/ /θ/ /ð/ /s/ /z/ /ʃ/ /ʒ/ /h/
/tʃ/ /dʒ/
/m/ /n/ /ŋ/
/l/ /r/ /w/ /j/
```

对中国小朋友优先训练的难点：

```text
/iː/ vs /ɪ/
/e/ vs /æ/
/ʌ/ vs /ɑ/
/ʊ/ vs /uː/
/θ/ vs /s/
/ð/ vs /z/ or /d/
/ʃ/ vs /s/
/tʃ/ vs /tr/ or /ʃ/
/v/ vs /w/
/r/ vs /l/
/ŋ/ final sound
/ɝ/ and /ɚ/
```

## 7. 调度与复习逻辑

第一版不需要复杂算法，但应避免完全随机。

建议调度规则：

1. 每日词数由配置决定，默认 10；
2. 今日练习由新词和复习词混合组成；
3. 默认比例：60% 新词，40% 复习词；
4. 复习词优先选择最近错误的 phoneme 对应词；
5. 如果某个 phoneme 的正确率低于阈值，例如 70%，增加该 phoneme 的练习权重；
6. 每个词不要连续多日重复，除非前一次答错；
7. 每个音位需要有最少练习次数后才判断为 mastered。

MVP 可采用简单 scoring：

```text
phoneme_score = correct_count / attempt_count
word_score = correct_count / attempt_count
mastered = attempt_count >= 5 and phoneme_score >= 0.85
weak = attempt_count >= 3 and phoneme_score < 0.70
```

后续可以加入 spaced repetition，但不应作为第一版阻塞项。

## 8. 技术架构

### 8.1 推荐技术栈

后端：Python FastAPI。

数据库：SQLite。

ORM：SQLModel 或 SQLAlchemy。

前端：Vite + React，或 Vite + Vue。若无强偏好，建议 React。

部署：VPS + Nginx + systemd，或 Docker Compose。

音频：第一版使用浏览器 TTS 或预生成 mp3。若使用预生成音频，作为静态文件由 Nginx 或 FastAPI 提供。

### 8.2 架构图

```text
Mobile Browser / PWA
        |
        | HTTPS
        v
Nginx Reverse Proxy
        |
        v
FastAPI Backend
        |
        +-- SQLite DB
        |
        +-- Static Word/IPA Data
        |
        +-- Audio Files or TTS config
        |
        +-- Content Build Scripts
```

### 8.3 项目目录建议

```text
tiny-ipa/
  README.md
  LICENSE
  .env.example
  docker-compose.yml
  backend/
    pyproject.toml
    app/
      main.py
      config.py
      db.py
      models.py
      schemas.py
      routes/
        practice.py
        progress.py
        settings.py
        content.py
      services/
        scheduler.py
        grading.py
        progress.py
        content_loader.py
      data/
        seed_words.json
        phonemes.json
    scripts/
      import_words.py
      validate_content.py
      generate_tts_audio.py
    tests/
      test_scheduler.py
      test_progress.py
      test_content_validation.py
  frontend/
    package.json
    index.html
    src/
      main.tsx
      App.tsx
      api.ts
      pages/
        TodayPractice.tsx
        Progress.tsx
        Settings.tsx
      components/
        IpaCard.tsx
        AudioButton.tsx
        ChoiceQuestion.tsx
        ProgressBadge.tsx
      styles/
        global.css
  docs/
    product-spec.md
    data-format.md
    deployment.md
```

## 9. 后端数据模型

### 9.1 tables

建议 SQLite 表：

```sql
users(
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL
)

settings(
  user_id TEXT PRIMARY KEY,
  primary_accent TEXT NOT NULL,
  daily_word_count INTEGER NOT NULL,
  show_translation INTEGER NOT NULL,
  show_accent_compare INTEGER NOT NULL,
  practice_mode TEXT NOT NULL,
  difficulty_level TEXT NOT NULL,
  focus_phonemes TEXT,
  review_strength TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

words(
  id TEXT PRIMARY KEY,
  word TEXT NOT NULL,
  level TEXT NOT NULL,
  frequency_rank INTEGER,
  ipa_us TEXT,
  ipa_uk TEXT,
  audio_us TEXT,
  audio_uk TEXT,
  meaning_zh TEXT,
  example TEXT,
  phoneme_tags TEXT NOT NULL,
  difficulty_tags TEXT,
  minimal_pair_group TEXT,
  source TEXT,
  license TEXT,
  review_status TEXT NOT NULL
)

phonemes(
  id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  category TEXT NOT NULL,
  example_word TEXT,
  priority INTEGER NOT NULL,
  description_zh TEXT
)

daily_sessions(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_date TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
)

session_items(
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  word_id TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  target_phonemes TEXT,
  item_type TEXT NOT NULL,
  status TEXT NOT NULL
)

attempts(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  session_item_id TEXT NOT NULL,
  word_id TEXT NOT NULL,
  question_type TEXT NOT NULL,
  target_phoneme TEXT,
  selected_answer TEXT,
  correct_answer TEXT,
  is_correct INTEGER NOT NULL,
  created_at TEXT NOT NULL
)

phoneme_stats(
  user_id TEXT NOT NULL,
  phoneme_id TEXT NOT NULL,
  attempt_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL,
  last_attempt_at TEXT,
  last_wrong_at TEXT,
  mastery_status TEXT NOT NULL,
  PRIMARY KEY(user_id, phoneme_id)
)
```

MVP 可以省略 `users` 的真实管理功能，但保留表和默认用户。

## 10. API 设计

### 10.1 获取今日练习

```http
GET /api/today
```

返回：

```json
{
  "session_id": "2026-06-06-default",
  "date": "2026-06-06",
  "daily_word_count": 10,
  "items": [
    {
      "session_item_id": "item_001",
      "word_id": "ship",
      "display_ipa": "/ʃɪp/",
      "ipa_us": "/ʃɪp/",
      "ipa_uk": "/ʃɪp/",
      "word": "ship",
      "meaning_zh": "船；大船",
      "audio_url": "/audio/us/ship.mp3",
      "target_phonemes": ["/ʃ/", "/ɪ/"],
      "question": {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": ["/ʃɪp/", "/ʃiːp/", "/sɪp/"],
        "answer": "/ʃɪp/"
      }
    }
  ]
}
```

For safety, the backend may omit `answer` from production responses and grade server-side. For MVP, including answer is acceptable if simplicity is prioritized, but server-side grading is cleaner.

### 10.2 提交答案

```http
POST /api/attempt
Content-Type: application/json
```

Request:

```json
{
  "session_item_id": "item_001",
  "word_id": "ship",
  "question_type": "choose_ipa",
  "target_phoneme": "/ɪ/",
  "selected_answer": "/ʃɪp/"
}
```

Response:

```json
{
  "is_correct": true,
  "correct_answer": "/ʃɪp/",
  "explanation": "ship contains /ɪ/, as in short i."
}
```

### 10.3 获取进度

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
    {"phoneme": "/ɪ/", "accuracy": 0.62, "attempt_count": 13},
    {"phoneme": "/θ/", "accuracy": 0.55, "attempt_count": 9}
  ],
  "strong_phonemes": [
    {"phoneme": "/ʃ/", "accuracy": 0.92, "attempt_count": 12}
  ]
}
```

### 10.4 获取配置

```http
GET /api/settings
```

### 10.5 更新配置

```http
PUT /api/settings
Content-Type: application/json
```

Request:

```json
{
  "primary_accent": "US",
  "daily_word_count": 10,
  "show_translation": true,
  "show_accent_compare": false,
  "practice_mode": "ipa_first",
  "difficulty_level": "beginner",
  "focus_phonemes": [],
  "review_strength": "normal"
}
```

## 11. 前端页面设计

### 11.1 TodayPractice 页面

主页面打开即练。移动端优先。

卡片状态：

```text
State A: IPA only
  /ʃɪp/
  [I read it]
  [Reveal word]

State B: revealed
  /ʃɪp/
  ship
  船；大船
  [Play audio]
  Question choices...

State C: feedback
  Correct / Try again
  Explanation
  [Next]
```

注意事项：

1. IPA 字体要足够大；
2. 单词初始隐藏；
3. 音频按钮明显；
4. 每次只显示一个核心动作；
5. 不要做复杂页面跳转；
6. 完成后显示简短总结。

### 11.2 Progress 页面

内容简洁，适合孩子自己看：

```text
Today: Done
Streak: 5 days
You practiced: 120 sounds
Needs practice: /ɪ/, /θ/, /æ/
Doing well: /ʃ/, /iː/, /m/
```

可用进度条展示 phoneme accuracy，但不要做家长式报表。

### 11.3 Settings 页面

配置项尽量少。若加 PIN，入口可以是设置按钮后输入 4 位 PIN。

配置页文案要让非技术用户理解：

```text
Main accent: American / British
Words per day: 5 / 10 / 15
Show Chinese meaning: on/off
Show UK/US comparison: on/off
Practice focus: all sounds / vowels / consonants / difficult sounds
Review strength: light / normal / strong
```

## 12. 内容构建脚本

### 12.1 import_words.py

职责：读取 `seed_words.json`，校验字段，导入 SQLite。

校验规则：

1. `word` 必填；
2. `ipa_us` 至少在 US 主线下必填；
3. `phoneme_tags` 不得为空；
4. `phoneme_tags` 中每个音位必须存在于 phonemes 表；
5. `review_status` 必须是 `draft`、`reviewed` 或 `disabled`；
6. `level` 必须是 `beginner` 或未来允许值；
7. 如果 audio_url 存在，检查文件是否存在。

### 12.2 validate_content.py

职责：生成内容质量报告。

输出：

```text
Total words: 312
Reviewed words: 145
Missing IPA US: 0
Missing meaning_zh: 12
Missing audio: 86
Unknown phoneme tags: 0
Words per phoneme:
  /ɪ/: 34
  /iː/: 28
  /æ/: 31
Weak coverage:
  /ð/: 5
  /ʒ/: 2
```

### 12.3 generate_tts_audio.py

职责：可选地为词条生成 mp3。第一版可以不实现，直接用浏览器 speechSynthesis。

如果实现，应避免把特定云服务写死。建议抽象：

```text
provider = browser_tts | edge_tts | azure | local
```

## 13. 部署方案

### 13.1 VPS systemd 方案

后端：

```bash
cd tiny-ipa/backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

前端：

```bash
cd tiny-ipa/frontend
npm install
npm run build
```

Nginx：

```nginx
server {
    listen 80;
    server_name tiny-ipa.example.com;

    root /opt/tiny-ipa/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8010/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /audio/ {
        alias /opt/tiny-ipa/audio/;
    }

    location / {
        try_files $uri /index.html;
    }
}
```

HTTPS 可用 Caddy 或 certbot 配置。第一版建议直接使用 HTTPS，因为浏览器音频、未来录音、PWA 都更稳定。

### 13.2 Docker Compose 方案

可后续补充。MVP 若开发者熟悉 Docker，可直接提供：

```text
backend container + nginx container + mounted sqlite/data volume
```

但 SQLite + systemd 对个人 VPS 已足够。

## 14. 开发里程碑

### Milestone 0: Repo 初始化

目标：创建可运行项目骨架。

任务：

1. 初始化 `tiny-ipa` repo；
2. 创建 backend FastAPI skeleton；
3. 创建 frontend Vite skeleton；
4. 添加 README；
5. 添加 `.env.example`；
6. 添加基础 lint/test 命令；
7. 确认本地可启动前后端。

验收：访问前端首页，能调用 `/api/health`。

### Milestone 1: 静态词库与今日练习

目标：跑通最小练习闭环，不依赖数据库复杂逻辑。

任务：

1. 编写 `phonemes.json`；
2. 编写 30–50 个 `seed_words.json`；
3. 后端实现 `/api/today`；
4. 前端实现 TodayPractice 页面；
5. 支持 IPA first reveal；
6. 支持浏览器 TTS 或静态音频占位。

验收：手机浏览器打开后可以完成 10 个词的练习流程。

### Milestone 2: SQLite 持久化与答题记录

目标：记录学习行为。

任务：

1. 添加 SQLite models；
2. 实现 seed import；
3. 实现 `/api/attempt`；
4. 记录 attempt；
5. 更新 phoneme_stats；
6. 前端提交题目结果并显示反馈。

验收：刷新页面后进度不丢失；数据库中能看到 attempts 和 phoneme_stats。

### Milestone 3: 进度页

目标：学习者能看到自己的音标掌握情况。

任务：

1. 实现 `/api/progress`；
2. 前端实现 Progress 页面；
3. 展示 weak phonemes 和 strong phonemes；
4. 展示 streak 和 total attempts；
5. 做移动端样式优化。

验收：完成多次练习后，进度页统计合理。

### Milestone 4: 配置页

目标：支持轻量家长/老师配置。

任务：

1. 实现 settings 表；
2. 实现 `/api/settings` GET/PUT；
3. 前端实现 Settings 页面；
4. 支持每日词数、主口音、中文释义、UK/US 对照开关；
5. 可选 PIN 保护。

验收：修改每日词数后，下一次 `/api/today` 生效。

### Milestone 5: 调度逻辑增强

目标：从随机词变成基于音位薄弱项的练习。

任务：

1. 实现新词/复习词混合；
2. 根据 phoneme_stats 提升弱项权重；
3. 避免短期重复；
4. 支持 focus_phonemes；
5. 添加 scheduler 单元测试。

验收：当 `/ɪ/` 连续答错后，后续练习中包含 `/ɪ/` 的词比例上升。

### Milestone 6: 内容扩展到 Core 300

目标：获得足够真实可用的阶段性词库。

任务：

1. 扩展词库到 300 个；
2. 标注 IPA US；
3. 标注 phoneme_tags；
4. 添加中文短释义；
5. 运行 validate_content；
6. 人工抽检重点难点音。

验收：Core 300 覆盖主要目标音位；validate_content 无严重错误。

### Milestone 7: VPS 部署

目标：真实手机可访问。

任务：

1. 在 VPS 安装运行环境；
2. 配置 Nginx；
3. 配置 HTTPS；
4. 配置 systemd 服务；
5. 部署前端 build；
6. 配置数据备份；
7. 写 deployment.md。

验收：手机浏览器可通过域名访问并完成练习。

## 15. 测试策略

后端必须测试：

1. 内容导入校验；
2. `/api/today` 返回数量正确；
3. scheduler 不返回 disabled words；
4. attempt 提交后更新 phoneme_stats；
5. settings 更新后影响 daily_word_count；
6. weak phoneme 权重逻辑。

前端手动测试：

1. 手机浏览器页面布局；
2. IPA 字符显示正常；
3. 音频播放可用；
4. reveal 流程无误；
5. 答题反馈正确；
6. 刷新后当天 session 不丢失；
7. 设置更新后生效。

内容测试：

1. IPA 符号统一；
2. US/UK 不混用；
3. 目标音位 tags 正确；
4. 中文释义短而儿童可理解；
5. minimal pair 不误配。

## 16. 未来增强项

优先级从高到低：

1. 增加 Core 500；
2. 支持 UK IPA 可选对照；
3. 支持 minimal pair 专项练习；
4. 支持浏览器本地提醒；
5. 支持 PWA install；
6. 支持预生成高质量音频；
7. 支持录音回放，不做自动评分；
8. 支持 pronunciation assessment 自动评分；
9. 支持微信小程序前端；
10. 支持 Hermes 给家长账号提醒；
11. 支持多个 local profiles；
12. 支持导入/导出学习记录。

## 17. Codex 执行建议

建议 Codex 优先从 Milestone 0–2 开始，不要先做复杂 UI 和数据爬取。

第一轮 Codex 任务可以是：

```text
Create the Tiny IPA repo skeleton with FastAPI backend and Vite React frontend. Implement /api/health, /api/today using a static seed_words.json with 20 words, and a mobile-first TodayPractice page that shows IPA first, then reveals word, meaning, and audio button placeholder.
```

第二轮 Codex 任务：

```text
Add SQLite persistence with SQLModel. Implement words, daily_sessions, session_items, attempts, and phoneme_stats tables. Add import_words.py and validate_content.py. Implement POST /api/attempt and update phoneme_stats after each answer.
```

第三轮 Codex 任务：

```text
Implement Progress and Settings pages. Add GET /api/progress, GET/PUT /api/settings. Make the daily scheduler respect daily_word_count and weak phoneme review weighting.
```

第四轮 Codex 任务：

```text
Expand the seed content format and add at least 100 reviewed beginner words with ipa_us, meaning_zh, phoneme_tags, and difficulty_tags. Add content validation tests and a coverage report by phoneme.
```

## 18. 最终推荐实现边界

第一版的成功标准不是功能多，而是下面几个条件同时成立：

1. 手机打开即练；
2. 每天 10 个词流程顺畅；
3. 学习者先看 IPA，而不是先看单词；
4. 音频可以用于自我验证；
5. 系统按 phoneme 记录掌握情况；
6. 错得多的音会被更多复习；
7. 家长/老师只需偶尔改配置；
8. 数据和部署足够简单，开源用户可以自部署。

如果上述条件成立，“小音标”就已经完成了它的核心使命：用一个小而干净的词库，帮助小朋友完成阶段性的英语音标学习。
