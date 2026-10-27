# UX Research and Practice Experience Optimization

This document defines a repeatable UX research and optimization workflow for Tiny IPA. It is written as a project asset, not a one-off M10 checklist, so the same pattern can be reused in later milestones or other learner-facing apps.

## Purpose

Tiny IPA is a youth-facing learning product. UI quality is not only a matter of polish; it affects whether learners understand the practice loop, stay oriented after mistakes, trust feedback, and want to come back without pressure.

M10 should therefore improve the experience through evidence-grounded research, walkthroughs, and scoped experiments rather than ad hoc redesign.

## Core Principle

Every UX change should pass through this loop:

```text
scenario contract
  -> walkthrough or observation evidence
  -> finding synthesis
  -> scoped design or implementation issue
  -> browser/manual verification
  -> explicit accept, defer, or follow-up decision
```

The goal is repeatable judgment. A design decision is stronger when future contributors can see the user scenario, the evidence, the tradeoff, and the verification path.

## Target Learners

Primary audience:

```text
teen or pre-teen English learners
mobile-first usage
limited IPA confidence
short attention windows
needs clear feedback after mistakes
may use Chinese meanings as support
```

Secondary audience:

```text
parents or tutors checking progress
adult English beginners using the same practice loop
project maintainers reviewing UX changes
```

M10 should avoid optimizing only for developer convenience or adult productivity-tool expectations.

## Capability Stack

Use these skills and project practices as complementary roles:

```text
frontend-workflow-designer
  Owns scenario contracts, action semantics, state transitions, and walkthrough gates.

frontend-design
  Owns visual direction exploration, typography, palette, interaction mood, and interface copy quality.

web-design-guidelines
  Reviews UI code against web interface guidelines, including focus states, semantic controls, touch ergonomics, motion, copy, and content handling.

webapp-testing
  Provides local Playwright walkthroughs, screenshots, browser logs, and repeatable interaction evidence.

agent-collaboration
  Keeps GitHub issues, execution contracts, review handoffs, and Project state coherent.
```

No standalone accessibility skill is required for M10 setup, but accessibility concerns still remain in scope through `web-design-guidelines`, manual review, and browser walkthroughs.

## External Skill References

This methodology may reference external skills without importing them into the project or treating them as Agent Foundry-native assets. External skills remain optional, reviewable dependencies that a target environment can install during asset refresh or setup.

Recommended external references:

```text
frontend-design
  Source: anthropics/skills@frontend-design
  Purpose: visual direction exploration, typography, palette, interface tone, and non-template UI critique.
  Requirement: recommended, not mandatory.
  Fallback: use the design exploration gate in this document with local design judgment and screenshots.

web-design-guidelines
  Source: vercel-labs/agent-skills@web-design-guidelines
  Purpose: UI/code review against web interface guidelines, including focus, semantic controls, copy, touch ergonomics, motion, and content handling.
  Requirement: recommended, not mandatory.
  Fallback: manually review against the rules captured in the current project and any locally available UI checklist.

webapp-testing
  Source: anthropics/skills@webapp-testing
  Purpose: repeatable browser walkthroughs, screenshots, traces, and local webapp interaction evidence.
  Requirement: recommended for browser evidence, not mandatory for methodology adoption.
  Fallback: use the existing project Playwright setup or documented manual viewport walkthroughs.
```

Readiness states:

```text
ready
  The external skill is installed and its entry instructions can be read.

optional missing
  The skill is not installed, but the methodology can proceed with the documented fallback.

blocked
  The task explicitly requires that skill's capability and no local fallback is acceptable.
```

Future reusable Agent Foundry assets should declare these references instead of vendoring external skill contents. Asset refresh or installation can then show the missing references, trust notes, and suggested install commands while leaving the final install decision to the target environment.

## Research Units

Use small research units instead of broad redesign themes. Each unit should name:

```text
learner goal
starting state
successful completion state
primary path
alternate path
empty or failure state
evidence required
decision owner
implementation boundary
```

Recommended first units:

```text
Today practice orientation
mistake review and recovery
Entry/Mid level switching
Progress motivation and fatigue
Settings clarity
audio playback confidence
```

## Evidence Types

M10 accepts several evidence types, but each finding must say which type it uses.

```text
browser walkthrough
manual observation note
annotated screenshot
Playwright trace or screenshot
copy comprehension note
design review finding
user or parent/tutor feedback
```

Evidence should capture what the learner experiences, not only whether a component renders.

## Finding Format

Each UX finding should use this shape:

```text
Finding:
Impact:
Evidence:
Affected flow:
Likely cause:
Decision needed:
Recommended next issue:
Risk if deferred:
```

Findings should not directly become code changes until the scope and acceptance path are clear.

## Design Exploration Gate

Visual exploration should happen before large UI rewrites. A design direction proposal should include:

```text
audience fit
tone words
palette tokens
type roles
interaction signature
mobile constraints
what it deliberately avoids
screens or flows affected
acceptance questions
```

For Tiny IPA, useful directions should feel encouraging, clear, and memorable without becoming childish, noisy, or coercive.

## Browser Walkthrough Gate

Every accepted UX implementation issue should define a walkthrough path before coding starts.

Minimum walkthrough fields:

```text
viewport
seed data or fixture state
entry URL
steps
expected visible copy
expected available actions
expected blocked or hidden actions
screenshots or trace required
failure states covered
```

If the flow cannot be automated yet, record the manual path and the reason automation is deferred.

## Repeatable M10 Walkthrough Harness

Issue #176 adds a repeatable browser harness for M10 UX observations:

```bash
cd frontend
pnpm test:e2e:m10
```

The harness runs desktop Chromium and Pixel 5 Chromium projects with disposable route-mocked API data. It does not connect to the local backend and does not mutate `backend/tiny_ipa.sqlite`.

Evidence output:

```text
frontend/test-results/m10-walkthrough/
frontend/playwright-report/m10/
```

Scenario matrix:

| Flow | Viewport | Seed state | Entry URL | Expected visible copy | Expected actions | Hidden or blocked actions | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Today start | desktop and mobile | no active group; Entry selected; no completed groups | `/` | `Today practice hub`, `Entry selected`, `No active group` | `Start Entry group`, `Review recent mistakes`, `View Progress` | no practice question before start | `m10-today-start` screenshot attachment |
| Wrong answer feedback | desktop and mobile | Entry group with `ship` then `thin`; first answer deliberately wrong | `/` then `Start Entry group` | `Not quite`, `You picked`, `Correct IPA`, `Target sound` | IPA choices remain visible until auto-advance | current-group review is unavailable before summary | `m10-wrong-answer-feedback` screenshot attachment |
| Completion recovery | desktop and mobile | Entry group completed with one miss | same session | `Practice group complete`, `Misses from this group` | `Review misses from this group`, `Review recent mistakes`, `Start next Entry group`, `Return to Progress` | no current-review action when no miss exists in later review summary | `m10-completion-recovery-actions` screenshot attachment |
| Current-group review | desktop and mobile | source group has one missed item | summary action | `Current-group review: 1 / 1`, `Reviewing misses from the group you just finished.` | answer review item | raw group ids are not exposed | `m10-current-group-review` screenshot attachment |
| Recent mistake review | desktop and mobile | recent review source has one item | summary action | `Recent mistake review: 1 / 1`, `Reviewing recent mistakes from earlier practice.` | answer review item | current-group source copy is not reused | `m10-recent-review` screenshot attachment |
| Progress focus entry | desktop and mobile | Entry weak phoneme `/ʃ/` | Progress tab | `Progress`, `Needs practice in Entry`, `day streak` | `Focus /ʃ/`, `Clear focus` after focused practice starts | manual IPA entry is not required | `m10-progress-focus-entry` screenshot attachment |
| Settings level switch | desktop and mobile | active Entry group; selected level changes to Mid | Settings tab | `Saved`, `Mid selected`, `You selected Mid. This Entry group is still in progress.` | `Resume Entry group`, `End this Entry group and start Mid` | Mid content does not replace the active Entry group without explicit action | `m10-settings-mid-pending` screenshot attachment |
| Mid transition | desktop and mobile | active Entry group; Mid selected; confirmation accepted | Today hub action | `Practice group: 1 / 1`, `Mid practice group.`, `remember` | answer Mid item | old Entry item is no longer shown after the intentional switch | `m10-mid-active` screenshot attachment |
| Recent-review empty state | desktop and mobile | no active group; Mid selected; recent-review queue empty | Today hub | `No recent incorrect attempts are available for review.` | `Start Mid group` remains available | empty review does not replace the hub with a fatal error | `m10-recent-review-empty` screenshot attachment |
| Audio confidence signal | desktop and mobile | first Entry item has no static audio URL | active Entry group | audio button exposes `Play pronunciation (TTS)` | TTS-labeled audio button is visible | static-audio-only assumption is not required | covered in wrong-answer flow |
| Mobile Today and Settings | Pixel 5 Chromium | same mocked learner states as above | `/` and Settings tab | hub/settings copy remains visible; `Advanced/debug: manual IPA focus entry` remains observable | same actions as desktop | mobile does not hide core actions | `m10-mobile-today`, `m10-mobile-settings` screenshot attachments |

The M10 harness is a workflow-evidence harness, not a production API contract test. Backend scheduling, persistence, and import behavior remain covered by backend tests and by the live manual audit path recorded on #174.

## M10 Child Issue Pattern

Each M10 child issue should include:

```text
Parent Epic: #102
Roadmap: M10 UX Research and Practice Experience Optimization
Priority: P0/P1/P2
Owner role
Review role
Acceptance role
Dependencies
User-visible behavior or UX impact
Human verification needed
Implementation boundary
Completion handoff
Verification required
```

Child issues should separate research, design exploration, implementation, and readiness review when the decisions are meaningfully different.

## Completion Gate

M10 is ready to close only when:

```text
the research protocol is documented
key existing flows have walkthrough evidence
high-impact findings are accepted, fixed, or explicitly deferred
at least one visual direction decision is recorded
UX implementation changes preserve IPA-first practice and scheduler/progress boundaries
browser or manual viewport evidence exists for accepted user-visible changes
residual risks are documented on #102
```

M10 should not require production analytics, accounts, social features, or pressure-based gamification unless a separate product decision approves those boundaries.

## Reuse Checklist

For future projects, reuse this workflow by replacing only:

```text
target learner or user group
core product flows
evidence types available
design tone constraints
completion gate
```

Keep the research loop, finding format, walkthrough gate, and issue pattern intact unless the project has a better local workflow.

## #316 听辨小课方案 v0.1（Human 已同意继续，离线候选）

目标：让初学者在不先看到 IPA/释义提示的情况下，听录音区分一个具体对立；
结果只说明这组材料的首答表现。方案可先完成离线原型及自动化验证，人工试用
和教学效果判断继续延期。没有本轮上线、账号管理或录音评分范围。

### 审计决定的前置条件

- 先修复同一 session item 重放可重复计分的问题，验证并发、重试及组完成边界。
- 先为13词标签丢失制定修正及历史统计处理方案；首个小课候选不使用这些词。
  不自动重算已有学习记录，也不修改已审定音频清单。
- 现有 whole-answer `phoneme_stats` 不是听辨诊断。小课首答与讲解后再答单独呈现，
  第一版不把小课结果写入现有 mastered/weak 统计或改变 Today 调度。
- 原始素材作者同为 Dvortygirl 的记录不是已验证同一说话人的证据。候选启用前
  必须核对实际录音的词、口音、有序音位和明显音量/录制线索；不能把由文件名、
  拼写或不同声音猜答案当作学会音位对立。现有 hash/解码检查仅证明素材完整可播。

### 推荐的第一课：/k/ 与 /g/，先做四词八题

| 阶段 | 素材 | 学习者看到/听到什么 | 结果含义 |
|---|---|---|---|
| 示范 | came / game | 可切换播放两词，揭示 IPA 和一条简短对比提示；不计分 | 了解操作及本课目标 |
| 练习4题 | came / game，每词2次 | 先点播放，再在两词中选择；选项位置与录音顺序平衡 | 仅统计每题首答，显示即时反馈 |
| 换词检查4题 | back / bag，每词2次 | 换新词组与词尾位置；前面不提供这对词的示范 | 探索跨词/位置表现，不称迁移能力已证实 |
| 完成 | 本组摘要 | “首答正确 x/8”；分开展示前4题与后4题，可重听错题或结束 | 不显示掌握认证、等级或排名 |

这四词现有 US 音频齐全，均不在13词标签异常集合中。第一课选择它们是因为
素材和可核对的对立关系足够小，方便验证产品闭环；不代表 `/k/-/g/` 已被证明
是所有目标儿童最需要的训练。每词出现两次仍不构成独立能力测量。

后续候选：three/tree（`/θ/-/t/`），ship/shop（`/ɪ/-/ɑ/`）。每对目前只有一组词，
优先作为下一课示范候选；增加对应对立的其他词后，才讨论跨词检查。暂不直接
扩至整个 Core300 或宣称完成高变异语音训练（HVPT）。

### 一条完整使用路线

起点：已登录、Today hub 无进行中的小课，现有普通练习与设置照常可用。
提议在 hub 增加独立“听辨小课（试验）”入口，不改变当前 practice_mode 设置。

```text
进入小课 -> 查看目标 -> 两词示范 -> 开始8题
  -> 点播放 -> 选择 -> 首答反馈 -> 可重听/揭示对比 -> 下一题
  -> 换词检查 -> 本组摘要 -> 重听错题 或 返回Today
下次进入：恢复同一未完成小课；完成后主动“再练一组”才生成新组
```

| 状态/事件 | 可用动作及界面反馈 | 计分/持久化边界 |
|---|---|---|
| 未播放 | 播放；答案先不可提交 | 不记 attempts |
| 播放中 | 等待播放结束；离开可暂停 | 同时只播一段，播放不计分 |
| 可作答 | 二选一；重播 | 首答只保存一次 |
| 首答已保存 | 显示正确词、IPA及对比；重听或下一题 | 同题再点/请求重试不得重复累计 |
| 录音缺失/失败 | “录音暂不可用”，可重试或退出 | 不计错、不自动用不受控TTS替代题目 |
| 提交失去响应 | 正在确认；可重试 | 同 item 重试返回已保存结果，不生成第二条首答 |
| 中途退出/刷新/重登 | 保存处恢复，标明剩余题数 | 保留已提交结果；未提交选择不算答过 |
| 完成后重听错题 | 明确“练习回放，不计入首答分数” | 不覆盖首答、不增加 mastered 统计 |
| 主动再练 | 新组、重新说明统计范围 | 历史组保留，重复词不冒充新能力证据 |

复用现有认证、内容与静态音频服务；lesson 分组、首答和恢复的 domain/API 边界
在方案接受后再收敛，保持小课与普通组的可区分性。不能仅在前端隐藏重复提交按钮
或增加一个选项，就把后端一次计分、恢复和统计归属视为已解决。

### 后续实现的验证与本次 review 决策

自动化验收应覆盖上述完整路线：实际录音播放才能作答、答对/答错反馈、选项与
顺序平衡、技术重试和并发一次计分、播放失败不计错、刷新/重登续做、完成摘要、
回放与新组，以及现有普通练习/统计不被污染。使用临时库与合成账号，不要求
Human 参与工程验证；真实儿童体验、发音对齐和教学效果仍需后续明确证据。

研究依据：听辨训练值得探索，但研究效应不等于 Tiny IPA 的产品有效性；
多说话人和材料变异是独立设计变量，不在第一版同时加大难度。
[2025年79项研究的HVPT meta-analysis](https://www.cambridge.org/core/journals/studies-in-second-language-acquisition/article/high-variability-phonetic-training-hvpt-a-metaanalysis-of-l2-perceptual-training-studies/6ABB8C1F32D88D53EA8D05A4565E76F6)，
[儿童/成人变异训练对比研究](https://irep.ntu.ac.uk/id/eprint/32584/)。

请 review 的产品选择：是否接受先处理已发现计分/标签问题，再做上述四词八题的
`/k/-/g/` 小课原型；是否接受小课分数独立显示、暂不进入现有掌握度。接受方案只
授权后续范围规划，不代表已经授权上线、历史数据处理或人工试用。


#318 已准备首答重试保护和独立标签修正候选；线上尚未采用、历史统计未重算。
后续离线原型可以在临时库应用这两项前置修复后验证路线。素材语音核对、真实
学习效果及任何上线仍分别保留证据/批准边界。
