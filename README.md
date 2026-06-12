# Tiny IPA

Tiny IPA / 小音标 is a small, self-hostable IPA practice app for children and English beginners.

## Quick start

### Backend

```bash
cd backend
uv sync --extra dev --locked
uv run uvicorn app.main:app --reload --port 8010
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8010` by default. Open `http://localhost:5173` in a browser.

### Tests

```bash
# Backend
cd backend && uv run pytest

# Frontend type check
cd frontend && npx tsc --noEmit
```

Backend dependencies are resolved through the project-local `backend/uv.lock` and
`backend/.venv`. Use global tools such as `uv`, `node`, and `npm` to launch the
project commands, but do not rely on globally installed Python or Node project
libraries as verification evidence.

## Documentation

- [Design document index](docs/00-design-index.md)
- [Initial development plan](docs/tiny-ipa-dev-plan.md)
- [Content auto-selection](docs/03-content-auto-selection.md)

The recommended first implementation step is the content feasibility spike described in [Content Auto-Selection](docs/03-content-auto-selection.md).
