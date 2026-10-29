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

## M8 Core 1000 source feasibility evidence

#123 re-ran the source feasibility question for Mid/Core 1000 as a read-only
probe over the existing generated candidate pool and curated Core 300 runtime set:

```bash
python3 backend/scripts/probe_core1000_feasibility.py
python3 backend/scripts/probe_core1000_feasibility.py --json
```

The probe does not write generated content and does not promote a Core 1000
runtime set. It estimates syllable count from IPA vowel nuclei, which is good
enough for source selection evidence but not a final learner-facing
syllabification model.

Observed evidence from the checked-in `content/generated/candidate_words.json`
and `content/core_300_words.json`:

```text
candidate_pool_count: 3792
candidate_pool_syllables: one=1603, two=1787, three_plus=402
candidate_pool_multisyllable_count: 2189
core300_runtime_count: 300
core300_syllables: one=94, two=135, three_plus=71
naive_score_top1000_syllables: one=909, two=90, three_plus=1
top1000_traceability gaps: missing_ipa_us=0, missing_source_ipa_us=0,
  missing_source_frequency=0, missing_license_notes=0, missing_uk_ipa=71
```

Recommendation for #124:

```text
Proceed with the existing wordfreq + open-dict-data/ipa-dict pipeline.
Add syllable-aware Core 1000 ranking/rebalance reports instead of taking the
current candidate_score order directly.
Keep CMUdict as an optional US-only cross-check/fallback, not the primary Mid
source, unless #124 adds an ARPABET-to-IPA conversion gate and UK/accent
traceability plan.
```

Why not switch primary source to CMUdict for #124:

```text
CMUdict has permissive source terms and is useful for US pronunciation
cross-checking, but it is ARPABET and US-only. Making it primary would add
conversion risk and would not solve UK/accent metadata. The current ipa-dict
path already carries direct US/UK IPA fields and source metadata.
```

Source/license traceability notes:

```text
ipa-dict: https://github.com/open-dict-data/ipa-dict
  repository says MIT unless otherwise specified; English US/UK credits include
  derived source notes that generated reports should preserve.
wordfreq: https://github.com/rspeer/wordfreq
  code is Apache-2.0; NOTICE documents data attribution/share-alike details.
CMUdict: https://github.com/cmusphinx/cmudict
  permissive CMU source license with origin acknowledgement request; US ARPABET only.
```

Residual risks for #124/#125:

```text
naive candidate_score order underweights multi-syllable words
syllable counts are heuristic IPA vowel-nucleus estimates
STRUT and r-colored vowels already required manual overrides in Core 100/300
some high-frequency candidates are acronym-like or too abstract for learners
meaning_zh remains absent in generated candidates and needs curation
ipa-dict and wordfreq source/license notes must stay in generated reports
```

## M8 Core 1000 candidate generation and rebalance report

#124 extends `backend/scripts/select_candidates.py` so the same reproducible
pipeline still writes Core 100 / Core 300 outputs and additionally writes:

```text
core_1000_candidates.json
core_1000_report.json
```

Recommended dry-run command:

```bash
uv run --project backend --extra content python backend/scripts/select_candidates.py \
  --top-n 5000 \
  --ipa-dict-dir content/sources/ipa-dict \
  --selection-config content/selection_config.json \
  --core-300-reference content/core_300_words.json \
  --output-dir /tmp/tiny-ipa-core1000
```

The generated output is candidate/report evidence only. It must not be imported
or promoted as runtime Mid content until #125 curation accepts it.

Core 1000 selection is syllable-aware. It uses bucket targets instead of taking
the current `candidate_score` top 1000 directly:

```text
one: 250
two: 500
three_plus: 250
```

Observed #124 dry-run evidence:

```text
input words: 5000
joined US IPA: 4930
joined UK IPA: 4302
after hard filters: 3792
Core 100 generated: 100
Core 300 generated: 300
Core 1000 generated: 1000
Core 1000 syllables: one=250, two=500, three_plus=250
Core 1000 multi-syllable: 750 / 1000 = 75.0%
Accepted Core 300 reference multi-syllable: 206 / 300 = 68.7%
```

`core_1000_report.json` also preserves:

```text
rejection_reasons
candidate_pool_syllable_distribution
naive_score_top1000_syllable_distribution
accepted Core 300 reference distribution
generated Core 300 distribution
Core 1000 phoneme coverage
top missing phonemes
sample candidates by syllable bucket
quality review flags
runtime_content_promoted = false
```

#125 curation recommendation:

```text
Use core_1000_candidates.json as the Mid curation starting point.
Review acronym-like/no-vowel words, very short words, missing UK IPA entries,
missing meaning_zh, child/learner appropriateness, and known STRUT/r-colored
vowel override risks before promoting any runtime Core 1000 file.
```

#125/#126 Mid runtime curation and level-aware validation:

```bash
uv run --project backend python backend/scripts/select_candidates.py \
  --top-n 5000 \
  --ipa-dict-dir content/sources/ipa-dict \
  --selection-config content/selection_config.json \
  --core-300-reference content/core_300_words.json \
  --output-dir /tmp/tiny-ipa-core1000

uv run --project backend python backend/scripts/curate_core_1000.py \
  --candidates /tmp/tiny-ipa-core1000/core_1000_candidates.json \
  --pool content/generated/candidate_words.json \
  --mid-meanings content/core_1000_meanings_zh.json \
  --output content/core_1000_words.json \
  --report content/core_1000_curation_report.json

uv run --project backend python backend/scripts/validate_content.py \
  content/core_1000_words.json --content-level mid
```

The promoted Mid runtime file uses `mid_<source_word_id>` IDs so importing
Core1000 does not overwrite existing Entry/Core300 rows. The compact curation
report records:

```text
runtime_content_promoted = true
core_1000_count = 1000
syllable distribution = one 250 / two 500 / three_plus 250
multisyllable = 750 (75.0%)
missing UK IPA = 53 warning-only entries
meaning_zh placeholders = 0
meaning_zh curated Mid meanings = 845
phoneme overrides = 13 accepted STRUT/r-colored overrides reused from Core100
```

`content/core_1000_words.json` is a runtime/source artifact for Mid import.
`content/core_1000_curation_report.json` is intentionally compact review
evidence, not the raw generated candidate report. #127 still owns runtime
settings/scheduler/API/UI level selection.


## Core100 内容与听辨准备审计（#316）

运行 `backend/scripts/audit_core100_learning.py` 可从冻结 Core100 与扩充音频
manifest 重建审计结果。当前 schema validator 返回零 errors；它检查标签是否合法，
并不证明每个词的标签完整、音频与 IPA 一致或教学正确。

- 100词中99词有扩充 US 音频，`wood` 保持不可用；99词的声明标签覆盖41音位，
  但 `/ð/` 只有1词，`/θ/` 只有4词。这是标签覆盖，不是听辨训练充分性。
- 13词存在超出已说明元音记法转换的标签丢失：bus、cup、cut、fun、jump、luck、
  paper、river、run、sister、sun、teacher、water。所有词都有既有人工修正说明；
  但例如 bus 的 `/b/、/s/`、paper 的 `/p/、/eɪ/` 被删掉，不能用
  `/ə/→/ʌ/` 或 `/ɝ/→/ɚ/` 的说明豁免。审计分别列出可解释转换与未解释丢失，
  不自动重写这些来源资产、冻结 manifest 或线上数据。
- 现有 choose_word scorer 对100词都能提供3个干扰项，没有 fallback；
  knew/new 的相同 US IPA 被识别并排除互作干扰项。这只证明四选一结构，
  不是严格最小对立、音位诊断或录音可辨性。
- IPA parser 会去重音位，因此不能直接用输出标签序列证明两个词只相差一个音；
  音源页面作者也不等于已验证的说话人身份。听辨候选需另核对有序音位、
  重音、音节、实际录音及口音；不能把文件 hash 正确当作这些问题已通过。

修复标签和重新发布内容需保留来源、明确修正规则、重跑覆盖/干扰项报告，
并单独 review 线上词库与既有统计的处理清单。优先修复这些已定位问题，再
扩充常见易混音所需的少量词和同口音音频，不以词数增长替代训练覆盖。


### #318 修正候选与冻结来源

保留 `core_100_words.json` 和已有音频 manifest 的历史字节；新增小型
`core_100_phoneme_corrections.json` 只列13词的 before/after。派生候选保留
全部解析音位，再按这些词既有说明进行 /ə/→/ʌ/、/ɝ/→/ɚ/ 转换，例如
bus 为 /b,ʌ,s/，paper 为 /p,eɪ,ɚ/。审计 JSON 分开报告冻结源的历史问题和
`corrected_candidate` 的结果，后者未解释标签差异为零。
这不等于完成录音/IPA人工核对，也不自动改 Core300/Core1000 或真实 DB。
使用 `uv run --project backend python backend/scripts/correct_core100_tags.py`
可在 stdout 检查完整候选；临时测试按13项补丁应用后验证其他字段和历史表不变。


### Core300 / Core1000 来源审计（#322）

运行 `uv run --project backend python backend/scripts/audit_core100_learning.py --all-packs`
重建两个等级的来源审计；CI 加 `--probe-attempts`，报告与输入 hash 保存在既有
`core100-learning-audit` artifact。此处审计仓库来源，不推断线上 DB 与来源相同。

- Core300：300词，`feb` 已 disabled，choose_word 实际检查299个有效目标；
  Core1000：1000个有效目标。两包有效目标均有3个干扰项、无 fallback；
  同 IPA 干扰项排除仍有效，但不等于声学可辨性已经验证。
- Core300 来源仍有同样13词丢失辅音/其他元音标签，恰好匹配现有 Core100
  修正的 before 值。已上线的13词修复不代表这些冻结来源文件已更新。
- Core1000 的13项差异是 mid_run/love/fun/cut/cup/father/teacher/water/paper/
  better/letter/sister/river；也存在非目标音位丢失。其逐词说明使用
  `phoneme_override_note`（没有前导下划线）；此前审计遗漏了这个字段。修订审计
  读取两种说明，但仍能识别丢失的辅音/其他元音；不跨 mid_ ID 应用 Core100 补丁。
- Core300 的300个 audio_us 是来源 URL 引用，其中99个与现有许可包的 ID+URL
  绑定，其余201个没有本包证据；Core1000 的 audio_us 全为空。URL、planned
  状态、同名词或 source_word_id 都不能当作已安装录音的证明。
- 两包均没有 minimal_pair_group 元数据；现有 Sound Compare 在这些来源下
  不具备启动内容。真实浏览器回归检查明确的不可用提示与零新增作答。
- UK 标签差异分别为30/221词，均涉及现有 parser 未识别符号。parser 是现有
  US 归一化工具；这些是待分流的报告，不应直接计为30/221条内容错误。

后续建议：先为两个等级制作有来源绑定的 US 标签修正候选，保留冻结资产及
历史统计；再为一个小范围声音对比补足经核对的配对元数据。录音/IPA一致性、
说话人和教学效果仍未通过人工验证；不自动发布内容或启用线上听辨小课。


### Core300 / Core1000 标签候选与导入保护（#324）

`core_300_phoneme_corrections.json` 与 `core_1000_phoneme_corrections.json`
分别绑定冻结来源 hash、13词的 ID/IPA/before/after 及原有逐词说明。候选保留
全部已解析音素，只应用已说明的 STRUT/r-colored 记法转换；原始词库字节、UK
标签、音频、释义、等级和历史数据不重写。可以无数据库地检查派生候选：

```bash
uv run --project backend python backend/scripts/correct_expanded_tags.py --pack 300
uv run --project backend python backend/scripts/correct_expanded_tags.py --pack 1000
```

通用 importer 对精确匹配冻结来源的文件（包括原样复制的文件）自动派生13项
修正后再验证/导入，返回 `tag_corrections` 来源信息；修改过的原始路径拒绝
导入，需另审新的来源绑定。任意来源的旧/缺失标签不能覆盖库中这些已修正行，
此检查不能用 `--skip-validation` 绕过，检查与写入使用同一 IMMEDIATE 事务，
拒绝时没有领域数据写入。新的自定义内容仍走现有校验，不声明它已获教学验收。

重复导入保留已有 default 设置；仅缺少设置时创建默认值。测试在临时库上
证明非空 session/items/attempts/stats 和设置完整保留，未对线上库运行 importer。
`--all-packs` 审计同时报告冻结来源问题与 corrected_candidate；两个候选的
未解释 US 标签差异为零，不代表录音/IPA 或教学效果已通过人工验证。


### 四组声音对比开发候选（#326 / #334）

`content/sound_compare_pairs_candidate.json` 保留 came/game（词首）与 back/bag
（词尾）两组 /k/-/g/ 配对，并在 #334 增加 cat/hat 的词首 /k/-/h/、map/match
的词尾 /p/-/tʃ/。/tʃ/ 是既有 inventory 的单个音素，不能拆成 /t/ 与 /ʃ/；新增
两组不作“仅清浊不同”的说明。每个成员绑定冻结 Core100/Core300 的 beginner
等级、ID/IPA/原始 null 配对字段和已有许可音频 manifest/hash，显式保存有序音素；
验证同为单音节、重音位置一致，且只有一个词首/词尾的已知音素不同，不使用
去重后的标签推断顺序，也不自动发现或生成任意配对。

```bash
uv run --project backend python backend/scripts/prepare_sound_compare.py --pack 300
```

此命令只输出“已修正标签＋8项 minimal_pair_group”的候选 JSON，不打开数据库、
不改冻结来源，也不成为默认 importer 输入。`--pack 100` 用于独立的真实浏览器
fixture；默认 fixture 仍验证 Sound Compare 暂不可用。需要显式 opt-in 的另一份
临时库才安装8项元数据，验证现有 Sound Compare 的正向流程。

这仍是既有 Word→IPA 题型及可播放录音的专项组，不是仅听录音答题的新题型。
配对候选最初只证明内容可接入既有流程。后续 #328 增加 Sound Compare 专用
规则，保证选项包含另一成员的 IPA；合同见 `05-data-api-contracts.md`。这仍
不等同于声学或教学有效性已被验证。
音频来源作者不等于说话人身份；未承诺同一说话人、声学一致性或教学效果。
未上线候选内容，听辨小课的 development-only 开关与独立计分保持不变。


### 全词库导入完整性（#330）

基础完整性检查不再只保护26个已修正词：所有输入记录都须为对象，身份为
无冲突、无重复的非空字符串；US 音素须为非空数组，UK 仍可缺省或为空。
已提供的数组只接受非空、无首尾空白、无重复的字符串。US 标签必须属于
inventory；UK 未知字符串仍保留既有 warning 策略，不在本次自动重写 UK 内容。
这些基础检查在 `--skip-validation` 下也执行；该选项只跳过其余语义检查。

词库校验复用同一数组检查，非法嵌套对象不会让统计崩溃；覆盖计数按每词
每音素一次计算，不因重复标签虚增。所有冻结来源及修正 overlay 保持原样。

导入的 schema 初始化、全部词条、音素 inventory 和缺失默认设置的创建都在
同一 IMMEDIATE 事务内。任何阶段失败即回滚整批，不再逐行报错后提交其他行。
报告含 `committed` / `rolled_back`，回滚后成功写入计数为零、`tables_created`
为空，CLI 明示事务状态；已有设置、非空学习记录和统计保持不变。提交时的
延迟 FK 约束失败也按失败处理。预检失败不打开 DB；写入阶段失败可能留下
空 SQLite 文件或引擎辅助文件，不承诺文件字节不变，不自动删除这些文件。
