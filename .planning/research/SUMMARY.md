# Project Research Summary

**Project:** Cognitive Adversarial Testing — Socratic AI Tutoring Module
**Domain:** Multi-agent Socratic dialogue engine integrated into existing Vue3+FastAPI learning platform
**Researched:** 2026-02-28
**Confidence:** MEDIUM-HIGH

## Executive Summary

This milestone adds a dual-agent Socratic tutoring system to an existing learning assistant platform. The system uses two distinct AI agents — a Guide (引导者) that leads with questions and a Challenger (质疑者) that surfaces contradictions — to expose cognitive blind spots in a learner's understanding of a concept. Academic research (SocratiQ, SPL, SocraticAI) confirms that dual-agent protocols produce better critical thinking outcomes than single-agent tutors, and that the key differentiator over tools like Khanmigo is explicit blind spot extraction and a tangible diagnostic report artifact. The recommended approach is to build this as a clean additive module on top of the existing FastAPI+agno+Vue3 stack, reusing all existing infrastructure and adding only SSE streaming and a new engine package.

The core technical approach is: SSE streaming via `sse-starlette` + `EventSourceResponse`, two `agno.Agent` instances coordinated by a custom `TurnScheduler`, session state held in-memory per round and persisted to four new SQLAlchemy tables, and a Vue3 composable (`useCogTestStream`) wrapping the `EventSource` lifecycle. No new orchestration frameworks, no new databases, no WebSockets. The existing `LLMService` needs one addition — a `stream_generate()` async generator method — before any other work can proceed.

The two highest risks are prompt engineering failures (the Guide agent drifting into answer-giving, the Challenger agent feeling hostile rather than curious) and silent data pipeline failures (regex-based blind spot extraction returning empty results without error). Both must be addressed before any UI work begins. The build order is strictly bottom-up: DB schema → engine pure functions → LLM streaming → agent orchestration → SSE endpoint → frontend composable → UI → report export.

---

## Key Findings

### Recommended Stack

The existing stack (FastAPI 0.115, agno 1.2.8, SQLAlchemy 2.0.35 async, Vue 3.5, Pinia 2.2, axios 1.7) handles everything except SSE streaming. The only new backend dependency is `sse-starlette==1.8.2` for named SSE event types (`turn_start`, `token`, `round_complete`, `done`). The frontend needs zero new npm packages — native `EventSource` API wrapped in a 30-line composable is sufficient. Do not introduce LangGraph, CrewAI, WebSockets, Redis, or any second orchestration framework.

**Core technologies:**
- `sse-starlette` 1.8.2: named SSE event framing — required for multi-event-type stream protocol
- `agno.agent.Agent` (existing): Guide + Challenger as two Agent instances with distinct system prompts
- `asyncio.Queue` (stdlib): decouples agent token generation from HTTP SSE delivery
- Native `EventSource` API (browser built-in): SSE consumer — zero dependency, auto-reconnects
- `useCogTestStream` composable (new): Vue3 reactive wrapper owning EventSource lifecycle
- `pydantic.BaseModel` (existing): in-memory session state model, serialized to JSON for snapshots
- JWT via query param (`?token=`): SSE auth workaround since EventSource cannot send custom headers

### Expected Features

**Must have (table stakes — v1 launch):**
- Guided questioning with no direct answers — core Socratic contract; Guide must refuse even when learner pushes
- Session anchored to a model card concept — pre-loaded context, not generic tutoring
- Multi-turn dialogue with persistent conversation history — stateless Q&A is not tutoring
- SSE streaming for both agents — waiting for full response breaks conversational flow
- Stop-anytime with immediate diagnostic summary — learner controls the session
- Feedback explaining why an answer is incomplete — distinguishes "wrong" from "incomplete reasoning"

**Should have (differentiators — v1 launch):**
- Dual-agent role split (Guide + Challenger) — core innovation; role clarity improves dialogue quality
- Turn scheduler — controls pacing and adversarial intensity
- Understanding score (per-turn, derived from LLM analysis) — concrete comprehension signal
- Blind spot extraction (LLM classifies each response as gap/understood/unclear) — core value proposition
- Cognitive diagnostic report (Markdown export) — tangible artifact, makes invisible learning visible

**Add after validation (v1.x):**
- Cognitive evolution snapshot (state tree per turn) — add when learners ask "how did my understanding change?"
- Cross-session blind spot persistence — add when learners return for second sessions
- Spaced repetition integration — surface gaps as higher-priority review items
- Cross-turn contradiction detection — add when single-turn gap detection is reliable

**Defer (v2+):**
- Android mobile adaptation — out of scope per PROJECT.md
- Voice input/output — high complexity, low validated demand
- Peer/cohort blind spot aggregation — privacy implications need careful design
- Teacher/instructor dashboard — different user persona

**Anti-features to avoid:**
- Direct answer mode ("just tell me") — defeats the purpose; offer hints instead
- Real-time score visible during session — learners game the metric; show only in report
- Gamification (points, badges) — shifts motivation from understanding to score-chasing
- Automatic concept remediation — breaks Socratic contract; let spaced repetition handle gaps

### Architecture Approach

The system is a clean additive module: a new `engine/` Python package containing pure functions (TurnScheduler, ScoreCalculator, ReportExporter) and async generators (AgentRunner, SessionStateLoader, BlindSpotExtractor, SnapshotService), wired together by a new `cog_test` FastAPI router with one SSE endpoint and standard CRUD endpoints. Four new SQLAlchemy ORM models (`CogTestSession`, `CogTestTurn`, `CogTestBlindSpot`, `CogTestSnapshot`) extend the existing schema. The frontend adds one new view (`CogTestView.vue`), one composable (`useCogTestStream.ts`), and a trigger button on the existing `ModelCardDetailView`.

**Major components:**
1. `TurnScheduler` (engine/scheduler.py) — pure function: `(round, blind_spot_count, score) → agent_name`; Guide opens round 1, Challenger on even rounds, Guide wraps up when score > 80 after round 3
2. `AgentRunner` (engine/agent_runner.py) — async generator wrapping `LLMService.stream_generate()`; yields typed SSE events (`turn_start`, `token`, `turn_complete`)
3. `BlindSpotExtractor` (engine/parsers.py) — parses structured JSON block from agent output (not regex); returns `BlindSpot[]`; logs failures rather than silently returning empty
4. `ScoreCalculator` (engine/score.py) — pure function over session turns and blind spots; uses qualitative labels not raw percentage
5. `SnapshotService` (engine/snapshot.py) — persists state tree to DB on session end and explicit user save only (not every round)
6. `ReportExporter` (engine/export.py) — pure function generating Markdown diagnostic report from session + snapshots
7. `useCogTestStream.ts` — Vue3 composable owning EventSource lifecycle; closes on `onUnmounted`; writes to Pinia store
8. SSE event protocol — typed events: `turn_start | token | turn_complete | round_complete | error | done`

### Critical Pitfalls

1. **Guide agent drifts into answer-giving** — enforce output format (every response must end with exactly one `?`); add explicit negative constraint in system prompt; use temperature 0.3-0.4; add post-generation validator. Address in Phase 1 before any UI work.

2. **Blind spot extraction silently fails** — use JSON-mode structured output (agent appends a `<structured>` JSON block), not regex; log parse failures as "unextracted" rounds rather than returning empty arrays. Address in Phase 1 during agent output schema design.

3. **Challenger agent feels hostile** — frame as curiosity not contradiction ("我有个疑问..." not "你的理解有矛盾"); acknowledge what learner got right before raising a question; temperature 0.5-0.6; validate tone with real learners before launch. Address in Phase 1.

4. **SSE stream orphaned on client disconnect** — check `await request.is_disconnected()` before each agent call AND inside the token loop; failure burns LLM tokens and holds DB connections indefinitely. Address in Phase 2.

5. **LLMService has no streaming support** — add `stream_generate()` async generator method before building the engine; keep it separate from `generate()`; test with a simple endpoint first. This is the first task of the entire milestone.

---

## Implications for Roadmap

Based on research, the dependency chain is strict: DB schema → engine pure functions → LLM streaming → agent orchestration → SSE endpoint → frontend → report. Suggested 4-phase structure:

### Phase 1: Foundation — Prompts, Schema, and Streaming Infrastructure

**Rationale:** Three critical design decisions must be locked before any implementation: agent system prompts (prevents answer-drift and hostile tone), agent output schema (prevents silent extraction failures), and understanding score formula (prevents meaningless metric). These are design artifacts, not code — but getting them wrong requires rewrites of everything downstream. Simultaneously, the LLM streaming gap must be closed since it blocks all subsequent phases.

**Delivers:** Agent system prompts (guide.md, challenger.md) validated against anti-drift and tone criteria; structured JSON output schema for blind spot extraction; understanding score formula with edge cases reviewed; `LLMService.stream_generate()` async generator tested; DB migration for 4 new tables; Alembic migration applied.

**Addresses:** Guided questioning (table stakes), understanding score (differentiator), blind spot extraction (differentiator)

**Avoids:** Pitfall 1 (answer-drift), Pitfall 3 (regex silent failures), Pitfall 5 (hostile challenger), Pitfall 7 (meaningless score formula), Pitfall 8 (no streaming support)

**Research flag:** Needs `/gsd:research-phase` — agent prompt engineering for Socratic tutoring is nuanced; score formula design for learning domain has no established standard.

---

### Phase 2: Backend Engine — Turn Scheduler, Agent Orchestration, SSE Endpoint

**Rationale:** With schema and streaming in place, build the engine bottom-up as pure functions first (testable without HTTP), then wire to the SSE endpoint. Session state management strategy (in-memory per round, DB write at round end) must be established here to avoid the DB contention pitfall.

**Delivers:** `engine/` package with TurnScheduler, AgentRunner, BlindSpotExtractor, ScoreCalculator, SnapshotService; `cog_test` FastAPI router with session CRUD + SSE stream endpoint; disconnect detection; SSE heartbeat; JWT query-param auth for EventSource; session state in-memory cache pattern.

**Uses:** `sse-starlette` 1.8.2, `agno.agent.Agent`, `asyncio.Queue`, `LLMService.stream_generate()`

**Implements:** Async generator SSE pipeline, typed SSE event protocol, turn scheduler as pure function, JWT auth via query param

**Avoids:** Pitfall 2 (SSE orphan on disconnect), Pitfall 4 (DB state load per agent call), Pitfall 9 (snapshot bloat), Pitfall 10 (over-complex scheduler), Pitfall 11 (no heartbeat)

**Research flag:** Standard patterns — skip `/gsd:research-phase`. FastAPI SSE + agno patterns are well-documented and verified.

---

### Phase 3: Frontend — Dialogue UI and SSE Consumer

**Rationale:** Backend engine must be complete and testable before frontend work begins. The composable owns the EventSource lifecycle — building it before the endpoint is ready leads to mocking complexity and integration surprises.

**Delivers:** `useCogTestStream.ts` composable with EventSource lifecycle management and `onUnmounted` cleanup; `CogTestView.vue` with distinct visual identity for Guide vs Challenger turns, persistent "Stop and Diagnose" button, streaming token display without layout reflow; `ModelCardDetailView` trigger button as primary action; Vue Router entry for `/cog-test/:sessionId`; Pinia store `useCognitiveTestStore`.

**Avoids:** Pitfall 6 (EventSource not cleaned up), UX pitfall (no visual distinction between agents), UX pitfall (stop affordance not visible), UX pitfall (streaming layout reflow), Pitfall 12 (entry point buried)

**Research flag:** Standard patterns — skip `/gsd:research-phase`. Vue3 composable + EventSource patterns are well-established.

---

### Phase 4: Diagnostic Report and Integration Polish

**Rationale:** Report export has no blocking dependencies on frontend work and can be deferred until the core dialogue loop is validated. This phase also handles the spaced repetition integration hook and any prompt/tone refinements discovered during Phase 3 testing.

**Delivers:** `ReportExporter` generating sanitized Markdown diagnostic report; report download endpoint; report render in `CogTestView`; blind spot → spaced repetition integration hook (v1.x); security hardening (session ownership check, LLM output sanitization for XSS, report content sanitization).

**Avoids:** Security mistake (session ID without auth check), security mistake (LLM output as raw HTML), security mistake (unsanitized report export)

**Research flag:** Standard patterns for report generation. Spaced repetition integration may need a brief research spike depending on existing SR system API surface.

---

### Phase Ordering Rationale

- Phase 1 before everything: prompt engineering and output schema failures are the highest-recovery-cost pitfalls. Discovering answer-drift or silent extraction failures after the UI is built requires rewrites across all layers.
- Phase 2 before Phase 3: the SSE event protocol is the contract between backend and frontend. Building the frontend against a stable, tested event protocol eliminates integration surprises.
- Phase 4 last: report export is a pure function over session data with no blocking dependencies. Deferring it keeps Phase 2 and 3 focused on the core dialogue loop validation.
- LLM streaming extension is the first task of Phase 1, not Phase 2: it's a prerequisite for testing agent prompts in Phase 1 (you need to see streaming output to validate tone and format).

### Research Flags

Phases needing deeper research during planning:
- **Phase 1 (Prompts + Score Formula):** Agent prompt engineering for Socratic tutoring is domain-specific with limited production examples. Understanding score formula for learning has no established standard — needs design research before implementation.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Backend Engine):** FastAPI SSE + agno multi-agent patterns are verified via official docs and direct codebase inspection. Build order is clear.
- **Phase 3 (Frontend):** Vue3 composable + EventSource patterns are well-documented. No novel integration challenges.
- **Phase 4 (Report + Polish):** Markdown export is a pure function. Security patterns are standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing codebase directly inspected; agno Team API verified via GitHub; sse-starlette compatibility verified; no new major dependencies |
| Features | MEDIUM | Academic research (SocratiQ, SPL, SocraticAI) is HIGH confidence; product feature specifics (Khanmigo) are MEDIUM; dual-agent tutoring has limited real-world production deployments |
| Architecture | HIGH | Existing codebase directly inspected; SSE/FastAPI patterns verified via official docs; build order derived from actual dependency analysis |
| Pitfalls | MEDIUM | Core pitfalls (SSE disconnect, regex parsing, LLM streaming gap) verified via direct code inspection and multiple sources; learning-specific pitfalls (hostile challenger, answer-drift) from academic research — MEDIUM confidence |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Understanding score formula:** No established standard for learning domain. Research confirms ProdMind's formula is wrong for this context, but the right formula is not specified. Needs design work in Phase 1 — start with qualitative labels ("初步探索" / "深入理解" / "掌握") and evolve from there.
- **Agent prompt validation:** Tone and anti-drift constraints need validation with real learners, not just design review. Plan for a prompt iteration cycle in Phase 1 before locking prompts.
- **agno Team vs. two independent Agent calls:** Research recommends `agno.Team` with `TeamMode.coordinate`, but notes a fallback to two independent `Agent.arun()` calls if Team streaming proves insufficient. This needs a quick spike in Phase 2 to confirm which path works.
- **Spaced repetition integration surface:** The existing SR system's API surface was not inspected during research. Phase 4 integration hook complexity is unknown — flag for a brief research spike.

---

## Sources

### Primary (HIGH confidence)
- Existing LAS backend direct inspection (`llm_service.py`, `conversations.py`, `requirements.txt`) — confirmed no streaming support, existing agno usage, SQLAlchemy async patterns
- ProdMind reference engine direct inspection (`ref/prodmind2-web/src/lib/engine/`) — scheduler, parsers, context-builder, export patterns
- agno GitHub (agno-agi/agno) — Team modes, Agent streaming API, version 1.2.8
- MDN Web Docs EventSource API — browser EventSource spec, 6-connection limit, cleanup requirements
- sse-starlette PyPI — version 1.8.2, Starlette 0.40+ compatibility
- SocraticAI (arxiv 2512.03501) — scaffolded CS tutoring, EMT principles
- SPL (arxiv 2406.13919) — Socratic Playground for Learning, multi-turn guided dialogue
- Frontiers in Education 2025 — Socratic wisdom comparative study

### Secondary (MEDIUM confidence)
- Khanmigo AI Review 2025 (aiflowreview.com) — feature comparison
- Multi-agent debate failure modes (arxiv 2509.05396) — sycophancy and conformity in large MAD systems
- FastAPI SSE patterns 2025 (multiple sources) — StreamingResponse + async generator
- Vue3 SSE composable patterns 2025 (multiple sources) — native EventSource recommended
- jasoncameron.dev — FastAPI disconnect detection pattern
- Brookings Institution 2025 — learner anxiety under adversarial questioning
- SocratiQ (emergentmind.com) — dual-agent Socratic dialogue systems

### Tertiary (LOW confidence)
- softcery.com — "The AI Agent Prompt Engineering Trap" — prompt engineering diminishing returns (single source, needs validation)

---
*Research completed: 2026-02-28*
*Ready for roadmap: yes*
