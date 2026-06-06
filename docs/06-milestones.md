# 阶段计划与验收标准

## Milestone 0：可行性实验与架构骨架

目标：验证自动内容管线是否成立，并建立长期目录边界。

交付：

```text
content/ directory
backend/ skeleton
frontend/ skeleton
/api/health
select_candidates.py disposable experiment
candidate_words.json sample
content_report.json sample
```

验收：

```text
能从词频 + ipa-dict 自动生成候选词
能输出 US/UK IPA 和 phoneme coverage
能访问前端并调用 /api/health
```

## Milestone 1：静态练习闭环

目标：证明 IPA-first 练习体验。

交付：

```text
20-50 auto-selected words
/api/today from JSON or SQLite
TodayPractice mobile UI
IPA first -> reveal -> browser TTS/audio placeholder -> choose IPA -> feedback
```

验收：

```text
手机浏览器能完成 10 个词
单词初始隐藏
答题反馈正确
页面没有复杂跳转
```

## Milestone 2：SQLite 与服务端判题

目标：学习行为可持久化，统计按 phoneme 聚合。

交付：

```text
SQLite models
import_words.py
/api/attempt
attempts
phoneme_stats
server-side grading
```

验收：

```text
刷新后当天 session 不丢
提交答案后 attempts 有记录
phoneme_stats 正确更新
错误路径有稳定错误码
```

## Milestone 3：Core 100 自动候选与音频预生成

目标：从演示进入真实可用的最小内容集。

交付：

```text
Core 100 candidate set
audio/us/*.mp3
generate_tts_audio.py --only-missing
validate_content.py
Nginx /audio/ deployment note
```

验收：

```text
Core 100 全部有 ipa_us
Core 100 全部有 phoneme_tags_us
Core 100 全部有 audio_us 或明确 missing reason
validate_content 无 unknown phoneme symbols
手机播放的是静态 mp3
```

## Milestone 4：Progress 与 Settings

目标：形成个人学习闭环。

交付：

```text
/api/progress
/api/settings GET/PUT
Progress page
Settings page
daily_word_count 生效
```

验收：

```text
能看到今日完成、streak、weak phonemes、strong phonemes
修改 daily_word_count 后下一次 today 生效
primary_accent 字段存在但 UI 可先固定 US
```

## Milestone 5：调度增强

目标：从固定/随机练习变为音位驱动复习。

交付：

```text
new/review ratio
weak phoneme weighting
avoid short-term repeats
focus_phonemes internal support
scheduler tests
```

验收：

```text
某音位连续答错后，后续相关词比例上升
disabled words 不会被调度
同一词不会无故连续多日重复
```

## Milestone 6：Core 300 与内容报告

目标：覆盖一个阶段的音标训练。

交付：

```text
Core 300 candidate/core set
coverage report
minimal_pair_group
meaning_zh first pass
重点音位抽检记录
```

验收：

```text
主要 US phonemes 覆盖达标
难点音有足够词例
候选来源、license、rejection reasons 可追踪
人工只需要挑选和抽检，不需要逐词查 IPA
```

## Milestone 7：VPS 部署与备份

目标：真实手机可访问，并能长期自部署。

交付：

```text
Nginx
HTTPS
systemd backend service
frontend build
SQLite backup script
deployment.md
```

验收：

```text
域名 HTTPS 可访问
/api/health 正常
/audio/ 静态音频正常
服务重启后数据仍在
备份可恢复
```

## Milestone 8：UK 对照子集与专项练习

目标：在不改变主架构的情况下打开后续能力。

交付：

```text
UK reviewed subset
show_accent_compare
minimal pair practice
target phoneme practice
```

验收：

```text
US/UK phoneme stats 不混
UK 对照只在明确打开时展示
专项练习复用既有 question/grading/progress 边界
```

## 范围控制

每个 milestone 必须满足：

```text
只打开当前用户可验证的一段能力
不破坏内容源数据和 API 合同
不把未来 provider、账号、多租户提前实现
不把临时脚本结果当作长期源事实
```
