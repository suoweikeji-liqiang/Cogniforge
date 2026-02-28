# Stack Research

**Domain:** Real-time multi-agent Socratic AI dialogue — additive milestone on Vue3 + FastAPI
**Researched:** 2026-02-28
**Confidence:** MEDIUM-HIGH (core patterns verified via official docs and multiple sources; agno team streaming API verified via GitHub/docs)

---

## Context: What Already Exists (Do Not Re-introduce)

The existing system already has these locked in — do not replace or duplicate:

| Already Present | Version | Notes |
|-----------------|---------|-------|
| FastAPI | 0.115.0 | Async, already in use |
| agno | 1.2.8 | LLM orchestration layer — REUSE this |
| SQLAlchemy (async) | 2.0.35 | ORM — extend, don't replace |
| Vue 3 | ^3.5.0 | Frontend framework |
| Pinia | ^2.2.0 | State management |
| axios | ^1.7.0 | HTTP client — already configured with auth interceptors |
| openai / anthropic SDKs | installed | Via agno's provider abstraction |

The milestone adds: SSE streaming endpoint, agno Team orchestration, session state tracking, snapshot persistence.

---

## Recommended Stack (New Additions Only)

### Backend: SSE Streaming Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `fastapi.responses.StreamingResponse` | built-in (0.115.0) | SSE transport | Already in FastAPI — no new dependency. Use `media_type="text/event-stream"` with an async generator. Zero overhead. |
| `sse-starlette` | 1.8.2 | SSE helper (optional) | Provides `EventSourceResponse` with proper SSE framing (retry, event ID, named events). Use if you need named event types beyond raw `data:` lines. |
| `asyncio` | stdlib | Async coordination between agents | Already available — use `asyncio.Queue` to pipe agent output tokens into the SSE stream. |

**Decision:** Start with raw `StreamingResponse` + async generator. Add `sse-starlette` only if named event types (e.g., `event: turn_change`, `event: score_update`) are needed — they will be, given the multi-agent turn scheduler requirement.

### Backend: Agent Orchestration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `agno.team.Team` | 1.2.8 (already installed) | Two-tutor coordination | agno's `Team` class with `TeamMode.coordinate` handles turn-based multi-agent dialogue natively. Reuses existing LLM provider config — no new SDK calls. |
| `agno.agent.Agent` | 1.2.8 | Individual tutor roles (Guide + Challenger) | Each tutor is an `Agent` with a distinct system prompt and role. agno handles per-agent context isolation. |

**Pattern:** Two `Agent` instances (Guide + Challenger) wrapped in a `Team`. The turn scheduler is a custom Python class that calls `agent.arun()` or `agent.run_stream()` alternately, piping output into an `asyncio.Queue` consumed by the SSE generator.

**Do NOT use LangGraph or CrewAI** — agno is already installed and the existing `llm_service.py` uses it. Introducing a second orchestration framework creates dual dependency hell and breaks the existing LLM provider abstraction.

### Backend: Session State + Snapshot

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python `dataclasses` / Pydantic `BaseModel` | stdlib / 2.9.2 | In-memory session state | Pydantic is already installed. Model the session state (turn count, understanding score, blind spots list, current phase) as a Pydantic model. Serialize to JSON for snapshots. |
| SQLAlchemy JSON column | 2.0.35 | Snapshot persistence | Existing `EvolutionLog.snapshot` column is already a `JSON` column — same pattern works for cognitive test snapshots. No schema migration complexity beyond adding new tables. |
| `asyncio.Queue` | stdlib | Token pipeline from agent → SSE | Decouples agent generation from HTTP streaming. Agent pushes tokens; SSE generator consumes them. Handles backpressure naturally. |

### Frontend: SSE Consumption

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Native `EventSource` API | browser built-in | SSE connection | Zero dependency. Works in all modern browsers. Auto-reconnects on drop. Use this over any library. |
| Custom Vue composable `useDialogueStream` | — | Reactive SSE wrapper | Wrap `EventSource` in a composable that exposes `ref`s for `messages`, `isStreaming`, `currentSpeaker`, `score`. Integrates naturally with Pinia. |
| Pinia store `useCognitiveTestStore` | ^2.2.0 (already installed) | Session state across components | Dialogue state (session ID, turn history, blind spots, score) lives in Pinia. The composable writes to the store; components read from it. |

**Do NOT use `vue-sse` plugin** — it's a thin wrapper around `EventSource` with no meaningful abstraction benefit and adds a dependency. A 30-line composable does the same job with full control over event parsing.

**Do NOT use axios for SSE** — axios buffers responses and does not support streaming. The existing `api/index.ts` axios instance is fine for REST calls; SSE needs a separate `EventSource` or `fetch` with `ReadableStream`.

### Frontend: Real-time UI Updates

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Vue 3 `ref` + `computed` | ^3.5.0 | Reactive token accumulation | Append tokens to a `ref<string>` as they arrive. `computed` derives display state. No extra library needed. |
| `markdown-it` | ^14.1.0 (already installed) | Render tutor responses as Markdown | Already in the project. Render accumulated text through `markdown-it` on each token append for live Markdown preview. |

---

## Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sse-starlette` | 1.8.2 | Named SSE events with proper framing | Add when you need `event: turn_change` or `event: session_end` typed events — required for the turn scheduler UI sync |
| `python-statemachine` | 2.1.1 | Explicit FSM for dialogue phase transitions | Use if dialogue phases (intro → probing → challenge → diagnosis → done) need guarded transitions with callbacks. Alternative: plain Python enum + dict is sufficient for 5 states. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| WebSockets | Bidirectional — overkill for server-push-only dialogue streaming. Adds connection management complexity and CORS complications. | SSE via `StreamingResponse` |
| LangGraph | Second orchestration framework alongside agno. Doubles dependency surface, breaks existing LLM provider abstraction, steep learning curve. | agno `Team` (already installed) |
| CrewAI | Same problem as LangGraph. Role-based but opinionated about agent communication patterns that conflict with the custom turn scheduler needed here. | agno `Team` |
| `vue-sse` npm package | Thin wrapper with no benefit over native `EventSource`. Last meaningful update 2022. | Native `EventSource` in a composable |
| axios for SSE | Buffers entire response — SSE never streams. | Native `EventSource` or `fetch` + `ReadableStream` |
| Redis / message broker | Unnecessary for single-user session streaming. Adds infra complexity. | `asyncio.Queue` in-process |
| Supabase / separate DB | Out of scope per PROJECT.md constraints. | Existing SQLAlchemy + SQLite |

---

## Stack Patterns by Variant

**If the turn scheduler needs strict phase enforcement (intro → probing → challenge → diagnosis):**
- Use `python-statemachine` 2.1.1 for the FSM
- Because guarded transitions prevent invalid state jumps and callbacks trigger snapshot saves automatically

**If 5 phases feel like overkill for v1:**
- Use a plain Python `Enum` + `match` statement
- Because it's 10 lines vs a full FSM library, and phases are linear not branching

**If the SSE connection needs to survive proxy timeouts (nginx default 60s):**
- Send a `data: {"type":"heartbeat"}\n\n` every 15s from the async generator
- Because SSE connections through nginx/Caddy get killed at idle timeout without keepalive pings

**If agno's `Team` streaming API proves insufficient for interleaved multi-agent output:**
- Fall back to two independent `Agent.arun()` calls coordinated by the turn scheduler
- Because the turn scheduler owns sequencing anyway — agno `Team` is a convenience, not a requirement

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| agno 1.2.8 | FastAPI 0.115.0 | No conflicts — agno uses httpx internally, same as existing stack |
| sse-starlette 1.8.2 | FastAPI 0.115.0 / Starlette 0.40+ | FastAPI 0.115 ships Starlette 0.40.x — compatible |
| python-statemachine 2.1.1 | Python 3.8+ | No conflicts with existing deps |
| pinia 2.2.0 | Vue 3.5.0 | Fully compatible |

---

## Installation

```bash
# Backend — only new additions
pip install sse-starlette==1.8.2

# Optional: only if using explicit FSM
pip install python-statemachine==2.1.1

# Frontend — no new npm packages needed
# Native EventSource API is browser-built-in
# All other frontend deps already installed
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| agno `Team` | LangGraph | If you were starting fresh without agno, or needed complex DAG-based workflows |
| Native `EventSource` | `@microsoft/fetch-event-source` | If you need POST-based SSE (EventSource only supports GET) — relevant if auth token can't go in query params |
| `asyncio.Queue` | Redis Pub/Sub | If multiple backend workers need to share stream state (not needed here — single session, single worker) |
| `StreamingResponse` + `sse-starlette` | WebSockets | If you needed bidirectional real-time (user typing indicators, etc.) |
| Pydantic session model | SQLAlchemy session table | If sessions needed to survive server restarts mid-dialogue (v1 doesn't require this) |

---

## Key Architecture Decision: Auth with SSE

`EventSource` does not support custom headers — it can't send `Authorization: Bearer <token>`. Two options:

1. **Query param token** (simpler): `GET /api/cognitive-test/stream?token=<jwt>` — validate token in the endpoint. Acceptable for short-lived SSE connections.
2. **Cookie-based auth** (more secure): Set an `HttpOnly` session cookie on session start, `EventSource` sends it automatically.

**Recommendation:** Use query param token for v1. The existing JWT auth in `app/api/routes/auth.py` can be reused — just extract token from query params instead of `Authorization` header. Flag for upgrade to cookie auth in a later phase.

---

## Sources

- agno GitHub (agno-agi/agno) — version 2.5.5 confirmed Feb 25 2026; Team modes (coordinate/route/broadcast/tasks) verified
- FastAPI official docs (fastapi.tiangolo.com/advanced/stream-data/) — StreamingResponse + async generator pattern
- sse-starlette PyPI — version 1.8.2, Starlette compatibility
- python-statemachine readthedocs.io 2.1.1 — FSM transitions and events
- WebSearch: FastAPI SSE patterns 2025 (MEDIUM confidence — multiple sources agree on StreamingResponse pattern)
- WebSearch: Vue3 SSE composable patterns 2025 (MEDIUM confidence — native EventSource recommended across sources)
- Existing codebase audit: `requirements.txt`, `llm_service.py`, `main.py`, `package.json` (HIGH confidence — direct inspection)

---
*Stack research for: Cognitive Adversarial Testing — SSE streaming + multi-agent Socratic dialogue on Vue3+FastAPI*
*Researched: 2026-02-28*
