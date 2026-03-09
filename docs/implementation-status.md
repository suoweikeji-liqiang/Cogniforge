# Implementation Status

**Last updated:** 2026-03-09

## Current Major Milestone

### v1.1 Problem-Centered Learning Loop Core

This is the current major milestone for the repository.

It reflects the codebase as it exists now, not an aspirational product description.

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

### 6. Recall Consequence Visibility

- Recall is no longer only about queue/origin visibility.
- The current repo now surfaces recall consequences such as:
  - stability state
  - recent recall outcome
  - recommended next action
- Those signals are visible in:
  - `ProblemDetail`
  - derived concept handoff state
  - model-card surfaces
  - recall session outcome UI

## What Is Still Thin

These areas are still intentionally limited:

1. recall does not automatically rewrite model-card content
2. review prioritization is still lightweight
3. model evolution is present, but recall-driven evolution is not yet a strong closed loop
4. legacy / secondary surfaces still exist in the codebase

## Next Milestone

### v1.2 Learning Asset Evolution

The next milestone should focus on turning learning evidence and recall evidence into more deliberate model-card evolution and follow-up learning actions.

The expected center of gravity for that milestone is:

- stronger feedback from weak recall back into the right workspace context
- clearer model-card evolution from learning and recall evidence
- better review prioritization without broadening the product surface
