---
phase: 04-report-and-integration
plan: "03"
subsystem: srs-integration
tags: [srs, cog-test, sse, stream, elevation, gap-closure]
dependency_graph:
  requires: ["04-02"]
  provides: ["stream-completion-srs-elevation"]
  affects: ["las_backend/app/api/cog_test.py"]
tech_stack:
  added: []
  patterns: ["async generator wrapper", "try/finally cleanup in SSE generator"]
key_files:
  created: []
  modified:
    - las_backend/app/api/cog_test.py
decisions:
  - "_stream_with_elevation uses try/finally so cleanup runs even on client disconnect"
  - "except Exception: pass in finally block is intentional — stop endpoint remains guaranteed fallback"
  - "Stream endpoint wiring deferred to Phase 2 Plan 02-03 (endpoint not yet created)"
metrics:
  duration: "~2 minutes"
  completed_date: "2026-03-01"
  tasks_completed: 1
  files_modified: 1
---

# Phase 4 Plan 03: SSE Stream Elevation Gap Closure Summary

**One-liner:** Added `_stream_with_elevation` async generator wrapper that calls `_elevate_srs_priority_if_blind_spots` inside the EventSourceResponse lifecycle after engine.run() exhausts for naturally completed sessions.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add post-stream SRS elevation wrapper to SSE stream endpoint | 000dea9 | las_backend/app/api/cog_test.py |

## What Was Built

### Backend (`las_backend/app/api/cog_test.py`)

Added import of `CogTestEngine`, `get_engine`, `unregister_engine` from `cog_test_engine`.

Added `_stream_with_elevation(engine, session_id, db)` async generator:
1. Yields all events from `engine.run(db)` (pass-through)
2. In `finally` block: fetches session, checks `status == "completed"`, calls `_elevate_srs_priority_if_blind_spots` and commits
3. Calls `unregister_engine(session_id)` unconditionally in `finally`
4. Inner `except Exception: pass` keeps the stream path best-effort — stop endpoint remains the guaranteed fallback

The wrapper is ready to be wired into the stream endpoint when Phase 2 Plan 02-03 creates `GET /sessions/{id}/stream`. At that point, replace `EventSourceResponse(engine.run(db))` with `EventSourceResponse(_stream_with_elevation(engine, session_id, db))`.

## Decisions Made

1. **try/finally pattern** — Ensures `unregister_engine` and the elevation check run even when the client disconnects mid-stream (generator cleanup fires on cancellation).

2. **best-effort inner exception handling** — The `except Exception: pass` inside `finally` is intentional. If the DB is unavailable post-stream, the stop endpoint (which runs synchronously before the response) remains the guaranteed elevation trigger.

3. **Deferred wiring** — Phase 2 Plan 02-03 has not yet run, so the stream endpoint does not exist. The wrapper is added now with a comment linking to 02-03 so the wiring is a one-line change when that plan executes.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- las_backend/app/api/cog_test.py: FOUND
- .planning/phases/04-report-and-integration/04-03-SUMMARY.md: FOUND
- Commit 000dea9: FOUND
