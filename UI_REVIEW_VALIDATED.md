# Cogniforge UI Review Validation

## Scope

This document validates and consolidates the conclusions from:

- `UI_INTERACTION_AUDIT.md`
- `UI_UX_审核报告.md`

Validation baseline:

- Current frontend implementation under `las_frontend/src`
- Existing Playwright coverage under `las_frontend/tests`
- Project product constraints in `AGENTS.md`

Review date: 2026-03-11

---

## Overall Judgment

The two reports are directionally useful, but not fully reliable as-is.

- About 70% of the strategic direction is sound.
- About 30% of the claims overstate the problem or conflict with the current implementation.

The correct conclusion is not "there is no learning loop". The correct conclusion is:

> The main learning loop already exists and is partially protected by tests, but the UI still presents too much parallel information and too many secondary decisions around that loop.

This distinction matters. If we misdiagnose the product as "no main path", we risk doing a broad route or page rewrite that throws away learning-mode structure that already exists.

---

## What The Reports Got Right

### 1. Dashboard focus is diluted

This is accurate.

Current `DashboardView.vue` gives the user:

- one focus card
- three metrics
- recent problems
- review queue
- recent model cards
- four quick actions

Several of these point to overlapping next steps. The page does contain a main recommendation, but it competes with too many other entry points.

Validated against:

- `las_frontend/src/views/DashboardView.vue`

### 2. ProblemDetail is the real main workspace, but it is very dense

This is accurate and important.

`ProblemDetailView.vue` is already the center of the learning workflow and includes:

- learning mode state
- path navigation
- current step and progress
- turn interaction
- turn outcome
- derived concepts
- derived paths
- notes and resources
- review reinforcement context

The problem is not lack of product structure. The problem is excessive simultaneous exposure of product structure.

Validated against:

- `las_frontend/src/views/ProblemDetailView.vue`

### 3. Reviews currently mix multiple concepts

This is accurate.

`ReviewsView.vue` currently combines:

- SRS queue and launch points
- model-card lifecycle visibility
- manual review archive

Those are related, but not the same user task. The page reads as a lifecycle dashboard more than a single-purpose execution surface.

Validated against:

- `las_frontend/src/views/ReviewsView.vue`

### 4. Model card list density is high

This is accurate.

Each card in `ModelCardsView.vue` can expose:

- lifecycle stage
- version and stats
- evolution state
- recall state
- recommended action
- reinforcement state
- up to four actions

The information is meaningful, but the list view is carrying too much detail at once.

Validated against:

- `las_frontend/src/views/ModelCardsView.vue`

### 5. Secondary surfaces still create product ambiguity

This is accurate.

- `ChatView.vue` is explicitly marked legacy.
- `PracticeView.vue` and `SRSReviewView.vue` are explicitly marked secondary surfaces.

That means the product direction is already known in code, but the surfaces still exist and still require user interpretation.

Validated against:

- `las_frontend/src/views/ChatView.vue`
- `las_frontend/src/views/PracticeView.vue`
- `las_frontend/src/views/SRSReviewView.vue`

---

## What The Reports Got Wrong Or Overstated

### 1. "The product has no main path"

This is overstated.

The main path is already visible in both code and tests:

- Problems are the main workspace entry
- ProblemDetail handles the core learning loop
- derived concepts can become model cards
- model cards can enter SRS review
- weak recall can send the user back into workspace reinforcement

This is explicitly exercised in Playwright coverage.

Validated against:

- `las_frontend/tests/problem-detail-workflow.spec.ts`
- `las_frontend/tests/app-shell-nav.spec.ts`

### 2. "Learning mode switch only changes wording"

This is incorrect.

The current implementation models `socratic` and `exploration` as distinct protocols:

- separate interaction surfaces
- separate submission flows
- separate streamed behavior
- explicit `question_kind` for Socratic
- explicit `answer_type` for Exploration
- different turn outcomes and next actions

This aligns with the product rules in `AGENTS.md`.

Validated against:

- `las_frontend/src/views/problem-detail/learningActions.ts`
- `las_frontend/src/components/problem-workspace/ProblemTurnOutcomePanel.vue`

### 3. "Users face 14+ top-level pages in navigation"

This is inaccurate as a UI claim.

There are many routes in the router, but the main authenticated navigation exposes only four primary items:

- Dashboard
- Problems
- Model Cards
- Reviews

So the information-architecture concern is real, but the reports mix "route count in code" with "primary navigation burden on users".

Validated against:

- `las_frontend/src/router/index.ts`
- `las_frontend/src/App.vue`

### 4. "Review completion only shows next review time"

This is incorrect.

`SRSReviewView.vue` already shows:

- last review outcome
- recall state
- recommended action
- reinforcement state when applicable
- links back to workspace or model card

The better criticism is not "no feedback exists". The better criticism is "feedback is split across reviews, SRS, model cards, and workspace reinforcement surfaces".

Validated against:

- `las_frontend/src/views/SRSReviewView.vue`

### 5. Large route renames and broad IA rewrite should be the first move

This is not well aligned with the repository constraints.

Per `AGENTS.md`:

- ProblemDetail should remain the main learning workspace
- learning modes must stay explicit
- changes should be incremental and scoped

That means recommendations like renaming the whole app around `/workspace`, `/library`, and a fresh route hierarchy are plausible long-term ideas, but not the right first action for this codebase.

---

## Corrected Product Diagnosis

The current UI already expresses the intended learning system better than the two reports admit:

- dual learning modes are explicit
- derived concepts are structured artifacts
- derived path candidates are actionable
- branch and return flows exist
- reinforcement can route users back into the workspace

The actual design problem is this:

1. The system exposes too much state at once.
2. The hierarchy between primary action and supporting context is still weak.
3. Secondary surfaces remain visible enough to dilute confidence.
4. Review-related concepts are semantically mixed.
5. Lists expose operational detail before users need it.

This is a progressive-disclosure and flow-clarity problem, not evidence that the product lacks a learning architecture.

---

## Recommended Priorities

### P0: Clarify the existing main loop without changing the product model

Do first:

- simplify Dashboard around one primary action
- reduce duplicate navigation from quick actions
- make Reviews choose a clearer primary job

Do not do first:

- full route rename
- broad top-level IA rewrite
- splitting core workflow away from ProblemDetail

### P1: Reduce ProblemDetail cognitive load inside the same workspace

Recommended direction:

- keep ProblemDetail as the main workspace
- introduce stronger staged disclosure inside the page
- keep learning interaction primary
- collapse or defer concept and path management when not immediately relevant

This is better aligned with the repository than moving core learning to several disconnected pages.

### P1: Split review semantics, not necessarily review entry

Best next step:

- separate SRS execution from manual review archive conceptually
- preserve a direct path from "due now" into SRS execution
- avoid forcing users through an extra page just to start review

### P1: Simplify model-card list cards

List view should emphasize:

- concept title
- one primary status
- one primary action

Detailed evolution and reinforcement analysis can stay in detail view.

### P2: Clarify continuity and recovery

Examples:

- stronger "continue current task" cue
- better empty states
- better explanation of why a concept becomes a model card
- better explanation of why a fragile review sends the user back to workspace

---

## Actionable Conclusion

If these two reports are used for planning, they should be treated as raw input, not as accepted diagnosis.

The most reliable combined conclusion is:

1. Keep the current learning-loop architecture.
2. Simplify presentation around that architecture.
3. Reduce semantic mixing in Reviews.
4. Reduce density in Dashboard and Model Cards.
5. Preserve ProblemDetail as the main workspace and improve staged disclosure there.

That is a much safer and more repository-consistent direction than a broad rewrite based on the claim that the product has no usable main path.
