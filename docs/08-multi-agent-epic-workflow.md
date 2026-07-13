# Multi-Agent Epic Workflow

This project uses GitHub Project, Epic issues, child issues, branches, and PRs as the durable collaboration surface between agents.

## Roles

### Architect

The Architect owns:

- architecture and product boundary design
- Epic planning and child issue decomposition
- moving work from `Backlog` to `Ready`
- PR and issue review
- cross-issue integration review
- readiness decisions for downstream Epics

### Implementer

The Implementer owns:

- executing child issues
- creating issue branches
- writing code, tests, and docs
- opening PRs
- responding to review feedback
- posting completion comments

### Tester

The Tester owns objective evidence when testing depth is the bottleneck:

- test plans and test matrices
- route-mocked versus real-backend evidence boundaries
- temp-DB, browser, runtime, deployment-readiness, and regression evidence
- residual-risk and coverage-gap reporting

Tester does not approve, reject, merge, close, or replace Reviewer, Architect,
or Human acceptance. Use Tester selectively for risky user-visible or stateful
work; low-risk docs, helpers, or narrow implementation changes can still go
directly from Implementer to Reviewer or Architect when ordinary evidence is
enough.

These are roles, not identities. The same agent can play different roles in different turns, but role expectations should be explicit.

## Work Hierarchy

```text
Epic issue = capability / outcome / cross-issue coordination hub
Child issue = executable work and acceptance unit
Branch = implementation line for one child issue
Issue PR = request to merge one child issue branch into its target integration branch
Epic PR = request to merge one Epic integration branch into main
Milestone = optional roadmap or historical phase marker
```

Milestones are no longer the primary collaboration unit. Existing GitHub milestones may remain for history and roadmap browsing, but Epic issues are the canonical planning and review hubs.

## Issue Types

Use labels:

```text
type:epic
type:task
```

An Epic issue should include:

```markdown
## Epic Goal

## Child Issues
- [ ] #...

## Cross-Issue Coordination

## Notes
```

Child issues should stay scoped to one executable work package with clear acceptance criteria.

Epic issues are coordination containers, not implementation work items. Do not put `needs:implementer` on an Epic just to indicate that its child issues are ready. Put `needs:implementer` on the ready child issues instead.

If an Epic-level concern requires concrete implementer action, create a child task for it. Common examples:

```text
[M2] Run integration QA and close Epic readiness gaps
[M2] Fix cross-issue session/attempt integration gaps
[M2] Add final manual QA evidence for Epic closure
```

Keep the concern on the Epic when it is only coordination, review, or decision-making. Split it into a child task when it requires code, tests, manual verification, data migration, or a completion comment from an Implementer.

## Branch and PR Granularity

Default:

```text
one Epic -> one integration branch -> one final PR to main
one child issue -> one issue branch -> one PR to the Epic integration branch
```

Example:

```text
Epic:   #23 M3 TTS
Branch: epic/m3-tts
PR:     [M3] Integrate TTS capability
Base:   main

Issue:  #11 Persist daily sessions and make /api/today database-backed
Branch: agent/11-db-backed-today
PR:     [#11] Persist daily sessions and make /api/today database-backed
Base:   epic/m2-persisted-practice
```

This is the preferred path for current multi-agent work. It keeps final integration reliable while preserving issue-level PRs for scoped review.

Issue branches may target `main` directly only for independent documentation, tooling, or small fixes that do not belong to an active Epic integration branch.

Stacked PRs are an explicit exception, not the default. Use them only when every layer has independent review value, the dependency chain is real, and the Architect writes the stack order and final integration path before work starts.

Merging a stacked PR merges it into its base branch, not necessarily into `main`. Before closing issues or an Epic, verify that every required commit is reachable from `origin/main`. If stacked PRs were reviewed against non-main bases, use one of these release paths:

```text
Option A: retarget each PR to main after its lower dependency lands, then merge in order
Option B: open a final integration PR from the top stack branch to main
```

Do not treat a stacked PR as complete merely because GitHub shows it as merged; check the merge destination.

### Branch Strategy Contract

The Architect decides the branch strategy before moving a child issue to `Ready`. Implementers should not infer or choose the strategy at pickup time.

Every ready child issue should include an execution contract:

```markdown
## Execution Contract

Branch strategy: epic integration branch | issue branch to main | stacked PR
Base branch: `...`
Target PR base: `...`
Depends on: #... / none
Expected PR shape: one PR for this issue
Merge rule: ...
Verification required: ...
```

`Ready` means the issue is planned, specified, and available for Implementer queue management. It does not always mean the issue can be coded immediately. The `Depends on` line is the executable gate.

Architects may move a dependent sequence of child issues to `Ready` at the same time and label them `needs:implementer` when:

- every issue has an execution contract
- dependencies are explicit and checkable
- all issue branches target the same Epic integration branch unless an exception is documented
- the Implementer can continue the queue without another Architect handoff

Implementers may queue multiple ready issues, but must execute them in dependency order. Do not create a working branch, code changes, or a PR for a dependent issue until its `Depends on` condition is satisfied.

Avoid making review of each earlier issue a default queue-wide blocker. A child issue review blocks later implementation only when:

- the later issue has an explicit `Depends on` gate that is not satisfied
- the Architect adds a clear Epic-level hold comment
- the review finding changes a shared contract that later issues would build on

Otherwise, later ready issues can continue while earlier PRs are being reviewed. This keeps the workflow closer to fail-fast iteration instead of turning the Architect into a manual release valve after every child issue.

If a dependency is not satisfied yet, the Implementer may leave a queue comment:

```markdown
## Queued by Implementer

Dependency not satisfied yet.
Waiting for #... to merge into `epic/...`.
```

For the default Epic integration path:

```markdown
Branch strategy: epic integration branch
Base branch: `epic/m3-tts`
Target PR base: `epic/m3-tts`
Final integration: Architect owns the Epic PR from `epic/m3-tts` to `main`.
```

For a stacked PR exception:

```markdown
Branch strategy: stacked PR
Base branch: `agent/<lower-issue-branch>`
Target PR base: `agent/<lower-issue-branch>`
Final integration: retarget in order or open one final integration PR to `main`.
```

When the Implementer picks up a ready issue, the first issue comment should confirm the contract:

```markdown
## Pickup confirmed

Branch strategy: ...
Working branch: `agent/<issue-number>-...`
PR base: `...`
Verification plan: ...
```

Use `Pickup confirmed` only when dependencies are satisfied and implementation is actually starting.

If the execution contract is missing or the intended PR base is unclear, the Implementer should move the issue to `needs:architect` instead of starting work.

## Project Status Flow

Use the Kanban status as shared state:

```text
Backlog -> Ready -> In progress -> In Review -> Done
```

Responsibilities:

```text
Architect:   Backlog -> Ready
Implementer: Ready -> In progress
Implementer: In progress -> In Review after PR is open
Architect:   In Review -> Done after merge and issue closure
```

Do not start work from `Backlog` unless the user explicitly overrides the workflow.

## Handoff Labels

Project status is optimized for human planning. Handoff labels are the machine-readable signal that tells an agent what to pick up next.

Use exactly one primary next-action label on an active issue or PR unless the work is genuinely blocked:

```text
needs:architect   Architect should plan, review, merge, or make a readiness decision
needs:implementer Implementer should code, fix, verify, or update a PR
needs:tester      Tester should plan or gather objective test evidence
needs:user        User decision or clarification is required
needs:ci          Waiting for CI or automated checks
needs:merge       Reviewed and ready to merge
blocked           Blocked; latest comment must explain why
```

Allowed use by issue type:

```text
type:task:
  may use needs:implementer, needs:tester, needs:architect, needs:user, needs:ci, needs:merge, blocked

type:epic:
  may use needs:architect, needs:user, blocked
  should not use needs:implementer, needs:tester, needs:ci, or needs:merge
```

Epic handoff labels mean the next action is coordination-level work:

```text
needs:architect on Epic -> planning, decomposition, readiness review, or closure decision
needs:user on Epic      -> scope, priority, product, or process decision
blocked on Epic         -> cross-issue dependency or external blocker
```

Recommended transitions:

```text
Backlog task selected by Architect:
  add needs:implementer
  move Project status to Ready

Implementer starts task:
  remove needs:implementer
  move Project status to In progress

Implementer opens PR:
  add needs:architect
  move issue/PR to In Review

Implementer finishes evidence-sensitive work:
  add needs:tester when the contract says Tester evidence is required

Tester completes evidence pass:
  remove needs:tester
  add needs:reviewer, needs:architect, or needs:implementer per contract

Architect requests changes:
  remove needs:architect
  add needs:implementer

Architect approves and CI is green:
  remove needs:architect
  add needs:merge

Merged and closed:
  remove needs:* labels
  move Project status to Done

Blocked:
  add blocked plus needs:user or needs:architect
  post a comment with the blocker and the exact next decision needed
```

Agent pickup commands:

```bash
# Architect inbox
tools/agents/agent-inbox architect

# Implementer inbox
tools/agents/agent-inbox implementer

# Implementer queue with dependency gates
tools/agents/agent-ready-queue

# Tester evidence queue
tools/agents/agent-inbox tester
tools/agents/agent-ready-queue --role tester

# User-decision queue
tools/agents/agent-inbox user

# Merge queue
tools/agents/agent-inbox merge
```

When changing handoff ownership, always add a short comment that states what changed and what the next agent should do. The label is the routing signal; the comment is the context.

When marking an Epic's child issues ready, leave a comment on the Epic that points Implementers to the child issues, but do not label the Epic `needs:implementer`.

### Review Handoff Contract

When the Architect sends a task back from review, the handoff must be visible from both the child issue and the linked PR. Agents may scan either surface first, so single-channel feedback is not reliable.

Required actions:

```text
1. Post detailed code/API feedback on the PR.
2. Post a short handoff comment on the linked child issue.
3. If the reason for the handoff is not already the latest PR comment, post a short PR follow-up comment too.
4. Replace needs:architect with needs:implementer on the child issue.
5. Leave the Project status as In Review unless the task is explicitly reopened.
```

The issue comment must include:

```markdown
## Implementer handoff: changes requested

This issue was moved back to `needs:implementer` after Architect review.

Fix branch: `agent/<issue-number>-...`
PR: #...
Detailed review: <PR comment URL>

Next action:
- Checkout the fix branch.
- Apply the requested fix from the PR review comment.
- Add or adjust regression tests for the blocker.
- Push the same branch and move this issue back to `needs:architect` when ready for re-review.
```

Do not rely on PR comments alone for a role handoff. Implementers discover work from issue labels first, so the issue must contain a durable pointer to the PR feedback.

Do not rely on issue comments alone for a PR-specific or stacked-branch handoff. Implementers often inspect PR conversations when fixing an open PR, so the PR must also contain a short pointer to the latest action.

Implementer re-review pickup command:

```bash
tools/agents/agent-inbox implementer
tools/agents/agent-issue-context <issue-number>
gh pr view <pr-number> -R farmerhunter/tiny-ipa --comments
```

## Comment Routing

Route durable coordination through GitHub:

```text
single-feature implementation issue -> child issue or linked PR
code-level review -> PR review/comment
cross-issue integration issue -> Epic
manual QA / readiness review -> Epic
Project state or workflow closure -> Epic
architecture change -> design issue or docs PR
```

Examples:

```text
UK accent choices are wrong in /api/today -> child issue for /api/today
manual end-to-end QA has not run -> Epic
PRs merged but Project status is stale -> Epic
session + attempt + stats fail together -> Epic unless one child issue clearly owns it
```

## PR Merge Rules

Auto-merge is allowed when:

- PR scope maps clearly to one child issue.
- CI passes.
- Review has no blocker.
- Completion comment is present.
- The change is non-destructive and has no unresolved data/schema risk.

Do not auto-merge when:

- CI fails.
- Review has blocker findings.
- The PR changes schema or data behavior without migration or rollback notes.
- It introduces new external dependencies without explanation.
- The PR body says `hold` or `do not merge`.
- It spans multiple child issues without a clear mapping.

PR body should include:

```markdown
Closes #...

## Scope completed

## Verification

## Manual QA

## Residual risks
```

## Epic Readiness

An Epic can close only when:

- all required child issues are closed or explicitly deferred
- linked PRs are merged into `main`
- CI and relevant manual QA are recorded
- cross-issue findings are fixed or converted to follow-up issues
- Project state is aligned
- the Architect posts a final readiness comment

The readiness comment should state whether downstream Epics may move from `Backlog` to `Ready`.

## GitHub CLI Notes

Prefer labels for agent pickup because they are fast, portable, and supported by `gh issue list`. GitHub Project v2 fields are still useful as the visual board, but Project item updates require Project item IDs, field IDs, and option IDs, which makes automation slower and more brittle.

The project-local helpers are part of a lightweight multi-agent scheduler, not
only GitHub access accelerators. They are designed for a local environment where
GitHub operations can be slow and flaky, while still preserving the scheduling
semantics needed by independent agent sessions:

```text
labels route the next actor
comments preserve the handoff context
Execution Contracts remove workflow guesswork
ready queues and dependency gates reduce handoff frequency
audits detect scheduler drift without rewriting state
Project status mirrors the board after routing state is updated
```

Daily agent work should optimize for:

```text
few network round trips
short durable handoff comments
explicit branch/dependency/review contracts
batch checkpoints for related low-risk child issues
local context extraction before broad GitHub scanning
```

Do not turn every child issue into a mandatory cross-session handoff when an
Epic contract allows a queue or batch checkpoint. A handoff is required when the
next action changes role, a dependency gate blocks progress, review finds a
blocker, a shared contract changes, or user/Architect authority is needed.

Tiny IPA has project-local helpers under `tools/agents/`:

```bash
tools/agents/agent-permission-smoke
tools/agents/agent-inbox architect
tools/agents/agent-inbox implementer
tools/agents/agent-ready-queue
tools/agents/agent-issue-context <issue-number>
tools/agents/agent-pr-context <pr-number>
tools/agents/agent-project-status <issue-number> "In Review"
```

Use these helpers first in daily agent work. They standardize retries, avoid unnecessary Project v2 reads, and cache Project item IDs in `.agent-cache/` when a Project status update is needed.

Delegated thread permission gate:

```text
Before doing GitHub writes, Git metadata writes, branch creation, or PR work,
run `tools/agents/agent-permission-smoke`. If this delegated/resumed turn starts
under restricted network or local Git metadata permissions, do not proceed with
branch/PR workflow. Report the permission downgrade and wait for a user turn
with full GitHub network access and local Git metadata write permission.
```

Architect dispatch prompts should include that gate whenever they use direct
thread dispatch as an acceleration ping. The ping remains non-authoritative:
the durable issue, PR, labels, comments, and Execution Contract still control
what work may start.

Inbox, issue-context, PR-context, and label-routing helpers should prefer GitHub REST API reads/writes over `gh issue list/view/edit` and `gh pr view`, because those commands can use GraphQL and have repeatedly hit TLS timeouts in this project. Project v2 remains separate and low-frequency.

Operational rule:

```text
Daily routing: labels + issue/PR comments
Human board sync: Project status, updated after labels/comments
Full Project scans: rare, cached, and not part of ordinary inbox lookup
```

Roadmap Status or other project-specific planning fields should be treated the
same way as Project status: important for planning, but optional and
configuration-driven for helper scripts. The default scheduler path must not
depend on those fields.

Use layered checks:

```text
agent-audit
  fast label and contract consistency

agent-audit --project
  optional Project/Roadmap drift check when the project config defines fields

agent-project-sync --dry-run
  print intended Project/Roadmap repairs

agent-project-sync --apply
  mutate only a specified issue or narrow filter
```

Do not make ordinary inbox, ready-queue, pickup, or handoff commands query
Project v2 just to detect board drift. These commands should remain fast and
portable. Project/Roadmap synchronization belongs in audit or explicit sync
commands, and missing config should produce a clear skip message instead of
false errors.

Observed limitations and mitigations:

- Project status and issue state are separate. Moving a card to `Done` does not close the issue, and closing an issue does not always update every Project field as expected. Agents should update both when finishing work.
- Parent/child issue relationships are not fully covered by simple `gh issue edit` commands. Use GitHub's sub-issues REST API or the web UI when creating Epic child links.
- Project v2 status cannot be queried as simply as issue labels through `gh issue list`. Use `needs:*` labels as the reliable automation entry point.
- Network operations can intermittently fail on HTTP/2 or TLS framing. Retry `gh` commands, and use `GIT_HTTP_VERSION=HTTP/1.1 git fetch` or `git push` if Git transport flakes.
- Issue deletion is available through `gh issue delete --yes`, but deletion should remain rare; prefer closing obsolete planning issues unless a workflow migration creates clearly invalid duplicates.

The current GitHub auth scopes are sufficient for repo, issue, PR, workflow, and Project operations. More auth is not needed unless a future automation needs organization-level administration, secrets management, or cross-repository bulk changes.
