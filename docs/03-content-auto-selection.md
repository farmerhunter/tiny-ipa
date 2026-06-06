# 内容自动选词与 IPA 数据方案

## 目标

Tiny IPA 不希望依赖手工逐词查 IPA。内容可行性调研的目标是：

```text
自动生成 500-1000 个高质量候选词
  -> 自动带 ipa_us / ipa_uk
  -> 自动解析 phoneme_tags_us / phoneme_tags_uk
  -> 自动计算词频、复杂度、音位覆盖和筛选原因
  -> 自动选出 Core 100 / Core 300 候选
  -> 人工只做最终挑选、删除和少量抽检
```

这不是承诺零人工审核，而是把人工工作从“造词库”变成“挑候选”。

## 推荐数据源

### IPA

优先使用 `open-dict-data/ipa-dict`：

```text
en_US: General American
en_UK: Received Pronunciation style
```

参考：https://github.com/open-dict-data/ipa-dict

注意：该仓库主体与不同语种/来源可能有不同 license，内容构建报告必须保留 source 和 license metadata。不要把商业词典网页抓取作为数据源。

### 词频

优先使用：

```text
wordfreq Python package
SUBTLEX-US as optional validation or score boost
```

参考：

```text
https://pypi.org/project/wordfreq/
https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexus/
```

词频只用于生成候选，不直接决定最终 Core 列表。Tiny IPA 选词目标是音位覆盖，不是纯高频词榜。

### 中文短释义

中文短释义不从商业词典复制。推荐：

```text
机器初稿
  -> 规则压缩
  -> 人工改写或抽检
```

MVP 中中文释义只帮助确认意思，不承担词典义项完整性。

## 自动筛选流程

```text
load top N frequent English words
        |
        v
normalize words
        |
        v
join ipa-dict en_US and en_UK
        |
        v
apply hard filters
        |
        v
parse IPA into phoneme tags
        |
        v
score candidates
        |
        v
greedy select by phoneme coverage
        |
        v
write candidate_words.json and content_report.json
```

## Hard Filters

先用硬规则排除高风险词：

```text
not lowercase ascii word
contains space, hyphen, apostrophe, digit
too long for beginner stage
missing ipa_us
missing ipa_uk for dual-accent candidate pool
has too many pronunciation variants
IPA contains unsupported symbol
function word likely to have strong/weak form ambiguity
proper noun
offensive or age-inappropriate word
low frequency
```

MVP 可以分两类池：

```text
us_ready_pool: 必须有 ipa_us
dual_accent_pool: 必须同时有 ipa_us 和 ipa_uk
```

Core 100 主线来自 `us_ready_pool`，但优先选择也在 `dual_accent_pool` 中存在的词。

## 候选评分

建议评分：

```text
score =
  frequency_score
  + phoneme_coverage_score
  + difficult_phoneme_value
  + minimal_pair_value
  + spelling_simplicity_score
  + accent_stability_score
  - variant_penalty
  - function_word_penalty
  - abstract_meaning_penalty
  - ipa_complexity_penalty
```

其中 `phoneme_coverage_score` 权重最高。Tiny IPA 需要的是覆盖 `/ɪ/`、`/iː/`、`/æ/`、`/θ/`、`/ʃ/` 等目标音位的训练载体，而不是普通词频榜。

## 自动选 Core 300

推荐 greedy coverage algorithm：

1. 初始化目标音位覆盖需求。
2. 选择能补足最稀缺音位且总分高的词。
3. 每选一个词，更新 US phoneme coverage。
4. 对已经充足的音位降低收益。
5. 控制同类词、同韵词、同难点标签不要过度集中。
6. 输出 Core 100、Core 300 和 rejected list。

示例覆盖目标：

```text
/ɪ/  >= 20
/iː/ >= 20
/æ/  >= 20
/ʌ/  >= 15
/ʊ/  >= 10
/uː/ >= 15
/θ/  >= 8
/ð/  >= 5
/ʃ/  >= 10
/tʃ/ >= 10
/ŋ/  >= 8
/ɝ/  >= 6
/ɚ/  >= 6
```

实际目标应由 `selection_config.json` 管理。

## IPA 解析与口音字段

源词条建议结构：

```json
{
  "word_id": "ship",
  "word": "ship",
  "ipa_us": "/ʃɪp/",
  "ipa_uk": "/ʃɪp/",
  "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
  "phoneme_tags_uk": ["/ʃ/", "/ɪ/", "/p/"],
  "frequency_zipf": 4.5,
  "candidate_score": 82.4,
  "source_ipa_us": "open-dict-data/ipa-dict en_US",
  "source_ipa_uk": "open-dict-data/ipa-dict en_UK",
  "source_frequency": "wordfreq",
  "license_notes": "see source metadata",
  "selection_status": "auto_selected"
}
```

不要只存一份 `phoneme_tags`。例如 `car`：

```json
{
  "word": "car",
  "ipa_us": "/kɑr/",
  "ipa_uk": "/kɑː/",
  "phoneme_tags_us": ["/k/", "/ɑ/", "/r/"],
  "phoneme_tags_uk": ["/k/", "/ɑː/"]
}
```

如果未来打开 UK 对照，进度统计和题目生成必须基于当前 primary accent 的 tags。

## 输出报告

`select_candidates.py` 应输出：

```text
generated/candidate_words.json
generated/core_100_candidates.json
generated/core_300_candidates.json
generated/content_report.json
```

报告至少包含：

```text
input_word_count
joined_us_count
joined_uk_count
dual_accent_count
selected_count
rejection_reasons
phoneme_coverage_us
phoneme_coverage_uk
unsupported_ipa_symbols
top_missing_phonemes
license_summary
```

## 人工介入边界

人工工作只做：

```text
最终挑选 Core 100 / Core 300
删除不适合儿童的词
抽检重点音位和英美差异词
改写中文短释义
必要时添加 manual_overrides
```

不做：

```text
逐词查 IPA
逐词手工标 phoneme tags
逐词从商业词典复制释义
```

## 可行性实验

在正式开发前，建议做一个 disposable experiment：

```text
输入 wordfreq top 5000
加载 ipa-dict en_US / en_UK
生成 dual_accent_pool
输出 Core 300 候选和覆盖报告
人工快速浏览 50 个样本
```

验收问题：

1. 是否能得到 300 个同时有 US/UK IPA 的简单常见词？
2. 自动 IPA parser 的失败率是否低于可接受范围？
3. 稀缺音位如 `/ð/`、`/ʒ/`、`/ɚ/` 是否覆盖不足？
4. 候选词是否适合儿童和初学者？
5. License metadata 是否足够清楚？
