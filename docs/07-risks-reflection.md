# 风险、反思与待验证问题

## 反思：容易遗漏的点

### 1. MVP 小，不等于架构短

如果只做静态 JSON + 前端播放，很快能演示，但后面接 SQLite、音频、调度、UK 对照时会返工。正确做法是：

```text
实现切片小
边界设计完整
字段和目录为后续保留
```

### 2. 内容质量是最大风险

Tiny IPA 的关键不是 CRUD，而是内容资产：

```text
词是否适合儿童
IPA 是否统一
US/UK 是否分清
phoneme_tags 是否可解析
audio 是否稳定
中文释义是否短而准确
```

如果内容自动选词失败，后端和前端做得再好也只是空架子。

### 3. 双口音不能后补成单字段

`ipa_us` 和 `ipa_uk` 可以晚展示，但必须早建模。尤其是 `phoneme_tags_us` 和 `phoneme_tags_uk`，否则进度统计会混。

### 4. TTS provider 不该过早商业化

当前不需要复杂 provider registry。需要的是：

```text
运行时静态 audio_url
构建期 generate_tts_audio.py
validate_content 检查音频资产
```

以后要换 provider，再扩展脚本。

### 5. 题目干扰项不能完全随机

看单词选 IPA 的干扰项应围绕真实易混音生成，例如：

```text
/ɪ/ vs /iː/
/æ/ vs /e/
/θ/ vs /s/
/ʃ/ vs /s/
```

完全随机 IPA 选项会降低教学价值。

### 6. 功能词和弱读是陷阱

`the`、`of`、`to` 这类高频词不一定适合早期音标训练。自动选词不能等同于高频词列表。

## 待验证问题

### Content Feasibility

1. `ipa-dict` + `wordfreq` 是否能稳定产出 300 个简单、常见、同时有 US/UK IPA 的候选词？
2. IPA parser 能否覆盖候选词中的符号？
3. `/ð/`、`/ʒ/`、`/ɚ/` 等稀缺音位是否需要人工补词？
4. `ipa-dict` 的 license metadata 是否满足开源自部署项目使用？
5. 自动选出的词是否包含过多抽象词、功能词或成人语境词？

### Audio Feasibility

1. VPS 是否能稳定运行选定 TTS 生成工具？
2. 生成 Core 100 / Core 300 的成本和时间是否可接受？
3. 手机和微信内置浏览器播放 `/audio/*.mp3` 是否稳定？
4. Core 100 中 minimal pairs 的音频是否足够可辨？

### Product Feasibility

1. IPA-first 流程对儿童是否太抽象？
2. 每天 10 个词是否合适？
3. 中文释义是否应该默认显示？
4. Progress 页显示 weak phonemes 是否对儿童有激励，还是会造成挫败？

### Engineering Feasibility

1. SQLite + systemd 是否足够满足长期个人自部署？
2. 是否需要从一开始做备份和导入导出？
3. 前端是否需要离线 PWA，还是 HTTPS 在线访问即可？
4. 是否需要为内容构建脚本生成 debug bundle，方便未来 agent 复现失败？

## 风险登记

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 自动选词质量不足 | Core 300 不可用 | 先做 disposable experiment，输出候选样本和覆盖报告 |
| IPA 来源 license 不清 | 开源发布受限 | 记录 source/license，避免商业词典抓取 |
| US/UK 统计混淆 | 后续对照功能返工 | 从第一版保存 accent-specific tags 和 stats |
| 浏览器 TTS 不稳定 | 学习体验不一致 | Epic M3 切到 VPS 预生成 mp3 |
| TTS 过早抽象 | MVP 变重 | 只保留构建脚本参数，provider registry 后置 |
| 调度算法过早复杂 | 难以测试 | 先做错题复现，再做 weak phoneme weighting |
| 内容脚本失败不可复现 | 后续维护困难 | 输出 content_report 和 rejection reasons |

## 立即建议的下一步

先做一个内容可行性 spike，而不是直接搭完整产品：

```text
1. 拉取或安装 wordfreq 与 ipa-dict 数据
2. 用 top 5000 英文词生成候选
3. join en_US / en_UK IPA
4. 解析 phoneme tags
5. 输出 Core 300 candidate report
6. 人工快速浏览样本
```

如果这个实验成立，Tiny IPA 的最大不确定性就下降很多。随后再进入 FastAPI + React 骨架实现，会更稳。
