---
phase: 04-report-and-integration
plan: "02"
subsystem: srs-integration
tags: [srs, cog-test, blind-spots, priority-elevation]
dependency_graph:
  requires: ["04-01"]
  provides: ["srs-elevation-on-blind-spots", "session-model-card-link"]
  affects: ["las_backend/app/api/cog_test.py", "las_frontend/src/stores/cogTest.ts"]
tech_stack:
  added: []
  patterns: ["SM-2 quality=0 reset", "nullable FK passthrough", "transaction-owned helper"]
key_files:
  created: []
  modified:
    - las_backend/app/api/cog_test.py
    - las_frontend/src/stores/cogTest.ts
    - las_frontend/src/views/ModelCardDetailView.vue
decisions:
  - "Stop endpoint is the guaranteed SRS elevation trigger point (SSE stream endpoint not used — EventSourceResponse lifecycle makes post-stream DB access unreliable)"
  - "Auto-create ReviewSchedule with quality=0 if none exists — ensures first blind-spot session always elevates priority"
  - "model_card_id sent as null (not omitted) for backward-compatible sessions without card link"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-03-01"
  tasks_completed: 2
  files_modified: 3
---

# Phase 4 Plan 02: SRS Priority Elevation on Blind Spots Summary

**One-liner:** Auto-elevate model card SRS priority (quality=0, interval=1 day) when a cog test session ends with blind spots, using a transaction-owned helper wired into the stop endpoint.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | SRS elevation helper + backend wiring | 034361f | las_backend/app/api/cog_test.py |
| 2 | Frontend model_card_id passthrough | 5059c3c | las_frontend/src/stores/cogTest.ts, ModelCardDetailView.vue |

## What Was Built

### Backend (`las_backend/app/api/cog_test.py`)

Added `_elevate_srs_priority_if_blind_spots(session, db)` — an async helper that:
1. Checks for at least one `CogTestBlindSpot` for the session (returns early if none)
2. Checks `session.model_card_id` is set (returns early if None — graceful degradation)
3. Looks up existing `ReviewSchedule` for `(user_id, model_card_id)`
4. Auto-creates a schedule via `srs_service.schedule_card()` if none exists
5. Applies `srs_service.process_review(schedule, quality=0)` — resets interval to 1 day
6. Does NOT commit — caller owns the transaction

Also added:
- `StartSessionBody` Pydantic model with `model_card_id: Optional[str] = None`
- `POST /cog-test/sessions` — creates session, persists `model_card_id`
- `POST /cog-test/sessions/{id}/stop` — sets status=stopped, calls helper, commits
- `GET /cog-test/sessions` — list sessions for current user

### Frontend (`las_frontend/src/stores/cogTest.ts`)

Updated `startSession(conceptName: string, modelCardId?: string)`:
- Passes `model_card_id: modelCardId || null` in POST body
- Backward-compatible: existing callers without `modelCardId` send `null`

Updated `ModelCardDetailView.vue`:
- `startCogTest` now calls `cogTestStore.startSession(card.value.title, card.value.id)`
- Card ID is available at call site — full link established

## Decisions Made

1. **Stop endpoint as elevation trigger** — The SSE stream endpoint uses `EventSourceResponse` which makes reliable post-stream DB access complex. The stop endpoint is the guaranteed trigger for both manual stops and (via future integration) session completion.

2. **Auto-create ReviewSchedule** — If no schedule exists when blind spots are found, one is created with `quality=0` applied immediately. This ensures the first test session always elevates priority rather than silently skipping.

3. **null vs omit for model_card_id** — Frontend sends `null` explicitly rather than omitting the field, keeping the API contract explicit and the backend Pydantic model simple.

## Deviations from Plan

### Auto-added Missing Functionality

**[Rule 2 - Missing] Added session creation and list endpoints**
- Found during: Task 1
- Issue: `cog_test.py` had no `POST /sessions` or `GET /sessions` endpoints — the frontend store calls both, and the stop endpoint references sessions that must be created somewhere
- Fix: Added `POST /cog-test/sessions`, `POST /cog-test/sessions/{id}/stop`, and `GET /cog-test/sessions` endpoints
- Files modified: `las_backend/app/api/cog_test.py`
- Commit: 034361f

**[Rule 3 - Blocking] SSE stream elevation skipped**
- Found during: Task 1 Step 4
- Issue: `CogTestEngine.run()` is still a stub (`raise NotImplementedError`) — wiring elevation into the stream completion path would require the engine to be fully implemented
- Decision: Stop endpoint is the guaranteed trigger point per plan's own alternative guidance. Documented in decisions.

## Self-Check: PASSED

- las_backend/app/api/cog_test.py: FOUND
- las_frontend/src/stores/cogTest.ts: FOUND
- .planning/phases/04-report-and-integration/04-02-SUMMARY.md: FOUND
- Commit 034361f: FOUND
- Commit 5059c3c: FOUND
