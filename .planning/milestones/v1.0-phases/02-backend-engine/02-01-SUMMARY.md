---
phase: 02-backend-engine
plan: "01"
subsystem: backend
tags: [orm, sqlalchemy, engine, scheduler, asyncio]
dependency_graph:
  requires: []
  provides:
    - CogTestSession ORM class
    - CogTestTurn ORM class
    - CogTestBlindSpot ORM class
    - CogTestSnapshot ORM class
    - CogTestEngine service class
    - TurnScheduler
    - engine registry (get_engine, register_engine, unregister_engine)
  affects:
    - las_backend/app/models/entities/user.py
    - las_backend/app/services/cog_test_engine.py
tech_stack:
  added: []
  patterns:
    - SQLAlchemy ORM with UUID string PKs and back_populates relationships
    - asyncio.Event + asyncio.Task for cancellable async engine lifecycle
    - Module-level dict registry for in-process engine lookup
key_files:
  created:
    - las_backend/app/services/cog_test_engine.py
  modified:
    - las_backend/app/models/entities/user.py
decisions:
  - "Replaced placeholder CogTest ORM classes (wrong schema) with plan-spec versions — concept, round_number, understanding_level, max_rounds columns added"
  - "analysis_json stored as Text (not JSON column) to match plan spec — allows raw string storage before parsing"
  - "TurnScheduler round increments after Challenger finishes (not after Guide) — Challenger is the closing agent of each round"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-02-28"
  tasks_completed: 2
  files_changed: 2
---

# Phase 2 Plan 01: ORM Models + CogTestEngine Skeleton Summary

SQLAlchemy ORM classes for all four cog-test tables plus CogTestEngine with TurnScheduler and engine registry — the foundational layer all downstream plans depend on.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add CogTest ORM classes to user.py | 1c7d5fa | las_backend/app/models/entities/user.py |
| 2 | Implement CogTestEngine service | 6a20f29 | las_backend/app/services/cog_test_engine.py |

## What Was Built

### Task 1 — ORM Classes (user.py)

Replaced the existing placeholder CogTest models with the plan-spec schema:

- `CogTestSession`: `concept`, `max_rounds`, corrected `agent_mode` default (`guide_challenger`), proper `back_populates` on all three child relationships
- `CogTestTurn`: added `round_number` (Int, not null), `understanding_level` (String 10), changed `analysis_json` from JSON column to Text
- `CogTestBlindSpot`: replaced `blind_spot_type`/`evidence` with `category`/`description`; fixed `turn` relationship to use `back_populates` instead of `backref`
- `CogTestSnapshot`: added `round_number` (nullable — None = final snapshot), `blind_spot_count`, `snapshot_json` (Text); removed incorrect columns

### Task 2 — CogTestEngine (cog_test_engine.py)

New file implementing:

- `TurnScheduler`: guide-first alternation, `advance()` increments `round_number` when Challenger finishes, `is_session_complete` property
- `CogTestEngine.__init__`: session_id, concept, scheduler, history list, `_stop_event` (asyncio.Event), `_current_task`, `_turn_index`
- `stop()`: sets stop event, cancels in-flight task, awaits catching CancelledError
- `_violates_socratic_contract()`: checks 7 forbidden phrases (Chinese + English)
- `calculate_round_score()`: Guide 40% + Challenger 60% weighted blend using `_LEVEL_TO_FLOAT` map
- `aggregate_session_score()`: simple average, 0.0 for empty list
- `run()` stub: raises NotImplementedError (implemented in 02-02)
- Registry: `_engines` dict + `get_engine`, `register_engine`, `unregister_engine`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced incorrect pre-existing ORM schema**
- Found during: Task 1
- Issue: user.py already contained CogTest ORM classes from an earlier draft with wrong columns (`blind_spot_type`, `evidence`, missing `concept`, `round_number`, `understanding_level`, `max_rounds`). The `CogTestBlindSpot.turn` used `backref` instead of `back_populates`, which would conflict with the plan-spec `CogTestTurn.blind_spots` relationship.
- Fix: Replaced all four classes with plan-spec versions. No other existing classes were touched.
- Files modified: las_backend/app/models/entities/user.py
- Commit: 1c7d5fa

## Verification Results

```
# Task 1
from app.models.entities.user import CogTestSession, CogTestTurn, CogTestBlindSpot, CogTestSnapshot
# Output: ORM OK

# Task 2
e = CogTestEngine('s1', 'recursion')
e.scheduler.current_agent()   # → 'guide'
e.scheduler.advance()
e.scheduler.current_agent()   # → 'challenger'
e.scheduler.advance()
e.scheduler.round_number      # → 2
# Output: Engine OK
```

## Self-Check: PASSED

- `las_backend/app/models/entities/user.py` — FOUND
- `las_backend/app/services/cog_test_engine.py` — FOUND
- Commit 1c7d5fa — FOUND
- Commit 6a20f29 — FOUND
