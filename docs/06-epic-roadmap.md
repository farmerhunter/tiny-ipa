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
| M6 Core 300 Content and Coverage | #26 | In progress |
| M7 Practice Loop and Review UX | #114 | Backlog |
| M8 Level-based Content Expansion and Core 1000 Rebalance | #108 | Backlog |
| M9 VPS Deployment and Backup | #27 | Backlog |
| M10 UK Accent Compare and Specialty Practice | #28 | Backlog |
| M11 UX Research and Practice Experience Optimization | #102 | Backlog |

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

Expected child issue areas:

```text
practice group model and same-day multi-group flow
continue with another 10-word group after completion
recent mistake review queue
wrong-word and weak-phoneme summary after each group
lightweight answer explanation for missed items
Progress page actions for weak phonemes
focus_phonemes UX replacement with selectable chips/actions
settings wording: words per group rather than words per day
```

Acceptance:

```text
learner can complete multiple 10-word groups in one day
completed group summary shows wrong words and implicated phonemes
learner can start a review group from recent mistakes
weak phonemes can be selected from Progress without typing raw IPA text
focus_phonemes behavior is visible in the next generated group
existing phoneme_stats and scheduler weighting remain the source of review behavior
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
```

## M9：VPS Deployment and Backup

Goal: make the app reachable on a real phone and maintainable on a personal VPS.

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
```

## M10：UK Accent Compare and Specialty Practice

Goal: open optional UK comparison and specialty practice without changing core boundaries.

Expected child issue areas:

```text
UK reviewed subset
show_accent_compare
minimal pair practice
target phoneme practice
accent-specific stats checks
```

Acceptance:

```text
US and UK stats do not mix
UK comparison appears only when enabled
specialty practice reuses question/grading/progress boundaries
```

## M11：UX Research and Practice Experience Optimization

Goal: improve the learning experience after the core practice loop, level model, deployment path, and specialty practice foundations are in place.

Expected child issue areas:

```text
manual observation of learner practice sessions
question wording and feedback comprehension
audio playback ergonomics
mobile layout and child-friendly interaction checks
progress motivation and fatigue controls
```

Acceptance:

```text
UX findings are recorded as evidence, not ad hoc redesign impulses
high-impact interaction fixes are split into scoped child issues
practice experience changes preserve existing scheduling and progress boundaries
```

## Scope Control

Each Epic should:

```text
open only the smallest user-verifiable capability slice
preserve content source and API contracts
avoid premature multi-tenant/provider/account machinery
turn cross-issue findings into Epic comments or follow-up child issues
```
