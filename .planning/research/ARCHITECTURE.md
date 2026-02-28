# Architecture Research

**Domain:** Multi-agent Socratic dialogue system integrated into existing Vue3+FastAPI learning platform
**Researched:** 2026-02-28
**Confidence:** HIGH (existing codebase verified by direct inspection; SSE/FastAPI patterns verified via official docs and multiple sources)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Vue3 Frontend                                 │
├──────────────────┬──────────────────┬───────────────────────────────┤
│  ModelCardDetail │  CogTestView     │  Existing Views               │
│  (trigger entry) │  (dialogue UI)   │  (unchanged)                  │
└────────┬─────────┴────────┬─────────┴───────────────────────────────┘
         │  POST /sessions  │  GET /sessions/{id}/stream (SSE)
         │                  │  POST /sessions/{id}/stop
         ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                               │
├──────────────────┬──────────────────┬───────────────────────────────┤
│  cog_test router │  SSE endpoint    │  Existing routers             │
│  (session CRUD)  │  (stream rounds) │  (unchanged)                  │
└────────┬─────────┴────────┬─────────┴───────────────────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Cognitive Test Engine                            │
├──────────────────┬──────────────────┬───────────────────────────────┤
│  TurnScheduler   │  SessionState    │  AgentRunner                  │
│  (who speaks)    │  (round context) │  (streams tokens via LLM)     │
└────────┬─────────┴────────┬─────────┴────────┬──────────────────────┘
         │                  │                   │
         ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Existing Infrastructure (reused)                    │
├──────────────────┬──────────────────┬───────────────────────────────┤
│  LLMService      │  SQLAlchemy ORM  │  Auth / JWT middleware        │
│  (provider pool) │  (SQLite)        │  (get_current_user dep)       │
└──────────────────┴──────────────────┴───────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `ModelCardDetailView.vue` | Entry point — "Start Cognitive Test" button | Existing view, add one button + router-push |
| `CogTestView.vue` | Full dialogue UI, SSE consumer, score display | New Vue3 view with EventSource composable |
| `useCogTestStream.ts` | Composable wrapping EventSource lifecycle | `new EventSource(url)`, reactive state, cleanup |
| `cog_test` router (FastAPI) | Session CRUD + SSE stream endpoint | New `APIRouter`, mounted at `/api/cog-test` |
| `TurnScheduler` | Decides which agent speaks each round | Pure function: `(session_state, round) → agent_name` |
| `SessionStateLoader` | Loads full session context from DB for agent prompt | Async function querying SQLAlchemy session |
| `AgentRunner` | Calls LLMService with role prompt + context, yields tokens | Async generator wrapping existing `llm_service` |
| `BlindSpotExtractor` | Parses agent output for cognitive gaps | Regex/structured-output parser, returns `BlindSpot[]` |
| `ScoreCalculator` | Computes understanding score from blind spots + rounds | Pure function, called after each round |
| `SnapshotService` | Saves per-round state tree to DB | Writes `CogTestSnapshot` row after each round |
| `ReportExporter` | Generates Markdown diagnostic report | Pure function over session + snapshots data |
| `CogTestSession` (ORM) | Root session record (model_card_id, round, score) | New SQLAlchemy model, FK to `model_cards` |
| `CogTestTurn` (ORM) | One agent utterance per turn | New SQLAlchemy model, FK to session |
| `CogTestBlindSpot` (ORM) | Extracted cognitive gap per session | New SQLAlchemy model, FK to session |
| `CogTestSnapshot` (ORM) | Per-round state tree JSON | New SQLAlchemy model, FK to session |

---

## Recommended Project Structure

```
las_backend/app/
├── api/routes/
│   └── cog_test.py              # New: session CRUD + SSE stream endpoint
├── engine/                      # New package — cognitive test engine
│   ├── __init__.py
│   ├── scheduler.py             # TurnScheduler: pure function
│   ├── state_loader.py          # SessionStateLoader: DB → context string
│   ├── agent_runner.py          # AgentRunner: async generator → tokens
│   ├── parsers.py               # BlindSpotExtractor: output → structured data
│   ├── score.py                 # ScoreCalculator: pure function
│   ├── snapshot.py              # SnapshotService: persist state tree
│   └── export.py                # ReportExporter: session → Markdown
├── models/entities/
│   └── cog_test.py              # New ORM models (4 tables)
├── schemas/
│   └── cog_test.py              # Pydantic request/response schemas
└── prompts/                     # New: agent system prompts as .md files
    ├── guide.md                 # 引导者 system prompt
    └── challenger.md            # 质疑者 system prompt

las_frontend/src/
├── views/
│   └── CogTestView.vue          # New: full dialogue UI
├── composables/
│   └── useCogTestStream.ts      # New: EventSource wrapper composable
└── router/index.ts              # Add /cog-test/:sessionId route
```

### Structure Rationale

- `engine/` mirrors ProdMind's `src/lib/engine/` but as a Python package — keeps all dialogue logic isolated from HTTP concerns
- `prompts/` as `.md` files loaded at runtime — same pattern as ProdMind's `loadPrompt()`, easy to iterate without code changes
- `composables/useCogTestStream.ts` — Vue3 idiomatic pattern for stateful side-effects; keeps `CogTestView.vue` clean
- New ORM models in their own file — avoids touching the already-large `user.py` entity file

---

## Architectural Patterns

### Pattern 1: Async Generator SSE Pipeline

**What:** FastAPI endpoint returns `EventSourceResponse` wrapping an async generator. The generator yields typed SSE events as the engine runs each turn.

**When to use:** Any time you need to stream multi-step AI output with structured event types (not just raw tokens).

**Trade-offs:** Simple, no message broker needed. Single-server only — fine for this scale.

**Example:**
```python
# las_backend/app/api/routes/cog_test.py
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter, Depends
import json

router = APIRouter(prefix="/cog-test", tags=["CognitiveTest"])

@router.get("/sessions/{session_id}/stream")
async def stream_round(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def event_generator():
        async for event in run_dialogue_round(db, current_user.id, session_id):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())
```

### Pattern 2: Typed SSE Event Protocol

**What:** Define a fixed set of event types as a Python TypedDict (or dataclass). Every yield from the engine is one of these types. The frontend switches on `event.type`.

**When to use:** Multi-step pipelines where the frontend needs to react differently to "agent started speaking" vs "token arrived" vs "round complete".

**Trade-offs:** Adds a small schema contract to maintain. Worth it — prevents frontend/backend drift.

**Example:**
```python
# engine/agent_runner.py — event types emitted by the engine
# { "type": "turn_start",    "agent": "guide" }
# { "type": "token",         "agent": "guide", "content": "..." }
# { "type": "turn_complete", "agent": "guide" }
# { "type": "round_complete","round": 2, "score": 67, "blind_spots": [...] }
# { "type": "error",         "message": "..." }
# { "type": "done" }
```

```typescript
// composables/useCogTestStream.ts
const source = new EventSource(`/api/cog-test/sessions/${sessionId}/stream`, {
  withCredentials: false  // JWT passed as query param for EventSource
})
source.onmessage = (e) => {
  const event = JSON.parse(e.data)
  if (event.type === 'token') appendToken(event.agent, event.content)
  if (event.type === 'round_complete') updateScore(event.score)
  if (event.type === 'done') source.close()
}
```

### Pattern 3: Turn Scheduler as Pure Function

**What:** The scheduler takes session state (round number, blind spots found so far, score) and returns which agent speaks next. No side effects, no DB calls.

**When to use:** Always — keeping scheduling logic pure makes it trivially testable and easy to tune.

**Trade-offs:** None for this scale. Would need to become stateful only if agents could dynamically spawn sub-agents (not in scope).

**Example:**
```python
# engine/scheduler.py
def get_next_agent(round: int, blind_spot_count: int, score: int) -> str:
    """
    Round 1: guide always opens.
    Even rounds: challenger questions.
    Odd rounds after 1: guide probes deeper.
    If score > 80 and round > 3: guide wraps up.
    """
    if round == 1:
        return "guide"
    if score > 80 and round > 3:
        return "guide"  # wrap-up mode
    return "challenger" if round % 2 == 0 else "guide"
```

### Pattern 4: JWT Auth for SSE via Query Parameter

**What:** `EventSource` in browsers cannot set custom headers. Pass the JWT as a `?token=` query parameter. FastAPI middleware or a dependency extracts it.

**When to use:** Required for any authenticated SSE endpoint — this is the standard workaround.

**Trade-offs:** Token visible in server logs. Mitigate with short-lived tokens or by accepting the tradeoff for an internal tool.

**Example:**
```python
# Dependency that accepts token from header OR query param
async def get_current_user_sse(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Query(None),
):
    auth_header = request.headers.get("Authorization")
    resolved = token or (auth_header.split(" ")[1] if auth_header else None)
    if not resolved:
        raise HTTPException(status_code=401)
    return await verify_token(resolved, db)
```

---

## Data Flow

### Session Start Flow

```
User clicks "Start Test" on ModelCardDetail
    ↓
POST /api/cog-test/sessions  { model_card_id }
    ↓
Backend creates CogTestSession row, returns { session_id }
    ↓
Frontend router.push('/cog-test/{session_id}')
    ↓
CogTestView mounts → useCogTestStream opens EventSource
    ↓
GET /api/cog-test/sessions/{id}/stream?token=JWT
```

### Round Streaming Flow

```
EventSource connection opens
    ↓
engine.run_dialogue_round(db, user_id, session_id)
    ↓
TurnScheduler.get_next_agent(round, blind_spots, score)
    → yields { type: "turn_start", agent: "guide" }
    ↓
SessionStateLoader.load(db, session_id)
    → builds context string from model_card + prior turns
    ↓
AgentRunner.stream(llm_service, agent, context)
    → yields { type: "token", agent, content } per token
    → yields { type: "turn_complete", agent }
    ↓
BlindSpotExtractor.parse(full_output)
    → persists CogTestBlindSpot rows
    ↓
ScoreCalculator.compute(session_id, db)
    → updates CogTestSession.score
    ↓
SnapshotService.save(db, session_id, round)
    → persists CogTestSnapshot row
    ↓
yields { type: "round_complete", round, score, blind_spots }
    ↓
yields { type: "done" }
    ↓
EventSource closes
```

### Stop + Diagnose Flow

```
User clicks "Stop"
    ↓
Frontend: source.close()  (closes SSE connection)
    ↓
POST /api/cog-test/sessions/{id}/stop
    ↓
Backend: marks session status = "stopped", runs final ScoreCalculator
    ↓
GET /api/cog-test/sessions/{id}/report
    ↓
ReportExporter.generate(db, session_id) → Markdown string
    ↓
Frontend renders report, offers download
```

### State Management (Frontend)

```
useCogTestStream composable
    ↓ (reactive refs)
CogTestView.vue
  - turns: Ref<Turn[]>          ← appended on token/turn_complete events
  - score: Ref<number>          ← updated on round_complete
  - blindSpots: Ref<BlindSpot[]>← updated on round_complete
  - status: Ref<SessionStatus>  ← 'idle'|'streaming'|'stopped'|'done'
```

---

## Database Schema (New Tables)

```
cog_test_sessions
  id            String PK
  user_id       FK → users.id
  model_card_id FK → model_cards.id
  status        String  ('active'|'stopped'|'done')
  current_round Integer default 0
  score         Integer default 0
  created_at    DateTime
  updated_at    DateTime

cog_test_turns
  id            String PK
  session_id    FK → cog_test_sessions.id
  round         Integer
  agent         String  ('guide'|'challenger')
  content       Text
  created_at    DateTime

cog_test_blind_spots
  id            String PK
  session_id    FK → cog_test_sessions.id
  round         Integer
  content       Text
  source_agent  String
  created_at    DateTime

cog_test_snapshots
  id            String PK
  session_id    FK → cog_test_sessions.id
  version       Integer
  trigger       String
  state_tree    JSON    (turns, blind_spots, score at this point)
  created_at    DateTime
```

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `cog_test` router ↔ engine | Direct Python function calls | Engine is a plain package, no HTTP boundary |
| engine ↔ `llm_service` | `await llm_service.generate_stream(...)` | Need to add `generate_stream` async generator method to existing `LLMService` |
| engine ↔ SQLAlchemy | `AsyncSession` passed as parameter | Same pattern as all existing routes |
| `CogTestView` ↔ backend | SSE for streaming, REST for CRUD | Two separate connection types, composable manages both |
| `ModelCardDetailView` ↔ `CogTestView` | Vue Router push with `session_id` | Session created before navigation |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM providers (OpenAI/Anthropic/Ollama) | Reuse existing `LLMService` | Must add streaming variant — current `generate()` is non-streaming |
| SQLite | Reuse existing `AsyncSession` + Alembic | Add new migration for 4 new tables |

---

## Anti-Patterns

### Anti-Pattern 1: Blocking LLM Call Inside SSE Generator

**What people do:** Call `await llm_service.generate(prompt)` (non-streaming) inside the SSE generator, then yield the full response as one event.

**Why it's wrong:** User sees nothing for 5-15 seconds, then gets a wall of text. Defeats the purpose of SSE. Also risks timeout on the SSE connection.

**Do this instead:** Add `generate_stream()` async generator to `LLMService` that yields tokens as they arrive from the provider. The engine's `AgentRunner` wraps this and yields `token` events.

### Anti-Pattern 2: Storing Full Dialogue in a Single JSON Column

**What people do:** Append turns to a `messages: JSON` column on the session (like the existing `Conversation.messages`).

**Why it's wrong:** Can't query individual turns, can't paginate, can't efficiently extract blind spots by round. JSON column grows unbounded.

**Do this instead:** Use `cog_test_turns` as a proper relational table. The existing `Conversation.messages` JSON pattern is acceptable for simple chat but not for a structured multi-agent session with per-turn analytics.

### Anti-Pattern 3: Putting Scheduling Logic in the Route Handler

**What people do:** Write `if round == 1: agent = "guide" elif round % 2 == 0: agent = "challenger"` directly in the FastAPI route.

**Why it's wrong:** Untestable, hard to tune, mixes HTTP concerns with domain logic.

**Do this instead:** `TurnScheduler` as a pure function in `engine/scheduler.py`. Route handler calls it, doesn't contain the logic.

### Anti-Pattern 4: One SSE Connection Per Token Request

**What people do:** Open a new SSE connection for each round, close it when the round ends, reopen for the next.

**Why it's wrong:** Connection setup overhead, reconnect flicker in the UI, browser limits on concurrent EventSource connections.

**Do this instead:** One SSE connection per session. The generator loops over rounds internally, yielding `round_complete` events between rounds. The frontend keeps the connection open until `done` or user stops.

---

## Suggested Build Order

Dependencies flow bottom-up. Build in this order:

1. **DB models + Alembic migration** — everything else depends on the schema existing
2. **`engine/scheduler.py`** — pure function, no dependencies, testable immediately
3. **`LLMService.generate_stream()`** — add streaming variant to existing service
4. **`engine/agent_runner.py`** — depends on LLMService streaming
5. **`engine/state_loader.py`** — depends on DB models
6. **`engine/parsers.py` + `engine/score.py`** — pure functions, no dependencies
7. **`engine/snapshot.py`** — depends on DB models
8. **`cog_test` router + SSE endpoint** — wires all engine pieces together
9. **`useCogTestStream.ts` composable** — frontend SSE consumer
10. **`CogTestView.vue`** — depends on composable
11. **`ModelCardDetailView.vue` trigger** — add button, depends on router
12. **`engine/export.py` + report endpoint** — can be deferred, no blocking dependencies

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 concurrent sessions | Current design is fine — SQLite + single FastAPI process handles this |
| 100-1k concurrent sessions | Switch SQLite → PostgreSQL (async driver), keep single process |
| 1k+ concurrent sessions | Add Redis pub/sub for SSE fan-out; move to multiple FastAPI workers behind a load balancer |

### Scaling Priorities

1. **First bottleneck:** SQLite write contention under concurrent sessions — fix by migrating to PostgreSQL before scaling
2. **Second bottleneck:** LLM API rate limits — fix with per-user request queuing or provider load balancing (already partially supported by `LLMProvider.priority`)

---

## Sources

- ProdMind reference engine (direct inspection): `ref/prodmind2-web/src/lib/engine/` — scheduler, debate, roles, context-builder, parsers, export patterns
- Existing LAS backend (direct inspection): `las_backend/app/services/llm_service.py`, `app/api/routes/conversations.py`, `app/models/entities/user.py`
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) — production SSE for FastAPI/Starlette (HIGH confidence)
- [FastAPI Streaming Responses](https://hassaanbinaslam.github.io/posts/2025-01-19-streaming-responses-fastapi.html) — EventSourceResponse pattern (MEDIUM confidence)
- [FastAPI SSE Auth via query param](https://openillumi.com/en/en-fastapi-sse-auth-bearer-token-middleware-strategy/) — JWT workaround for EventSource (MEDIUM confidence)
- [MDN EventSource API](https://developer.mozilla.org/en-US/docs/Web/API/EventSource) — browser EventSource spec (HIGH confidence)
- [Multi-agent state machine patterns](https://www.zedhaque.com/blog/voice-agents-state-machines/) — turn-taking state machine design (MEDIUM confidence)

---
*Architecture research for: Cognitive Adversarial Testing — Vue3+FastAPI integration*
*Researched: 2026-02-28*
