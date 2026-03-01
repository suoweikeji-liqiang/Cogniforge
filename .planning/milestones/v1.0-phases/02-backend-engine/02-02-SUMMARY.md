---
phase: 02-backend-engine
plan: "02"
subsystem: backend
tags: [engine, asyncio, sse, llm, scoring, persistence, auth]
dependency_graph:
  requires:
    - 02-01 (CogTestEngine skeleton, ORM classes, TurnScheduler)
  provides:
    - CogTestEngine.run() full async generator SSE loop
    - CogTestEngine._run_agent_turn() with dual-layer retry
    - CogTestEngine._persist_turn() DB persistence
    - CogTestEngine._save_snapshot() round/session snapshots
    - CogTestEngine.submit_user_turn() user input queue
    - get_current_user_from_query dependency (query-param JWT auth)
  affects:
    - las_backend/app/services/cog_test_engine.py
    - las_backend/app/api/deps.py
tech_stack:
  added: []
  patterns:
    - Async generator with try/finally for SSE lifecycle + stop handling
    - Two independent retry loops (LLM exception inner, Socratic contract outer)
    - asyncio.Queue for decoupled user-input delivery to run() loop
    - db.flush() before blind-spot inserts to get turn.id FK
    - Query-param JWT auth dependency for SSE (EventSource cannot send headers)
key_files:
  created: []
  modified:
    - las_backend/app/services/cog_test_engine.py
    - las_backend/app/api/deps.py
decisions:
  - "_run_agent_turn implemented as plain coroutine (not async generator) returning (AgentOutput, list[SSE_events], llm_failed) tuple — avoids Python async generator return value limitation"
  - "Socratic contract retry is outer loop in run(); LLM exception retry is inner loop inside _run_agent_turn() — strictly separate concerns"
  - "db.flush() called before CogTestBlindSpot inserts so turn.id FK is available without a full commit"
  - "get_current_user_from_query uses decode_access_token from app.core.security, not app.api.routes.auth — avoids circular import with get_current_user"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-03-01"
  tasks_completed: 2
  files_changed: 2
---

# Phase 2 Plan 02: CogTestEngine run() Loop + SSE Auth Summary

Full CogTestEngine.run() async generator loop with dual-layer retry (LLM exception + Socratic contract), DB persistence (turns, blind spots, snapshots), round scoring, and query-param JWT dependency for SSE endpoints.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Implement CogTestEngine.run() loop with full agent turn logic | cbd304d | las_backend/app/services/cog_test_engine.py |
| 2 | Add get_current_user_from_query to deps.py | 3a740e4 | las_backend/app/api/deps.py |

## What Was Built

### Task 1 — CogTestEngine.run() Full Loop (cog_test_engine.py)

**`run(db: AsyncSession) -> AsyncGenerator`**

Yields SSE event dicts in this sequence per session:
- `session_start` — session_id, concept, max_rounds
- Per turn: `turn_start` → `token`... → `turn_complete`
- Per round (after Challenger): `round_complete`
- Final: `session_complete` (status=completed|stopped)

Stop handling via try/finally: if session not completed normally, yields `session_complete` with `status=stopped` and saves final snapshot before calling `unregister_engine()`.

**`_run_agent_turn(db, role) -> (Optional[AgentOutput], list[dict], bool)`**

Plain coroutine (not async generator) that returns all token SSE events as a list plus the parsed output and an `llm_failed` flag. This avoids the Python limitation that async generators cannot `return` a value.

Layer 1 — LLM exception retry (inner loop, 3 attempts):
- Wraps `async for token in llm_service.stream_generate(...)` in try/except
- On exception: exponential backoff `(2**attempt) + random.uniform(0, 0.5)` seconds
- After 3 failures: returns error SSE event and `llm_failed=True`

Layer 2 — Socratic contract retry (outer loop, 3 attempts, in `run()`):
- Re-calls `_run_agent_turn()` if `_violates_socratic_contract(dialogue_text)` is True
- On exhaustion: logs warning and proceeds (does not break session)

**`_persist_turn(db, role, round_number, parsed, raw_text)`**

- Creates `CogTestTurn` row with turn_index, role, dialogue_text, analysis_json, understanding_level
- `db.flush()` to get `turn.id` before creating `CogTestBlindSpot` rows
- Appends agent dialogue to `self.history` as `{"role": "assistant", "content": ...}`
- Increments `_turn_index`
- `db.commit()` to persist all

**`_save_snapshot(db, round_number, round_scores, guide_level, challenger_level)`**

- Per-round: score = `calculate_round_score(guide_level, challenger_level)` (Guide 40%, Challenger 60%)
- Final (round_number=None): score = `aggregate_session_score(round_scores)`
- Queries DB for blind_spot_count
- Creates `CogTestSnapshot` with understanding_score as string, snapshot_json

**`submit_user_turn(text)` + `_user_input_queue`**

- `_user_input_queue: asyncio.Queue` initialized in `__init__`
- `submit_user_turn()` appends user text to `self.history` and puts it on the queue
- `run()` calls `await self._user_input_queue.get()` after each `turn_complete` to wait for user input before next agent turn

**Module-level scoring functions** (for backward-compat imports from plan spec):
- `calculate_round_score(guide_level, challenger_level) -> float`
- `aggregate_session_score(round_scores) -> float`

### Task 2 — get_current_user_from_query (deps.py)

New FastAPI dependency that reads JWT from `?token=` query parameter instead of the Authorization header. This is required because the browser's `EventSource` API cannot send custom headers, so SSE endpoints must authenticate via query param.

Implementation:
- `token: str = Query(...)` extracts JWT from URL
- `decode_access_token(token)` from `app.core.security` validates it
- DB lookup for user by `payload["sub"]`
- Raises `HTTP 401` on any validation failure
- `require_admin` dependency unchanged

## Deviations from Plan

### Design Choices (not bugs)

**1. _run_agent_turn as plain coroutine instead of async generator**

The plan noted: "Note: because `_run_agent_turn` yields token events AND returns a value, it must be an async generator." However, Python async generators cannot `return` a value (they raise `StopAsyncIteration` without a value). The plan acknowledged this and offered the alternative: "implement `_run_agent_turn` as a plain coroutine that accumulates tokens internally and yields them via a shared list."

Implemented as plain coroutine returning `(AgentOutput, list[SSE_events], llm_failed)`. The caller (`run()`) iterates the token_events list and re-yields them. This is clean and avoids synchronization complexity.

**2. _save_snapshot signature extended with guide_level/challenger_level parameters**

The plan spec described `_save_snapshot(db, round_number, round_scores)`. To correctly calculate per-round scores using `calculate_round_score(guide_level, challenger_level)`, the method needs the two understanding levels. Added as optional keyword arguments with sensible defaults (falls back to `aggregate_session_score` if levels not provided).

## Verification Results

```
# Task 1
calculate_round_score('high', 'medium') == round(1.0*0.4 + 0.66*0.6, 2)  # 0.796
aggregate_session_score([0.5, 0.8]) == 0.65
aggregate_session_score([]) == 0.0
TurnScheduler: guide -> challenger -> round_number=2, guide
run() is async generator function (inspect.isasyncgenfunction == True)
# Output: Engine logic OK

# Task 2
from app.api.deps import get_current_user_from_query, require_admin
# Output: deps OK
```

## Self-Check: PASSED

- `las_backend/app/services/cog_test_engine.py` — FOUND
- `las_backend/app/api/deps.py` — FOUND
- Commit cbd304d — FOUND
- Commit 3a740e4 — FOUND
