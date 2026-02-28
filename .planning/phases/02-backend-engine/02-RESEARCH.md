# Phase 2: Backend Engine - Research

**Researched:** 2026-02-28
**Domain:** FastAPI async SSE streaming, multi-agent turn scheduling, LLM cancellation, SQLAlchemy async persistence
**Confidence:** HIGH (codebase is the primary source; patterns are well-established)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Turn Scheduling**
- Fixed alternation per round: Guide → user → Challenger → user
- Default 3 rounds per session, with optional "Continue" after round 3
- Guide opens the session by prompting with the concept name: "What do you know about X?"
- Full conversation history passed to each agent every turn (no sliding window)

**SSE Event Protocol**
- Rich event vocabulary: session_start, turn_start, token, turn_complete, round_complete, session_complete
- Token events carry text only — role info comes from the preceding turn_start event
- Analysis data (blind spots, scores) stays server-side, only surfaces in the final report
- LLM failures: silent retry up to 2 attempts, then send error event and close stream

**Session Lifecycle**
- "Stop and Diagnose": immediate cancel of in-flight LLM call, generate summary from accumulated data, send session_complete
- No timeout for abandoned sessions — sessions stay active until explicitly stopped
- Sessions are resumable — user can return to an active session and continue dialogue
- One active session per user at a time — starting a new session auto-stops the previous one

**Scoring & Analysis**
- Blind spots extracted from every agent turn (both Guide and Challenger), stored immediately in CogTestBlindSpot
- CogTestSnapshot created per round + one final aggregated snapshot at session end
- Round-level understanding_score: Challenger-weighted average (Challenger ~60%, Guide ~40%)
- Duplicate blind spots stored as-is — deduplication happens at report generation time

### Claude's Discretion
- Exact retry backoff strategy for LLM failures
- How to aggregate the final session-level understanding score from round snapshots
- Internal data structures for managing the turn scheduler state
- How to detect and cancel in-flight LLM calls on stop

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGNT-01 | Guide agent prompts learner with positive Socratic questions | Prompts ready in `cog_test_prompts.py`; `stream_generate()` accepts `system_prompt` + `temperature` |
| AGNT-02 | Challenger agent gently surfaces contradictions and gaps | Same as AGNT-01; CHALLENGER_SYSTEM_PROMPT + CHALLENGER_TEMPERATURE=0.6 already defined |
| AGNT-03 | Both agents enforce Socratic contract — never give direct answers | Output validation layer: scan `dialogue_text` for forbidden phrases before streaming tokens to client |
| AGNT-04 | Turn scheduler controls which agent speaks each turn | Stateful scheduler class; fixed Guide→Challenger alternation per round |
| AGNT-05 | Agent feedback explains WHY answer is incomplete, not just wrong/right | Enforced by prompt design (already in cog_test_prompts.py); no extra code needed |
| SESS-02 | Agent replies stream via SSE, token by token | `EventSourceResponse` + `stream_generate()` already proven in `/stream-test` endpoint |
| SESS-03 | Each turn built on full conversation history | Pass accumulated `messages: list[dict]` to every `stream_generate()` call |
| SESS-04 | User can stop at any time and get diagnostic summary | asyncio.Task cancellation + summary generation from persisted data |
| ANLS-01 | Understanding score calculated per round (report only) | Challenger-weighted average of `understanding_level` values from `AgentOutput`; map low/medium/high → 0.33/0.66/1.0 |
| ANLS-02 | Blind spots extracted per turn, classified into categories | `parse_agent_output()` already returns `BlindSpot(category, description)`; persist to `cog_test_blind_spots` |
| ANLS-03 | Cognitive snapshot saved per round + final aggregated snapshot | Create `CogTestSnapshot` at round_complete and session_complete events |
</phase_requirements>

---

## Summary

Phase 2 builds entirely on top of Phase 1 assets. The streaming infrastructure (`EventSourceResponse`, `stream_generate()`), agent prompts (`cog_test_prompts.py`), output parser (`cog_test_parser.py`), and DB schema (`cog_test_sessions`, `cog_test_turns`, `cog_test_blind_spots`, `cog_test_snapshots`) are all in place. The work here is wiring them together into a coherent engine.

The three hard problems are: (1) cancelling an in-flight async generator when the client disconnects or calls `/stop`, (2) enforcing the Socratic contract at the output layer before tokens reach the client, and (3) managing the turn scheduler state across an async SSE stream that may be interrupted and resumed. Everything else is straightforward plumbing.

The existing `stream_generate()` is an `AsyncGenerator[str, None]`. Cancellation works by wrapping the generator in an `asyncio.Task` and calling `.cancel()` — the generator will raise `asyncio.CancelledError` at the next `yield` point. The session state (current round, current agent, accumulated history) must live in memory during an active stream and be recoverable from the DB on resume.

**Primary recommendation:** Implement a `CogTestEngine` service class that owns the turn scheduler, manages the in-flight task reference, and exposes `start()`, `submit_user_turn()`, and `stop()` coroutines. The SSE endpoint delegates entirely to this class.

---

## Standard Stack

### Core (all already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | installed | `EventSourceResponse` for SSE | Already used in `/stream-test`; proven pattern |
| FastAPI | installed | HTTP + SSE endpoints | Project standard |
| SQLAlchemy async | installed | Async DB persistence | Project standard; all models use it |
| asyncio | stdlib | Task management, cancellation | Only option for async task control in Python |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.Queue` | stdlib | Pass tokens from LLM task to SSE generator | When LLM task and SSE generator run as separate coroutines |
| `asyncio.Event` | stdlib | Signal stop/cancel across coroutines | Coordinating stop between HTTP endpoint and running stream |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.Task cancellation | asyncio.Event flag | Event flag is cleaner for graceful stop; Task.cancel() is needed for immediate abort of blocking LLM call |
| In-memory engine state | Redis session store | Redis adds infra complexity; single-process FastAPI is fine for v1 |
| Streaming tokens directly | Buffer full response then stream | Direct streaming is lower latency; buffering would allow pre-validation but defeats SSE purpose |

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── api/
│   └── cog_test.py          # Expand: add session CRUD + stream endpoint
├── services/
│   ├── cog_test_engine.py   # NEW: CogTestEngine class (core of this phase)
│   ├── cog_test_prompts.py  # EXISTS: ready to use
│   └── cog_test_parser.py   # EXISTS: ready to use
└── models/entities/
    └── user.py              # EXISTS: add CogTestSession/Turn/BlindSpot/Snapshot ORM classes
```

### Pattern 1: CogTestEngine as Stateful Service

The engine holds all mutable state for one active session. It is instantiated per-session and stored in a module-level dict keyed by `session_id`.

```python
# app/services/cog_test_engine.py
import asyncio
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TurnScheduler:
    round_number: int = 1
    max_rounds: int = 3
    # True = Guide's turn, False = Challenger's turn
    agent_is_guide: bool = True

    def current_agent(self) -> str:
        return "guide" if self.agent_is_guide else "challenger"

    def advance(self):
        """Called after each agent turn completes."""
        if not self.agent_is_guide:
            # Challenger just finished — round complete
            self.round_number += 1
        self.agent_is_guide = not self.agent_is_guide

    @property
    def round_complete(self) -> bool:
        """True immediately after Challenger finishes."""
        return self.agent_is_guide and self.round_number > 1

class CogTestEngine:
    def __init__(self, session_id: str, concept: str):
        self.session_id = session_id
        self.concept = concept
        self.scheduler = TurnScheduler()
        self.history: list[dict] = []          # full conversation history
        self._stop_event = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None

    async def stop(self):
        self._stop_event.set()
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
```

### Pattern 2: SSE Generator Delegates to Engine

The SSE endpoint creates an async generator that pulls events from the engine. The engine does the heavy lifting; the endpoint is thin.

```python
# app/api/cog_test.py
@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
    token: str,  # JWT via query param (EventSource cannot send headers)
    current_user=Depends(get_current_user_from_query),
    db: AsyncSession = Depends(get_db),
):
    engine = get_or_create_engine(session_id)

    async def event_generator():
        yield {"event": "session_start", "data": json.dumps({"session_id": session_id})}
        async for event in engine.run(db):
            yield event

    return EventSourceResponse(event_generator())
```

### Pattern 3: Token Accumulation for Post-Stream Analysis

`stream_generate()` yields tokens one at a time. The analysis block (`<analysis>...</analysis>`) arrives at the end of the full response. Accumulate all tokens into a buffer, then call `parse_agent_output()` after the stream ends.

```python
async def _run_agent_turn(self, db, system_prompt, temperature):
    buffer = []
    async for token in llm_service.stream_generate(
        messages=self.history,
        system_prompt=system_prompt,
        temperature=temperature,
    ):
        buffer.append(token)
        # Yield token event immediately — don't wait for full response
        yield {"event": "token", "data": token}

    full_response = "".join(buffer)
    parsed = parse_agent_output(full_response)
    # Now persist blind spots, update snapshot, etc.
    await self._persist_turn(db, parsed)
```

### Pattern 4: Socratic Contract Validation

After accumulating the full response, check `dialogue_text` for forbidden phrases before the turn is considered complete. If violated, retry the LLM call (up to 2 attempts). On second failure, log and proceed — don't break the session.

```python
FORBIDDEN_PHRASES = ["答案是", "正确答案", "其实是", "应该是", "正确的理解是"]

def _violates_socratic_contract(self, dialogue_text: str) -> bool:
    return any(phrase in dialogue_text for phrase in FORBIDDEN_PHRASES)
```

Note: validation happens on the complete `dialogue_text` after streaming. Tokens already sent to the client cannot be recalled. This is acceptable — the contract check is a quality gate for persistence and retry, not a real-time filter. If a violation is detected on retry 2, log it and persist anyway (the prompt design makes violations rare).

### Pattern 5: LLM Retry with Backoff (Claude's Discretion)

Recommended: exponential backoff with jitter, max 2 retries.

```python
import asyncio, random

async def _call_with_retry(self, call_fn, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return await call_fn()
        except Exception as exc:
            if attempt == max_retries:
                raise
            wait = (2 ** attempt) + random.uniform(0, 0.5)
            await asyncio.sleep(wait)
```

### Pattern 6: Session-Level Score Aggregation (Claude's Discretion)

Map `understanding_level` strings to floats: `low=0.33`, `medium=0.66`, `high=1.0`.

Per-round score = `(guide_score * 0.4) + (challenger_score * 0.6)`.

Final session score = simple average of all round scores. Store as a float 0.0–1.0 in `CogTestSnapshot.understanding_score` (the column is `String(10)` — store as `"0.72"` to match existing schema).

### Anti-Patterns to Avoid

- **Streaming tokens through a validation buffer before sending to client:** Defeats the purpose of SSE. Validate after the full response is accumulated; accept that already-sent tokens cannot be recalled.
- **Storing engine state in the FastAPI request scope:** The SSE connection is long-lived. Engine state must outlive the request — use a module-level registry dict.
- **Using `asyncio.sleep(0)` polling loops for stop detection:** Use `asyncio.Event` instead. Polling wastes CPU and adds latency.
- **Opening a new DB session per token:** Open one `AsyncSession` per agent turn, not per token. The session is cheap to hold open for the duration of a turn.
- **Calling `parse_agent_output()` on partial token buffers:** Only call it once, on the complete accumulated response after the stream ends.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE transport | Custom chunked HTTP | `sse-starlette EventSourceResponse` | Handles keep-alive, reconnect headers, client disconnect detection |
| Async task cancellation | Manual flag polling | `asyncio.Task.cancel()` + `CancelledError` | Python stdlib; propagates through `await` chains correctly |
| JSON parsing of agent output | Custom regex | `parse_agent_output()` from `cog_test_parser.py` | Already handles malformed JSON, missing blocks, invalid categories |
| LLM streaming | Direct HTTP chunked reads | `llm_service.stream_generate()` | Already handles OpenAI and Anthropic providers |

**Key insight:** The hard infrastructure work (SSE, LLM streaming, output parsing) is already done. This phase is about orchestration logic, not new infrastructure.

---

## Common Pitfalls

### Pitfall 1: Client Disconnect Not Detected

**What goes wrong:** Client closes the EventSource connection (tab close, network drop). The SSE generator keeps running, LLM calls continue, tokens are sent to nobody, DB writes accumulate.

**Why it happens:** FastAPI/Starlette does not automatically cancel the generator on disconnect. The generator only discovers the disconnect when it tries to `yield` and gets a `ConnectionResetError` or `BrokenPipeError`.

**How to avoid:** Wrap the generator body in a `try/except` that catches `asyncio.CancelledError` and connection errors. Call `engine.stop()` in the `finally` block. `sse-starlette` does propagate disconnect as a `CancelledError` to the generator — rely on this.

**Warning signs:** LLM API costs keep accumulating after frontend tests; DB has turns with no corresponding session activity.

### Pitfall 2: History Grows Without Bound

**What goes wrong:** Full conversation history is passed to every LLM call. After many turns, the context window fills up and the LLM call fails or truncates.

**Why it happens:** The decision is "no sliding window" — full history always. This is correct for v1 (3 rounds = ~6 agent turns + 6 user turns = manageable). But if "Continue" is used repeatedly, history can grow.

**How to avoid:** For v1 with 3 rounds + optional continue, this is not a real problem. Log a warning if `len(history)` exceeds 20 messages. Add a note in code for v2 to add sliding window.

**Warning signs:** LLM API returning context length errors.

### Pitfall 3: Analysis Block Arrives Mid-Stream

**What goes wrong:** The `<analysis>` block is part of the LLM response stream. If you call `parse_agent_output()` on a partial buffer (e.g., after a timeout), you get `parse_success=False` and lose blind spot data.

**Why it happens:** Impatience — trying to parse before the stream is fully consumed.

**How to avoid:** Always consume the entire `stream_generate()` generator before calling `parse_agent_output()`. The token events are yielded to the client in real time; parsing happens after the generator is exhausted.

### Pitfall 4: Race Condition on Stop + Persist

**What goes wrong:** `/stop` is called while an agent turn is mid-stream. The turn is cancelled before `_persist_turn()` runs. The session ends with no snapshot for the current partial round.

**Why it happens:** `asyncio.Task.cancel()` raises `CancelledError` at the next `await`, which may be inside the token loop before persistence.

**How to avoid:** Structure the engine so persistence happens in a `finally` block after the token loop. Even on cancellation, attempt to persist whatever was accumulated in the buffer. A partial turn with `parse_success=False` is better than no record.

```python
buffer = []
try:
    async for token in llm_service.stream_generate(...):
        buffer.append(token)
        yield {"event": "token", "data": token}
finally:
    # Runs even on CancelledError
    if buffer:
        full_response = "".join(buffer)
        parsed = parse_agent_output(full_response)
        await _persist_turn(db, parsed)
```

### Pitfall 5: One Active Session Enforcement

**What goes wrong:** User starts a new session while the previous one is still streaming. Two engines run simultaneously, both writing to DB, both consuming LLM quota.

**Why it happens:** The "one active session per user" rule requires checking and stopping the previous session before creating a new one. Easy to forget.

**How to avoid:** In the `POST /sessions` endpoint, query for any `active` session for the user and call `engine.stop()` on it before creating the new session. The engine registry (module-level dict) makes this lookup O(1).

---

## Code Examples

### SSE Event Shape (all events this phase must emit)

```python
# session_start — sent once when stream opens
{"event": "session_start", "data": '{"session_id": "...", "concept": "...", "max_rounds": 3}'}

# turn_start — sent before tokens for each agent turn
{"event": "turn_start", "data": '{"role": "guide", "round": 1}'}

# token — one per LLM token
{"event": "token", "data": "你觉得"}

# turn_complete — sent after all tokens for a turn
{"event": "turn_complete", "data": '{"role": "guide", "round": 1, "turn_index": 0}'}

# round_complete — sent after Challenger finishes each round
{"event": "round_complete", "data": '{"round": 1}'}

# session_complete — sent on normal end or stop-and-diagnose
{"event": "session_complete", "data": '{"status": "stopped", "rounds_completed": 2}'}

# error — LLM failure after retries exhausted
{"event": "error", "data": '{"message": "LLM call failed after 2 retries"}'}
```

### JWT Auth via Query Param (existing pattern)

```python
# EventSource cannot send Authorization header — use ?token= query param
from app.core.security import decode_access_token

async def get_current_user_from_query(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token)
    # ... same as get_current_user but reads from query param
```

### Engine Registry Pattern

```python
# app/services/cog_test_engine.py
_engines: dict[str, "CogTestEngine"] = {}

def get_engine(session_id: str) -> Optional["CogTestEngine"]:
    return _engines.get(session_id)

def register_engine(session_id: str, engine: "CogTestEngine"):
    _engines[session_id] = engine

def unregister_engine(session_id: str):
    _engines.pop(session_id, None)
```

### Understanding Score Calculation

```python
_LEVEL_TO_FLOAT = {"low": 0.33, "medium": 0.66, "high": 1.0}

def calculate_round_score(guide_level: str, challenger_level: str) -> float:
    g = _LEVEL_TO_FLOAT.get(guide_level, 0.33)
    c = _LEVEL_TO_FLOAT.get(challenger_level, 0.33)
    return round(g * 0.4 + c * 0.6, 2)

def aggregate_session_score(round_scores: list[float]) -> float:
    if not round_scores:
        return 0.0
    return round(sum(round_scores) / len(round_scores), 2)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| WebSockets for streaming | SSE (EventSourceResponse) | Simpler client, auto-reconnect, HTTP/2 compatible — already decided |
| Polling for LLM results | Async generators | Lower latency, no wasted requests |
| Separate analysis LLM call | Inline `<analysis>` block in agent response | One LLM call per turn instead of two; already implemented in prompts |

---

## Open Questions

1. **ORM models for CogTest entities not yet in `user.py`**
   - What we know: Migration `001` created the tables. ORM classes (`CogTestSession`, `CogTestTurn`, `CogTestBlindSpot`, `CogTestSnapshot`) are referenced in CONTEXT.md but not yet in `user.py`.
   - What's unclear: Were they added in Phase 1 Plan 02 or are they still missing?
   - Recommendation: Plan 01 of this phase should add ORM classes to `user.py` if not present, before any engine work.

2. **`get_current_user_from_query` for SSE auth**
   - What we know: JWT via query param is the established pattern (noted in STATE.md decisions).
   - What's unclear: Whether a `get_current_user_from_query` dependency already exists or needs to be created.
   - Recommendation: Check `app/api/deps.py` at plan time; create if missing.

3. **`cog_test_snapshots.understanding_score` column type**
   - What we know: Migration defines it as `String(10)`. The scoring logic produces a float.
   - What's unclear: Whether to store `"0.72"` (string) or change the column to `Float`.
   - Recommendation: Store as string `"0.72"` to match existing schema. Changing the column type requires a new migration and is out of scope for this phase.

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` — skipping this section.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `las_backend/app/api/cog_test.py` — existing SSE pattern
- Codebase: `las_backend/app/services/llm_service.py` — `stream_generate()` signature and behavior
- Codebase: `las_backend/app/services/cog_test_prompts.py` — agent prompts, temperatures, forbidden phrases
- Codebase: `las_backend/app/services/cog_test_parser.py` — `parse_agent_output()`, `AgentOutput` schema
- Codebase: `las_backend/alembic/versions/001_add_cog_test_tables.py` — DB schema
- `.planning/phases/02-backend-engine/02-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)
- Python asyncio docs: `asyncio.Task.cancel()` propagates `CancelledError` through `await` chains — standard behavior
- sse-starlette README: disconnect propagates as `CancelledError` to the generator — documented behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, patterns already proven
- Architecture: HIGH — derived directly from existing code patterns and locked decisions
- Pitfalls: HIGH — derived from async Python fundamentals and the specific constraints of this codebase

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable stack, no fast-moving dependencies)
