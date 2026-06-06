# Development Workflow

## Epic-driven development

Tiny IPA uses Epic issues as the planning and cross-issue coordination layer. Child issues are the executable work and acceptance units.

```text
Epic issue -> child issues -> issue branches -> PRs -> main
```

Use:

```text
type:epic
type:task
```

Read `docs/08-multi-agent-epic-workflow.md` before coordinating multi-agent work.

## Finding agent work

Use `needs:*` labels as the cross-agent handoff inbox. Project status remains the visual board, but labels are the reliable CLI lookup mechanism.

```bash
# Architect: planning, review, merge, readiness
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:architect

# Implementer: coding, fixes, verification
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:implementer

# User decision needed
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:user

# Ready to merge
gh issue list -R farmerhunter/tiny-ipa --state open --label needs:merge
```

When handing work to another role, update the label and add a short issue or PR comment explaining the next action.

Do not put `needs:implementer` on an Epic. Implementers pick up child issues, not Epic containers. If an Epic-level concern requires execution, create a child task such as integration QA, cross-issue gap fixing, or final manual QA evidence.

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

1. Read the docs referenced in the issue body.
2. Check the parent Epic for dependencies and readiness notes.
3. Confirm the child issue is in `Ready`.
4. Move the child issue to `In progress`.
5. Create a branch from `main`.

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

- Code work should be submitted as a PR against `main`.
- PRs that pass CI checks may be auto-merged for normal scoped changes.
- Default PR granularity is one child issue per PR.
- Cross-issue findings belong on the parent Epic unless one child issue clearly owns them.
- **Do not auto-merge** if:
  - CI is failing
  - The change touches the database schema without a migration path
  - The change is destructive (deletes data, rewrites history)
  - The change introduces new external dependencies without discussion
  - The PR description includes a "hold" or "do not merge" note
  - The PR spans multiple child issues without clear mapping

### Project status flow

Use the Project board as shared state:

```text
Backlog -> Ready -> In progress -> In Review -> Done
```

Architect moves work from `Backlog` to `Ready`. Implementer moves claimed work to `In progress` and then `In Review` once the PR is open. Architect moves it to `Done` only after merge, issue closure, and required verification.

Handoff labels must match the current owner of the next action:

```text
needs:implementer -> implementer should pick up or fix a child issue or PR
needs:architect   -> architect should review, merge, or decide readiness
needs:user        -> user decision is needed
needs:ci          -> checks are still running
needs:merge       -> reviewed and ready to merge
blocked           -> latest comment explains the blocker
```

Allowed Epic handoff labels are `needs:architect`, `needs:user`, and `blocked`. `needs:implementer`, `needs:ci`, and `needs:merge` belong on child issues or PRs.

## Local development

### Prerequisites

- Python >= 3.9 (>= 3.11 recommended)
- Node.js >= 18
- npm

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
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api` to `localhost:8010`.

Type check:

```bash
npx tsc --noEmit
```

Production build:

```bash
npm run build
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
