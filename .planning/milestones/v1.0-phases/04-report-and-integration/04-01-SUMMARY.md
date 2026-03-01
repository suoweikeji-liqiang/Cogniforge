---
phase: 04-report-and-integration
plan: "01"
subsystem: report-export
tags: [report, markdown, export, orm, frontend]
dependency_graph:
  requires: []
  provides: [GET /cog-test/sessions/{id}/report, CogTestSession.model_card_id]
  affects: [CogTestListView, CogTestSessionView, cogTest store]
tech_stack:
  added: []
  patterns: [Response with Content-Disposition, Blob URL download, SQLAlchemy async select]
key_files:
  created: []
  modified:
    - las_backend/app/models/entities/user.py
    - las_backend/app/api/cog_test.py
    - las_frontend/src/stores/cogTest.ts
    - las_frontend/src/views/CogTestListView.vue
    - las_frontend/src/views/CogTestSessionView.vue
    - las_frontend/src/locales/en.json
    - las_frontend/src/locales/zh.json
decisions:
  - "Report endpoint uses in-memory Response(content=md_string) not FileResponse — no disk write needed"
  - "Filename sanitized with re.sub([^\\w\\-]) to handle non-ASCII concept names in Content-Disposition header"
  - "Export button shown for both completed and stopped sessions (not just completed)"
  - "Import path fixed: get_current_user from app.api.routes.auth, get_db from app.core.database"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-03-01"
  tasks_completed: 2
  files_changed: 7
---

# Phase 4 Plan 01: Diagnostic Report Export Summary

**One-liner:** Markdown report export via GET /cog-test/sessions/{id}/report + browser Blob download buttons in list and session views, with model_card_id ORM fix as prerequisite for Plan 04-02.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | ORM fix (model_card_id) + report endpoint | 47f727b |
| 2 | Frontend export buttons + i18n | 777e054 |

## What Was Built

**Backend (Task 1):**
- Added `model_card_id = Column(String(36), ForeignKey("model_cards.id"), nullable=True)` to `CogTestSession` ORM — column already existed in DB migration 001 but was missing from the ORM class
- Added `model_card = relationship("ModelCard", backref="cog_test_sessions")` relationship
- Added `GET /cog-test/sessions/{id}/report` endpoint that queries `CogTestBlindSpot` and `CogTestSnapshot` rows, assembles Markdown, returns `Response` with `Content-Disposition: attachment`
- Added `_build_report_markdown()` helper producing four sections: header, Blind Spots, Score Trajectory, Improvement Suggestions
- Active sessions return HTTP 400; wrong user returns 404

**Frontend (Task 2):**
- Added `exportReport(sid, conceptName)` to `cogTest` store — fetches with `responseType: 'blob'`, creates Blob URL, clicks hidden anchor, revokes URL
- Added Export Report button to `CogTestListView.vue` per session row (visible when `status === 'completed' || 'stopped'`)
- Added Export Report button to `CogTestSessionView.vue` status bar (visible when `status === 'completed' || 'stopped'`)
- Added `cogTest.exportReport` i18n key to `en.json` ("Export Report") and `zh.json` ("导出报告")

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wrong auth/db import paths in cog_test.py**
- **Found during:** Task 1 verification
- **Issue:** Plan spec used `from app.core.auth import get_current_user` and `from app.api.deps import get_db` — neither path exists in this codebase
- **Fix:** Corrected to `from app.api.routes.auth import get_current_user` and `from app.core.database import get_db` (matching pattern in `las_backend/app/api/routes/srs.py`)
- **Files modified:** `las_backend/app/api/cog_test.py`
- **Commit:** 47f727b

**2. [Rule 2 - Missing functionality] Export button also shown for stopped sessions in SessionView**
- **Found during:** Task 2 implementation
- **Issue:** Plan spec showed `v-if="store.status === 'completed'"` for SessionView button, but stopped sessions also have a complete diagnostic and should be exportable
- **Fix:** Changed condition to `store.status === 'completed' || store.status === 'stopped'` — consistent with ListVew behavior and the plan's own success criteria which lists both statuses
- **Files modified:** `las_frontend/src/views/CogTestSessionView.vue`
- **Commit:** 777e054

## Self-Check: PASSED

- `las_backend/app/api/cog_test.py` — FOUND
- `las_backend/app/models/entities/user.py` — FOUND (model_card_id attribute confirmed)
- `las_frontend/src/stores/cogTest.ts` — FOUND (exportReport exported)
- `las_frontend/src/views/CogTestListView.vue` — FOUND (exportReport button)
- `las_frontend/src/views/CogTestSessionView.vue` — FOUND (exportReport button)
- `las_frontend/src/locales/en.json` — FOUND (exportReport key)
- `las_frontend/src/locales/zh.json` — FOUND (exportReport key)
- Commit 47f727b — FOUND
- Commit 777e054 — FOUND
