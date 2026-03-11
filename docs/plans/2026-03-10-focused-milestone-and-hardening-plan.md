# Focused Milestone and Hardening Plan (2026-03-10)

## 0. Status Snapshot (2026-03-11)

- `P0` is complete.
- `P1` is in progress.
- This document is the active plan for the current cycle.
- The earlier `2026-03-05-learning-loop-hardening-plan.md` has been archived as superseded.
- A narrow list-scaling slice for larger `Problems` and `Model Cards` libraries was pulled into `P1` because it directly improves the core learning loop at moderate scale without opening graph scope.

## 1. Goal

Turn the current beta learning loop into a more stable and traceable product by:

1. closing the knowledge-asset loop first
2. running a hardening pass immediately after

This plan is intentionally narrower than the full backlog. It is meant to preserve momentum on the core product rather than spread effort across all open issues.

## 2. Why This Sequence

The repository already has the main product direction:

`Problems -> ProblemDetail -> derived concepts / paths -> Reviews / Recall -> reinforcement -> knowledge assets`

The current gap is no longer basic functionality. The main remaining gap is that the knowledge-asset flow is still only partially closed:

- provenance is not explicit enough
- manual asset creation is too thin
- revision is hinted at but not yet actionable
- learner-facing language still undersells the product structure

If these issues are fixed first, the product shape becomes much clearer.
Only then is it worth spending the next cycle on reliability hardening and maintainability work.

## 3. P0: Focused Milestone

### Theme

`v1.3 Guided Knowledge Revision`

### Objective

Make the path from learning output to durable knowledge asset explicit and actionable.

### Scope

1. Formalize lifecycle and provenance
   - issue: `#28`
   - clarify the progression from concept candidate to accepted concept to knowledge asset
   - add explicit origin/provenance support for manual vs problem-derived assets

2. Redesign manual knowledge-asset creation
   - issue: `#26`
   - keep manual creation, but reshape it into a draft-first asset flow
   - ensure the manual path feels like creating a durable asset, not a generic note

3. Add a minimal guided revision workflow
   - currently not split into its own issue yet
   - turn revision-focus hints into one or two concrete revision actions
   - keep actions lightweight and traceable

4. Tighten product language and page framing
   - issues: `#27`, `#30`
   - improve learner-facing naming, Chinese copy, and page-level framing for the core loop

### P0 Completion Criteria

- a knowledge asset can be traced back to where it came from
- manual-origin and problem-derived assets are clearly distinguished
- revision is no longer only advisory text
- learners can understand the role of Problems, ProblemDetail, knowledge assets, and Reviews from the UI alone

## 4. P1: Hardening Pass

### Theme

`stability, maintainability, and regression protection`

### Objective

Stabilize the revised knowledge loop before taking on broader surface-area work.

Limited multi-problem and multi-model-card list/query improvements can be included here when they directly reduce friction in the core learning loop.

### Scope

1. Harden structured outputs
   - issue: `#24`
   - replace prompt-only JSON discipline with provider-native structured output where supported

2. Reduce concentration risk in core files
   - issue: `#23`
   - split oversized backend/frontend workflow files into maintainable modules

3. Expand automated protection
   - add regression coverage around:
     - knowledge-asset lifecycle
     - manual asset creation flow
     - revision workflow
     - structured-output degradation paths
     - reinforcement return flow

4. Improve responsiveness where it matters
   - issue: `#25`
   - add incremental streaming UX to `ProblemDetail`
   - do not expose raw chain-of-thought

### P1 Completion Criteria

- core learning artifacts are less fragile to malformed model output
- the main workflow code is easier to evolve without regressions
- the revised knowledge loop has automated regression coverage
- `ProblemDetail` no longer feels fully blocking for key AI interactions

## 5. P2: Deferred Work

These are useful, but not part of the immediate path from beta to a more stable product:

- deeper list/index scaling beyond core-loop ergonomics (`#29`)
- graph-oriented knowledge navigation
- broader secondary-surface expansion
- large analytics or dashboard work

## 6. Practical Rule For New Work

When deciding whether a new task belongs in the next cycle, prefer it only if it strengthens one of these:

1. learning output -> knowledge asset traceability
2. knowledge asset revision workflow
3. core learning-loop reliability
4. core workflow maintainability

If it does not clearly strengthen one of those, it should likely wait until after the hardening pass.
