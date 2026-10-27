# TTS 与音频资产方案

## 目标

Tiny IPA 的音频目标是稳定、低成本、适合自部署。当前不追求商业级、多 provider、运行时弹性扩缩容。

核心原则：

```text
运行时播放静态音频
内容构建期生成或更新音频
前端只拿 audio_url
TTS provider 抽象后置
```

## 阶段路线

### 阶段 1：浏览器 TTS

用途：快速验证练习体验。

实现：

```text
frontend -> window.speechSynthesis -> device/browser voice
```

优点：

```text
不需要音频文件
不需要 VPS 生成
不需要云服务 API key
```

缺点：

```text
不同设备声音不一致
微信内置浏览器和 iOS 行为可能不稳定
发音质量不可控
```

结论：只用于 Milestone 1，不作为长期主方案。

### 阶段 2：VPS 预生成 mp3

用途：真实使用主方案。

实现：

```text
content/generated/core_words.json
        |
        v
generate_tts_audio.py
        |
        v
audio/us/ship.mp3
audio/uk/ship.mp3
        |
        v
Nginx /audio/
        |
        v
frontend Audio playback
```

运行时不请求 TTS 服务。用户点击播放时，只下载或播放已经生成好的 mp3。

部署目录形状由后续 Human-gated VPS run 决定；此处只保留 placeholder：

```text
<app-root>/
  backend/
<frontend-dist-dir>/
<data-dir>/tiny_ipa.sqlite
  content/
<audio-dir>/
    us/
    uk/
```

`TINY_IPA_AUDIO_DIR` 是音频目录的唯一 runtime variable。FastAPI 的本地
`/audio/` fallback 与后续 reverse proxy 都必须使用同一个 `<audio-dir>`。
`TINY_IPA_AUDIO_ROOT` 没有兼容 alias，不应写入部署环境文件。

Nginx template（仅供后续 Human 审阅，不授权写入或 reload）：

```nginx
location ^~ /audio/ {
    alias <audio-dir>/;
    add_header Cache-Control "public, max-age=31536000";
}
```

生成命令：

```bash
python backend/scripts/generate_tts_audio.py --accent us --only-missing
python backend/scripts/validate_content.py
python backend/scripts/import_words.py
```

### 阶段 3：有限 provider 替换

这个阶段靠后。它不是为了商业化，而是为了未来如果默认 TTS 质量、可用性或授权不理想，可以替换生成来源。

早期只需要脚本参数：

```text
TTS_PROVIDER=edge_tts
TTS_VOICE_US=en-US-JennyNeural
TTS_VOICE_UK=en-GB-SoniaNeural
```

不需要在应用运行时实现复杂 provider registry。

## 可选生成来源

### edge-tts

特点：

```text
脚本简单
通常不需要自己申请 Azure key
音质可接受
依赖外部在线服务
```

它不是纯本地方案。VPS 需要能访问外网。

### 正式云 TTS

例如：

```text
Azure Speech
Google Cloud Text-to-Speech
Amazon Polly
OpenAI TTS
```

特点：

```text
质量和稳定性更可控
需要账号、API key、计费和额度控制
适合未来替换，不适合作为 MVP 阻塞项
```

### 本地 TTS

例如：

```text
Piper
Coqui TTS
espeak-ng
```

特点：

```text
无云依赖
部署和模型管理更重
音质不一定适合儿童学习
VPS CPU 生成可能较慢
```

早期不推荐作为默认路线，除非外部服务不可接受。

## 数据字段

词条中保存：

```json
{
  "audio_us": "/audio/us/ship.mp3",
  "audio_uk": "/audio/uk/ship.mp3",
  "audio_status_us": "ready",
  "audio_status_uk": "missing",
  "audio_provider_us": "edge_tts",
  "audio_voice_us": "en-US-JennyNeural",
  "audio_generated_at": "2026-06-06T00:00:00Z"
}
```

状态建议：

```text
missing
queued
generated
ready
failed
disabled
```

## 质量控制

`validate_content.py` 应检查：

```text
Core 100 是否全部有 audio_us
audio_us 文件是否存在
音频文件大小是否异常
audio_url 是否和 accent 匹配
missing audio report
generation failed reasons
```

人工抽检优先级：

```text
minimal pairs
中国学习者难点音
US/UK 差异明显词
Core 100 高频使用词
```

## 不做运行时实时 TTS

不推荐：

```text
用户点击播放
  -> FastAPI 请求云 TTS
  -> 返回音频流
```

原因：

```text
延迟高
成本不可控
错误会影响学习流程
API key 风险更高
个人 VPS 没必要
```

Tiny IPA 的推荐方式是：

```text
内容更新时生成一次
日常学习时播放静态文件
```

## Core100 扩展候选包（#314）

本轮保留 M14 的十文件 manifest 和原始 Core100 内容作为历史输入，新增独立
`deploy/jingyun/core100-content-audio.manifest.json` 候选。目标覆盖 99/100 个美式
单词录音；原十个 MP3 字节及既有来源声明保持不变，其余来自逐文件核验的
Wikimedia Commons MP3 转码。授权、作者/未具名状态、原始文件页、license URL、
来源/输出 checksum、转换说明保存在 manifest 与 attribution 中。

`wood` 只有未确认美式口音的候选来源，本包不将澳式或未确认地区录音标为美式。
它在候选内容中的 `audio_us` 仍为 `null`。缺口保存在 `build.missing_word_ids`，
不会伪装成 Core100 全量音频，也不依赖 Human 此时提供试用反馈。

以下操作只构建本地候选，不安装到 VPS，不修改线上数据库/账户：

```bash
uv run --project backend python backend/scripts/prepare_core100_audio.py \
  --allow-download --check-media \
  --report content/generated/core100-audio-validation.json
cd frontend
pnpm test:e2e:core100-real
```

首次准备会按固定 URL/checksum 下载公开文件；Commons 请求串行并保留间隔。
已有十文件可从本地 `audio/us/` 复用，否则使用其已部署静态 URL 取得相同字节。
命中缓存后，无需 `--allow-download` 即可重复构建。不同 checksum 的既有文件
一律保留并报错，不自动覆盖。不存在生产安装模式；音频输出只允许本地候选或
系统临时目录。`--check-media` 需要 ffmpeg/ffprobe，逐文件验证 MP3 解码、时长、
采样率和非静音；这是媒体完整性证据，不是人工发音或教学质量验收。

本地生成物：

- `audio/core100-candidate/us/` 与公开用 `ATTRIBUTION-4634c26243c49ad5.md`；
- `content/generated/core_100_audio_candidate.json`（仅根据可用资产派生音频字段）；
- `content/generated/core100-audio-validation.json`（显式命令请求的原始验证结果）。

`test:e2e:core100-real` 使用临时 SQLite、新建的合成账户、真实 FastAPI、Vite
同源 API/audio 代理和 Chromium 的原生播放器，不 mock API、媒体数据或播放结果。
测试覆盖未登录拒绝、12词练习、真实新录音播放、提交、刷新后续做、登出/重登、
完成后 Progress 与 attempts 不重复、不丢失。12个不同词确保练习组至少包含两个
不在旧十词包中的词。数据库路径必须是不存在的系统临时文件，禁止复用真实 DB。
真实流程现由 CI 的 `core100-real` job 自动执行。测试素材来自仓库内冻结包，
运行时不下载音频，也不请求线上站点；依赖安装和 Chromium 安装仍需要网络。

PR #315 已于 Human 审定清单后合并并上线：新增89条音频，线上覆盖99/100，
旧十文件与旧署名保持原样。执行及独立部署复核见 #314 的上线回执。后续
VPS 文件、数据库字段及运行配置变更仍须另列具体清单 review。无需为本轮
自动验证请求 Human 练习、视觉或教学反馈；这些验收保持延期。


### 受限音频字段激活候选

通用 `import_words.py` 会同时 upsert 默认 settings，后续线上激活不得直接重跑
该完整导入器。`backend/scripts/activate_core100_audio.py` 默认仅生成只读计划：

```bash
uv run --project backend python backend/scripts/activate_core100_audio.py \
  --manifest deploy/jingyun/core100-content-audio.manifest.json \
  --repo-root . --audio-root audio/core100-candidate \
  --db <reviewed-existing-db>
```

计划绑定 manifest hash、当前全部词条的 id/word/ipa_us/audio_us 状态 hash，逐项列出
89 个预期从 null 增加为静态 URL 的字段。只允许缺失音频的新增，不允许覆盖既有
自定义 URL、改变词条 ID/拼写/IPA、写设置/用户/练习表。未来获得具体线上清单
批准后才可使用 `--apply-plan-sha256 <reviewed-plan>`；它在一个 IMMEDIATE 事务中
重算计划并逐行检查更新数，任何漂移即回滚。该参数只是绑定被审对象，不代表
Human 已同意执行。#314 已在单独批准的线上执行中验证这一受限事务；
后续执行不继承该次授权。

真实浏览器 fixture 从原十音频状态导入新建临时库，先保存12词自定义设置，再
通过这同一受限事务启用89条URL，确认设置未被重置后启动实际后端，连接了
“候选资产→词库字段激活→真实播放/答题/持久化”的路径。


新署名URL为 `/audio/ATTRIBUTION-4634c26243c49ad5.md`，文件名绑定其内容hash，
适配现有 `/audio/` 的长期immutable缓存。线上原 `ATTRIBUTION.md` 保持原样，
无需替换或Nginx改动；旧客户端可继续使用原十录音及旧署名，新包/清单使用新的
版本化署名。verifier同时支持历史固定文件名与hash匹配的新文件名，其余路径拒绝。


### CI 冻结音频素材（#316）

`frontend/tests/fixtures/core100-media.zip` 包含同一 manifest 对应的99个原始 MP3
以及版本化署名，压缩包1,381,455字节。来源、作者、许可和转换说明保留于
`deploy/jingyun/core100-content-audio.manifest.json` 和
`deploy/jingyun/core100-audio-attribution.md`；这些许可同样适用于素材包内文件。
压缩仅用于存储，未重新编码音频，包内每个文件仍按 manifest 的 SHA-256 校验。

测试 fixture 会先验证完整成员白名单（含重复/额外成员）、字节数、音频及署名
hash，再将音频写入新建的临时 cache，交给已有 candidate preparer；不执行
`extractall`、不允许未审定替换，不用真实站点补齐损坏或缺失文件。
CI 覆盖的是录音完整性、真实播放及练习持久化，不是人工发音或教学效果验收。
