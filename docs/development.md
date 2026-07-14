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

## M14 frontend build and reverse-proxy routing contract

This #279 contract defines a reviewable routing shape only. It does not
authorize an Nginx install, configuration write, syntax check, reload, VPS
connection, DNS/TLS change, or deployment. Replace placeholders only after a
Human owner supplies the host details and authorizes that host action.

### Canonical build and audio configuration

`VITE_API_BASE` is the frontend build variable. Its deployed value is `/api`,
so browser API requests stay same-origin and carry the session cookie through
the reverse proxy. It may be overridden only by local disposable integration
harnesses. `VITE_API_BASE_URL` is not supported by the current frontend client.

`TINY_IPA_AUDIO_DIR` is the single canonical deployment variable for the audio
directory. FastAPI reads it for the local-development `/audio/` fallback; the
production reverse proxy must use the same physical directory as its
`/audio/` alias. `TINY_IPA_AUDIO_ROOT` is not a supported alias: it has no
precedence or compatibility path and must not be added to an environment file.

Build only from the repository checkout, with the production path made
explicit:

```bash
cd frontend
VITE_API_BASE=/api pnpm run build
```

The build output is `<frontend-dist-dir>`. Do not copy it to a VPS web root
under #279.

### Nginx template shape

This is a prototype for later Human review. It has no real hostname, filesystem
path, port, or certificate value:

```nginx
server {
    listen <tls-listen>;
    server_name <public-hostname>;

    root <frontend-dist-dir>;
    index index.html;

    location = /api/health {
        proxy_pass http://127.0.0.1:<backend-port>;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:<backend-port>;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location ^~ /audio/ {
        alias <audio-dir>/;
        add_header Cache-Control "public, max-age=31536000";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Expected behavior is limited to the contract: `/api` and `/api/health` proxy
to the loopback backend, `/audio/` resolves under the same `<audio-dir>` named
by `TINY_IPA_AUDIO_DIR`, built static assets resolve from
`<frontend-dist-dir>`, and unknown SPA routes fall back to `index.html`.
`/audio/` missing files must remain missing rather than falling back to the SPA.

### Repo-safe verification and Human gates

Repo-safe evidence is the frontend production build, backend local `/audio/`
static-route tests, and the M14 routing contract test. They do not prove that
Nginx is installed or that a production host serves these paths.

Later Human-gated host commands may include `nginx -t`, a loopback
`/api/health` request, and a browser request for a known `/audio/` asset after
the owner approves VPS access. Do not run Nginx writes/reloads, copy the build,
write an environment file, or change DNS/TLS under #279. #280 owns
backup/restore and #281 owns the final deployment smoke/rollback checklist.

## M14 SQLite backup and restore dry-run

This #280 tool proves a backup/restore round trip with disposable fixture data.
It is not a production backup command and does not authorize reading, copying,
or restoring a private database. All three paths must be under the operating
system temporary directory: the existing source fixture, a new backup artifact,
and a separate new restore target. The tool rejects repository and production
paths, existing output files, missing required tables, and any in-place restore.

The artifact is a SQLite database copy created with the SQLite backup API. The
tool runs `PRAGMA quick_check` and compares schema plus non-secret per-table
counts and fingerprints across source, backup artifact, and restore target. It verifies
shared `words`/`phonemes` plus `users`, `auth_sessions`, `settings`,
`daily_sessions`, `session_items`, `attempts`, and `phoneme_stats`. It never
prints user rows, password hashes, session token hashes, or secrets.

The automated dry-run creates its own temporary fixture and is the reproducible
local proof:

```bash
uv run --project backend pytest backend/tests/test_backup_restore_dry_run.py -q
```

For an explicit disposable fixture created by a test or local experiment, run:

```bash
uv run --project backend python backend/scripts/backup_restore_dry_run.py \
  --source <temp-dir>/source.sqlite \
  --backup <temp-dir>/backup.sqlite \
  --restore <temp-dir>/restored.sqlite
```

Keep the temporary artifact and restored database only until the result has
been reviewed, then remove that temporary directory using the local operating
system cleanup procedure. Do not add overwrite, owner-claim apply, cron,
systemd, or remote-copy behavior to this dry-run tool. Production retention,
off-host copies, restore authorization, and rollback execution remain
Human-gated; #281 owns the all-system smoke/rollback checklist.

## M14 deployment smoke, rollback, and evidence checklist

This #281 checklist is the evidence packet for the later #282 Architect/User
readiness gate. It is not evidence that a VPS, systemd unit, Nginx, TLS,
backup artifact, or restore has been validated. Record every row as one of
`local-passed`, `pending-human-input`, `vps-passed`, or `blocked`; a missing
row is a blocker rather than an assumed pass.

### Result record format

Use this format for each check in the eventual #282 evidence comment. Do not
paste credentials, session cookies, token hashes, or private database rows.

```text
check: <checklist item>
status: local-passed | pending-human-input | vps-passed | blocked
evidence: <command result, sanitized log location, screenshot, or PR link>
owner: <Human operator or role>
stop condition: <what prevents the next check>
```

### Local/disposable preflight: executable now

These commands are objective local evidence only. They neither start a service
nor contact a VPS:

```bash
uv run --project backend pytest \
  backend/tests/test_auth_api.py \
  backend/tests/test_audio_validation.py \
  backend/tests/test_backup_restore_dry_run.py \
  backend/tests/test_m14_deployment_contract.py \
  backend/tests/test_m14_systemd_runbook.py \
  backend/tests/test_m14_reverse_proxy_contract.py \
  backend/tests/test_m14_backup_restore_contract.py -q

cd frontend
VITE_API_BASE=/api pnpm run build

cd ..
git diff --check
tools/agents/agent-audit
```

Mark the backup row `local-passed` only when #280's temporary fixture round
trip passes. That proof covers shared content plus authenticated runtime tables,
but it is not a production artifact or production restore authorization.

### Human-gated VPS preflight inputs

Before a real-host smoke, a Human operator must record all of the following as
`pending-human-input` until supplied: exact HTTPS domain, approved SSH host and
service user, operating-system/runtime versions, reserved backend/proxy ports,
reverse-proxy and TLS ownership, session-secret provisioning channel, production
database path, backup destination/retention, and the authorized restore owner.

Do not start if #277 production checks are unresolved: an exact allowed HTTPS
origin, secure cookie policy, and Human-provisioned session secret are required
before a production start. #278 owns the service/environment template; #279
owns the placeholder reverse-proxy contract; #280 is temporary-only proof.

### Human-gated real-host smoke sequence

Run this sequence only after the preflight inputs are recorded and the Human
operator authorizes the VPS action. Capture sanitized command output, browser
screenshots, and service-log timestamps without capturing secrets or private
learner data.

| Check | Expected evidence | Stop condition |
|---|---|---|
| HTTPS/domain | exact approved domain loads over HTTPS; certificate and hostname match | DNS, TLS, redirect, or hostname mismatch |
| frontend load | built SPA loads and a non-API route falls back to `index.html` | missing static asset or SPA fallback failure |
| health | `/api/health` returns its unauthenticated readiness response through the proxy | backend/proxy disagreement or non-OK response |
| authenticated login | approved test account can log in; cookie behavior matches #277 policy | auth error, insecure cookie, wildcard origin, or credential leak in evidence |
| Settings save | a permitted setting persists after reload for the same approved test account | save failure, wrong account state, or cross-user data exposure |
| Today start/resume | a normal group starts, then the same group resumes at its stored breakpoint | group duplication, item-1 replay, or user-state mismatch |
| audio/static | a known approved `/audio/` asset loads from the directory named by `TINY_IPA_AUDIO_DIR` | missing/static fallback ambiguity or use of `TINY_IPA_AUDIO_ROOT` |
| service restart | after a Human-authorized restart, health and the approved test-account state remain coherent | restart loop, unavailable health, or unexpected runtime-data loss |

The deployed frontend must use `VITE_API_BASE=/api`. `TINY_IPA_AUDIO_DIR` is
the canonical audio variable; `TINY_IPA_AUDIO_ROOT` is not a supported alias.
Do not substitute a direct backend origin for the #279 reverse-proxy contract.

### Backup, restore, rollback, and stop criteria

Before any production restart or rollback decision, record whether a Human has
authorized production backup creation and whether its retention location is
approved. #280 does not authorize either action: its temporary-only artifact
proves the schema/data comparison method, not a production restore.

Stop and escalate to Architect/Human owner when any of the following occurs:

1. Production origin/secret/cookie policy from #277 is invalid or unverified.
2. Any smoke row is `blocked`, including health, login, settings isolation,
   Today resume, audio/static serving, or restart persistence.
3. Backup evidence is absent, the restore target is not separate, or a restore
   could overwrite the only known-good private database.
4. The release requires a schema/data migration, a destructive cleanup, or an
   unreviewed change to runtime/deployment/security configuration.

The first rollback choice is to stop new rollout activity and preserve
sanitized evidence. Do not restore in place, delete a database, or copy a
private artifact without explicit Human authorization. A later authorized
rollback must identify the release being reverted, the approved backup artifact,
the separate restore target, the data-loss assessment, the accountable owner,
and the post-restore health/login/settings/Today/audio evidence.

After the checklist is complete, #282 alone decides whether local evidence,
Human inputs, VPS evidence, and residual blockers justify a deployment decision.
