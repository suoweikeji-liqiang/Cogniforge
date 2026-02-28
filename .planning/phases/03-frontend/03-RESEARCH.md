# Phase 3: Frontend - Research

**Researched:** 2026-02-28
**Domain:** Vue 3 SSE streaming UI, Pinia state management, real-time chat interface, Vue Router navigation
**Confidence:** HIGH (codebase is the primary source; all patterns are already established in the project)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SESS-01 | User can launch a cog test session from the model card detail page, concept auto-loaded | Add "Start Cognitive Test" button to `ModelCardDetailView.vue`; POST `/cog-test/sessions` with `concept=card.title`; navigate to session view |
| SESS-05 | Dialogue records persisted to DB; user can view history session list | `GET /cog-test/sessions` returns all sessions; render in `CogTestListView.vue` with concept, date, status |
| SESS-06 | "Cognitive Tests" nav entry lists all past sessions with concept name, date, final score | Add nav link in `App.vue`; route `/cog-test` → `CogTestListView.vue`; add i18n keys to both locale files |
</phase_requirements>

---

## Summary

Phase 3 is a pure frontend phase. The backend API surface is fully defined by Phase 2: five endpoints (`POST /sessions`, `GET /sessions`, `GET /sessions/{id}/stream`, `POST /sessions/{id}/turns`, `POST /sessions/{id}/stop`) plus the SSE event vocabulary (`session_start`, `turn_start`, `token`, `turn_complete`, `round_complete`, `session_complete`, `error`). The frontend work is wiring these into Vue 3 components that match the existing project conventions.

The three non-trivial problems are: (1) consuming the SSE stream with the native `EventSource` API, which requires passing the JWT as a query param (not a header) — this is already decided and documented in Phase 2; (2) rendering streaming tokens in real time as they arrive, appending to the current agent's message bubble without re-rendering the whole list; and (3) managing the session lifecycle state (idle → streaming → waiting-for-user → stopped) cleanly in a Pinia store so the UI stays consistent.

Everything else is straightforward: the project already has a chat-style UI in `ChatView.vue`, a detail page pattern in `ModelCardDetailView.vue`, a list page pattern in `ModelCardsView.vue`, a Pinia auth store, vue-i18n with both `en.json` and `zh.json`, and a global nav in `App.vue`. Phase 3 follows all of these patterns exactly — no new libraries needed.

**Primary recommendation:** Build three artifacts: (1) a `useCogTestStore` Pinia store that owns all session state and SSE lifecycle, (2) a `CogTestSessionView.vue` that renders the streaming dialogue, and (3) a `CogTestListView.vue` for the history list. Add a button to `ModelCardDetailView.vue` and a nav link to `App.vue`.

---

## Standard Stack

### Core (all already in project — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vue 3 | ^3.5.0 | Component framework | Project standard |
| Pinia | ^2.2.0 | State management | Project standard; auth store already uses it |
| Vue Router | ^4.4.0 | Navigation + route params | Project standard; all views use it |
| vue-i18n | ^9.14.4 | Bilingual strings (zh/en) | Project standard; all views use `useI18n()` |
| axios | ^1.7.0 | REST API calls (non-SSE) | Project standard; `src/api/index.ts` |
| Native `EventSource` | browser built-in | SSE stream consumption | No library needed; browser API handles reconnect |

### Supporting (already in project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@capacitor/core` | ^8.1.0 | Native platform detection | Already used in `api/index.ts` for base URL; SSE URL must also handle native platform |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `EventSource` | `@microsoft/fetch-event-source` | fetch-event-source allows custom headers (no query param needed) but adds a dependency; native EventSource is already the established pattern in this project per Phase 2 decisions |
| Pinia store for SSE state | Composable `useCogTest()` | Composable is lighter but state would not persist across route navigation; Pinia store survives navigation, which matters when user navigates away mid-session |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── views/
│   ├── CogTestSessionView.vue   # NEW: streaming dialogue UI
│   └── CogTestListView.vue      # NEW: history list
├── stores/
│   └── cogTest.ts               # NEW: Pinia store for session state + SSE
├── views/
│   └── ModelCardDetailView.vue  # MODIFY: add "Start Cognitive Test" button
├── App.vue                      # MODIFY: add nav link
├── router/index.ts              # MODIFY: add two routes
└── locales/
    ├── en.json                  # MODIFY: add cogTest keys
    └── zh.json                  # MODIFY: add cogTest keys
```

### Pattern 1: Pinia Store Owns SSE Lifecycle

The store is the single source of truth for session state. The view is a thin renderer.

```typescript
// src/stores/cogTest.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

interface Message {
  role: 'guide' | 'challenger' | 'user'
  content: string
  streaming?: boolean  // true while tokens are still arriving
}

type SessionStatus = 'idle' | 'connecting' | 'streaming' | 'waiting' | 'stopped' | 'completed'

export const useCogTestStore = defineStore('cogTest', () => {
  const sessionId = ref<string | null>(null)
  const concept = ref<string>('')
  const status = ref<SessionStatus>('idle')
  const messages = ref<Message[]>([])
  const currentRound = ref(1)
  const maxRounds = ref(3)
  const error = ref<string | null>(null)

  let eventSource: EventSource | null = null

  const startSession = async (conceptName: string) => {
    const res = await api.post('/cog-test/sessions', { concept: conceptName, max_rounds: 3 })
    sessionId.value = res.data.session_id
    concept.value = conceptName
    status.value = 'connecting'
    messages.value = []
    _openStream()
  }

  const _openStream = () => {
    const authStore = useAuthStore()
    const token = authStore.token
    const baseUrl = /* same logic as api/index.ts */ '/api'
    const url = `${baseUrl}/cog-test/sessions/${sessionId.value}/stream?token=${token}`
    eventSource = new EventSource(url)

    eventSource.addEventListener('session_start', (e) => {
      const data = JSON.parse(e.data)
      maxRounds.value = data.max_rounds
      status.value = 'streaming'
    })

    eventSource.addEventListener('turn_start', (e) => {
      const data = JSON.parse(e.data)
      // Push a new empty message bubble for this agent turn
      messages.value.push({ role: data.role, content: '', streaming: true })
      currentRound.value = data.round
    })

    eventSource.addEventListener('token', (e) => {
      // Append token to the last message (currently streaming)
      const last = messages.value[messages.value.length - 1]
      if (last?.streaming) last.content += e.data
    })

    eventSource.addEventListener('turn_complete', () => {
      const last = messages.value[messages.value.length - 1]
      if (last) last.streaming = false
      status.value = 'waiting'  // waiting for user input
    })

    eventSource.addEventListener('round_complete', (e) => {
      const data = JSON.parse(e.data)
      currentRound.value = data.round
    })

    eventSource.addEventListener('session_complete', () => {
      status.value = 'completed'
      eventSource?.close()
      eventSource = null
    })

    eventSource.addEventListener('error', (e: MessageEvent) => {
      error.value = JSON.parse(e.data).message
      status.value = 'stopped'
      eventSource?.close()
    })

    eventSource.onerror = () => {
      // EventSource connection error (not an SSE error event)
      if (status.value !== 'completed' && status.value !== 'stopped') {
        status.value = 'stopped'
        error.value = 'Connection lost'
      }
      eventSource?.close()
    }
  }

  const submitUserTurn = async (text: string) => {
    if (!sessionId.value) return
    messages.value.push({ role: 'user', content: text })
    status.value = 'streaming'
    await api.post(`/cog-test/sessions/${sessionId.value}/turns`, { text })
  }

  const stopSession = async () => {
    if (!sessionId.value) return
    await api.post(`/cog-test/sessions/${sessionId.value}/stop`)
    eventSource?.close()
    eventSource = null
    status.value = 'stopped'
  }

  return {
    sessionId, concept, status, messages, currentRound, maxRounds, error,
    startSession, submitUserTurn, stopSession,
  }
})
```

### Pattern 2: EventSource URL Construction for Native Platform

The existing `api/index.ts` uses `Capacitor.isNativePlatform()` to switch base URLs. The SSE URL must do the same.

```typescript
// In cogTest.ts store
import { Capacitor } from '@capacitor/core'

const getSSEBaseUrl = () => {
  if (Capacitor.isNativePlatform()) {
    return localStorage.getItem('api_server_url') || 'http://10.0.2.2:8002/api'
  }
  return '/api'
}

const url = `${getSSEBaseUrl()}/cog-test/sessions/${sessionId.value}/stream?token=${token}`
```

### Pattern 3: Streaming Message Bubble

The key rendering challenge is appending tokens to the last message without re-rendering the whole list. Vue 3 reactivity handles this automatically when you mutate `last.content` directly — no need for special tricks.

```vue
<!-- CogTestSessionView.vue -->
<div
  v-for="(msg, i) in store.messages"
  :key="i"
  class="message"
  :class="[msg.role, { streaming: msg.streaming }]"
>
  <span class="role-label">{{ roleLabel(msg.role) }}</span>
  <div class="message-content">{{ msg.content }}<span v-if="msg.streaming" class="cursor">|</span></div>
</div>
```

Guide and Challenger are visually distinct via CSS class on `.message.guide` vs `.message.challenger`.

### Pattern 4: "Stop and Diagnose" Button Always Visible

The button is always rendered during an active session (status is `streaming` or `waiting`). It calls `store.stopSession()`.

```vue
<button
  v-if="store.status === 'streaming' || store.status === 'waiting'"
  class="btn btn-stop"
  @click="store.stopSession()"
>
  {{ t('cogTest.stopAndDiagnose') }}
</button>
```

### Pattern 5: Launch from Model Card Detail

Add a single button to `ModelCardDetailView.vue`. On click: call `store.startSession(card.title)` then navigate to `/cog-test/session`.

```vue
<!-- In ModelCardDetailView.vue, inside the card-info section -->
<button class="btn btn-primary" @click="startCogTest">
  {{ t('cogTest.startTest') }}
</button>
```

```typescript
import { useCogTestStore } from '@/stores/cogTest'
import { useRouter } from 'vue-router'

const cogTestStore = useCogTestStore()
const router = useRouter()

const startCogTest = async () => {
  await cogTestStore.startSession(card.value.title)
  router.push('/cog-test/session')
}
```

### Pattern 6: History List View

Follows the same pattern as `ModelCardsView.vue` — fetch on mount, render a list.

```typescript
// CogTestListView.vue
const sessions = ref<any[]>([])
onMounted(async () => {
  const res = await api.get('/cog-test/sessions')
  sessions.value = res.data
})
```

The list shows: concept name, date (`created_at`), status. The backend `GET /cog-test/sessions` returns `[{id, concept, status, created_at}]`.

### Anti-Patterns to Avoid

- **Opening EventSource inside the component:** If the component unmounts (user navigates away), the EventSource is destroyed and the stream is lost. Keep EventSource in the Pinia store so it survives navigation.
- **Passing JWT in Authorization header to EventSource:** The browser `EventSource` API does not support custom headers. JWT must be in the `?token=` query param — this is already the established pattern from Phase 2.
- **Re-creating the message array on each token:** Mutate `last.content` in place. Replacing the array triggers full list re-render and causes visible flicker.
- **Forgetting to close EventSource on component unmount:** Call `eventSource.close()` in the store's `stopSession()` and on `session_complete`. Also close on `onerror` to prevent reconnect loops.
- **Using `eventSource.onmessage` instead of `addEventListener`:** The backend sends named events (`turn_start`, `token`, etc.). `onmessage` only fires for unnamed events (no `event:` field). Use `addEventListener('turn_start', ...)` for each named event type.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE client | Custom fetch + ReadableStream parser | Native `EventSource` | Browser handles reconnect, event parsing, connection management |
| Token streaming display | Virtual scroll / complex buffer | Direct Vue reactive mutation of `last.content` | Vue 3 reactivity is fine-grained; mutating a nested string property re-renders only that text node |
| Auth token injection for SSE | Custom SSE wrapper library | `?token=` query param on EventSource URL | Already decided in Phase 2; EventSource cannot send headers |
| Bilingual strings | Hardcoded strings | `useI18n()` + add keys to `en.json` / `zh.json` | Project standard; all views use it |

**Key insight:** The browser's native `EventSource` is sufficient. No SSE client library is needed.

---

## Common Pitfalls

### Pitfall 1: EventSource Reconnects Automatically on Error

**What goes wrong:** When the SSE stream ends normally (server closes connection after `session_complete`), `EventSource.onerror` fires and the browser automatically tries to reconnect. This causes a new stream to open on a session that is already complete.

**Why it happens:** `EventSource` is designed for persistent streams and reconnects by default. It does not distinguish between "server closed intentionally" and "network error."

**How to avoid:** Call `eventSource.close()` explicitly inside the `session_complete` event handler before the browser can attempt reconnect. Also call it in `onerror` after setting status to stopped/error.

**Warning signs:** Duplicate `session_start` events in the console; session appears to restart after completing.

### Pitfall 2: Status Desync Between Store and UI

**What goes wrong:** The "Stop and Diagnose" button disappears or the input is enabled when it shouldn't be, because the `status` ref is not updated atomically with the message list.

**Why it happens:** SSE events arrive asynchronously. If `turn_complete` sets `status = 'waiting'` but the message list hasn't been updated yet, the UI briefly shows the wrong state.

**How to avoid:** Update `status` only after updating `messages`. In the `turn_complete` handler: first mark `last.streaming = false`, then set `status = 'waiting'`. Vue 3 batches reactive updates within the same synchronous block, so this is safe.

### Pitfall 3: User Input Submitted Before Engine is Waiting

**What goes wrong:** User types fast and submits a reply while the agent is still streaming. The backend receives the turn submission before the engine has called `await _user_input_queue.get()`, causing the text to be queued correctly — but the frontend shows the wrong status.

**Why it happens:** The frontend `status` transitions to `'waiting'` on `turn_complete`, but the user could submit before that event arrives.

**How to avoid:** Disable the user input form when `status !== 'waiting'`. Only enable it when `status === 'waiting'`.

```vue
<form @submit.prevent="submitTurn">
  <input v-model="userInput" :disabled="store.status !== 'waiting'" />
  <button type="submit" :disabled="store.status !== 'waiting' || !userInput.trim()">
    {{ t('cogTest.send') }}
  </button>
</form>
```

### Pitfall 4: i18n Keys Missing in One Locale

**What goes wrong:** The app works in Chinese but shows raw key strings in English (or vice versa) because keys were added to only one locale file.

**Why it happens:** Easy to forget to update both `en.json` and `zh.json`.

**How to avoid:** Always update both files in the same task. The keys needed are: `cogTest.startTest`, `cogTest.stopAndDiagnose`, `cogTest.send`, `cogTest.guide`, `cogTest.challenger`, `cogTest.you`, `cogTest.sessionComplete`, `cogTest.history`, `cogTest.concept`, `cogTest.date`, `cogTest.status`, `nav.cogTest`.

### Pitfall 5: Navigation Away Loses Active Session

**What goes wrong:** User navigates to another page mid-session. The EventSource in the store stays open (good), but when they navigate back, the view re-mounts and tries to start a new session, overwriting the active one.

**Why it happens:** `onMounted` in the view calls `startSession()` unconditionally.

**How to avoid:** In `CogTestSessionView.vue`, check `store.status` on mount. If it's already `streaming` or `waiting`, don't call `startSession()` — just render the existing `store.messages`.

---

## Code Examples

### Route Definitions to Add

```typescript
// src/router/index.ts — add inside routes array
{
  path: '/cog-test',
  name: 'cog-test-list',
  component: () => import('@/views/CogTestListView.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/cog-test/session',
  name: 'cog-test-session',
  component: () => import('@/views/CogTestSessionView.vue'),
  meta: { requiresAuth: true },
},
```

### Nav Link to Add in App.vue

```vue
<!-- In App.vue, inside .nav-links div, alongside other router-links -->
<router-link to="/cog-test">{{ t('nav.cogTest') }}</router-link>
```

### i18n Keys to Add (both locales)

```json
// en.json additions
"nav": {
  "cogTest": "Cognitive Tests"
},
"cogTest": {
  "startTest": "Start Cognitive Test",
  "stopAndDiagnose": "Stop and Diagnose",
  "send": "Send",
  "guide": "Guide",
  "challenger": "Challenger",
  "you": "You",
  "sessionComplete": "Session complete",
  "history": "Test History",
  "concept": "Concept",
  "date": "Date",
  "status": "Status",
  "noSessions": "No cognitive tests yet",
  "round": "Round",
  "connecting": "Connecting..."
}
```

```json
// zh.json additions
"nav": {
  "cogTest": "认知测试"
},
"cogTest": {
  "startTest": "发起认知测试",
  "stopAndDiagnose": "停止并诊断",
  "send": "发送",
  "guide": "引导者",
  "challenger": "质疑者",
  "you": "你",
  "sessionComplete": "会话已完成",
  "history": "测试历史",
  "concept": "概念",
  "date": "日期",
  "status": "状态",
  "noSessions": "暂无认知测试记录",
  "round": "轮次",
  "connecting": "连接中..."
}
```

### CogTestListView.vue Skeleton

```vue
<template>
  <div class="cog-test-list">
    <h1>{{ t('cogTest.history') }}</h1>
    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="sessions.length === 0" class="empty">{{ t('cogTest.noSessions') }}</div>
    <div v-else class="sessions-list">
      <div v-for="s in sessions" :key="s.id" class="card session-item">
        <span class="concept">{{ s.concept }}</span>
        <span class="date">{{ formatDate(s.created_at) }}</span>
        <span class="status-badge" :class="s.status">{{ s.status }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const sessions = ref<any[]>([])
const loading = ref(true)
const formatDate = (d: string) => new Date(d).toLocaleDateString()

onMounted(async () => {
  try {
    const res = await api.get('/cog-test/sessions')
    sessions.value = res.data
  } finally {
    loading.value = false
  }
})
</script>
```

### Role Label Color Convention

Guide and Challenger are visually distinct. Use the existing CSS variable system:

```css
/* In CogTestSessionView.vue <style scoped> */
.message.guide .role-label   { color: var(--primary); }       /* green */
.message.challenger .role-label { color: #f59e0b; }           /* amber */
.message.user .role-label    { color: var(--text-muted); }    /* grey */

.message.guide .message-content   { background: var(--bg-card); border-left: 3px solid var(--primary); }
.message.challenger .message-content { background: var(--bg-card); border-left: 3px solid #f59e0b; }
.message.user .message-content    { background: var(--bg-dark); align-self: flex-end; }

.cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Polling for new messages | SSE push | Already decided in Phase 2; frontend just consumes the stream |
| WebSocket for streaming | SSE + EventSource | Simpler client; no library needed; already decided |
| Component-local SSE state | Pinia store | Survives navigation; single source of truth |

---

## Open Questions

1. **SSE base URL on native Capacitor platform**
   - What we know: `api/index.ts` uses `Capacitor.isNativePlatform()` to switch to `localStorage.getItem('api_server_url')`. The SSE URL must do the same.
   - What's unclear: Whether the Capacitor Android WebView supports `EventSource` natively or needs a polyfill.
   - Recommendation: Android v1 is out of scope (see REQUIREMENTS.md Out of Scope). For web, native `EventSource` works. Add a TODO comment in the store for future Capacitor SSE handling.

2. **Session resumption on page reload**
   - What we know: The backend keeps sessions active until explicitly stopped. The Pinia store is in-memory and resets on page reload.
   - What's unclear: Whether Phase 3 needs to handle resuming an in-progress session after reload.
   - Recommendation: Out of scope for Phase 3. On reload, the store is empty; the user can navigate to the history list and see the session as "active" but cannot resume the stream. This is acceptable for v1.

3. **Score display in history list**
   - What we know: `GET /cog-test/sessions` returns `{id, concept, status, created_at}`. The understanding score is in `CogTestSnapshot`, not in the session row directly.
   - What's unclear: Whether the backend list endpoint will include the final score, or whether a separate call is needed.
   - Recommendation: SESS-05 says "concept name, date, and final score." The backend plan (02-03) only returns `{id, concept, status, created_at}`. The planner should either (a) add score to the list endpoint response in Phase 2 plan 03, or (b) accept that Phase 3 shows status instead of score for v1. Flag this for the planner.

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` — skipping this section.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `las_frontend/src/views/ChatView.vue` — existing streaming-style chat UI pattern
- Codebase: `las_frontend/src/views/ModelCardDetailView.vue` — detail page pattern, button placement
- Codebase: `las_frontend/src/App.vue` — nav link pattern
- Codebase: `las_frontend/src/router/index.ts` — route registration pattern
- Codebase: `las_frontend/src/stores/auth.ts` — Pinia store pattern
- Codebase: `las_frontend/src/api/index.ts` — axios instance, Capacitor base URL logic
- Codebase: `las_frontend/src/locales/en.json` + `zh.json` — i18n key structure
- Codebase: `las_frontend/src/assets/main.css` — CSS variable system
- Codebase: `las_frontend/package.json` — confirmed no SSE library present; native EventSource is the approach
- `.planning/phases/02-backend-engine/02-03-PLAN.md` — confirmed backend API surface (5 endpoints + SSE event vocabulary)
- `.planning/phases/02-backend-engine/02-CONTEXT.md` — JWT via query param decision locked

### Secondary (MEDIUM confidence)

- MDN Web Docs (training knowledge): `EventSource` named event listeners via `addEventListener('event-name', handler)` — standard browser API behavior
- MDN Web Docs (training knowledge): `EventSource.close()` must be called explicitly to prevent auto-reconnect

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, no new dependencies
- Architecture: HIGH — derived directly from existing code patterns and Phase 2 API contracts
- Pitfalls: HIGH — derived from EventSource browser API behavior and Vue 3 reactivity fundamentals

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable stack; Vue 3 + Pinia + EventSource are not fast-moving)
