# M9 UK Accent Compare and Specialty Practice Contract

This document is the accepted Architect contract for Epic #28 / M9. It defines
the product, data, API, stats, audio, and learner-facing boundaries before any
downstream implementation issues are released.

## Contract Decision

M9 keeps UK pronunciation as comparison-only support data. It does not expose UK
as a learner-selectable `primary_accent`.

The learner's graded practice path remains US-first in M9:

```text
primary_accent = "US"
question correct answer = ipa_us
target_phonemes = phoneme_tags_us
audio_url = audio_us
phoneme_stats scope = ("default", "US", phoneme_id)
```

`show_accent_compare` may reveal reviewed UK IPA/tags as a labeled comparison,
but learner-facing copy must not imply that UK answers are accepted for grading.
The comparison is a pronunciation note, not a second answer key.

Rationale:

1. Tiny IPA is still a beginner, teen-facing learning app. M9 should avoid
   making the main answer path ambiguous.
2. Current runtime already models `primary_accent` across sessions, attempts,
   scheduling, and stats, but UK content/audio quality is not yet accepted as a
   production practice path.
3. Comparison-only UK support lets the project validate reviewed UK content and
   learner-facing presentation before expanding grading, audio, and progress UI.

## Accent Field Semantics

Source content continues to carry accent-specific fields:

```text
ipa_us              required for practice-ready words
phoneme_tags_us     required for practice-ready words
audio_us            required for stable production playback where available

ipa_uk              optional in general content, required for UK comparison rows
phoneme_tags_uk     optional in general content, required for UK comparison rows
audio_uk            optional; not required for M9 comparison display
review_status_uk    required by downstream content report before display
```

For M9 comparison eligibility, a word is UK-comparison-ready only when all of the
following are true:

```text
ipa_us is present
ipa_uk is present
phoneme_tags_us is present
phoneme_tags_uk is present
review_status_uk is accepted by the M9 content gate
content_status is not disabled
```

Missing or unreviewed UK fields must result in no comparison row for that word.
They must not produce empty cards, placeholder IPA, or degraded grading.

## Settings Contract

`show_accent_compare` is the only M9 user-facing switch for UK behavior.

| Setting | M9 behavior |
| --- | --- |
| `show_accent_compare = false` | Hide all UK comparison UI. Practice behaves as the current US-first path. |
| `show_accent_compare = true` | Show UK comparison only for eligible reviewed words. Grading remains US. |
| `primary_accent = "US"` | Required runtime learner path for M9. |
| `primary_accent = "UK"` | May remain accepted by lower-level APIs for existing model completeness, but must not be exposed as an M9 learner setting. |

If a backend or local fixture already allows `primary_accent = "UK"`, M9 may add
regression tests for isolation, but UI must not turn that into a supported
learner workflow.

## Practice Response Contract

The existing `GET /api/today` item shape keeps its current US-first fields:

```json
{
  "display_ipa": "/ship-us/",
  "audio_url": "/audio/us/ship.mp3",
  "target_phonemes": ["/.../"],
  "question": {
    "correct_answer": "/ship-us/"
  }
}
```

Downstream UK comparison work may add a separate optional field, for example:

```json
{
  "accent_compare": {
    "enabled": true,
    "primary": {
      "accent": "US",
      "ipa": "/.../",
      "label": "American"
    },
    "comparison": {
      "accent": "UK",
      "ipa": "/.../",
      "label": "British",
      "phoneme_tags": ["/.../"],
      "review_note": "Reviewed for M9 comparison"
    }
  }
}
```

This field is optional and display-only. It must not alter:

```text
question.options
question.correct_answer
display_ipa
audio_url
target_phonemes
attempt.correct_answer
attempt.primary_accent
phoneme_stats primary_accent
```

The frontend may render the comparison as a compact note near the revealed word
or feedback summary. It should use beginner-friendly labels such as
`American sound` and `British note`, not expert-only labels that make a child
feel they chose the wrong system.

## Question, Grading, and Stats Contract

All M9 attempts continue through the existing path:

```text
session_items -> POST /api/attempt -> attempts -> phoneme_stats
```

The session's `primary_accent` remains the single source of truth for grading:

```text
correct_answer = ipa_us when session.primary_accent == "US"
correct_answer = ipa_uk only in lower-level tests or future gated work
```

M9 implementation must not introduce:

```text
parallel attempt tables
parallel specialty stats tables
frontend-only grading
blended US/UK weak or strong phoneme lists
```

Accent-specific stats separation is still a blocking Epic acceptance criterion.
Even though UK is not exposed as an M9 learner path, regression tests must prove
that if a UK session exists, its attempts update:

```text
phoneme_stats(user_id, "UK", phoneme_id)
```

and do not update or read:

```text
phoneme_stats(user_id, "US", phoneme_id)
```

Progress defaults to the current learner path. In M9 production UI this means US
progress. No M9 Progress view may blend US and UK weak/strong phonemes unless a
future contract defines an explicit comparison mode.

## Audio Contract

M9 UK comparison does not require UK audio playback.

Audio behavior remains:

```text
practice audio_url = audio_us for US sessions
recorded/static audio tries first
browser speech fallback remains a confidence/fallback state
no runtime cloud TTS
```

If `audio_uk` exists and is reviewed, a downstream UI may show it only as an
optional comparison affordance after Architect acceptance. It must not replace
the main practice audio, and it must have clear unavailable/fallback states.

## Specialty Practice Contract

Specialty practice reuses the existing group/session/attempt/stat architecture.
It adds new group semantics, not new scoring infrastructure.

Approved M9 specialty group types:

```text
minimal_pair
target_phoneme
```

Both group types must use:

```text
daily_sessions.group_type
session_items
attempts
phoneme_stats
POST /api/attempt
```

Both must preserve `primary_accent` on the session and attempt, and must select
words/tags from the active session accent. For M9 production UI, that active
accent is US.

### Relationship to Existing Review and Focus

| Flow | Source | Learner meaning | M9 boundary |
| --- | --- | --- | --- |
| `normal` | Scheduler-selected level pool | Regular practice group | Unchanged |
| `mistake_review` current group | Misses from the just-completed group | Fix this group's misses | Not specialty practice |
| `mistake_review` recent | Recent wrong attempts across groups | Review recent mistakes | Not specialty practice |
| `weak_focus` | Weak phonemes from `phoneme_stats` or guided focus | Remedial focus on weak sound | Existing recovery/focus flow |
| `minimal_pair` | Reviewed minimal-pair metadata | Compare two easily confused sounds | New M9 specialty |
| `target_phoneme` | Guided selected phoneme or approved specialty list | Practice one chosen sound intentionally | New M9 specialty |

`target_phoneme` may share scheduler weighting code with `weak_focus`, but its
product meaning is different. `weak_focus` is remedial and stat-driven;
`target_phoneme` is learner/teacher-directed specialty practice. If downstream
design cannot keep that distinction clear, `target_phoneme` must be delayed or
folded back into `weak_focus` by Architect decision.

### Minimal-Pair Requirements

Minimal-pair practice requires reviewed metadata before runtime exposure:

```text
minimal_pair_group
target contrast phonemes
candidate words
reason included
child-safety/content caveat
```

The group may include both words from a pair or a small balanced set from the
same contrast. Empty or insufficient candidate states must be learner-safe and
must not create an unanswerable group.

### Target-Phoneme Requirements

Target-phoneme practice must be launched from a guided selection source:

```text
Progress weak sounds
approved specialty sound list
Architect-approved learner-facing entry point
```

It must not require children to type raw IPA. Raw/manual IPA entry remains
advanced tooling, not the primary learner path.

## UK Content Quality Gate

The first downstream content issue must produce a reviewed UK-ready subset and a
human-readable sample table. The sample must include at least:

| word | US IPA | UK IPA | reason included | caveat |
| --- | --- | --- | --- | --- |
| ship | `/.../` | `/.../` | stable beginner word; useful contrast | example row only |

The real report must also include:

```text
source and license metadata
review_status_uk for displayed rows
missing UK IPA/tags count
unsupported UK symbol count
accent-difference candidates
minimal-pair candidates
target-phoneme candidate coverage
known caveats or excluded ambiguous words
```

Architect/content acceptance is required before UK comparison UI depends on the
subset. Reviewer verification covers report mechanics; Architect acceptance
covers pronunciation/content quality fit.

## Learner-Facing Copy and UX Gates

M9 UI copy must keep three ideas separate:

```text
This is the answer for this practice.
This is a British pronunciation note.
This is a specialty practice group.
```

Required copy constraints:

1. Do not label UK IPA as another correct answer in M9.
2. Do not show UK comparison when it is unavailable or unreviewed.
3. Do not use raw internal group names (`minimal_pair`, `target_phoneme`) as the
   only learner-facing labels.
4. Do not make specialty practice look like mistake recovery.
5. Keep mobile density readable; comparison notes should be compact and optional.

Architect acceptance is required for learner-facing comparison/specialty entry
copy. Human trial is required only if the final M9 readiness review finds that
the comparison or specialty entry point is visually confusing or pronunciation
quality remains subjective.

## Downstream Release Plan

After this contract is accepted, release only the foundational issues first:

1. UK-ready content subset and accent coverage report.
2. Accent-specific stats separation and regression checks.

Those may proceed in parallel after issue contracts are created because they
touch different risk areas. UK comparison UI, minimal-pair practice, and
target-phoneme practice remain blocked until the relevant content and stats gates
are accepted.

| Downstream area | Depends on | Gate |
| --- | --- | --- |
| UK content subset | This contract | Architect/content quality acceptance |
| Stats separation checks | This contract | Reviewer objective verification |
| UK comparison UI/API | Content subset + stats checks | Architect copy/UX acceptance |
| Minimal-pair practice | Content subset + stats checks | Architect specialty entry acceptance |
| Target-phoneme practice | Content subset + shared specialty semantics | Architect overlap decision with `weak_focus` |
| Final M9 readiness | All accepted child work | Architect/user gate if subjective trial remains |

## Final M9 Readiness Evidence

The final M9 readiness issue must publish a user-facing note before Epic closure
or final `main` integration. It must include:

```text
completed capability summary
changed learner behavior
trial path for UK comparison off/on
trial path for each accepted specialty practice entry
desktop or mobile screenshots/browser evidence
verification commands
exclusions
residual pronunciation/content risks
whether human trial is required
follow-up gates, if any
```

Final Epic integration to `main` remains Architect/user gated if subjective
accent quality, learner comprehension, or visual fit remains unresolved.

