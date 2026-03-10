gsd_state_version: 1.2
milestone: v1.2
milestone_name: learning-asset-evolution
status: functionally-complete
last_updated: "2026-03-10T00:00:00Z"
---

# Project State

## Current Position

**Current major milestone:** `v1.2 Learning Asset Evolution`
**Status:** Functionally complete, ready to close out
**Current focus:** Close out Milestone 2 clearly and prepare for Milestone 3 planning without re-expanding product scope.

## Working Definition

The repository is currently centered on a single adaptive learning flow:

`Problems -> ProblemDetail -> Reviews / Recall -> reinforcement -> Model Cards -> revision focus`

This means:

1. `ProblemDetail` is the main active-learning battleground.
2. `socratic` and `exploration` are explicit modes, not implicit UI states.
3. Learning turns generate structured artifacts that can be governed and revisited.
4. Branch learning paths remain traceable back to the main path.
5. Review and recall are part of the same learning loop, not detached modules.
6. Weak recall can now return the learner to the right path, target, starter, and linked model card context.
7. Model cards now expose explicit asset state and a lightweight revision direction.

## Repository Signals Supporting This State

- Frontend primary navigation is focused on `Learn`, `Problems`, `Model Cards`, and `Reviews`.
- Review and recall surfaces now display origin, consequence, and reinforcement data.
- Recent commits have emphasized:
  - path-precise reinforcement resume
  - source/error/evidence-aware starters
  - model-card evolution state
  - revision focus hints
  - real-provider timeout degradation on create-problem and provider-test paths
  - auth entry layout hardening for login/register surfaces

## Current Known Gaps

These are still intentionally outside the current milestone's completion bar:

1. recall outcomes do not automatically rewrite model-card content
2. revision focus hints do not yet form a full edit workflow
3. review prioritization is still relatively simple
4. some secondary / legacy surfaces still remain in the codebase

## Next Milestone Direction

The next major milestone should be `v1.3 Guided Knowledge Revision`.

That milestone should focus on making current revision guidance actionable in a lightweight, traceable way, without re-expanding the product surface or introducing automatic rewriting.
