---
phase: 03-frontend
plan: "03"
subsystem: frontend
tags: [vue3, pinia, i18n, cog-test, history-list]
dependency_graph:
  requires: [03-01]
  provides: [CogTestListView]
  affects: [router/cog-test]
tech_stack:
  added: []
  patterns: [pinia-store-view, loading-empty-list, status-badge]
key_files:
  created:
    - las_frontend/src/views/CogTestListView.vue
  modified: []
decisions:
  - "Score column rendered only when s.score != null — v1 backend omits score field, forward-compatible"
metrics:
  duration: "2 minutes"
  completed_date: "2026-02-28"
---

# Phase 3 Plan 03: CogTestListView Session History Summary

**One-liner:** Vue3 session history list view using useCogTestStore with loading/empty/list states and forward-compatible score-or-status-badge display.

## What Was Built

`CogTestListView.vue` — the landing page for `/cog-test`. Calls `store.fetchSessions()` on mount, shows a loading state while fetching, an empty-state message when the list is empty, and a card-per-session list otherwise. Each card shows concept name, formatted date, and either a score percentage (when `s.score != null`) or a colored status badge (active/completed/stopped).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create CogTestListView.vue history list | d2dd6a1 | las_frontend/src/views/CogTestListView.vue |

## Verification

- `store.fetchSessions()` called in `onMounted` try/finally block
- `loading` ref set to false in finally — guarantees state transition even on error
- `v-if="loading"` / `v-else-if="store.sessions.length === 0"` / `v-else` covers all three states
- `s.score != null` guard renders score when present, falls back to status badge (v1 backend compatibility)
- Status badge classes `.active`, `.completed`, `.stopped` styled with CSS variables
- TypeScript type check: pre-existing Capacitor module errors only (out of scope), no errors in new file

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- FOUND: las_frontend/src/views/CogTestListView.vue
- FOUND: commit d2dd6a1
