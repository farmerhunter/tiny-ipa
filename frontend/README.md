# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

## M7 Walkthrough

Run the M7 v2 learner workflow harness from this directory:

```bash
pnpm test:e2e:m7
```

The harness uses `@playwright/test`, Chromium, a mobile viewport, and route-mocked disposable API data. It does not connect to the local backend or mutate `backend/tiny_ipa.sqlite`. Failure screenshots, traces, and videos are written under `test-results/m7-walkthrough`; the HTML report is written under `playwright-report/m7`.

Some contract assertions are marked as expected failures until the later M7 v2 implementation issues add the scoped next-group, current-group review, recent-review, and focused-practice behavior. Tooling/bootstrap failures are still surfaced by the passing smoke and summary tests.

## M10 UX Walkthrough

Run the M10 UX evidence harness from this directory:

```bash
pnpm test:e2e:m10
```

The harness uses desktop and Pixel 5 Chromium projects with route-mocked disposable API data. It preserves the #174 audit scenarios as repeatable evidence: Today start, wrong-answer feedback, current-group review, recent mistakes, Entry/Mid switching, Progress focus entry, Settings changes, audio/TTS visible status, mobile Today, and mobile Settings. It does not connect to the local backend or mutate `backend/tiny_ipa.sqlite`. Screenshots are attached to Playwright test results under `test-results/m10-walkthrough`; the HTML report is written under `playwright-report/m10`.

## M11 Real Backend State Walkthrough

Run the M11 Today/Progress/Settings consistency harness from this directory:

```bash
pnpm test:e2e:m11-real
```

The harness starts FastAPI against an isolated `/tmp/tiny-ipa-m11-real-*.sqlite` database, imports the small backend content fixture, seeds deterministic weak-phoneme state, and runs the frontend against that backend through `VITE_API_BASE`. It covers Settings review-strength persistence, future regular-group scheduling, Progress unfinished/resume callout behavior, Today resume, completion clearing the callout, and zh-CN visible-copy regression checks. It does not mutate `backend/tiny_ipa.sqlite`.

## Real workflow CI gate

```bash
pnpm test:e2e:core100-real
pnpm test:e2e:m13-real
```

The first command runs all three mobile Chromium workflows in CI: regular practice
with native MP3 decoding and relogin persistence; the development-only listening
preview; and Settings mode changes, next regular group, current-group review,
weak focus, clear-focus return, unavailable Sound Compare, chosen-sound practice,
and return/resume of regular practice. The second runs the mode/review/specialty
workflow alone using the same isolated harness.

Each run creates a fresh temporary SQLite database and audio root from the frozen
99-file archive. A separate synthetic workflow account keeps its one-item groups
and weak-sound fixture independent of the twelve-item media test. No production
account, API response or media playback mock is used. Sound Compare intentionally
checks the empty-state/no-score path: current source packs have no pair metadata;
this is not evidence of a working content-backed comparison group. Results and
failure traces are under `test-results/core100-real` and `playwright-report/core100-real`.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```


## Opt-in Sound Compare content candidate

```bash
pnpm test:e2e:sound-compare-candidate
```

Runs a separate temporary database/audio root with only four validated pair fields
added to the frozen Core100 fixture: came/game and back/bag. The mobile walkthrough
uses real API/SQLite and native playback of all four packaged recordings; it checks
one wrong answer, first-answer replay without extra counting, completion, and return
to the selected normal choose-word mode with reload/resume. The default three-flow
suite still tests the actual unavailable comparison state without candidate metadata.
Both commands run in CI. Candidate failure evidence has its own
`test-results/sound-compare-candidate` / `playwright-report/sound-compare-candidate`.
This proves the existing Word-to-IPA specialty route, not listening diagnosis or
human phonetic/teaching acceptance. No production content or lesson activation.
