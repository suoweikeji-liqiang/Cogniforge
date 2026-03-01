---
phase: 02-backend-engine
plan: "03"
subsystem: api
tags: [fastapi, sse, asyncio, session, crud, auth]

requires:
  - phase: 02-02
    provides: CogTestEngine.run() async generator, get_current_user_from_query dep, engine registry (get/register/unregister_engine)

provides:
  - POST /cog-test/sessions — creates session, stops any existing active session, registers engine
  - GET /cog-test/sessions — lists all sessions for current user ordered by created_at desc
  - GET /cog-test/sessions/{id}/stream — SSE stream via EventSourceResponse(_stream_with_elevation)
  - POST /cog-test/sessions/{id}/turns — submits user reply via engine.submit_user_turn
  - POST /cog-test/sessions/{id}/stop — stops engine, updates DB status, elevates SRS on blind spots

affects:
  - las_frontend (Phase 3 — consumes all 5 endpoints)
  - Phase 4 report endpoint (same file, uses same session ORM)

tech-stack:
  added: []
  patterns:
    - Thin router pattern — all business logic in CogTestEngine service layer
    - Two separate db dependencies in stream endpoint — auth dep has its own internal session, engine.run() gets an explicit separate one via Depends(get_db)
    - EventSourceResponse wrapping async generator (_stream_with_elevation) for SSE lifecycle with SRS elevation
    - Engine registry (get/register/unregister_engine) decouples HTTP surface from async engine lifecycle

key-files:
  created: []
  modified:
    - las_backend/app/api/cog_test.py

key-decisions:
  - "stream_session declares two independent db parameters: current_user gets its own via get_current_user_from_query's internal Depends(get_db), engine.run() gets an explicit separate db: AsyncSession = Depends(get_db) — prevents session sharing across async boundaries"
  - "stop endpoint does not 400 on non-active sessions — calls engine.stop() if engine found, only updates DB status if session was active, always returns 200 — idempotent design per plan spec"
  - "create_session stops any existing active session before creating new one — query by user_id+status=active, call engine.stop() if engine registered, flip status to stopped, then create new session and register new engine"

patterns-established:
  - "Thin router: router functions only validate ownership and delegate to engine or ORM — no business logic"
  - "Engine registration lifecycle: create_session registers engine, _stream_with_elevation unregisters on generator exit"

requirements-completed: [SESS-02, SESS-04]

duration: 6min
completed: 2026-03-01
---

# Phase 2 Plan 03: Cog Test HTTP Surface Summary

**Full session CRUD + SSE stream endpoint for CogTestEngine, exposing 5 thin FastAPI routes that delegate to the service layer**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-01T13:27:39Z
- **Completed:** 2026-03-01T13:33:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `GET /cog-test/sessions/{id}/stream` with `EventSourceResponse(_stream_with_elevation)` and SSE query-param auth
- Added `POST /cog-test/sessions/{id}/turns` that calls `engine.submit_user_turn(text)` to unblock the run() loop
- Updated `POST /cog-test/sessions` to stop any existing active session and register the new engine via `register_engine`
- Updated `POST /cog-test/sessions/{id}/stop` to call `engine.stop()` and handle both active and already-stopped sessions gracefully
- Added `SubmitTurnBody` Pydantic model for the turns endpoint request body

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace cog_test.py with full session endpoints** - `b175b46` (feat)

## Files Created/Modified
- `las_backend/app/api/cog_test.py` - Added stream and turns endpoints; updated create_session and stop_session; imported register_engine and get_current_user_from_query

## Decisions Made
- Stream endpoint signature: `current_user: User = Depends(get_current_user_from_query)` and `db: AsyncSession = Depends(get_db)` as two separate parameters. The auth dependency uses its own internal DB session; the engine gets the explicit `db` to avoid session reuse across async boundaries.
- Stop endpoint is idempotent: does not raise 400 on already-stopped sessions. Calls `engine.stop()` if engine found; only updates DB status if session was active. Returns `{"status": "stopped"}` in all cases.
- Create session stops any existing active session first (query user_id+status=active), calls engine.stop() if registered, flips status to "stopped", then creates the new session and registers a new CogTestEngine.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] import register_engine was absent**
- **Found during:** Task 1 (reviewing existing cog_test.py imports)
- **Issue:** The existing file imported only `get_engine` and `unregister_engine` from `cog_test_engine`, but `create_session` needed to call `register_engine` after creating each session. Without it the engine would never be registered and the stream endpoint would always return 404.
- **Fix:** Added `register_engine` to the import from `app.services.cog_test_engine`
- **Files modified:** las_backend/app/api/cog_test.py
- **Verification:** Router imports cleanly; `register_engine` callable verified
- **Committed in:** b175b46 (Task 1 commit)

**2. [Rule 2 - Missing Critical] get_current_user_from_query not imported**
- **Found during:** Task 1 (adding stream endpoint)
- **Issue:** `get_current_user_from_query` from `app.api.deps` was not imported in the existing file, making the SSE auth dependency unusable
- **Fix:** Added `from app.api.deps import get_current_user_from_query`
- **Files modified:** las_backend/app/api/cog_test.py
- **Verification:** stream_session endpoint function inspected — current_user parameter resolves to get_current_user_from_query
- **Committed in:** b175b46 (Task 1 commit)

**3. [Rule 1 - Bug] create_session missing engine registration**
- **Found during:** Task 1 (reviewing existing create_session logic)
- **Issue:** The original create_session created the DB session row but never instantiated `CogTestEngine` or called `register_engine`. Any subsequent call to `GET /sessions/{id}/stream` would find no engine in the registry and return 404.
- **Fix:** Added `CogTestEngine(session_id, concept, max_rounds)` instantiation and `register_engine(session.id, engine)` call after DB commit
- **Files modified:** las_backend/app/api/cog_test.py
- **Verification:** Route list and logic inspected; engine registered on create
- **Committed in:** b175b46 (Task 1 commit)

**4. [Rule 1 - Bug] create_session missing active-session stop logic**
- **Found during:** Task 1 (reviewing plan must_haves truths)
- **Issue:** The original create_session did not query for or stop any existing active session for the user — violating the plan's first must_have truth
- **Fix:** Added DB query for active sessions by user_id, engine.stop() call if engine exists, and status update to "stopped" before creating the new session
- **Files modified:** las_backend/app/api/cog_test.py
- **Verification:** Logic reviewed inline
- **Committed in:** b175b46 (Task 1 commit)

---

**Total deviations:** 4 auto-fixed (2 missing critical imports, 2 bugs in existing create_session)
**Impact on plan:** All auto-fixes required for correctness. The plan was partially implemented from prior sessions — missing pieces were the stream/turns endpoints and correct create_session logic.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 5 HTTP endpoints are in place and the router imports cleanly
- The SSE stream, user turns, and stop endpoints all correctly delegate to CogTestEngine
- Phase 3 (Frontend) can now build against these endpoints
- Any further changes to Phase 4 (report endpoint already present in the same file)

---
*Phase: 02-backend-engine*
*Completed: 2026-03-01*
