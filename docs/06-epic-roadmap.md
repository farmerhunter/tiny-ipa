# Epic Roadmap

Tiny IPA uses Epic issues as the primary planning and multi-agent coordination unit. The old milestone names are preserved below as roadmap labels, but GitHub Epic issues now carry cross-issue review, manual QA, and readiness decisions.

## Current Epic Issues

| Epic | GitHub Issue | Status |
| --- | --- | --- |
| M0 Feasibility and Architecture Skeleton | #20 | Done |
| M1 Static Practice Loop | #21 | Done |
| M2 SQLite Persistence and Server-side Grading | #22 | Done |
| M3 Core 100 Audio and Static MP3 Playback | #23 | Done |
| M4 Progress and Settings | #24 | Done |
| M5 Phoneme-Driven Scheduling | #25 | Done |
| M6 Core 300 Content and Coverage | #26 | Done |
| M7 Practice Loop and Review UX | #114 | Done |
| M8 Level-based Content Expansion and Core 1000 Rebalance | #108 | Done |
| M9 UK Accent Compare and Specialty Practice | #28 | Done |
| M10 UX Research and Practice Experience Optimization | #102 | Done |
| M11 Localization and Configurable UI Language | #209 | Planning |
| M12 Minimal Auth and Multi-user Data Isolation | #210 | Planning |
| M13 VPS Deployment and Backup | #27 | Blocked |

## M0：Feasibility and Architecture Skeleton

Goal: validate the automatic content pipeline and establish stable repo boundaries.

Child issues:

```text
#1 content auto-selection feasibility spike
#2 FastAPI / React / content skeleton
#3 content schema, phoneme inventory, validation baseline
#4 developer workflow and CI smoke checks
```

Acceptance:

```text
content candidates can be generated from open sources
US/UK IPA and phoneme coverage reports exist
frontend and backend skeletons run
```

## M1：Static Practice Loop

Goal: prove the IPA-first practice experience with static content.

Child issues:

```text
#5 static seed pack
#6 static /api/today
#7 TodayPractice UI
#8 static-loop verification and QA checklist
```

Acceptance:

```text
mobile browser can complete 10 words
word is hidden before reveal
answer feedback works
manual QA is recorded
```

## M2：SQLite Persistence and Server-side Grading

Goal: make learning behavior persistent and aggregate progress by phoneme.

Child issues:

```text
#10 SQLite data layer and content import pipeline
#11 database-backed /api/today
#12 POST /api/attempt and phoneme_stats
#13 frontend attempt submission and refresh survival
```

Acceptance:

```text
refresh does not lose today's session
attempts persist
phoneme_stats updates correctly
errors have stable codes
Epic #22 records end-to-end persisted-flow QA
```

## M3：Core 100 Audio and Static MP3 Playback

Goal: move from browser TTS placeholder to static audio assets for real early use.

Child issues:

```text
#14 Core 100 audio-ready content set
#15 generate_tts_audio.py for US static MP3 assets
#16 audio metadata validation and /audio static serving in dev
#17 frontend static audio_url playback with browser TTS fallback
```

Acceptance:

```text
Core 100 has ipa_us and phoneme_tags_us
Core 100 has audio_us paths or explicit missing reasons
static /audio/us/*.mp3 playback works
browser TTS fallback still works
Epic #23 records audio/manual QA
```

## M4：Progress and Settings

Goal: form a complete personal learning loop.

Expected child issue areas:

```text
/api/progress
/api/settings GET/PUT
Progress page
Settings page
daily_word_count behavior
```

Acceptance:

```text
learner can see today status, streak, weak phonemes, strong phonemes
settings affect future practice generation
primary_accent remains modeled even if UI stays US-first
```

## M5：Phoneme-Driven Scheduling

Goal: shift practice from fixed/static selection to phoneme-aware review.

Expected child issue areas:

```text
new/review ratio
weak phoneme weighting
avoid short-term repeats
focus_phonemes
scheduler tests
```

Acceptance:

```text
weak phonemes appear more often after repeated mistakes
disabled words are never scheduled
short-term repetition is controlled
```

## M6：Core 300 Content and Coverage

Goal: cover a full stage of IPA learning with enough high-quality content.

Child issues (current execution sequence):

```text
#97 [P0] Refresh Core 300 candidate and coverage gap report
#98 [P1] Curate runtime Core 300 content set
#99 [P1] Add Core 300 validation thresholds and reports
#100 [P1] Verify Core 300 import, scheduling, and practice UX safety
#101 [P2] Run M6 content QA and readiness review
```

Acceptance:

```text
major US phonemes meet coverage goals by threshold and contrast coverage list
difficult learner contrasts have enough examples and explicit risk tags
sources, licenses, and rejection reasons remain auditable
runtime import/importer, scheduling, and UI safety checks all pass for core 300
epic-level readiness is approved by explicit review and residual-risk note
```

Execution contract (latest in #26 body):

```text
Branch strategy: epic integration branch
Integration branch: epic/26-core-300-content
Base branch: epic/26-core-300-content
Target PR base: epic/26-core-300-content
Final PR target: main
Owner role: architect for planning and acceptance
Review role: reviewer
Acceptance role: architect
Completion handoff: batch checkpoint
```

Phase plan:

```text
1) Candidate + coverage baseline (#97)
   - Refresh candidate generation inputs and coverage gap report.
   - Output a reviewable coverage snapshot for M6 planning.

2) Runtime set curation (#98)
   - Promote a curated 300-word runtime file and preserve traceability.
   - Validate required content fields and preserve UK metadata where available.

3) Validation hardening (#99)
   - Add thresholds and reporting around phoneme coverage, contrast gaps, and metadata quality.
   - Keep missing UK metadata/audio as warnings, not blockers.

4) Runtime safety verification (#100)
   - Verify import, scheduling, `/api/today` stability, and disabled-word behavior.
   - Verify larger set does not regress learner-facing UX safety.

5) M6 readiness gate (#101)
   - Record a durable review/readiness note on #26.
   - Confirm blockers cleared, residual risk documented, and go/no-go decision recorded.
```

Dependency model:

```text
#97 -> #98
#97 -> #99
#98 -> #100
#97+#98+#99 -> #101
```

## M7：Practice Loop and Review UX

Goal: turn the current daily quiz into a repeatable learning loop with multiple short practice groups, visible mistake follow-up, and user-understandable weak-phoneme practice.

M7 v1 implemented the first backend and UI slices, but hands-on trial showed
the product workflow was not complete. M7 v2 uses scenario-first delivery:
the learner workflow contract and Playwright walkthrough gate must exist before
additional API/UI implementation is released.

Expected child issue areas for M7 v2:

```text
end-to-end learner workflow contract with state transition table
Playwright mobile walkthrough harness for the accepted contract
explicit next-group, current-group review, recent-review, and focus API semantics
Today practice workflow UI rebuilt around scoped actions and clear copy
Progress/Settings focus workflow without raw IPA typing in the primary path
scenario readiness review with browser evidence
```

Acceptance:

```text
learner can understand the loop without external docs
learner can complete multiple 10-word groups in one day
completed group summary distinguishes current-group misses from broader review suggestions
learner can review current-group misses and recent/global mistakes as separate concepts
weak phonemes can be selected from Progress without typing raw IPA text
focused practice entry and clear-focus behavior are visible and testable
existing phoneme_stats and scheduler weighting remain the source of review behavior
Playwright walkthrough passes in a mobile viewport before M7 v2 acceptance
```

## M8：Level-based Content Expansion and Core 1000 Rebalance

Goal: introduce learner level selection and rebalance the content pipeline so beginner practice stays simple while mid-level practice has a richer multi-syllable word pool.

Expected child issue areas:

```text
level setting and API contract
Entry level using the current Core 300 runtime set
Mid level Core 1000 candidate generation and curation
rebalance selection heuristics for higher two-syllable and multi-syllable ratio
level-aware import and validation reports
level-aware scheduling filters
manual QA for Entry vs Mid practice difficulty
```

Acceptance:

```text
Entry level continues to use the current Core 300 content without regression
Mid level uses a newly generated and reviewed Core 1000 candidate set
Core 1000 improves two-syllable and multi-syllable coverage compared with Core 300
level selection affects future practice generation and is visible to the learner
validation reports separate Entry and Mid coverage/readiness
M8 closure includes final-user usage/trial notes for Entry vs Mid behavior
and browser walkthrough evidence for level switching and practice generation
```

Dependency plan:

```text
#122 defines the Entry/Mid API, domain, UX, and walkthrough contract.
#123 proves Core 1000 source feasibility and syllable metadata strategy.
#124 generates Core 1000 candidates plus rebalance reports.
#125 curates the Mid runtime content set and requires human sample acceptance.
#126 adds level-aware validation/import reports.
#127 wires settings, scheduler, and frontend level selection.
#128 performs final M8 QA, user-facing usage note, and Epic readiness review.
```

## M9：UK Accent Compare and Specialty Practice

Goal: open optional UK comparison and specialty practice without changing core boundaries.

Roadmap status:

```text
Done. Epic #28 closed after the accepted M9 contract, UK-ready content/report,
accent-specific stats separation, settings-gated display-only UK comparison,
minimal-pair specialty practice, target-phoneme specialty practice, and final
readiness/integration gate were completed and merged to main.
```

Completed child issue sequence:

```text
#193 Define M9 accent and specialty practice contract
#196 Build reviewed UK-ready content subset and accent coverage report
#197 Add accent-specific stats separation regression checks
#201 Add settings-gated display-only UK comparison UI/API
#203 Add minimal-pair specialty practice group
#205 Add target-phoneme specialty practice group
#207 Final M9 readiness review and integration gate
```

Acceptance:

```text
US and UK stats do not mix
UK comparison appears only when enabled
specialty practice reuses question/grading/progress boundaries
```

## M10：UX Research and Practice Experience Optimization

Goal: improve the learning experience after the core practice loop and level model, before the later UK comparison and specialty practice runtime work.

Roadmap status:

```text
Done. Epic #102 closed after the accepted UX methodology, learner-paced feedback,
recovery and level-switch copy, progress motivation copy, audio confidence
states, and 小音标 Morandi visual direction were completed and verified.
```

Completed child issue areas:

```text
UX methodology and repeatable design workflow
learner-paced wrong-answer feedback
recovery and level-switch copy clarification
progress motivation and fatigue-aware copy
audio confidence and unavailable-playback states
小音标 Morandi visual direction and placeholder login/account affordance
```

Acceptance:

```text
UX findings are recorded as evidence, not ad hoc redesign impulses
high-impact interaction fixes are split into scoped child issues
practice experience changes preserve existing scheduling and progress boundaries
final closeout is recorded on #102
```

## M11：Localization and Configurable UI Language

Goal: make Tiny IPA configurable for learner-facing UI language before auth and
deployment harden the user boundary.

Roadmap status:

```text
Planning. Epic #209 has been created as the next roadmap stage, but child
issues are not planned or released yet.
```

Expected child issue areas:

```text
UI language contract and learner-facing copy inventory
zh-CN and en-US locale resource structure
settings/API support for configurable UI language
frontend copy extraction across Today, Practice, Progress, Settings, audio,
review/focus, and error states
mobile text-fit and walkthrough evidence for both languages
final localization readiness review and user-facing trial note
```

Acceptance:

```text
zh-CN is the default learner-facing UI language unless product decision changes it
en-US is selectable without code changes
learner-facing copy is not hard-coded across production components
IPA strings, phoneme symbols, accent labels, source word content, and grading
semantics remain domain data rather than translated UI prose
missing translation keys fail visibly in dev/test or have a documented fallback
mobile walkthrough evidence covers major flows and long text fit in both languages
local dev remains runnable without auth or deployment prerequisites
```

Boundaries:

```text
do not translate source word content or meaning_zh in this Epic
do not add real auth, account management, family dashboard, OAuth, social login,
analytics, or deployment changes
do not rewrite scheduler, grading, content import, or progress semantics
```

Execution contract:

```text
Branch strategy: epic integration branch
Integration branch: epic/m11-localization-ui-language
Base branch: epic/m11-localization-ui-language
Target PR base: epic/m11-localization-ui-language
Final PR target: main
Owner role: architect for planning/decomposition; implementer per child issue
Review role: reviewer for UI/API changes; architect for cross-issue contract acceptance
Acceptance role: architect / user for language and copy acceptance
Completion handoff: batch checkpoint
```

## M12：Minimal Auth and Multi-user Data Isolation

Goal: add the minimum authentication and per-user data isolation needed before
personal VPS deployment exposes Tiny IPA beyond a single local default user.

Roadmap status:

```text
Planning. Epic #210 has been created after #209 and before #27. Child issues are
not planned or released yet.
```

Expected child issue areas:

```text
auth/domain contract and personal-VPS threat boundary
user model and owner/admin bootstrap strategy
login, logout, and current-user API/session behavior
per-user scoping for settings, sessions, attempts, progress, phoneme stats,
review/focus state, and backup/restore expectations
old default-user data migration or owner-claim strategy
minimal frontend login/logout/current-user UX using localized copy from M11
security/session tests, user-isolation regression tests, and local dev bootstrap
final auth/data-boundary readiness review before deployment release
```

Acceptance:

```text
runtime learner data resolves an authenticated/current user instead of one global user
settings, normal/review/focus sessions, attempts, progress, and phoneme stats are user-scoped
shared content tables remain global/source-driven
existing default data has an explicit migration or owner-claim strategy with backup guidance
owner/admin bootstrap exists for personal deployment while broad admin UI stays deferred
login/logout/current-user states are visible and tested or walkthrough-covered
local development remains easy without external OAuth
session/cookie/secret behavior needed by VPS deployment is documented and testable
```

Boundaries:

```text
do not add OAuth, social login, family dashboard, multi-role permission matrix,
billing, analytics, email verification, password reset, or broad SaaS account management
do not perform real data migration or mutate real SQLite data without explicit Human approval
do not bind business logic to a VPS provider, domain, or reverse proxy
```

Execution contract:

```text
Branch strategy: epic integration branch
Integration branch: epic/m12-minimal-auth-data-isolation
Base branch: epic/m12-minimal-auth-data-isolation
Target PR base: epic/m12-minimal-auth-data-isolation
Final PR target: main
Owner role: architect for planning/decomposition; implementer per child issue
Review role: reviewer for implementation PRs; architect for security/data-boundary acceptance
Acceptance role: architect / user for auth boundary and migration acceptance
Depends on: #209 for localization/copy boundary before learner-facing auth UI work
Completion handoff: batch checkpoint
```

## M13：VPS Deployment and Backup

Goal: make the app reachable on a real phone and maintainable on a personal VPS.

Roadmap status:

```text
Blocked. Epic #27 has moved after #209 Localization and #210 Minimal Auth /
Multi-user Data Isolation. It should not be decomposed or released to
Implementer until those prerequisites define the language, current-user,
auth-secret, session-cookie, and user-data backup boundaries.
```

Expected child issue areas:

```text
Nginx
HTTPS
systemd backend service
frontend build deployment
SQLite backup and restore
deployment.md
```

Acceptance:

```text
domain works over HTTPS
/api/health works
/audio/ works
service survives restart
backup can restore learning data
auth/session secrets and secure cookie behavior are verified for the deployment target
local dev remains runnable without VPS-only assumptions
```

Boundaries:

```text
deployment is an adapter/contract layer, not a place to add business logic
do not implement auth, localization, account management, or data migration here
do not mutate real SQLite data, secrets, DNS, VPS runtime, or deployment config
without explicit Human approval
```

## Scope Control

Each Epic should:

```text
open only the smallest user-verifiable capability slice
preserve content source and API contracts
avoid premature multi-tenant/provider/account machinery
turn cross-issue findings into Epic comments or follow-up child issues
```
