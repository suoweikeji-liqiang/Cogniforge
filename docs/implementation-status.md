# Implementation Status

**Last updated:** 2026-03-09

## Current Major Milestone

### v1.2 Learning Asset Evolution

This is the current major milestone for the repository.

It reflects the codebase as it exists now, not an aspirational product description.
The milestone is functionally complete enough to close out.

## What Is Implemented

### 1. Main Learning Workspace

- `ProblemDetail` is the main learning workspace.
- The primary navigation is focused on `Learn`, `Problems`, `Model Cards`, and `Reviews`.
- Secondary surfaces such as chat, notes, resources, and experiments remain in the codebase but are no longer the primary product identity.

### 2. Explicit Learning Modes

- `socratic` and `exploration` are explicit across the data model and main UI.
- The workspace makes the current mode, current step/path, turn output, and next action visible together.

### 3. Structured Learning Outputs

The current learning flow can already produce:

- mastery / progression feedback
- derived concept candidates
- derived learning path candidates
- review handoff state

### 4. Path Structure

- Main path and branch path relationships are modeled and navigable.
- Branch creation, activation, and return-to-parent flow exist in the main workspace.

### 5. Knowledge Asset Handoff

- Accepted concepts can be promoted into model cards.
- Model cards can be scheduled into review.
- Review items are traceable back to the originating problem and learning turn.

### 6. Reinforcement Routing

- Weak recall now creates durable reinforcement targets.
- Those targets can return the learner to:
  - the right problem
  - the right learning path
  - the right focused concept / turn
- `ProblemDetail` can show a concrete first reinforcement action.

### 7. Source / Error / Evidence Grounding

- Reinforcement starters are no longer generic.
- The current repo can ground them by:
  - source-turn context
  - likely confusion / error assertions
  - focused candidate evidence when the signal is reliable

### 8. Model-Card Evolution State

- Model cards no longer show only review presence and timeline events.
- The current repo now surfaces model-card state such as:
  - needs revision
  - rebuilding
  - reinforced recently
  - stable base
  - first recall queued
  - repeated confusion

### 9. Revision Direction Hints

- `ModelCardDetail` now shows a lightweight revision focus hint.
- The hint uses current recall / reinforcement / evolution signals to point toward a first revision direction without rewriting the card automatically.

## What Is Still Thin

These areas are still intentionally limited:

1. recall does not automatically rewrite model-card content
2. revision focus hints are not yet a full revision workflow
3. review prioritization is still lightweight
4. legacy / secondary surfaces still exist in the codebase

## Next Milestone

### v1.3 Guided Knowledge Revision

The next milestone should focus on turning the current state and revision-focus hints into lightweight, traceable knowledge-revision actions.

The expected center of gravity for that milestone is:

- turning revision focus hints into explicit edit intent
- keeping revisions traceable to learning / recall evidence
- feeding revision outcomes back into the learning loop without broadening the product surface
