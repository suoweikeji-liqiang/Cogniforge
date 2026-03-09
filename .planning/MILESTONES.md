# Milestones

## Current Major Milestone: v1.1 Problem-Centered Learning Loop Core

**Status:** Current repository milestone
**Last updated:** 2026-03-09

### Definition

This milestone is the point where Cogniforge behaves primarily like a structured learning loop, not a generic multi-tool workspace.

The milestone is considered present in the current repository because the codebase now has all of the following:

1. `Problems` and `ProblemDetail` are the primary active-learning surfaces.
2. `socratic` and `exploration` are modeled explicitly across the backend and frontend.
3. Learning turns can produce structured outputs:
   - mastery and progression signals
   - derived concept candidates
   - derived learning path candidates
   - review handoff state
4. Main path, branch path, prerequisite path, and comparison path relationships are navigable.
5. Accepted concepts can be promoted into model cards.
6. Review items are traceable back to their originating problem and turn context.
7. Recall outcomes are visible as consequences in the workspace and model-card surfaces.

### What This Milestone Is Not

This milestone does not imply:

- a fully mature review system
- automatic model-card rewriting from recall
- a generic chat-first product
- a PKM-style notes/resources product
- broad analytics or admin expansion

### Main Evidence In The Repo

- Frontend navigation is focused on `Learn`, `Problems`, `Model Cards`, and `Reviews`.
- `ProblemDetail` is the main learning workspace.
- Core domain models include `ProblemTurn`, `LearningPath`, `ProblemConceptCandidate`, `ProblemPathCandidate`, and `ReviewSchedule`.
- Recent commits have tightened:
  - workspace unification
  - review origin traceability
  - recall consequence visibility

## Next Major Milestone: v1.2 Learning Asset Evolution

### Brief Definition

The next milestone should make learning and recall update durable knowledge assets more deliberately.

### Expected Focus

1. use recall results to drive clearer follow-up actions back into the right problem/path context
2. tighten how model cards evolve from learning and recall evidence
3. improve review prioritization based on recent weakness or stability

### Not A Goal

- adding broad new product surfaces
- redesigning the whole review system
- reviving generic chat or PKM-centric identity

## Historical Note

The repository previously tracked an older `v1.0` milestone around cognitive adversarial testing. That work remains in the codebase, but it is no longer the best description of the product's current center of gravity. The current milestone definition is now based on the structured learning loop that dominates the active product surface and recent implementation work.
