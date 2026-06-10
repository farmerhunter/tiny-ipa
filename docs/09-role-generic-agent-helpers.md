# Role-Generic Agent Helper Model

This document designs the next version of the Tiny IPA GitHub helper tools from
first principles. The goal is not to automate one Architect / Implementer pair,
but to support multiple roles and multiple agent sessions moving work through
GitHub issues, PRs, comments, labels, and Project status.

The current helpers in `tools/agents/` are useful experiments. They proved that
fast REST-based reads, `needs:*` labels, and local audit scripts can make a
GitHub Project feel like a lightweight agent scheduler. The next step is to make
that scheduler role-generic before adding more write automation.

## Design Constraints and Principles

The helper model is a lightweight multi-agent scheduler built on GitHub under
severe local access constraints. It should not be reduced to a GitHub latency
optimizer, but slow and flaky GitHub access is a primary architectural
constraint that shapes every helper surface.

The design optimizes these goals together:

```text
low GitHub round trips
low handoff frequency
low agent process ambiguity
low token cost for context reconstruction
durable workflow state across independent agent sessions
```

GitHub remains the scheduling substrate, but the helpers should use the lowest
cost reliable surfaces for ordinary agent work:

```text
issues        = work items
labels        = fast routing and inbox state
comments      = durable handoff memory and compact context
PRs           = review and integration surface
Project v2    = human board mirror, not the source of truth
```

This leads to these operating principles:

1. Build a lightweight scheduler on GitHub, not a standalone scheduler.
2. Treat slow and unreliable GitHub access as a high-priority constraint, not
   the only goal.
3. Use labels as fast routing state and comments as durable context.
4. Keep Project status as a visual mirror, updated after labels and comments.
5. Make workflow contracts explicit so agents do not infer branch, dependency,
   review, or handoff rules.
6. Minimize handoff frequency through ready queues, dependency gates, and batch
   checkpoints.
7. When handoff is necessary, make it short, durable, and visible from the
   surfaces the next agent is likely to scan.
8. Prefer read-only audits and dry-runs before write automation.
9. Make role routing generic, while keeping decision authority and acceptance
   explicit.
10. Optimize round trips, token reconstruction cost, and process certainty as a
    single design problem.

Because there is no persistent scheduler session coordinating agents, the
helpers must preserve enough durable state for the next agent to continue
without chat history. They should also avoid creating unnecessary handoff stops:
related low-risk work should be released as dependency-gated queues or batch
checkpoints when the Execution Contract allows it.

## Design Goal

The helpers should treat role routing as data, not as hard-coded knowledge.

```text
role inbox label = needs:<role>
handoff = remove current role label, add next role label, write durable comment
Project status = visual mirror, not the source of truth
```

The same model must support at least these flows:

```text
Architect -> Implementer
Implementer -> Reviewer
Reviewer -> Implementer
Reviewer -> Architect
Architect -> Reviewer
Implementer -> Architect
CI -> Implementer
User -> Architect
```

`Reviewer` is intentionally first-class. It may be a separate agent session from
the Architect, and it may review code, QA evidence, docs, or integration risk.
Final acceptance can still belong to the Architect when the issue contract says
so.

## Core Concepts

### Role

A role is a responsibility boundary, not a person, model, or process.

Examples:

```text
architect
implementer
reviewer
user
ci
merge
```

The same agent session may play different roles in different turns, but helpers
should require the active role to be explicit when a command mutates routing.

### Role Inbox

`needs:<role>` labels are the machine-readable inbox.

Project status is useful for humans, but it is too slow and too awkward for
daily agent pickup. Helpers should read and write labels first, then optionally
sync Project status.

At most one primary `needs:<role>` label should be present on an open issue,
unless the issue contract explicitly allows multiple parallel actors.

### Handoff

A handoff is a state transition with durable evidence.

Every handoff should have:

```text
from role
to role, hold state, or no-route batch checkpoint
reason
expected next action
linked PR or evidence when relevant
label update
comment update
optional Project status update
```

The comment is not decoration. It is how the next agent reconstructs context
without relying on chat history.

### Execution Contract

Ready issues should keep the existing Execution Contract fields, but role
routing needs additional explicit fields.

Recommended contract shape:

```markdown
## Execution Contract

Owner role: implementer
Review role: reviewer / architect / none
Acceptance role: architect / reviewer / none
Branch strategy: epic integration branch | issue branch to main | stacked PR
Base branch: `...`
Target PR base: `...`
Depends on: #... / none
Expected PR shape: one PR for this issue
Completion handoff: to:reviewer | to:architect | batch checkpoint | close after evidence
Merge rule: ...
Verification required: ...
```

For simple two-role work, `Review role: architect` and `Completion handoff:
to:architect` are enough. For batch execution, `Completion handoff: batch
checkpoint` keeps child issues from becoming per-issue review stops.

The helper must fail closed when required contract fields are missing or when a
handoff value is unknown.

## Helper Surface

### `agent-inbox <role|all>`

Lists open issues carrying `needs:<role>` labels.

Current `agent-inbox` already follows this pattern, but it should not assume a
fixed role set beyond reserved system roles such as `user`, `ci`, and `merge`.

### `agent-ready-queue [--role <role>]`

Lists ready issues for a role and prints dependency gates plus routing contract
fields.

For `implementer`, this remains the coding queue. For `reviewer`, it can list
reviewable issues or PR-linked issues. For `architect`, it can list planning,
acceptance, or escalation work.

### `agent-pickup <issue> --role <role> [--apply]`

Confirms that the caller's role is the current next actor.

Expected behavior:

1. Read labels and latest effective Execution Contract.
2. Verify `needs:<role>` is present.
3. Check dependency gates relevant to that role.
4. In dry-run mode, print the planned label/status/comment changes.
5. With `--apply`, remove `needs:<role>`, optionally move Project status to
   `In progress`, and print or post a pickup comment template.

Pickup does not always mean creating a code branch. Reviewer pickup may mean
starting review. Architect pickup may mean making a readiness or acceptance
decision.

### `agent-handoff <issue> --from <role> [--to <role|none|batch>] [--apply]`

Completes the caller's current role action and routes the issue to the next
actor.

If `--to` is omitted, the script reads `Completion handoff:` from the latest
effective Execution Contract. The value should resolve to one of:

```text
to:<role>
batch checkpoint
close after evidence
hold
```

Expected behavior:

1. Read current labels and contract.
2. Verify the `from` role is allowed to perform this transition.
3. Remove any primary `needs:*` label that is no longer valid.
4. Add `needs:<role>` for `to:<role>`, or leave no next-action label for a
   declared batch checkpoint.
5. Print or post a completion / handoff comment template.
6. Optionally sync Project status.

### `agent-transition <issue> --from <role> --to <role|none|batch> [--apply]`

Longer term, `agent-pickup` and `agent-handoff` can be wrappers over a generic
transition command. Keeping the primitive explicit avoids repeatedly baking
workflow assumptions into new scripts.

### `agent-audit`

Audit must become role-aware.

Minimum checks:

- open issue has multiple primary `needs:<role>` labels without contract opt-in
- open issue has no next-action label and no documented batch checkpoint
- issue has unknown `needs:<role>` label
- `Completion handoff: to:<role>` names a role without a matching label
- issue is in review status but has no reviewer or acceptance route
- PR review requested changes but issue is not routed back to the responsible
  role
- pickup comment exists while old `needs:<role>` label remains
- closed issue still carries a primary next-action label
- Project Status and configured Roadmap Status disagree when project sync is
  explicitly enabled
- Project Status implies a route such as Ready or In Review, but the issue has
  no matching next-action label or review/acceptance route

Audit should be layered so ordinary runs stay fast and portable:

```text
Level 1: label routing consistency
  Default. Fast REST issue reads. Checks missing, unknown, conflicting, and
  stale next-action labels.

Level 2: contract/comment consistency
  Default or selectively enabled. Reads comments only for candidate issues that
  need contract, pickup, handoff, or batch-checkpoint validation.

Level 3: Project/Roadmap status consistency
  Optional. Requires project config. May query Project v2 and configured
  Roadmap Status fields. Read-only by default.

Level 4: Project/Roadmap repair
  Explicit apply-only workflow. Runs for a specified issue or narrow filter and
  prints a dry-run plan before mutation.
```

The fast path must not depend on Project v2. Project and roadmap consistency is
important for human planning, but it is too slow and project-specific to make
part of ordinary inbox, pickup, or ready-queue commands.

## Configuration

Tiny IPA can start with a small project-local config instead of a full workflow
engine.

Example shape:

```json
{
  "roles": {
    "architect": {
      "label": "needs:architect",
      "default_status_on_handoff": "In Review"
    },
    "implementer": {
      "label": "needs:implementer",
      "default_status_on_pickup": "In progress"
    },
    "reviewer": {
      "label": "needs:reviewer",
      "default_status_on_handoff": "In Review"
    },
    "user": {
      "label": "needs:user"
    },
    "ci": {
      "label": "needs:ci"
    },
    "merge": {
      "label": "needs:merge"
    }
  },
  "primary_next_labels": [
    "needs:architect",
    "needs:implementer",
    "needs:reviewer",
    "needs:user",
    "needs:ci",
    "needs:merge",
    "blocked"
  ]
}
```

The first implementation can keep this config embedded in shell defaults, but
the design target should be explicit configuration so other projects can add or
rename roles without editing helper code.

Configuration should be split into default-safe core settings and optional
project-specific settings.

Core defaults should cover:

```text
roles
primary next-action labels
blocked label
label mutual exclusion
no Project v2 dependency
```

Optional project config may cover:

```text
issue type labels
allowed labels by issue type
Project owner, number, status field, and status options
Roadmap Status source and allowed values
Project Status <-> Roadmap Status mapping
Epic and child issue conventions
```

When optional config is absent, helpers must fail closed or skip that capability
with a clear message. A new project should be able to run basic label-routing
audit without defining Project v2 or Roadmap Status. Unknown labels, unknown
status mappings, or unknown Roadmap values should be reported, not silently
rewritten.

Project/Roadmap synchronization should therefore be opt-in:

```text
agent-audit
  fast label and contract checks

agent-audit --project
  slower Project/Roadmap drift checks, only when configured

agent-project-sync --dry-run
  print a repair plan for configured Project/Roadmap drift

agent-project-sync --apply
  explicit mutation for a specified issue or narrow filter
```

This avoids importing Tiny IPA-specific labels, Project fields, or roadmap
states into projects that only want the portable role-routing helpers.

## What Not To Automate Yet

Do not build a full agent scheduler inside Tiny IPA.

The helpers should not:

- assign work based on model identity
- decide product scope
- decide architecture boundaries
- override issue contracts
- infer branch strategy from changed files
- close issues without completion evidence
- treat Project status as authoritative

They should make the existing GitHub workflow faster, more reliable, and easier
for different agent sessions to pick up.

## Migration Path

1. Keep the current read helpers as stable primitives.
2. Make `agent-label set-next` role-generic through a configurable primary label
   set.
3. Extend `agent-audit` to recognize unknown or conflicting role labels.
4. Add `Owner role`, `Review role`, `Acceptance role`, and role-generic
   `Completion handoff` examples to workflow docs.
5. Implement `agent-pickup` and `agent-handoff` only after they accept explicit
   `--role` / `--from` roles and fail closed on unknown handoff values.
6. Harvest the generic model into Agent Foundry after it survives at least one
   multi-role project flow.

## Open Questions

- Should `reviewer` be a default role in every project, or only enabled by
  project config?
- Should helper commands post comments directly, or print templates by default
  and require `--apply` to post?
- Should batch checkpoints use no `needs:*` label, or a role label such as
  `needs:architect` with a non-blocking batch marker?
- Should PR review state be mirrored into issue labels automatically, or only
  audited and suggested?
