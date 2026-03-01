---
phase: 03-frontend
plan: "01"
subsystem: frontend-store
tags: [pinia, sse, vue-router, i18n, cogtest]
dependency_graph:
  requires: [02-03]
  provides: [cogTest-store, cog-test-routes, cogTest-i18n]
  affects: [03-02, 03-03]
tech_stack:
  added: []
  patterns: [pinia-composition-api, sse-named-events, capacitor-aware-url]
key_files:
  created:
    - las_frontend/src/stores/cogTest.ts
  modified:
    - las_frontend/src/router/index.ts
    - las_frontend/src/App.vue
    - las_frontend/src/locales/en.json
    - las_frontend/src/locales/zh.json
decisions:
  - "EventSource uses addEventListener for named events (not onmessage) — backend sends named SSE events"
  - "eventSource variable is module-level non-reactive to avoid Vue reactivity overhead on DOM object"
  - "getSSEBaseUrl() mirrors api/index.ts Capacitor pattern for consistent native/web URL resolution"
metrics:
  duration: "15 minutes"
  completed_date: "2026-03-01"
  tasks_completed: 2
  files_changed: 5
requirements: [SESS-06]
---

# Phase 03 Plan 01: Cog-Test Store + Routing + i18n Summary

One-liner: Pinia cogTest store with full SSE named-event lifecycle, two auth-guarded routes, nav link, and bilingual i18n keys wiring the frontend foundation for Plans 02 and 03.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create cogTest Pinia store with SSE lifecycle | c0db2d7 | las_frontend/src/stores/cogTest.ts |
| 2 | Add routes, nav link, and i18n keys | 691a08b | router/index.ts, App.vue, en.json, zh.json |

## What Was Built

### cogTest.ts Store

Composition API Pinia store (`useCogTestStore`) owning all cognitive test session state:

- State refs: `sessionId`, `concept`, `status` (SessionStatus union type), `messages` (Message[]), `currentRound`, `maxRounds`, `error`, `sessions` (SessionSummary[])
- `startSession(conceptName)`: POSTs to `/cog-test/sessions`, sets state, calls `_openStream()`
- `_openStream()`: Creates `EventSource` with JWT token in query param; registers `addEventListener` for all 7 named SSE events
- SSE event handling: `session_start` sets maxRounds, `turn_start` pushes new streaming message, `token` appends to last message content, `turn_complete` marks streaming=false, `round_complete` updates round, `session_complete` closes stream, `error` sets error state and closes
- `submitUserTurn(text)`: pushes user message, POSTs turn
- `stopSession()`: POSTs stop, closes EventSource
- `fetchSessions()`: GETs history list
- `resetSession()`: closes stream, resets all refs to initial values

### Router

Two new routes added after `/notes`, before `/server-config`:
- `/cog-test` → `CogTestListView.vue` (name: `cog-test-list`, requiresAuth)
- `/cog-test/session` → `CogTestSessionView.vue` (name: `cog-test-session`, requiresAuth)

### App.vue Nav

`<router-link to="/cog-test">{{ t('nav.cogTest') }}</router-link>` added after `/reviews` link.

### i18n

Both `en.json` and `zh.json` updated with:
- `nav.cogTest` key
- Top-level `cogTest` section with 15 keys: startTest, stopAndDiagnose, send, guide, challenger, you, sessionComplete, history, concept, date, status, noSessions, round, connecting, inputPlaceholder, score

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `las_frontend/src/stores/cogTest.ts` — FOUND
- `las_frontend/src/router/index.ts` — FOUND (contains cog-test)
- `las_frontend/src/App.vue` — FOUND (contains cogTest)
- `las_frontend/src/locales/en.json` — FOUND (nav.cogTest + cogTest.* verified)
- `las_frontend/src/locales/zh.json` — FOUND (nav.cogTest + cogTest.* verified)
- Commit c0db2d7 — FOUND
- Commit 691a08b — FOUND
