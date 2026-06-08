# Agent GitHub Helpers

These helpers are project-local experiments for speeding up the Tiny IPA
multi-agent workflow. They prefer issue labels and comments for daily routing,
and touch GitHub Project v2 only when a human-visible Kanban status must change.

## Fast Inbox

```bash
tools/agents/agent-inbox architect
tools/agents/agent-inbox implementer
tools/agents/agent-ready-queue
```

`agent-inbox` reads `needs:*` labels only. It deliberately avoids Project v2
queries because labels are faster and more reliable for agent pickup.

`agent-ready-queue` extracts `Execution Contract` lines so an Implementer can
see which ready issues are immediately startable and which are waiting on
`Depends on`.

## Context Pickup

```bash
tools/agents/agent-issue-context 15
```

Use this before pickup, review, or re-review. The command prints the issue,
comments, and likely open PRs.

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
