# Tiny IPA 设计文档索引

本文档集是 Tiny IPA 的阶段性设计合同。它补充 `tiny-ipa-dev-plan.md`，目标不是扩大 MVP 功能，而是把从 MVP 到后续扩展的技术路线一次画通，避免后续在内容、音频、调度、前端或部署边界上反复推倒重来。

## 设计原则

1. MVP 功能保持小，但架构边界要完整。
2. 内容源数据是长期资产，运行时数据库只是导入结果。
3. US / UK 口音差异从数据结构上预留，但 MVP 主线只承诺 US。
4. 音频运行时播放静态资源，TTS 生成发生在内容构建期或部署期。
5. 后端服务拥有调度、判题和进度语义；前端只消费领域摘要。
6. 自动内容管线优先，人工工作应集中在最终挑选和少量抽检。
7. 对外部数据、TTS、部署故障建立显式状态和诊断报告。

## 文档结构

1. [产品边界与领域模型](01-product-domain.md)
   定义 Tiny IPA 到底是什么、不是什么，以及稳定领域对象。

2. [系统架构与边界](02-system-architecture.md)
   定义内容层、构建层、运行时后端、前端、音频资产和部署边界。

3. [内容自动选词与 IPA 数据方案](03-content-auto-selection.md)
   定义如何自动找到少量高质量词汇，生成 US / UK IPA、phoneme tags 和候选评分。

4. [TTS 与音频资产方案](04-tts-audio.md)
   定义浏览器 TTS、VPS 预生成 mp3、静态音频托管和后续可替换路线。

5. [数据模型与 API 合同](05-data-api-contracts.md)
   定义 SQLite 表、源内容字段、API 返回摘要和服务端判题边界。

6. [Epic Roadmap](06-epic-roadmap.md)
   定义从可行性调研到 Core 300 及后续部署/UK 对照的 Epic 路线图和验收边界。

7. [风险、反思与待验证问题](07-risks-reflection.md)
   记录容易遗漏、容易范围缩小或过度工程化的地方。

8. [Multi-Agent Epic Workflow](08-multi-agent-epic-workflow.md)
   定义 Architect / Implementer 双 agent 协作、Epic/issue/branch/PR 粒度、评论路由和 merge 规则。

## 当前建议路线

Tiny IPA 的推荐主线是：

```text
开放词频与 IPA 数据源
        |
        v
内容自动选词与质量过滤
        |
        v
人工挑选 Core 100 / Core 300
        |
        v
内容校验、音频预生成、SQLite 导入
        |
        v
FastAPI 领域服务
        |
        v
React PWA 移动端练习
```

第一版实现时可以只打开一部分能力，但目录、字段和 API 边界应按这条路线设计。
