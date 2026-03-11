# Cogniforge Plan

## Current Milestone

### v1.3 Guided Knowledge Revision + Hardening

Status: `P0 complete, P1 in progress` (updated 2026-03-11).

This is the active milestone for the repository.

The current cycle is focused on tightening the path from learning turns to durable knowledge assets, then hardening the core workflow before broader expansion.

What is already complete in this cycle:

- explicit model-card provenance and lifecycle for manual vs problem-derived assets (`#28`)
- draft-first manual knowledge-asset creation (`#26`)
- a minimal guided revision workflow grounded by revision focus
- learner-facing page framing and copy updates around the core loop (`#27`, `#30`)
- provider-native structured outputs across core JSON learning artifacts and the remaining major `ModelOSService` chains (`#24`)
- incremental streaming in `ProblemDetail` for exploration ask, Socratic question generation, and Socratic response evaluation (`#25`)
- a first multi-library scaling slice for larger `Problems` and `Model Cards` sets
- `limit` / `offset` list APIs, debounced search, and `Load More` in the main library views
- model-card list review summaries inlined into `/model-cards/` so the page no longer fetches a second full `/srs/schedules` payload

Working chain:

`Problems -> ProblemDetail -> derived concepts / paths -> Reviews / Recall -> reinforcement -> Model Cards -> guided revision`

Current P1 closeout priorities:

1. continue reducing concentration risk in oversized core files (`#23`)
2. expand automated protection around streaming fallback and auth / token-refresh boundaries
3. keep multi-problem and multi-model-card ergonomics scoped to core-loop list/query performance, not graph navigation

Still out of scope while P1 remains open:

- graph-oriented knowledge navigation
- broad dashboard or analytics expansion
- generic PKM or chat expansion
- automatic model-card rewriting
- broad new secondary learning surfaces

## Previous Milestone

### v1.2 Learning Asset Evolution

Status: closed functionally; kept here as historical context.

This milestone established the adaptive reinforcement loop on top of the Milestone 1 learning core:

- weak recall creates durable reinforcement targets
- reinforcement resume can return to the right problem and path context
- `ProblemDetail` can focus the learner on the right concept, turn, and outcome
- starters are grounded by source-turn context, likely confusion, and focused evidence when the signal is strong enough
- model cards show clearer learning-asset state and revision-focus hints
