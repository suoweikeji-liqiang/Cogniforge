# AGENTS.md

## Project Identity

Cogniforge is a learning system for structured cognition building, not a generic chat app.

The product centers on:
- Socratic learning mode: AI asks, user answers, system evaluates mastery and progression
- Exploration learning mode: user asks, AI explains, system derives concepts and next learning actions
- Derived concept candidates generated during dialogue
- Derived learning path candidates generated during dialogue
- Main path / branch path / prerequisite path / comparison path navigation
- Model evolution and long-term knowledge consolidation

When making implementation decisions, prefer strengthening the learning loop over adding unrelated surface features.

---

## Core Product Principles

1. Learning modes are first-class concepts.
   - `socratic` and `exploration` must be modeled explicitly.
   - Do not hide mode behavior behind ad hoc booleans or loosely coupled UI states.

2. Dialogue is productive, not ephemeral.
   - A learning turn should be able to produce structured outputs:
     - mastery signal
     - derived concepts
     - derived path suggestions
     - review or return recommendations

3. The system must preserve learning structure.
   - Main path and branch path relationships must remain traceable.
   - Users should not get lost after branching.

4. ProblemDetail is the main learning workspace.
   - Prefer integrating core learning interactions there.
   - Avoid scattering primary workflow across too many disconnected pages.

5. Model cards and concept assets are long-term knowledge artifacts.
   - New concepts and learning branches should be able to feed these assets over time.

---

## Working Style for Agents

Before changing code:

1. Read the issue carefully.
2. Inspect the relevant existing code paths first.
3. Produce a short implementation plan.
4. Make the smallest coherent change that solves the issue.
5. Update tests for touched behavior.
6. Summarize:
   - files changed
   - data/schema changes
   - test commands run
   - follow-up issues or unresolved ambiguities

Do not jump into broad refactors unless the issue explicitly requires it.

---

## Scope Control Rules

- Do not solve multiple unrelated issues in one task.
- Keep changes scoped to the current issue unless a small adjacent change is required for correctness.
- Prefer incremental delivery over broad redesign.
- Preserve existing behavior where possible.
- If a larger refactor seems beneficial, document it as a follow-up instead of silently expanding scope.

When ambiguity exists:
- choose the smallest reasonable interpretation
- document the assumption clearly in the final summary

---

## Backend Guidance

### Domain Modeling
Prefer explicit, typed, inspectable domain structures.

Use clear fields such as:
- `learning_mode`
- `question_kind`
- `answer_type`
- `derived_candidates`
- `derived_path_candidates`
- `path_kind`
- `source_turn_id`

Avoid:
- hidden behavior switches
- overloaded generic metadata blobs when typed fields are more appropriate
- logic that depends on UI wording rather than structured state

### Learning Modes
Treat these as distinct protocols:

#### Socratic mode
AI asks the user questions.
This mode focuses on:
- probing understanding
- checkpoint evaluation
- mastery scoring
- progression decisions
- clarification follow-ups

Socratic question kinds should be explicit when relevant, for example:
- `probe`
- `checkpoint`

#### Exploration mode
User asks the system about concepts.
This mode focuses on:
- concept explanation
- boundary clarification
- misconception correction
- comparison
- prerequisite discovery
- derived concept extraction
- derived path suggestion

Do not collapse Socratic and Exploration behavior into one generic response flow unless the shared abstraction remains clean and explicit.

### Derived Concepts
Derived concepts should be treated as structured candidate artifacts, not just tags.

When possible, preserve:
- name
- confidence
- source mode
- source turn
- evidence or rationale
- moderation state

### Derived Learning Paths
Derived learning paths are a core feature.
Support structured path suggestions such as:
- `prerequisite`
- `branch_deep_dive`
- `comparison_path`

Each suggested path should be traceable to the interaction that produced it.

### Path Relationships
Main path vs branch path must remain navigable and inspectable.
Support fields such as:
- `kind`
- `parent_path_id`
- `return_step_id`
- `source_turn_id`
- `branch_reason`

Do not introduce branch behavior that strands the user without a clear return flow.

---

## Frontend Guidance

### Primary Workspace
The main problem page should remain the primary learning workspace.

Core actions should be easy to see:
- teacher asks me
- I ask about a concept
- what happened this turn
- what new concepts appeared
- what new path options appeared
- where I am in the learning structure

### UX Priorities
When making UI choices, prioritize:
1. clarity of current learning mode
2. clarity of current path position
3. clarity of turn outcome
4. clarity of next-step action

The user should always be able to answer:
- What am I doing right now?
- Am I being evaluated or exploring?
- What did this turn produce?
- What should I do next?
- Am I on the main path or a branch?

### Avoid
- overly broad visual redesign unless requested
- hiding core learning outputs behind secondary pages
- mixing unrelated admin/configuration UI into core learning flow work

---

## Testing Expectations

For any meaningful behavior change, update tests.

Priority areas for tests:
- learning mode separation
- Socratic probe vs checkpoint behavior
- Exploration structured outputs
- derived concept generation and moderation flow
- derived learning path generation
- main/branch/prerequisite/comparison navigation
- return-to-main-path flow
- critical ProblemDetail interaction flow

When possible:
- add or update backend tests for schema/logic changes
- add or update frontend or E2E coverage for main workflow changes

Do not leave core learning flow changes untested if the repository already has a test pattern for that area.

---

## Preferred Delivery Pattern

A good task delivery usually looks like this:

1. inspect relevant files
2. identify existing partial support
3. propose a short plan
4. implement a minimal coherent slice
5. update tests
6. summarize outcome and remaining gaps

A good final summary should include:
- what was implemented
- what was intentionally left out of scope
- any migration or schema implications
- exact test commands run
- suggested next issue

---

## Repository-Specific Priorities

Current high-priority direction for Cogniforge:
1. establish dual learning modes cleanly
2. formalize Socratic interaction protocol
3. formalize Exploration interaction protocol
4. surface derived concepts in the main learning flow
5. generate and manage derived learning path candidates
6. support branch navigation and return flow
7. protect the above with E2E coverage

When in doubt, prefer work that strengthens this sequence.

---

## What Not To Optimize First

Unless explicitly requested, do not prioritize:
- cosmetic redesigns unrelated to learning flow
- unrelated settings/admin work
- generic chat feature expansion
- broad architecture rewrites without issue-driven justification
- speculative abstractions that are not needed by the current issue

---

## Agent Output Expectations

At the end of each task, provide:

### Implementation summary
- short explanation of what changed

### Files changed
- list of key files touched

### Tests
- exact commands run
- whether they passed or failed

### Notes
- assumptions made
- blockers
- follow-up issues worth tackling next

