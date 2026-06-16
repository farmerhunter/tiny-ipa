# Development Workflow

## Epic-driven development

Tiny IPA uses Epic issues as the planning and cross-issue coordination layer. Child issues are the executable work and acceptance units.

```text
Epic issue -> Epic integration branch -> child issues -> issue branches -> issue PRs -> Epic PR -> main
```

Use:

```text
type:epic
type:task
```

Read `docs/08-multi-agent-epic-workflow.md` before coordinating multi-agent work.
Read `docs/09-role-generic-agent-helpers.md` when changing helper behavior or
adding new role-routing automation.

## Finding agent work

Use `needs:*` labels as the cross-agent handoff inbox. Project status remains the visual board, but labels are the reliable CLI lookup mechanism.

```bash
# Delegated/resumed agent turn permission check
tools/agents/agent-permission-smoke

# Architect: planning, review, merge, readiness
tools/agents/agent-inbox architect

# Implementer: coding, fixes, verification
tools/agents/agent-inbox implementer

# Implementer queue with dependency gates
tools/agents/agent-ready-queue

# User decision needed
tools/agents/agent-inbox user

# Ready to merge
tools/agents/agent-inbox merge
```

The examples above are the roles currently used most often in Tiny IPA. The
helper model is intentionally role-generic: future projects or later phases may
add roles such as `reviewer` without changing the core inbox pattern.

When handing work to another role, update the label and add a short issue or PR comment explaining the next action.

The raw `gh issue list` commands still work, but agents should prefer the local helpers above. They use retry defaults, avoid Project v2 queries during ordinary pickup, and keep the command surface consistent across Codex, Claude Code, DeepSeek, and similar environments.

The helpers prefer GitHub REST API reads for inbox and issue context because `gh issue list/view` can use GraphQL and has been the most common source of TLS timeouts during M3.

Run `tools/agents/agent-permission-smoke` before GitHub-backed pickup when work
arrives through cross-thread dispatch or a resumed agent turn. If GitHub API,
remote Git, or local Git metadata writes are restricted, stop before creating a
branch or mutating durable state. Report the permission downgrade in the thread
and wait for a user turn with full GitHub network access and local Git metadata
write permission.

Do not put `needs:implementer` on an Epic. Implementers pick up child issues, not Epic containers. If an Epic-level concern requires execution, create a child task such as integration QA, cross-issue gap fixing, or final manual QA evidence.

`Ready + needs:implementer` may represent an Implementer queue, not only work that can start immediately. Implementers should read all ready issues in the queue, sort them by the `Depends on` line in each `Execution Contract`, and execute only the issues whose dependencies are satisfied.

Do not make every child issue review a queue-wide stop. A previous issue's review blocks later implementation only when the later issue's `Execution Contract` says so with a hard `Depends on` gate, or when the Architect posts an explicit hold on the Epic. Otherwise the Implementer may continue through the ready queue and let review feedback converge through the normal PR cycle.

When an issue returns from Architect review, read both the issue handoff comment and the linked PR comment:

```bash
tools/agents/agent-issue-context <issue-number>
tools/agents/agent-pr-context <pr-number>
```

Architect must not rely on only one comment surface when moving an issue back to `needs:implementer`. The issue comment should point to the PR review, name the fix branch, and summarize the blocker. The PR conversation should also include the latest handoff or a pointer to it, especially for stacked-branch refresh requests.

## Issue-driven execution

Each meaningful code change links to a child issue. Child issues are the source of truth for local scope, constraints, and acceptance criteria. Epic issues are the source of truth for cross-issue QA, readiness, and workflow closure.

Epic-level findings should stay on the Epic only when they are coordination, review, or decision-making work. Split them into child issues when they require code changes, tests, manual verification, data migration, or an Implementer completion comment.

### Branch naming

Feature branches follow the convention:

```
agent/<issue-number>-<short-description>
```

Example: `agent/2-scaffold-fastapi-react-skeleton`

### Before starting an issue

1. Run `tools/agents/agent-permission-smoke` for delegated or resumed turns.
2. Read the docs referenced in the issue body.
3. Check the parent Epic for dependencies and readiness notes.
4. Confirm the child issue is in `Ready`.
5. Read the issue's `Execution Contract`.
6. Confirm every `Depends on` condition is satisfied.
7. Move the child issue to `In progress`.
8. Comment with `Pickup confirmed`, including branch strategy, working branch, PR base, and verification plan.
9. Create the issue branch from the contract's base branch.

Do not start implementation if the `Execution Contract` is missing or the PR base is ambiguous. Move the issue to `needs:architect` and ask for the missing branch strategy.

Do not start implementation if `agent-permission-smoke` fails. A cross-thread
dispatch ping may arrive under a restricted sandbox profile; in that case the
agent should report the downgrade instead of triggering approval prompts across
every GitHub or Git metadata operation.

Do not start implementation for a dependent issue whose `Depends on` condition is not satisfied yet. Leave the issue in `Ready` and optionally add:

```markdown
## Queued by Implementer

Dependency not satisfied yet.
Waiting for #... to merge into `epic/...`.
```

### When completing an issue

Before closing an issue, add a completion comment with:

```markdown
## Completion

Scope completed:
- ...

Verification:
- Command: `...`
- Result: ...

Residual risks:
- ...
```

### Pull requests and auto-merge

- Default multi-agent code work should be submitted as an issue PR against the parent Epic integration branch.
- The Architect owns the final Epic PR from the Epic integration branch to `main`.
- PRs that pass CI checks may be auto-merged for normal scoped changes.
- Default PR granularity is one child issue per PR.
- Direct PRs to `main` are allowed for independent documentation, tooling, or small fixes outside an active Epic integration branch.
- Cross-issue findings belong on the parent Epic unless one child issue clearly owns them.
- Stacked PRs are an explicit exception. Use them only when the Architect has written the stack order and final integration path in the issue's `Execution Contract`.
- For stacked PRs, merging a PR only merges into that PR's base branch. Before closing issues or Epics, verify the final commits are reachable from `origin/main`. Use a final integration PR to `main` or retarget PRs in order.
- **Do not auto-merge** if:
  - CI is failing
  - The change touches the database schema without a migration path
  - The change is destructive (deletes data, rewrites history)
  - The change introduces new external dependencies without discussion
  - The PR description includes a "hold" or "do not merge" note
  - The PR spans multiple child issues without clear mapping

### Branch strategy

The Architect decides branch strategy before moving a child issue to `Ready`.

The Architect may move a whole dependent issue sequence to `Ready` at once when each issue has an `Execution Contract`. This avoids repeated Architect handoffs between issues. The Implementer owns queue ordering from that point, but dependency gates still apply.

Default:

```text
Branch strategy: epic integration branch
Issue branch base: epic/<epic-short-name>
Issue PR base: epic/<epic-short-name>
Final PR base: main
```

Allowed exceptions:

```text
issue branch to main
stacked PR
```

`issue branch to main` is for small independent work. `stacked PR` is for dependency chains where each layer has independent review value and the added Git complexity is justified.

### Project status flow

Use the Project board as shared state:

```text
Backlog -> Ready -> In progress -> In Review -> Done
```

Architect moves work from `Backlog` to `Ready`. Implementer moves claimed work to `In progress` and then `In Review` once the PR is open. Architect moves it to `Done` only after merge, issue closure, and required verification.

Use labels and comments first; sync Project status after the routing signal is already durable. For Project updates, prefer:

```bash
tools/agents/agent-project-status <issue-number> Ready
tools/agents/agent-project-status <issue-number> "In progress"
tools/agents/agent-project-status <issue-number> "In Review"
tools/agents/agent-project-status <issue-number> Done
```

The helper caches Project item IDs under `.agent-cache/` to avoid repeated full Project scans.

Handoff labels must match the current owner of the next action:

```text
needs:implementer -> implementer should pick up or fix a child issue or PR
needs:architect   -> architect should review, merge, or decide readiness
needs:user        -> user decision is needed
needs:ci          -> checks are still running
needs:merge       -> reviewed and ready to merge
blocked           -> latest comment explains the blocker
```

Prefer the REST-backed helper for next-action label routing:

```bash
tools/agents/agent-label <issue-number> set-next needs:implementer
tools/agents/agent-label <issue-number> set-next needs:architect
```

Allowed Epic handoff labels are `needs:architect`, `needs:user`, and `blocked`. `needs:implementer`, `needs:ci`, and `needs:merge` belong on child issues or PRs.

### Review handoff

If Architect requests changes on a PR, the handoff is complete only after:

- the PR has detailed review feedback
- the child issue has a short `Implementer handoff` comment linking to that PR feedback
- the PR also has the latest handoff or a short pointer to the issue handoff
- the child issue is labeled `needs:implementer`

Implementer fixes should be pushed to the existing issue branch, not a new branch, unless the Architect explicitly asks for a replacement branch.

## Local development

### Prerequisites

- Python >= 3.9 (>= 3.11 recommended)
- Node.js >= 18
- pnpm

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8010
```

Run tests:

```bash
pytest tests/ -v
```

### Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api` to `localhost:8010`.

Type check:

```bash
pnpm exec tsc --noEmit
```

Production build:

```bash
pnpm run build
```

### Content scripts

```bash
cd backend && source .venv/bin/activate

# Content auto-selection (requires ipa-dict data)
pip install -e ".[content]"
python scripts/select_candidates.py --top-n 5000 \
  --ipa-dict-dir ../content/sources/ipa-dict

# Content validation
python scripts/validate_content.py ../backend/tests/fixtures/content_sample.json
```

## CI

CI runs on every push to `main` and every PR. It checks:

- **Backend**: pytest (all tests in `backend/tests/`)
- **Frontend**: TypeScript type check + Vite production build

CI does not require secrets. Content auto-selection is not run in CI because it requires downloading external data.

## Directory conventions

| Directory | Purpose | Tracked? |
|---|---|---|
| `content/` | Source-of-truth content configs | Yes |
| `content/generated/` | Auto-generated candidate/report files | No |
| `content/sources/` | Downloaded external data (ipa-dict) | No |
| `audio/` | Generated mp3 audio assets | No |
| `*.sqlite` | SQLite database files | No |
