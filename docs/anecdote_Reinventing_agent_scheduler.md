# Vibe Coding 中的老登式多 Agent 调度经历

（本文是 [`anecdote_Introducing_view_model.md`](https://github.com/farmerhunter/token-panic/blob/main/design_docs/anecdote_Introducing_view_model.md) 的延续。

上一篇故事发生在开发 token-panic 时。这一篇故事已经换到了新项目 tiny-ipa：<https://github.com/farmerhunter/tiny-ipa>。

本文主要由 Codex 撰写（照例感谢）。）

上一篇讲到最后，我已经隐约意识到，所谓 vibe coding，并不是把需求扔给一个万能 AI，然后自己去喝咖啡。

更真实的画面是：一个 agent 写得快，容易局部最优；另一个 agent 稳一点，擅长抽象、review、总结；人类夹在中间，判断方向、调节火候、决定什么时候该停下来揉面。

那时这还只是一个朦胧的感觉。

到了 tiny-ipa，这件事开始长出骨架了。

## 一、老登开始领导两个 Agent 干活

tiny-ipa 是个很小的项目。目标也不花哨：做一个帮自己练英语音标的小工具。

需求听起来朴素：选几百个高质量单词，带英式和美式 IPA，做练习，做一点 TTS 音频，后面能部署到 VPS 上自己用。不是 SaaS，不追求商业化，不需要一上来就设计成十万用户规模。

按理说，这种项目很适合直接开干。

但上一个项目已经教育过我：小项目也会长腿。今天只是一个按钮，明天就变成数据来源、音标质量、TTS 生成、SQLite、练习记录、部署备份、英美音对比。你一边说“先 MVP”，一边发现每一步都在往后面的系统埋钩子。

于是我开始老登式地领导两个 agent。

DeepSeek 那边负责具体 coding。执行力强，给它一个 issue，它能一路把文件改起来、测试跑起来、PR 提起来。

Codex 这边逐渐变成了 architect / reviewer / planner。先把整体架构画到底，决定哪些东西现在做，哪些东西留接口但不提前复杂化；再把 milestone 拆成 issue；等 DeepSeek 做完，再回来 review，看它有没有漏掉边界、测试、文档、手动验证。

一开始我还没有给它们起角色名。只是凭感觉分配任务。

后来发现，名字其实已经在那里了。

一个像 implementer。

一个像 architect。

我，暂时像个拿着茶杯在旁边转悠的 engineering manager。

## 二、我的工作变成了 Copy / Paste

最早这种双 agent 协作非常土，但有效。

Codex 负责规划和 review，DeepSeek 负责执行。我负责在两个窗口之间转述：把计划贴过去，把完成报告贴回来，把 review 意见再贴过去。

这个模式跑了一阵以后，真正暴露出来的问题不是“agent 不会合作”，而是“合作缺少共享状态”。

只要共享状态还在我的剪贴板里，我就会变成人肉消息队列。谁该开工、谁该 review、哪个 issue 已经 ready、哪个 PR 需要补测试，这些信息都不应该靠我记着。

到这一步，问题已经不是 prompt engineering，而是 workflow engineering。

所谓自动化，也不是让两个 agent 神秘地互相聊天，而是把“下一步该谁做什么”变成一个可查询、可更新、可审计的系统状态。

## 三、从 Issue 到 Milestone，再到 Epic

我们很自然地把工作流放到了 GitHub Project 上。

原因也简单：既然 agent 都能用 `gh`，既然 issue / PR / comment / label 都是可读可写的，那 GitHub 就是最便宜、最稳、最不用自己造后台的协作数据库。

第一版很朴素：issue 记录 task，milestone 组织阶段，PR 承载代码交付。这已经足够让 DeepSeek 按 issue 执行，让 Codex 按 issue review。

但 milestone 很快显出局限。

Milestone 是时间切片，天然带有线性暗示：M0 完了再 M1，M1 完了再 M2。它适合表达路线图，却不适合表达多 agent 并行协作中的能力边界、依赖关系和集成验收。

更具体地说，milestone 有三个问题：

* 它不擅长承载跨 issue 的 readiness 语义。一个阶段是否完成，不等于所有 issue mechanically closed。
* 它容易把工作流串行化。多个 agent 本来可以并行推进不同能力，却被“当前 milestone”这个概念压回一条队列。
* 它不是一个很好的讨论对象。跨 issue 风险、manual QA、integration gap、后续放行判断，都需要一个可以 comment、label、link child issue 的协调容器。

我们曾经用 milestone readiness issue 补这个洞，但这本质上是在给 milestone 外挂一个临时器官。

Epic 才是更自然的边界。

Epic 对应一个能力阶段，下面挂 child issues。Child issue 是执行单元，Epic 是协调单元。代码、测试、文档、manual QA 这些可以拆到 child issue；跨 issue 风险、readiness、scope decision 则留在 Epic。

这样 milestone 就退回到路线图和历史阶段，Epic 成为真正的协作单位。

这个变化的价值不在“名字更时髦”，而在它打破了线性阶段感，让多 agent 协作可以围绕能力图而不是时间队列展开。

## 四、技术夹层：我们最后揉出来的流程

这一段讲具体流程，不感兴趣可以跳过。

现在 tiny-ipa 的多 agent 协作大概长这样：

```text
Epic issue = 能力 / 阶段 / 跨 issue 协调中心
Child issue = 可执行任务和验收单元
Branch = 一个 child issue 的实现线
PR = 一个 child issue 的合并请求
GitHub Project = 人类可看的 Kanban
needs:* label = agent 可自动检索的 next-action inbox
```

角色也变得清楚：

```text
Architect:
  - 架构设计
  - Epic 拆解
  - 把 child issue 从 Backlog 推到 Ready
  - review PR / issue
  - 做 Epic readiness 判断

Implementer:
  - 领取 Ready 的 child issue
  - 创建 issue branch
  - 写代码、测试、文档
  - 开 PR
  - 响应 review
  - 写 completion comment
```

GitHub Project 的状态负责给人看：

```text
Backlog -> Ready -> In progress -> In Review -> Done
```

`needs:*` label 负责给 agent 找活：

```text
needs:implementer -> implementer 应该处理某个 child issue 或 PR
needs:architect   -> architect 应该 review、merge、规划或做 readiness
needs:user        -> 需要用户决策
needs:ci          -> 等 CI
needs:merge       -> 可以 merge
blocked           -> 被阻塞，读最新 comment
```

一个重要修正是：Epic 本身不是 implementer 的工作项。

也就是说，不能因为 M2 的子任务 ready 了，就给 Epic #22 标 `needs:implementer`。Implementer 不应该“领取 Epic”，它应该领取 Epic 下面的 child issue。

如果 Epic-level 的事情需要人执行，比如：

```text
Run integration QA and close Epic readiness gaps
Fix cross-issue session / attempt integration gaps
Add final manual QA evidence for Epic closure
```

那就新建一个 child issue。

这条规则看起来小，其实很要命。它决定了 agent inbox 里出现的是“可以动手的任务”，而不是“一个大概需要你关心的阶段”。

人可以理解含糊话。

Agent 最好少吃含糊话。

## 五、兜兜转转，又回到老本行

把这些东西捋清楚以后，我突然有一种很微妙的感觉。

这不是我二十年前刚入行时干过的事吗？

那时候我的老本行，就是开发和部署配置管理、代码管理、流程管理系统。需求、任务、版本、分支、权限、状态流转、review、发布、回滚。系统的目标很清楚：让一群碳基程序员不要靠拍脑袋协作，不要靠吼一嗓子同步状态，不要靠“我以为你知道”推进项目。

二十年后，我绕了一圈，又在做同一件事。

只是服务对象变了。

当年的系统是给人用的。

现在这套系统，是给 agent 用的。

人类开发者需要 issue、分支、PR、review、CI，是因为人的记忆会漏，沟通会偏，责任边界会糊。

Agent 也一样。

甚至更需要。

因为 agent 没有稳定的组织记忆。上下文窗口一刷新，它就可能忘了前面为什么这么决定。你跟它说“继续上次的思路”，它也许能猜到，也许猜歪。你把规则写进 issue、comment、label、docs、practice，它就有东西可读，有状态可查，有边界可执行。

这时候我才意识到，所谓“管理 agent”，并不是把 agent 当人一样开会。

而是把软件工程里那些为人类发明的协作结构，重新校准给硅基同事使用。

## 六、第二层顿悟：我在手搓 Agent Scheduler

再往前想一层，这件事就更好笑了。

我本来只是想做个音标练习工具，结果先搭出了多 agent 协作流程，再把流程沉淀成 GitHub Project、Epic、label inbox、PR review 和 readiness gate。

换个名字看，这就是一个简陋的 agent scheduler。

它当然没有漂亮的 dashboard，没有自动派单算法，没有 agent runtime，也没有任务图数据库。

它很土：

```text
GitHub issue 是任务对象
Project Kanban 是状态机
label 是 routing key
comment 是消息体
PR 是交付物
CI 是自动验收
人类是仲裁器
```

但它已经具备调度系统最小闭环：任务对象、状态机、路由信号、上下文载体、交付物、验收门禁和人类仲裁。

2026 年中，我很难相信只有我一个人在摸这块石头。一个 agent 可以靠对话驱动；两个 agent 就开始需要共享上下文；三个 agent 以后，调度、权限、成本、review、memory、handoff 都会变成显性问题。

这时真正的问题不再是“哪个模型最聪明”，而是“怎么让这些不稳定的聪明，稳定地流过一个工程系统”。

成熟平台迟早会来。也许某家公司会做出一个漂亮的 agent operating system，把任务拆解、上下文装载、权限隔离、成本控制、review gate、memory、practice 全部打包起来。

但在那之前，手搓一个自己的小型 agent 调度管理系统，简直是每个 geek 很难抗拒的自然反应。

尤其是它还真的能帮你干活。

## 七、老登的茶杯暂时还放不下

所以 tiny-ipa 表面上是一个音标练习工具，暗线却是一套多 agent 软件开发流程的试验。

Codex 变成 architect，DeepSeek 变成 implementer。GitHub 从代码托管变成共享工作台，issue 变成上下文包，label 变成调度信号，comment 变成 agent-to-agent 的消息，Epic 变成跨任务的组织记忆。

我也没有真的甩手，只是从“亲自写每一行代码”，退到了“设计协作系统，让 agent 在里面少走弯路”。

以前带人，流程是给人减轻沟通成本。

现在带 agent，流程是给机器补上组织感。

所谓 vibe coding，也许最后不是一个人对着一个 AI 许愿，而是在一张很小的 GitHub Project 看板上，慢慢搭出一个软件团队的影子。

人类端着茶杯，看着这些硅基同事在 label 和 comment 之间来回流转，偶尔忍不住感叹一句：

兜兜转转，怎么又开始搞配置管理了。
