---
phase: 03-frontend
plan: "02"
subsystem: frontend-views
tags: [vue3, streaming, sse, pinia, cogtest, dialogue-ui]
dependency_graph:
  requires: [03-01]
  provides: [CogTestSessionView, ModelCardDetailView-launch]
  affects: [03-03]
tech_stack:
  added: []
  patterns: [streaming-message-list, role-based-styling, auto-scroll-watch, store-driven-ui]
key_files:
  created:
    - las_frontend/src/views/CogTestSessionView.vue
  modified:
    - las_frontend/src/views/ModelCardDetailView.vue
decisions:
  - "CogTestSessionView redirects to /cog-test on mount if status is idle and no sessionId — prevents blank session view on direct navigation"
  - "watch on store.messages with deep:true drives auto-scroll via nextTick to catch streaming token appends"
  - "Stop and Diagnose button only visible during streaming/waiting — hidden when completed or stopped"
metrics:
  duration: "10 minutes"
  completed_date: "2026-03-01"
  tasks_completed: 2
  files_changed: 2
requirements: [SESS-01]
---

# Phase 03 Plan 02: Streaming Dialogue UI Summary

One-liner: CogTestSessionView with real-time streaming message list, role-based visual distinction (guide=green, challenger=amber), auto-scroll, guarded input, and a Start Cognitive Test launch button wired into ModelCardDetailView.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create CogTestSessionView streaming dialogue UI | 4a9a918 | las_frontend/src/views/CogTestSessionView.vue |
| 2 | Add Start Cognitive Test button to ModelCardDetailView | 0a78b7e | las_frontend/src/views/ModelCardDetailView.vue |

## What Was Built

### CogTestSessionView.vue

Full streaming dialogue UI consuming `useCogTestStore`:

- Session header: back button, concept title (h1), round badge (currentRound/maxRounds)
- Status bar: connecting spinner, error display, session-complete confirmation — shown conditionally
- Messages container: `v-for` over `store.messages`, each message classed by role (`guide`, `challenger`, `user`) with role label and content bubble; streaming messages show blinking cursor
- Visual distinction: guide messages have green (`--primary`) left border and label; challenger messages have amber (`#f59e0b`) left border and label; user messages have dark background, no left border
- Auto-scroll: `watch(store.messages, scrollToBottom, { deep: true })` + `nextTick` scrolls container to bottom on every token append
- Input area: Stop and Diagnose button (visible during streaming/waiting), input form with text field and Send button both disabled when `status !== 'waiting'`
- Mount guard: redirects to `/cog-test` if `status === 'idle'` and no `sessionId` — prevents blank view on direct URL access

### ModelCardDetailView.vue

Minimal additive changes:

- Added `useRouter` to vue-router import
- Added `useCogTestStore` import
- Added `cogTestStore` and `router` instances
- Added `startCogTest()` handler: calls `cogTestStore.startSession(card.value.title)` then navigates to `/cog-test/session`
- Added `.cog-test-action` div with primary button after `.card-meta`, inside `.card-info`
- Added `.cog-test-action` scoped CSS with top border separator

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `las_frontend/src/views/CogTestSessionView.vue` — FOUND
- `las_frontend/src/views/ModelCardDetailView.vue` — FOUND (contains startCogTest)
- Commit 4a9a918 — FOUND
- Commit 0a78b7e — FOUND
