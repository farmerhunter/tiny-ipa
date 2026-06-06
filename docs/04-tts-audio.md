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

推荐 VPS 目录：

```text
/opt/tiny-ipa/
  backend/
  frontend/dist/
  data/tiny_ipa.sqlite
  content/
  audio/
    us/
    uk/
```

Nginx：

```nginx
location /audio/ {
    alias /opt/tiny-ipa/audio/;
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
