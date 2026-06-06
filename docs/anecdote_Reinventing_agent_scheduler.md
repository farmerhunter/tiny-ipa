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

最早这种双 agent 协作非常土。

我在 Codex 这里讨论规划，Codex 生成 milestone 和 issue 草案。我复制到 GitHub。

DeepSeek 在隔壁做完 M0，我回来告诉 Codex：“隔壁 DeepSeek 已经把 M0 做完了，你 review 一下。”

Codex review 出问题，我把 review comment 复制给 DeepSeek。

DeepSeek 修完，我再回来告诉 Codex：“隔壁修好了，你再检查一下。”

Codex 说可以开工 M1，我再去通知 DeepSeek。

这套流程居然能跑。

而且越跑越顺。

两个 agent 之间没有直接通信，也没有什么高大上的 agent orchestration framework。它们甚至不知道对方真实存在。它们只通过我的 copy / paste 彼此感知。

但问题也很明显。

我越来越像一个人肉消息队列。

Architect 说：“这个 issue 需要 implementer 处理。”

我复制。

Implementer 说：“这个 PR 已经完成，请 review。”

我复制。

Architect 说：“这里有 blocker，不能 merge。”

我再复制。

这时老登终于拍了一下桌子：这不就是工作流状态流转吗？这不就是应该自动化的吗？

## 三、从 Issue 到 Milestone，再到 Epic

我们很自然地把工作流放到了 GitHub Project 上。

原因也简单：既然 agent 都能用 `gh`，既然 issue / PR / comment / label 都是可读可写的，那 GitHub 就是最便宜、最稳、最不用自己造后台的协作数据库。

最开始只是用 issue 记 task。

M0 要做什么，开几个 issue。M1 要做什么，再开几个 issue。每个 issue 写清楚背景、约束、验收标准、测试要求。DeepSeek 可以拿一个 issue 开工，Codex 可以基于 issue review。

这已经比“把一大段需求贴给 agent”强很多。

后来我们开始按 milestone 做规划、执行、review。

M0 是 feasibility 和架构骨架。M1 是静态练习闭环。M2 是 SQLite 和服务端判题。M3 是核心 100 单词音频。每个 milestone 下面有一组 issue。做完以后，不是马上往前冲，而是先做 milestone-level review。

这一步很关键。

因为有些问题不是某个 issue 独自负责的。

比如 M1 做完后，单个 issue 看起来都完成了，但整体手动 QA 有没有跑？英式 IPA 的选择题路径有没有真的用 UK accent？前端刷新后状态有没有保住？这些东西更像 integration review，而不是某个按钮 issue 的小尾巴。

于是我们曾经发明了 milestone readiness issue。

看起来合理，但很快又别扭起来。

Milestone 本质上还是线性的。M0 完了再 M1，M1 完了再 M2。它适合一个人排队干活，不适合多个 agent 同时往不同方向推进。

更要命的是，readiness issue 有点像为了弥补 milestone 缺陷硬造出来的夹层。它不是能力本身，只是一个“等我检查完再放行”的门卫。

这时候 Epic 出场了。

我们把 milestone 对应的能力阶段转成 Epic issue：M2 是一个 Epic，下面挂 #10 到 #13；M3 是一个 Epic，下面挂 #14 到 #17。Epic 负责上下文、跨 issue 风险、集成验收、readiness。Child issue 负责具体执行。

这一下舒服多了。

不是“所有人排队等 M2 完了才能看 M3”，而是“每个 Epic 是一个能力容器，里面有可执行任务，任务之间有依赖，有些可以并行，有些需要等 readiness”。

Milestone 退回成历史阶段和路线图标记。

Epic 才是协作单位。

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

再往前想一层，就更好笑了。

我本来只是想做个音标练习工具。

做着做着，先变成了多 agent 协作。

协作着协作着，又变成了 GitHub Project + Epic + label inbox + PR review + readiness gate。

再往前推一步，这不就是一个简陋的智能体调度系统吗？

只不过它没有漂亮的 dashboard，没有自动派单算法，没有 agent runtime，没有任务图数据库，也没有什么 MCP 大一统平台。

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

但是它已经有了调度系统的味道。

谁该干活？

看 label。

干什么？

看 issue body 和最新 comment。

做到哪了？

看 Project status。

能不能合？

看 PR、CI、review、completion comment。

有没有跨任务风险？

看 Epic。

需要用户拍板吗？

挂 `needs:user`。

这套东西当然还很原始。但在 2026 年中，我很难相信只有我一个人在往这个方向走。

所有严肃的、业余的、半夜不睡觉折腾 agent 的玩家，大概都在某种程度上摸这块石头。

一个 agent 很有用。

两个 agent 开始需要协作。

三个 agent 就会需要调度。

再往后，测试 agent、review agent、文档 agent、planner agent、implementer agent、practice harvester agent、CI fixer agent，各自都有强项，也各自都会犯傻。

这时真正的问题不是“哪个模型最聪明”。

而是“怎么让这些不稳定的聪明，稳定地流过一个工程系统”。

成熟平台迟早会来。也许哪家公司会做出一个漂亮的 agent operating system，把任务拆解、上下文装载、权限隔离、成本控制、review gate、memory、practice 全部打包起来。

但在那之前，手搓一个自己的小型 agent 调度管理系统，简直是每个 geek 很难抗拒的自然反应。

尤其是它还真的能帮你干活。

## 七、老登的茶杯暂时还放不下

所以 tiny-ipa 表面上是一个音标练习工具。

暗线却是另一件事：我们在训练一套多 agent 软件开发流程。

Codex 不只是写文档，它开始扮演 architect。

DeepSeek 不只是写代码，它开始扮演 implementer。

GitHub 不只是代码托管，它变成了 agent 之间的共享工作台。

Issue 不只是任务列表，它变成了上下文包。

Label 不只是分类，它变成了调度信号。

Comment 不只是留言，它变成了 agent-to-agent 的消息。

Epic 不只是大 issue，它变成了跨任务的组织记忆。

我也没有真的甩手。

我只是从“亲自写每一行代码”，退到了“设计协作系统，让 agent 在里面少走弯路”。听起来还是老登，甚至更老登。

但这次有点不一样。

以前带人，流程是给人减轻沟通成本。

现在带 agent，流程是给机器补上组织感。

所谓 vibe coding，也许最后不是一个人对着一个 AI 许愿。

它更像是在一张很小的 GitHub Project 看板上，慢慢搭出一个软件团队的影子。有人快，有人稳，有人 review，有人执行，有人记账，有人总结 practice。

而人类端着茶杯，看着这些硅基同事在 label 和 comment 之间来回流转，偶尔忍不住感叹一句：

兜兜转转，怎么又开始搞配置管理了。
