# Roadmap: 认知对抗测试系统（Cognitive Adversarial Testing）

**Created:** 2026-02-28
**Depth:** Quick (3-5 phases)
**Coverage:** 19/19 v1 requirements mapped

---

## Phases

- [x] **Phase 1: Foundation** - DB schema, SSE dependency, LLM streaming extension, agent prompt design (completed 2026-02-28)
- [ ] **Phase 2: Backend Engine** - Turn scheduler, agent orchestration, SSE endpoint, analysis pipeline
- [ ] **Phase 3: Frontend** - Dialogue UI, SSE consumer composable, session history, nav entry
- [ ] **Phase 4: Report and Integration** - Diagnostic report export, spaced repetition hook

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete   | 2026-02-28 |
| 2. Backend Engine | 1/3 | In progress | - |
| 3. Frontend | 0/? | Not started | - |
| 4. Report and Integration | 0/? | Not started | - |

---

## Phase Details

### Phase 1: Foundation
**Goal**: Infrastructure is in place and agent design decisions are locked — DB schema migrated, SSE dependency installed, LLM streaming works, agent prompts validated against Socratic contract
**Depends on**: Nothing (first phase)
**Requirements**: INFR-01, INFR-02, INFR-03
**Success Criteria** (what must be TRUE):
  1. Four new DB tables (CogTestSession, CogTestTurn, CogTestBlindSpot, CogTestSnapshot) exist in the SQLite database and Alembic migration applies cleanly
  2. `LLMService.stream_generate()` async generator method exists and a test endpoint returns streamed tokens to the caller
  3. Guide agent system prompt produces responses that end with a question and never state the answer directly, verified by manual test prompts
  4. Challenger agent system prompt produces responses that acknowledge what the learner got right before raising a question, verified by manual test prompts
  5. Agent structured output schema (JSON block for blind spot extraction) is defined and a sample parse succeeds without error
**Plans**: TBD

### Phase 2: Backend Engine
**Goal**: The full backend dialogue engine runs end-to-end — a session can be started, agents take turns via the scheduler, blind spots are extracted, scores are calculated, and the SSE stream delivers typed events to any HTTP client
**Depends on**: Phase 1
**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, SESS-02, SESS-03, SESS-04, ANLS-01, ANLS-02, ANLS-03
**Success Criteria** (what must be TRUE):
  1. A `curl` or Postman SSE request to `/cog-test/sessions/{id}/stream` receives `turn_start`, `token`, `turn_complete`, `round_complete`, and `done` events in correct sequence
  2. The turn scheduler alternates Guide and Challenger correctly across rounds, with Guide opening round 1
  3. Stopping a session mid-stream (client disconnect or explicit stop call) returns a diagnostic summary object with current blind spots and score — no orphaned LLM calls continue after disconnect
  4. Each completed round persists a CogTestTurn row with blind spot classifications (gap / understood / unclear) and an understanding score
  5. Agent responses never contain a direct answer to the concept question — the Socratic contract is enforced at the output validation layer
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — ORM models + CogTestEngine skeleton (TurnScheduler, registry)
- [ ] 02-02-PLAN.md — Engine run() loop: agent turns, SSE events, persistence, scoring, Socratic validation
- [ ] 02-03-PLAN.md — HTTP endpoints: session CRUD + SSE stream endpoint

### Phase 3: Frontend
**Goal**: A learner can launch a cognitive test from a model card, have a real-time streamed dialogue with both agents, stop at any time, and find all past sessions in the nav
**Depends on**: Phase 2
**Requirements**: SESS-01, SESS-05, SESS-06
**Success Criteria** (what must be TRUE):
  1. A "Start Cognitive Test" button on the model card detail page launches a new session with the concept pre-loaded — no manual concept entry required
  2. Agent tokens appear on screen as they stream, with Guide and Challenger turns visually distinct (different label or color)
  3. A "Stop and Diagnose" button is always visible during a session and produces an immediate summary when clicked
  4. The "Cognitive Tests" nav entry lists all past sessions with concept name, date, and final score
**Plans**: TBD

### Phase 4: Report and Integration
**Goal**: A learner can export a full diagnostic report from any completed session, and blind spots discovered during testing automatically raise the review priority of the corresponding model card
**Depends on**: Phase 3
**Requirements**: REPT-01, REPT-02
**Success Criteria** (what must be TRUE):
  1. Clicking "Export Report" on a completed session downloads a Markdown file containing concept name, blind spot list, score trajectory, and improvement suggestions
  2. After a session ends, the model card's spaced repetition priority is visibly elevated in the review queue if blind spots were found
**Plans**: TBD

---

## Requirement Coverage

| Requirement | Phase | Description |
|-------------|-------|-------------|
| INFR-01 | Phase 1 | DB tables merged into existing SQLAlchemy/SQLite |
| INFR-02 | Phase 1 | AI calls reuse existing agno + LLM service layer |
| INFR-03 | Phase 1 | sse-starlette dependency added |
| AGNT-01 | Phase 2 | Guide agent questions for deep understanding |
| AGNT-02 | Phase 2 | Challenger agent surfaces contradictions gently |
| AGNT-03 | Phase 2 | Socratic contract — no direct answers |
| AGNT-04 | Phase 2 | Turn scheduler controls dialogue pacing |
| AGNT-05 | Phase 2 | Agent explains why answer is incomplete |
| SESS-02 | Phase 2 | SSE real-time streaming to frontend |
| SESS-03 | Phase 2 | Full history context per turn |
| SESS-04 | Phase 2 | Stop anytime with immediate diagnostic summary |
| ANLS-01 | Phase 2 | Per-turn understanding score (report only) |
| ANLS-02 | Phase 2 | Blind spot extraction per turn (gap/understood/unclear) |
| ANLS-03 | Phase 2 | Cognitive evolution snapshot saved per round |
| SESS-01 | Phase 3 | Launch session from model card, concept pre-loaded |
| SESS-05 | Phase 3 | Session history persisted, viewable as list |
| SESS-06 | Phase 3 | Nav entry for all cognitive test sessions |
| REPT-01 | Phase 4 | Export diagnostic report as Markdown |
| REPT-02 | Phase 4 | Blind spots raise SR priority for model card |

**Coverage: 19/19 v1 requirements mapped. No orphans.**
