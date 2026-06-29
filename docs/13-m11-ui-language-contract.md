# M11 UI Language Contract and Copy Inventory

This contract defines the first M11 localization boundary for learner-facing UI
language. It is an implementation guide for #214 through #217, not a locale
runtime implementation.

## Locale Contract

Initial supported UI locales:

```text
default locale: zh-CN
selectable locale: en-US
```

`zh-CN` is the default for new/local users unless a later Architect/User
acceptance decision changes it. `en-US` must be selectable without a code
change once #214/#215 implement settings and locale resources.

Locale keys use lower-case dotted paths:

```text
<surface>.<flow>.<element>[.<state>]
```

Examples:

```text
app.nav.today
today.hub.heading.start
practice.feedback.correct
review.recent.empty
settings.review_strength
audio.status.fallback
error.practice.invalid_request
```

Dynamic data remains explicit placeholders inside localized strings:

```text
{level}
{selectedLevel}
{currentLevel}
{groupIndex}
{count}
{phonemes}
{error}
{status}
```

Do not concatenate localized fragments around variable grammar unless the
locale helper supports ordered placeholders. Full phrases should own their
grammar, such as `today.confirm.abandon_pending`.

## Classification Boundary

The structured inventory lives at:

```text
frontend/tests/fixtures/ui-language-copy-inventory.json
```

Every entry is classified as one of:

```text
translatable
domain_token
content_data
developer_only
```

### Translatable Learner-Facing Copy

Move learner-visible prose, headings, buttons, helper text, notices, loading
states, empty states, and recoverable error details into locale resources.

Covered surfaces include:

```text
app shell
Today hub
normal practice
completion summary
current-group review
recent/global review
focus practice
specialty Sound Compare / Sound Practice
audio controls and fallback status
Progress
Settings
API error details that are shown to the learner
```

Backend fields such as `action_label`, `detail`, `question.prompt`, level
labels, and accent comparison labels are learner-visible when the frontend
renders them. Follow-up implementation may either localize them server-side or
return stable codes/parameters for frontend localization, but it must not leave
new learner-facing English copy hidden behind backend response fields.

### Stable Domain Tokens

These values are not ordinary prose and must not be translated as locale copy:

```text
IPA symbols and IPA choices
phoneme tags
US / UK accent identifiers
API enum values and source_scope/origin codes
group_type values
learner_level values: entry, mid
mastery_status values: new, weak, learning, mastered
error codes such as CONTENT_NOT_READY and INVALID_FOCUS
route paths and HTTP method names
```

User-facing labels for those tokens may be localized, but the token values
themselves remain stable data or machine contracts.

### Content Data

Do not move source content into locale resources:

```text
item.word
item.meaning_zh
IPA strings
correct_answer / selected_answer
phoneme inventory symbols
accent comparison IPA values
word/source metadata
content/core_*.json values
```

`meaning_zh` is content curation data, not UI locale text. M11 must not
translate source word content or reinterpret content import behavior.

### Developer-Only Copy

Test names, CSS class names, internal comments, CLI commands, fixture labels,
and non-rendered implementation notes do not need locale keys. If a command or
diagnostic is rendered to learners, classify the rendered prose as
`translatable` and keep the command/token itself as a stable token.

## Missing-Key Behavior

Implementation must fail visibly for missing learner-facing keys:

```text
dev/test: throw or render a deterministic missing-key marker
production: fall back to en-US text only with a visible telemetry/test signal
never: silently hide buttons, labels, or recovery actions
```

Recommended marker shape:

```text
⟦missing:<locale>:<key>⟧
```

Interactive controls must remain visible even when a key is missing. A missing
translation may degrade text quality, but must not remove actions such as start,
resume, review, focus, clear focus, audio replay, or retry.

## Accepted Initial Inventory

The inventory fixture currently covers these key families:

```text
app.*
today.*
practice.*
review.*
focus.*
specialty.*
audio.*
progress.*
settings.*
error.*
token.*
content.*
dev.*
```

The inventory is intentionally compact. It groups repeated variants when they
share one localization decision, for example `practice.feedback.explanation_labels`
and `progress.stats`.

## Follow-Up Implementation Guidance

#214 should add UI-language persistence and a Settings selector using this
contract without changing auth/account/deployment behavior.

#215 should add locale resources for `zh-CN` and `en-US`, enforce the missing-key
behavior, and decide whether backend-provided learner copy is localized
server-side or represented as codes and parameters.

#216 should extract frontend copy across the inventoried learner workflows.

#217 should verify mobile text fit and bilingual walkthrough evidence.

#218 remains the Architect/User readiness checkpoint for subjective wording,
trial notes, and final M11 acceptance.

## Subjective Product-Copy Decisions Deferred

These decisions are not blockers for #213 but need Architect/User acceptance
before M11 closure:

```text
English product display name for 小音标
whether developer setup hints such as import_words.py should be learner-visible
final Chinese wording for review/focus/specialty practice distinctions
whether Entry/Mid should be displayed as English tokens, Chinese labels, or both
tone for auth placeholder copy before real account work
```
