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
tools/agents/agent-ready-queue
```

`agent-inbox` reads `needs:*` labels only. It deliberately avoids Project v2
queries because labels are faster and more reliable for agent pickup. It uses
GitHub's REST API rather than `gh issue list` because the latter can hit
GraphQL/TLS timeouts in our current network setup. `agent-inbox all` fetches
open issues once and groups labels locally, instead of making one network call
per label.

`agent-ready-queue` extracts `Execution Contract` lines so an Implementer can
see which ready issues are immediately startable and which are waiting on
`Depends on`. It reads both issue bodies and issue comments because many
contracts are added after issue creation. It fetches the issue list once and
then reads comments only for the queued issues.

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
tools/agents/agent-label 15 remove needs:implementer
```

Use `agent-label` for role routing when GraphQL-backed `gh issue edit` is slow
or flaky. `set-next` removes the other primary next-action labels before adding
the requested label. It reads current labels first, so it avoids unnecessary
delete/add calls when the issue is already in the requested route.

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
