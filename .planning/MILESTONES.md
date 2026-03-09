# Milestones

## Current Major Milestone: v1.2 Learning Asset Evolution

**Status:** Functionally complete, ready to close out
**Last updated:** 2026-03-09

### Definition

This milestone is the point where Cogniforge not only behaves like a structured learning loop, but also treats recall and reinforcement as forces that shape durable knowledge assets.

The milestone is considered present in the current repository because the codebase now has all of the following:

1. Weak recall produces durable reinforcement targets instead of only display text.
2. Reinforcement resume can return the learner to the right problem, branch path, and focused target in `ProblemDetail`.
3. `ProblemDetail` can suggest a concrete first reinforcement action.
4. Reinforcement starters can be grounded by:
   - source-turn context
   - likely confusion / error assertions
   - focused candidate evidence when the signal is strong enough
5. Model cards now reflect recall / reinforcement as explicit asset state, not only as timeline events.
6. `ModelCardDetail` now surfaces lightweight revision focus hints derived from current recall / reinforcement signals.

### What This Milestone Is Not

This milestone does not imply:

- automatic model-card rewriting from recall
- a broad adaptive tutoring engine
- a full model-card editing workflow
- broad analytics or admin expansion

### Main Evidence In The Repo

- `ProblemDetail` is the main learning workspace.
- Recall and reinforcement now flow back into the workspace, model-card surfaces, and revision hints.
- Recent commits have tightened:
  - adaptive reinforcement targeting
  - source/error/evidence-aware starters
  - model-card evolution state and revision focus

## Next Major Milestone: v1.3 Guided Knowledge Revision

### Brief Definition

The next milestone should turn current state and revision-focus hints into a lightweight, traceable knowledge-revision workflow.

### Expected Focus

1. make revision focus hints lead to small explicit editing actions in `ModelCardDetail`
2. keep revision changes traceable to learning, reinforcement, and recall evidence
3. feed revision outcomes back into the learning / review loop without broadening the product surface

### Not A Goal

- adding broad new product surfaces
- redesigning the whole review system
- automatic model-card rewriting
- reviving generic chat or PKM-centric identity

## Historical Note

The repository previously tracked `v1.1` as the current milestone. That is now best understood as the foundation milestone that established the problem-centered learning loop. The current milestone definition has moved to `v1.2` because the repository now contains the main adaptive reinforcement and learning-asset evolution chain.
