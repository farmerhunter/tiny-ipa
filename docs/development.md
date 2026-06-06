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

## Milestone 1 manual QA checklist

Run through these steps before approving M1 as complete:

### Backend

- [ ] `GET /api/health` returns `{"status": "ok", ...}`
- [ ] `GET /api/today` returns 10 items with correct JSON shape
- [ ] `GET /api/today?daily_word_count=5` returns 5 items
- [ ] `GET /api/today?primary_accent=UK` returns UK IPA strings
- [ ] `GET /api/today?session_date=2026-01-15` returns stable results across refreshes
- [ ] `GET /api/today?primary_accent=FR` returns 422
- [ ] `pytest tests/ -v` — all tests pass (49+)
- [ ] Question choices include the correct IPA at least once per item
- [ ] Distractors are phoneme-contrast-aware (not random strings)

### Frontend

- [ ] App opens to TodayPractice screen (no landing page)
- [ ] Initial state shows IPA only; word is hidden
- [ ] "Show word" button reveals word and Chinese meaning
- [ ] Audio button visible after reveal; TTS plays without crashing when audio_url is null
- [ ] Question choices appear after reveal
- [ ] Correct answer → green highlight + "Correct!" feedback
- [ ] Wrong answer → red highlight + shows correct answer
- [ ] "Next" button advances to next item
- [ ] After last item, completed screen shows score
- [ ] "Try again" on error screen retries the API call
- [ ] Layout works on mobile-sized viewport (375px–480px width)
- [ ] IPA font is large and readable (2.5rem)
- [ ] Buttons are finger-friendly (≥14px padding)

### Content

- [ ] No function words in seed_words.json (verified by validate_content.py)
- [ ] All words have ipa_us, phoneme_tags_us, meaning_zh
- [ ] Key contrasts covered: /ɪ/vs/iː/, /e/vs/æ/, /θ/vs/s/, /ʃ/vs/s/, /tʃ/vs/ʃ/, /r/vs/l/, /v/vs/w/
- [ ] /ʌ/, /ɚ/, /ʒ/ have at least some representation

## Completion checklist template

When finishing an issue, include this in the completion comment:

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

## Directory conventions

| Directory | Purpose | Tracked? |
|---|---|---|
| `content/` | Source-of-truth content configs | Yes |
| `content/generated/` | Auto-generated candidate/report files | No |
| `content/sources/` | Downloaded external data (ipa-dict) | No |
| `audio/` | Generated mp3 audio assets | No |
| `*.sqlite` | SQLite database files | No |
