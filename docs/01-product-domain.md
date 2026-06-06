# 产品边界与领域模型

## 产品定位

Tiny IPA 是面向儿童和英语初学者的单用户音标练习应用。它的目标不是背单词、查词典或家庭教学管理，而是通过少量高质量初级词汇，让学习者反复经历：

```text
看 IPA -> 尝试读出声音 -> 揭示单词和音频 -> 完成简短辨识 -> 更新音位掌握状态
```

项目的长期成功标准是：学习者能围绕核心英语音位形成稳定识别能力，而不是累计记住多少单词。

## 非目标

MVP 和早期路线不做：

1. 完整词典查询。
2. 大规模背单词。
3. 商业词典网页抓取。
4. 多家庭、多租户、公开注册。
5. 家长 dashboard 或教师后台。
6. 原生 App 或微信小程序第一版。
7. 录音自动评分第一版。
8. 运行时实时云 TTS。
9. 复杂游戏化、社交、排行榜。

这些非目标不是永久禁止，而是避免当前产品被不相关复杂度吞掉。

## 稳定领域对象

Tiny IPA 的稳定对象包括：

```text
WordEntry
Phoneme
Accent
PracticeSession
SessionItem
Question
Attempt
PhonemeStat
Settings
AudioAsset
ContentCandidate
ContentBuildReport
```

其中最核心的是 `Phoneme` 和 `PhonemeStat`。`WordEntry` 是练习载体，不是学习目标本身。

## 独立变化轴

下面这些维度应独立建模，不能混成一个字段：

1. **口音**：US General American 与 UK/RP-style learning pronunciation 独立变化。
2. **内容源**：词频来源、IPA 来源、中文释义来源、音频来源各自独立。
3. **内容状态**：候选、自动校验通过、人工挑选、已导入、已禁用是不同状态。
4. **练习状态**：session 完成状态与单题 attempt 正误是不同状态。
5. **音位统计**：word_score 与 phoneme_score 是不同指标。
6. **音频生成**：生成 provider 与运行时播放 URL 是不同概念。

这意味着 `ipa_us`、`ipa_uk`、`phoneme_tags_us`、`phoneme_tags_uk` 应分开保存。MVP 可以只使用 US，但不应该把 UK 当作后面硬塞进去的扩展字段。

## 用户与角色

早期只有一个默认学习者：

```text
user_id = "default"
```

家长或老师不是独立业务角色，只是配置页的使用者。配置页可以有简单 PIN，但不引入账号体系。

## 核心体验状态

TodayPractice 页面至少有这些状态：

```text
Loading
EmptyOrNotReady
IpaOnly
Revealed
Answering
FeedbackCorrect
FeedbackWrong
Completed
Error
```

UI 不应散落判断这些状态。实现时建议引入轻量 ViewModel，让按钮可用性、显示内容和下一步动作由练习状态统一决定。

## MVP 主路径

MVP 只需证明这条主路径：

```text
打开手机页面
  -> 获取今日 10 个词
  -> IPA first reveal
  -> 播放音频或 TTS
  -> 服务端判题
  -> 记录 attempt
  -> 更新 phoneme_stats
  -> 显示完成摘要
```

所有架构设计服务于这条主路径，并为后续内容扩展、音频稳定化和调度增强保留边界。
