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

# Tester: test planning, evidence execution, gaps, residual risks
tools/agents/agent-inbox tester
tools/agents/agent-ready-queue --role tester

# Implementer queue with dependency gates
tools/agents/agent-ready-queue

# User decision needed
tools/agents/agent-inbox user

# Ready to merge
tools/agents/agent-inbox merge
```

The examples above are the roles currently used most often in Tiny IPA. The
helper model is intentionally role-generic: this repo now includes `tester` for
objective evidence planning and execution, but Tester is optional per issue.
Use it when evidence quality is the bottleneck; do not force a Tester gate for
small low-risk work where Implementer and Reviewer evidence is enough.

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

## Local auth bootstrap

M12 adds auth storage before login/logout routes. For personal deployment setup,
create the first owner explicitly:

```bash
cd backend
python scripts/bootstrap_auth.py --db-url ./tiny_ipa.sqlite owner \
  --username owner --password 'change-me-long-password'
```

For local development, use the guarded dev-user path:

```bash
cd backend
python scripts/bootstrap_auth.py --db-url /tmp/tiny_ipa_dev.sqlite dev-user \
  --enable-local-dev --environment development \
  --username local-dev --password 'local-dev-password'
```

The local-dev command refuses production/deployed environments and does not
enable an auth bypass. It only creates a normal user record for local testing.

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
needs:tester      -> tester should plan or gather objective test evidence
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
uv sync --extra dev --locked
uv run python scripts/import_words.py --source ../content/core_300_words.json
uv run uvicorn app.main:app --reload --port 8010
```

Run tests:

```bash
uv run pytest tests/ -v
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
cd backend

# Content auto-selection (requires ipa-dict data)
uv sync --extra content
uv run python scripts/select_candidates.py --top-n 5000 \
  --ipa-dict-dir ../content/sources/ipa-dict

# Content validation
uv run python scripts/validate_content.py ../backend/tests/fixtures/content_sample.json
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

## M14 VPS backend systemd runbook

This is a planning template for #278. It does not authorize SSH access,
package installation, writing an environment file, or changing systemd on a
real VPS. Replace every angle-bracket placeholder only after the Human owner
has supplied the deployment target details and explicitly authorized the host
action.

### Human inputs and stop conditions

Collect these values before preparing a host-specific unit. Stop if any value
is missing rather than guessing from a local checkout:

| Input | Required shape | Why it is Human-gated |
|---|---|---|
| `<app-root>` | absolute checkout path owned by the service user | determines the executable and read-only code path |
| `<service-user>` / `<service-group>` | non-root account already approved for the service | controls process and file ownership |
| `<data-dir>` / `<log-dir>` | absolute writable directories outside the checkout | protects SQLite and operational logs from source-tree writes |
| `<env-file>` | root-readable deployment file outside the repo | contains the Human-provisioned session secret |
| `<public-hostname>` | exact HTTPS origin selected by the owner | required for production CORS/cookie policy |
| `<backend-port>` | loopback port reserved for the backend | must not conflict with another local service |

Do not continue when the service user would be root, the database path is inside
the checkout, the public origin is not exact HTTPS, or the owner has not
authorized VPS access. #279 owns reverse-proxy routing, #280 owns backup and
restore, and #281 owns the end-to-end smoke/rollback checklist.

### Repo-safe local preflight

These commands run only against the local checkout and disposable local values.
They do not create a production secret or contact a VPS:

```bash
cd backend
uv sync --extra dev --locked
uv run pytest

TINY_IPA_ENV=production \
TINY_IPA_SESSION_SECRET=local-dry-run-only \
TINY_IPA_ALLOWED_ORIGINS=https://example.invalid \
TINY_IPA_COOKIE_SECURE=true \
TINY_IPA_COOKIE_SAMESITE=lax \
uv run python -c "from app.main import create_app; create_app()"
```

The final command only validates the production configuration parser. It does
not start a long-running service. Keep the value `local-dry-run-only` local; it
is not a production secret or a value to copy into a VPS environment file.

### systemd unit template shape

Use this only as a reviewable template. It is not a committed host unit and must
not be copied to `/etc/systemd/system/` without a later Human gate:

```ini
[Unit]
Description=Tiny IPA backend API
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=<service-user>
Group=<service-group>
WorkingDirectory=<app-root>/backend
EnvironmentFile=<env-file>
ExecStart=<app-root>/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port <backend-port>
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=<data-dir> <log-dir>

[Install]
WantedBy=multi-user.target
```

The service process should bind to loopback only. #279 decides how an authorized
reverse proxy reaches it; #278 does not configure that proxy, DNS, or TLS.

### Environment-file template shape

The environment file is a Human-owned deployment artifact. Never commit it,
never put a real value in `.env.example`, and do not generate its secret in this
repository:

```dotenv
TINY_IPA_ENV=production
TINY_IPA_DB_PATH=<data-dir>/tiny_ipa.sqlite
TINY_IPA_SESSION_SECRET=<Human-provisioned secret>
TINY_IPA_ALLOWED_ORIGINS=https://<public-hostname>
TINY_IPA_COOKIE_SECURE=true
TINY_IPA_COOKIE_SAMESITE=lax
TINY_IPA_AUDIO_DIR=<audio-dir>
TINY_IPA_LOG_DIR=<log-dir>
```

Set ownership and permissions so only the approved administrator and service
user can read `<env-file>`. The service must fail closed if its secret, exact
HTTPS origin, or secure cookie policy is invalid; see the M14 #277 contract.

### Authorized-host checks and failure diagnosis

The following commands are Human-gated because they inspect or operate a real
VPS. They are listed for the later authorized run, not for execution from this
repository:

```bash
systemd-analyze verify <unit-file>
systemctl status tiny-ipa-backend.service --no-pager
journalctl -u tiny-ipa-backend.service -n 100 --no-pager
curl --fail --silent --show-error http://127.0.0.1:<backend-port>/api/health
```

| Symptom | First evidence | Stop/escalate condition |
|---|---|---|
| service immediately exits | `journalctl` shows missing secret/origin or cookie policy error | correct only the Human-owned environment file; do not weaken production checks |
| service cannot open SQLite | service status plus data-dir ownership/permissions | hand off to #280 if backup/restore or data movement is implicated |
| port bind fails | journal entry names the occupied loopback port | choose an owner-approved port; do not edit reverse-proxy config in #278 |
| health request fails | local loopback health response and unit status | hand off routing/static behavior to #279 when backend is healthy but public access fails |
| repeated restart loop | journal evidence and systemd start-limit state | stop the unit and obtain Human/Architect review before changing runtime settings |

Do not run `systemctl daemon-reload`, `enable`, `start`, `restart`, package
install commands, SSH commands, DNS/TLS commands, or private SQLite operations
under #278. Those actions require later explicit authorization and their own
M14 acceptance evidence.
