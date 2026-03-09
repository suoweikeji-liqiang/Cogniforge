# Cogniforge Plan

## Current Milestone

### v1.2 Learning Asset Evolution

Status: Functionally complete, ready to close out.

This milestone established the adaptive reinforcement loop on top of the Milestone 1 learning core:

- weak recall now creates durable reinforcement targets
- reinforcement resume can return to the right problem and path context
- ProblemDetail can focus the learner on the right concept/turn/outcome
- ProblemDetail suggests a concrete first reinforcement action
- starters are grounded by source-turn context, likely confusion, and focused evidence when the signal is strong enough
- model cards now show clearer learning-asset state and revision-focus hints

Working chain:

`Problems -> ProblemDetail -> Reviews / Recall -> reinforcement target -> focused workspace recovery -> Model Cards -> revision focus`

Out of scope for v1.2:

- automatic model-card rewriting
- a broad practice or tutoring engine
- large mastery analytics dashboards
- generic PKM or chat expansion

## Next Milestone

### v1.3 Guided Knowledge Revision

Direction only. Not started yet.

This milestone should focus on turning current reinforcement and revision signals into lightweight, traceable revision workflows without broadening the product surface.

Likely focus:

- make revision focus hints easier to act on in the existing model-card workflow
- keep revision actions traceable to recall and reinforcement evidence
- tighten the handoff between active learning, reinforcement, and durable knowledge revision

Still out of scope unless explicitly pulled in:

- automatic content rewriting
- broad review-system redesign
- new standalone training surfaces
- broad dashboard or multi-tool expansion
