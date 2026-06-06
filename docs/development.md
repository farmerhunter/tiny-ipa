# Development Workflow

## Issue-driven development

Each meaningful change links to a GitHub issue. Issues are the source of truth for scope, constraints, and acceptance criteria.

### Branch naming

Feature branches follow the convention:

```
agent/<issue-number>-<short-description>
```

Example: `agent/2-scaffold-fastapi-react-skeleton`

### Before starting an issue

1. Read the docs referenced in the issue body.
2. Check if dependent issues are completed.
3. Create a branch from `main`.

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
- **Do not auto-merge** if:
  - CI is failing
  - The change touches the database schema without a migration path
  - The change is destructive (deletes data, rewrites history)
  - The change introduces new external dependencies without discussion
  - The PR description includes a "hold" or "do not merge" note

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
