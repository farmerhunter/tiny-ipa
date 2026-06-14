# Agent GitHub Helpers

These helpers are project-local experiments for speeding up the Tiny IPA
multi-agent workflow. They prefer issue labels and comments for daily routing,
and touch GitHub Project v2 only when a human-visible Kanban status must change.

Requirements:

```bash
gh
jq
```

## Fast Inbox

```bash
tools/agents/agent-inbox architect
tools/agents/agent-inbox implementer
tools/agents/agent-inbox reviewer
tools/agents/agent-role-config
tools/agents/agent-permission-smoke
tools/agents/agent-ready-queue
tools/agents/agent-ready-queue --role reviewer
tools/agents/agent-pickup 63 --role implementer
tools/agents/agent-handoff 64 --from implementer
tools/agents/agent-handoff 64 --from reviewer --to implementer
tools/agents/agent-comment issue 86 --body-file /tmp/comment.md
tools/agents/agent-batch-accept --epic 83 --issue 86 --issue 87
tools/agents/agent-release-queue --epic 83 --role implementer --issue 89 --issue 90
tools/agents/agent-dogfood-report --helper "agent-audit: clean" --verification "tests passed" --durable "PR #91"
tools/agents/agent-audit
```

Role routing is configured by `tools/agents/role-routing.conf`, with a built-in
fallback in `_lib.sh` so helpers still work if the config file is absent. The
config is shell-readable and defines roles, each role's inbox label, and the
primary next-action labels. Use `tools/agents/agent-role-config` to print the
active config compactly. Future projects can adapt the role set by changing
that one config file instead of editing every helper script.

`agent-permission-smoke` is the first check for delegated or resumed agent
turns. It verifies non-mutating GitHub API reads, remote Git reads, and local
Git metadata writes. If it fails, do not begin branch/PR work from that turn;
report the permission downgrade and wait for a user turn with full GitHub
network access and local Git metadata write permission.

`agent-inbox` reads primary next-action labels only. It deliberately avoids Project v2
queries because labels are faster and more reliable for agent pickup. It uses
GitHub's REST API rather than `gh issue list` because the latter can hit
GraphQL/TLS timeouts in our current network setup. `agent-inbox all` fetches
open issues once and groups the configured primary labels locally, instead of
making one network call per label.

`agent-ready-queue` defaults to the configured `implementer` role and also
accepts `--role <role>` for other configured role inboxes, such as `reviewer`.
It extracts `Execution Contract` lines so an agent can see which ready issues
are immediately startable and which are waiting on `Depends on`. It reads both
issue bodies and issue comments because many
contracts are added after issue creation. When multiple contracts exist, it
uses the latest highest-priority contract: `Final Execution Contract`, then
`Execution Contract`, then `Draft Execution Contract`. This prevents stale
draft contracts in issue bodies from overriding newer final handoffs.
It also prints a dependency gate hint, such as `Gate: startable` or
`Gate: waiting on #39`, so Implementers do not need to inspect every dependency
manually before deciding what to pick up. It also prints role-related contract
fields (`Owner role`, `Review role`, `Acceptance role`, and `Completion
handoff`) when present, using the same line-oriented contract parsing helpers
as other scripts. It fetches the open issue list once, filters configured role
labels locally, and then reads comments only for the queued issues.

`agent-pickup` is dry-run first. It verifies that the issue carries the
configured `needs:<role>` label, extracts the latest effective Execution
Contract, checks role and handoff fields, checks dependency gates, and prints
the scheduler changes plus a compact pickup comment template. The dry-run path
does not mutate labels, post comments, or read Project v2. `--apply` is not
implemented in the current prototype.

`agent-handoff` is also dry-run first. It validates the caller's `--from` role
against the configured primary next-action labels, extracts the latest effective
Execution Contract, resolves `Completion handoff:` values such as `to:<role>`,
`batch checkpoint`, `close after evidence`, and `hold`, and prints the planned
label changes plus a compact completion/handoff comment template. Use
`--to <role|none|batch>` to override the contract route for explicit handoffs.
The dry-run path does not mutate labels, post comments, close issues, or read
Project v2. `--apply` is not implemented in the current prototype.

`agent-comment` is a REST-first durable comment helper. It supports explicit
`issue` and `pr` targets by number, requires `--body-file` input, previews by
default, and posts only with `--apply`. It uses the REST issue-comments endpoint
for both issue and PR conversation comments, avoiding GraphQL-backed
`gh issue comment` / `gh pr comment` ordinary paths. It fails closed on unknown
target types, missing or empty body files, target/type mismatches, and failed
REST writes.

`agent-batch-accept` is dry-run only. It takes an Epic plus child issues or PRs
and prints an Architect batch acceptance plan: integration branch, child issue
state, PR base/head hints, linked issues, changed files, REST status hints when
available, merge/close/label/Project plans, release or hold notes, and a durable
batch checkpoint comment template. It never merges PRs, closes issues, mutates
labels, updates Project v2, or integrates into `main`.

`agent-release-queue` is dry-run only. It takes an Epic, a target role, and one
or more child issues, checks dependency gates from the latest effective
Execution Contract, and prints planned next-action label changes, release
comments, hold reasons, and Project sync decisions. It can check closed issue
dependencies and merged PR dependencies, but it never mutates labels, comments,
Project v2, issues, PRs, or `main`.

`agent-dogfood-report` is explicit-input only. It formats compact handoff
sections for helper commands used, verification, durable GitHub state,
direct-thread dispatch, fallback/manual work, manual steps reduced, and residual
risks. It deliberately does not parse arbitrary terminal logs or infer success.

`agent-audit` is a read-only consistency check. It looks for common workflow
drift without touching GitHub Project v2:

- open issues with multiple primary next-action labels
- open issues with unknown `needs:*` labels
- open task issues with no next-action label, no active pickup comment, and no
  batch checkpoint
- closed issues that still carry next-action labels
- pickup comments where the issue still carries a stale next-action label
- unknown or missing role-generic `Completion handoff:` values
- `needs:implementer` issues with missing contract fields
- open PRs whose base branch does not match the linked issue contract

## Context Pickup

```bash
tools/agents/agent-issue-context 15
tools/agents/agent-pr-context 44
```

Use this before pickup, review, or re-review. The command prints the issue,
comments, and likely open PRs. It also uses REST for issue/comment reads.

Use `agent-pr-context` before PR review. It reads PR metadata, commits, files,
comments, and review comments through REST, which is often faster and more
reliable than `gh pr view` in this project.

## Labels

```bash
tools/agents/agent-label 15 set-next needs:implementer
tools/agents/agent-label 15 set-next needs:architect
tools/agents/agent-label 15 set-next needs:reviewer
tools/agents/agent-label 15 remove needs:implementer
```

Use `agent-label` for role routing when GraphQL-backed `gh issue edit` is slow
or flaky. `set-next` accepts only configured primary next-action labels, removes
the other configured primary labels before adding the requested label, and fails
closed on unknown labels. It reads current labels first, so it avoids
unnecessary delete/add calls when the issue is already in the requested route.

## Project Status

```bash
tools/agents/agent-project-status 15 "In progress"
tools/agents/agent-project-status 15 "In Review"
tools/agents/agent-project-status 15 Done
```

Project v2 item IDs are cached in `.agent-cache/project-items.tsv`. Refresh
manually when needed:

```bash
tools/agents/agent-project-status --refresh
```

Do not use Project status as the only routing signal. Update labels and comments
first, then sync Project status for the visual board.
