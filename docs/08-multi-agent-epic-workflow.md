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
