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

These are roles, not identities. The same agent can play different roles in different turns, but role expectations should be explicit.

## Work Hierarchy

```text
Epic issue = capability / outcome / cross-issue coordination hub
Child issue = executable work and acceptance unit
Branch = implementation line for one child issue
PR = request to merge one child issue branch into main
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
one child issue -> one branch -> one PR
```

Example:

```text
Issue:  #11 Persist daily sessions and make /api/today database-backed
Branch: agent/11-db-backed-today
PR:     [#11] Persist daily sessions and make /api/today database-backed
Base:   main
```

Milestone-sized PRs are not the default. They are allowed only when the child issues are tightly coupled, the PR body maps every child issue to completed scope, and review remains tractable.

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
needs:user        User decision or clarification is required
needs:ci          Waiting for CI or automated checks
needs:merge       Reviewed and ready to merge
blocked           Blocked; latest comment must explain why
```

Allowed use by issue type:

```text
type:task:
  may use needs:implementer, needs:architect, needs:user, needs:ci, needs:merge, blocked

type:epic:
  may use needs:architect, needs:user, blocked
  should not use needs:implementer, needs:ci, or needs:merge
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
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:architect

# Implementer inbox
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:implementer

# User-decision queue
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:user

# Merge queue
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:merge
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
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:implementer
gh issue view <issue-number> -R farmerhunter/tiny-ipa --comments
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

Observed limitations and mitigations:

- Project status and issue state are separate. Moving a card to `Done` does not close the issue, and closing an issue does not always update every Project field as expected. Agents should update both when finishing work.
- Parent/child issue relationships are not fully covered by simple `gh issue edit` commands. Use GitHub's sub-issues REST API or the web UI when creating Epic child links.
- Project v2 status cannot be queried as simply as issue labels through `gh issue list`. Use `needs:*` labels as the reliable automation entry point.
- Network operations can intermittently fail on HTTP/2 or TLS framing. Retry `gh` commands, and use `GIT_HTTP_VERSION=HTTP/1.1 git fetch` or `git push` if Git transport flakes.
- Issue deletion is available through `gh issue delete --yes`, but deletion should remain rare; prefer closing obsolete planning issues unless a workflow migration creates clearly invalid duplicates.

The current GitHub auth scopes are sufficient for repo, issue, PR, workflow, and Project operations. More auth is not needed unless a future automation needs organization-level administration, secrets management, or cross-repository bulk changes.
