# Implementation Status

**Last updated:** 2026-03-11

## Active Milestone

### v1.3 Guided Knowledge Revision + Hardening

Status: `P0 complete, P1 in progress`

This document reflects the codebase as it exists now, not an aspirational product description.

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
- provider-native structured outputs across the core JSON learning artifacts and the remaining major `ModelOSService` chains

### 4. Path Structure

- Main path and branch path relationships are modeled and navigable.
- Branch creation, activation, and return-to-parent flow exist in the main workspace.

### 5. Knowledge-Asset Provenance And Handoff

- Accepted concepts can be promoted into model cards.
- Model cards now distinguish manual creation from problem-derived promotion.
- Where available, provenance stays linked to the originating problem, turn, and candidate.
- Manual-origin cards now follow a draft-first lifecycle before activation and review scheduling.
- Model cards can be scheduled into review.
- Review items are traceable back to the originating problem and learning turn.

### 6. Guided Revision Workflow

- `ModelCardDetail` no longer stops at advisory revision-focus text.
- The current repo can open a lightweight revision workflow and record revision intent against recent recall / reinforcement context.

### 7. Reinforcement Routing

- Weak recall now creates durable reinforcement targets.
- Those targets can return the learner to:
  - the right problem
  - the right learning path
  - the right focused concept / turn
- `ProblemDetail` can show a concrete first reinforcement action.

### 8. Source / Error / Evidence Grounding

- Reinforcement starters are no longer generic.
- The current repo can ground them by:
  - source-turn context
  - likely confusion / error assertions
  - focused candidate evidence when the signal is reliable

### 9. Model-Card Evolution State

- Model cards no longer show only review presence and timeline events.
- The current repo now surfaces model-card state such as:
  - needs revision
  - rebuilding
  - reinforced recently
  - stable base
  - first recall queued
  - repeated confusion

### 10. Responsiveness In The Main Workspace

- Exploration `/ask` now has a streaming answer preview plus final structured payload.
- Socratic question generation now streams into the workspace before the final payload lands.
- Socratic response evaluation now streams status and preview state before the final structured feedback lands.
- The blocking endpoints remain as fallbacks instead of being removed outright.

### 11. Problems And Model-Card Library Scaling

- The main list APIs now support `limit` / `offset`.
- `Problems` and `Model Cards` use debounced search plus `Load More` instead of assuming tiny libraries.
- `ModelCardsView` no longer fetches a second full `/srs/schedules` payload just to render review state for the current page.

### 12. Ongoing Maintainability Hardening

- Support modules have started to come out of `problems.py`, `ProblemDetailView.vue`, and `model_os_service.py`.
- This reduces local concentration risk, but the hardening pass is still underway rather than complete.

## What Is Still Thin

These areas are still intentionally limited:

1. concentration risk is still high in `problems.py`, `ProblemDetailView.vue`, and `model_os_service.py`
2. streaming fallback and auth / token-refresh boundary coverage is not yet fully closed
3. review prioritization is still lightweight
4. graph-oriented navigation and broader secondary surfaces remain deferred

## Current P1 Closeout Focus

- finish reducing concentration risk in the main workflow files (`#23`)
- expand regression coverage around the revised knowledge loop and streaming fallback paths
- keep multi-problem and multi-model-card optimizations limited to core-loop ergonomics rather than graph surfaces
