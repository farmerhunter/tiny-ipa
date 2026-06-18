# UX Research and Practice Experience Optimization

This document defines a repeatable UX research and optimization workflow for Tiny IPA. It is written as a project asset, not a one-off M10 checklist, so the same pattern can be reused in later milestones or other learner-facing apps.

## Purpose

Tiny IPA is a youth-facing learning product. UI quality is not only a matter of polish; it affects whether learners understand the practice loop, stay oriented after mistakes, trust feedback, and want to come back without pressure.

M10 should therefore improve the experience through evidence-grounded research, walkthroughs, and scoped experiments rather than ad hoc redesign.

## Core Principle

Every UX change should pass through this loop:

```text
scenario contract
  -> walkthrough or observation evidence
  -> finding synthesis
  -> scoped design or implementation issue
  -> browser/manual verification
  -> explicit accept, defer, or follow-up decision
```

The goal is repeatable judgment. A design decision is stronger when future contributors can see the user scenario, the evidence, the tradeoff, and the verification path.

## Target Learners

Primary audience:

```text
teen or pre-teen English learners
mobile-first usage
limited IPA confidence
short attention windows
needs clear feedback after mistakes
may use Chinese meanings as support
```

Secondary audience:

```text
parents or tutors checking progress
adult English beginners using the same practice loop
project maintainers reviewing UX changes
```

M10 should avoid optimizing only for developer convenience or adult productivity-tool expectations.

## Capability Stack

Use these skills and project practices as complementary roles:

```text
frontend-workflow-designer
  Owns scenario contracts, action semantics, state transitions, and walkthrough gates.

frontend-design
  Owns visual direction exploration, typography, palette, interaction mood, and interface copy quality.

web-design-guidelines
  Reviews UI code against web interface guidelines, including focus states, semantic controls, touch ergonomics, motion, copy, and content handling.

webapp-testing
  Provides local Playwright walkthroughs, screenshots, browser logs, and repeatable interaction evidence.

agent-collaboration
  Keeps GitHub issues, execution contracts, review handoffs, and Project state coherent.
```

No standalone accessibility skill is required for M10 setup, but accessibility concerns still remain in scope through `web-design-guidelines`, manual review, and browser walkthroughs.

## External Skill References

This methodology may reference external skills without importing them into the project or treating them as Agent Foundry-native assets. External skills remain optional, reviewable dependencies that a target environment can install during asset refresh or setup.

Recommended external references:

```text
frontend-design
  Source: anthropics/skills@frontend-design
  Purpose: visual direction exploration, typography, palette, interface tone, and non-template UI critique.
  Requirement: recommended, not mandatory.
  Fallback: use the design exploration gate in this document with local design judgment and screenshots.

web-design-guidelines
  Source: vercel-labs/agent-skills@web-design-guidelines
  Purpose: UI/code review against web interface guidelines, including focus, semantic controls, copy, touch ergonomics, motion, and content handling.
  Requirement: recommended, not mandatory.
  Fallback: manually review against the rules captured in the current project and any locally available UI checklist.

webapp-testing
  Source: anthropics/skills@webapp-testing
  Purpose: repeatable browser walkthroughs, screenshots, traces, and local webapp interaction evidence.
  Requirement: recommended for browser evidence, not mandatory for methodology adoption.
  Fallback: use the existing project Playwright setup or documented manual viewport walkthroughs.
```

Readiness states:

```text
ready
  The external skill is installed and its entry instructions can be read.

optional missing
  The skill is not installed, but the methodology can proceed with the documented fallback.

blocked
  The task explicitly requires that skill's capability and no local fallback is acceptable.
```

Future reusable Agent Foundry assets should declare these references instead of vendoring external skill contents. Asset refresh or installation can then show the missing references, trust notes, and suggested install commands while leaving the final install decision to the target environment.

## Research Units

Use small research units instead of broad redesign themes. Each unit should name:

```text
learner goal
starting state
successful completion state
primary path
alternate path
empty or failure state
evidence required
decision owner
implementation boundary
```

Recommended first units:

```text
Today practice orientation
mistake review and recovery
Entry/Mid level switching
Progress motivation and fatigue
Settings clarity
audio playback confidence
```

## Evidence Types

M10 accepts several evidence types, but each finding must say which type it uses.

```text
browser walkthrough
manual observation note
annotated screenshot
Playwright trace or screenshot
copy comprehension note
design review finding
user or parent/tutor feedback
```

Evidence should capture what the learner experiences, not only whether a component renders.

## Finding Format

Each UX finding should use this shape:

```text
Finding:
Impact:
Evidence:
Affected flow:
Likely cause:
Decision needed:
Recommended next issue:
Risk if deferred:
```

Findings should not directly become code changes until the scope and acceptance path are clear.

## Design Exploration Gate

Visual exploration should happen before large UI rewrites. A design direction proposal should include:

```text
audience fit
tone words
palette tokens
type roles
interaction signature
mobile constraints
what it deliberately avoids
screens or flows affected
acceptance questions
```

For Tiny IPA, useful directions should feel encouraging, clear, and memorable without becoming childish, noisy, or coercive.

## Browser Walkthrough Gate

Every accepted UX implementation issue should define a walkthrough path before coding starts.

Minimum walkthrough fields:

```text
viewport
seed data or fixture state
entry URL
steps
expected visible copy
expected available actions
expected blocked or hidden actions
screenshots or trace required
failure states covered
```

If the flow cannot be automated yet, record the manual path and the reason automation is deferred.

## M10 Child Issue Pattern

Each M10 child issue should include:

```text
Parent Epic: #102
Roadmap: M10 UX Research and Practice Experience Optimization
Priority: P0/P1/P2
Owner role
Review role
Acceptance role
Dependencies
User-visible behavior or UX impact
Human verification needed
Implementation boundary
Completion handoff
Verification required
```

Child issues should separate research, design exploration, implementation, and readiness review when the decisions are meaningfully different.

## Completion Gate

M10 is ready to close only when:

```text
the research protocol is documented
key existing flows have walkthrough evidence
high-impact findings are accepted, fixed, or explicitly deferred
at least one visual direction decision is recorded
UX implementation changes preserve IPA-first practice and scheduler/progress boundaries
browser or manual viewport evidence exists for accepted user-visible changes
residual risks are documented on #102
```

M10 should not require production analytics, accounts, social features, or pressure-based gamification unless a separate product decision approves those boundaries.

## Reuse Checklist

For future projects, reuse this workflow by replacing only:

```text
target learner or user group
core product flows
evidence types available
design tone constraints
completion gate
```

Keep the research loop, finding format, walkthrough gate, and issue pattern intact unless the project has a better local workflow.
