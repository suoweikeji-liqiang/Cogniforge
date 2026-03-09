---
gsd_state_version: 1.1
milestone: v1.1
milestone_name: problem-centered-learning-loop-core
status: active
last_updated: "2026-03-09T00:00:00Z"
---

# Project State

## Current Position

**Current major milestone:** `v1.1 Problem-Centered Learning Loop Core`
**Status:** Active repository milestone
**Current focus:** Keep tightening the main learning loop around `ProblemDetail`, model-card handoff, and review / recall consequences.

## Working Definition

The repository is currently centered on a single core flow:

`Problems -> ProblemDetail -> derived concepts / derived paths -> Model Cards -> Reviews / Recall`

This means:

1. `ProblemDetail` is the main active-learning battleground.
2. `socratic` and `exploration` are explicit modes, not implicit UI states.
3. Learning turns generate structured artifacts that can be governed and revisited.
4. Branch learning paths remain traceable back to the main path.
5. Review and recall are part of the same learning loop, not detached modules.

## Repository Signals Supporting This State

- Frontend primary navigation is focused on `Learn`, `Problems`, `Model Cards`, and `Reviews`.
- Review and recall surfaces now display origin and consequence data.
- Recent commits have emphasized:
  - product-surface shrink
  - main workspace unification
  - recall continuity
  - recall consequence visibility

## Current Known Gaps

These are still outside the current milestone's completion bar:

1. recall outcomes do not yet directly rewrite model-card content
2. review prioritization is still relatively simple
3. some secondary / legacy surfaces still remain in the codebase
4. path suggestions are not yet strongly driven by recall outcomes

## Next Milestone Direction

The next major milestone should be `v1.2 Learning Asset Evolution`.

That milestone should focus on making learning evidence and recall evidence shape model cards and follow-up learning actions more deliberately, without re-expanding the product surface.
