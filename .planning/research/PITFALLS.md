# Pitfalls Research

**Domain:** Socratic AI tutoring / cognitive adversarial testing (multi-agent dialogue engine ported to learning context)
**Researched:** 2026-02-28
**Confidence:** MEDIUM — core pitfalls verified across multiple sources; some learning-specific claims from single sources flagged inline

---

## Critical Pitfalls

### Pitfall 1: Socratic Tutor Drifts Into Answer-Giver

**What goes wrong:**
The "引导者" (guide) agent's system prompt is too permissive. After 2-3 turns of the learner struggling, the LLM's RLHF-trained helpfulness instinct overrides the Socratic constraint and it starts providing direct answers instead of questions. The session becomes a normal Q&A chat, defeating the entire purpose.

**Why it happens:**
LLMs are trained to be helpful and resolve user confusion. A system prompt saying "ask guiding questions" competes with the model's base training. Without explicit, repeated constraints and output format enforcement, the model defaults to helpfulness under pressure. ProdMind's `problem-architect.md` prompt avoids this by mandating a rigid output structure — the learning tutor prompts need the same discipline.

**How to avoid:**
- Enforce output format: every tutor response MUST end with exactly one question, no exceptions
- Add explicit negative constraint: "你绝对不能直接给出答案，即使学习者明确要求"
- Use temperature 0.3-0.4 for the guide agent (lower = more rule-following)
- Add a post-generation validator: if response contains no `?` character, reject and retry once

**Warning signs:**
- Tutor responses getting longer over time (answer-giving is verbose; question-asking is short)
- Learner stops responding with their own reasoning and just says "ok" or "I see"
- Session logs show tutor output contains phrases like "正确答案是" or "你应该知道"

**Phase to address:** Agent prompt design phase (before any UI work)

---

### Pitfall 2: SSE Stream Orphaned on Client Disconnect

**What goes wrong:**
The learner closes the browser tab or navigates away mid-session. The FastAPI async generator keeps running — calling the LLM, writing to the database, computing scores — for the full remaining round. With concurrent users, this burns LLM tokens, holds DB connections, and accumulates memory. Confirmed real-world issue: "100 dead connections = wasted CPU + memory leaks + slower responses for everyone else" (jasoncameron.dev).

**Why it happens:**
FastAPI's `StreamingResponse` with an async generator does not automatically cancel the generator when the client disconnects. The generator runs to completion unless you explicitly check `await request.is_disconnected()` inside the loop. The existing `conversations.py` in this codebase uses non-streaming responses, so this pattern hasn't been established yet.

**How to avoid:**
```python
async def session_stream(request: Request, session_id: str):
    async def generate():
        for agent in ["guide", "challenger"]:
            if await request.is_disconnected():
                break  # stop immediately, don't call LLM
            async for token in stream_agent(agent, context):
                if await request.is_disconnected():
                    return
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```
Check `is_disconnected()` before each agent call AND inside the token loop.

**Warning signs:**
- Memory usage grows linearly with session count and never drops
- LLM API costs higher than expected relative to completed sessions
- DB connection pool exhaustion under moderate load

**Phase to address:** SSE streaming implementation phase

---

### Pitfall 3: Regex-Based Output Parsing Breaks on LLM Variation

**What goes wrong:**
ProdMind's `parsers.ts` uses regex like `output.match(/##\s*隐含假设[\s\S]*?\n([\s\S]*?)(?=\n##|$)/)` to extract structured data from agent output. This works when the LLM follows the prompt format exactly. In practice, LLMs occasionally output `### 隐含假设` (three hashes), `**隐含假设**` (bold), or omit the section entirely. The parser returns empty arrays silently — the blind spot library never gets populated, the understanding score stays at zero, and the session appears to work but produces no diagnostic value.

**Why it happens:**
Regex parsers assume deterministic LLM output. LLMs are probabilistic. The ProdMind codebase accepts this tradeoff for a product-decision tool where missing one assumption is tolerable. For a learning diagnostic tool, missing blind spots IS the core failure mode.

**How to avoid:**
- Use JSON-mode output for structured extraction: instruct agents to output a `<structured>` JSON block at the end of their response, separate from the conversational text
- Parse the JSON block; use the conversational text for display
- Fallback: if JSON parse fails, log the raw output and flag the round as "unextracted" rather than silently returning empty
- Never use regex as the sole extraction mechanism for data that drives scoring

**Warning signs:**
- Blind spot library stays empty after multiple rounds
- Understanding score stuck at 0 or 100 (boundary values = parser failure)
- Agent outputs look correct in UI but DB tables for blind spots are empty

**Phase to address:** Agent output schema design (before implementing the blind spot library)

---

### Pitfall 4: Session State Rebuilt From DB on Every Agent Call

**What goes wrong:**
Following ProdMind's `context-builder.ts` pattern directly: each agent call loads full session state from the database (session, blind spots, scores, all previous turns). With SQLite and 2 agents per round, that's 2 full state loads per round. At round 5 with 20 previous turns, each load is a multi-table query. This is fine for ProdMind (Supabase, async, low concurrency). For SQLite with multiple concurrent learners, this creates lock contention and latency spikes.

**Why it happens:**
The pattern is copied from a Supabase-backed system where async DB calls are cheap and non-blocking. SQLite has a single-writer lock. The existing LAS backend already uses `AsyncSession` with SQLAlchemy, but SQLite's write lock means concurrent sessions will queue.

**How to avoid:**
- Keep session state in memory (Python dict or Pydantic model) for the duration of a round
- Load from DB once at round start, pass in-memory state to both agents
- Write to DB only at round end (after both agents complete)
- Use a session-keyed in-memory cache (simple dict, not Redis — this is SQLite scale)

**Warning signs:**
- Response latency increases with each round in a session
- DB lock timeout errors in logs under 3+ concurrent sessions
- Profiling shows >50% of round time spent in DB queries

**Phase to address:** Backend architecture phase (before implementing multi-agent orchestration)

---

### Pitfall 5: Challenger Agent Feels Hostile, Not Constructive

**What goes wrong:**
The "质疑者" (challenger) agent is prompted to "point out contradictions" but the framing lands as criticism rather than curiosity. Learners disengage, stop elaborating their reasoning, or give defensive one-word answers. The session produces no useful diagnostic data because the learner has shut down. Research confirms: adversarial questioning without psychological safety causes learners to perform worse, not better (Brookings, 2025).

**Why it happens:**
ProdMind's `devils-advocate.md` is designed for product teams who expect pushback as part of professional discourse. Learners — especially those early in a topic — have much lower tolerance for challenge. The same adversarial framing that works for a product manager feels like an attack to a student who isn't sure of themselves yet.

**How to avoid:**
- Frame challenger output as curiosity, not contradiction: "我有个疑问..." not "你的理解有矛盾"
- Challenger must acknowledge what the learner got right before raising a question
- Challenger temperature: 0.5-0.6 (slightly higher for natural variation, but not 0.8 like ProdMind's devil's advocate)
- Add explicit tone constraint: "用好奇和探索的语气，不用批评或否定的语气"
- Test prompts with actual learners before shipping — tone is hard to evaluate in isolation

**Warning signs:**
- Learner response length drops sharply after challenger turn
- Learner uses phrases like "I don't know" or "whatever you say" after round 2
- Session abandonment rate spikes at round 2 (first challenger appearance)

**Phase to address:** Agent prompt design phase, with UX validation before launch

---

## Moderate Pitfalls

### Pitfall 6: Vue EventSource Not Cleaned Up on Component Unmount

**What goes wrong:**
The Vue component that renders the session dialogue creates an `EventSource` connection. When the learner navigates away (e.g., back to model cards), the component unmounts but the `EventSource` is never closed. The browser keeps the connection open. On return, a new `EventSource` is created — now there are two connections receiving the same stream. Tokens appear duplicated in the UI.

**Why it happens:**
`EventSource` is not reactive — Vue's reactivity system doesn't track it. Developers forget to call `eventSource.close()` in `onUnmounted()`. The browser's 6-connection-per-domain limit (for HTTP/1.1) means this also blocks other requests.

**How to avoid:**
```typescript
// In the session composable
const eventSource = ref<EventSource | null>(null)

onUnmounted(() => {
  eventSource.value?.close()
  eventSource.value = null
})
```
Always close in `onUnmounted`. Use a composable (`useSessionStream`) so cleanup is co-located with creation.

**Warning signs:**
- Tokens appearing twice in the dialogue
- Network tab shows multiple open SSE connections to the same endpoint
- Browser console shows EventSource errors after navigation

**Phase to address:** Frontend SSE integration phase

---

### Pitfall 7: Understanding Score Formula Copied From ProdMind Without Adaptation

**What goes wrong:**
ProdMind's confidence index formula: `validated_assumptions / total * risk_exposure`. Ported directly to learning: `resolved_blind_spots / total * (1 - high_severity_gaps * 0.2)`. This produces a score that bounces erratically in early rounds (when total is small) and plateaus at 100% once all extracted blind spots are resolved — even if the learner's actual understanding is shallow. The score becomes meaningless and learners stop trusting it.

**Why it happens:**
The formula was designed for product decisions where "validated assumptions" is a meaningful proxy for confidence. In learning, understanding is not binary per blind spot — it's a spectrum. Directly porting the formula without adapting it to the learning domain produces a metric that looks right but measures the wrong thing.

**How to avoid:**
- Design the understanding score independently from ProdMind's formula
- Consider: weighted score based on blind spot severity + recency + learner explanation quality
- Start simple: a round counter with qualitative labels ("初步探索" / "深入理解" / "掌握") is more honest than a fake percentage
- Never show a percentage score unless you can explain exactly what it measures

**Warning signs:**
- Score jumps from 0% to 80% in one round
- Score reaches 100% but learner clearly doesn't understand the concept
- Learners ask "what does this number mean?"

**Phase to address:** Scoring design phase (before implementing the score display)

---

### Pitfall 8: LLM Service Has No Streaming Support

**What goes wrong:**
The existing `llm_service.py` uses synchronous `client.chat.completions.create()` (not `stream=True`). The entire LLM response is buffered before returning. For SSE streaming, you need `stream=True` with an async generator. Adding streaming to the existing service requires a non-trivial refactor — if this is discovered mid-implementation, it causes a rewrite of the service layer.

**Why it happens:**
The existing service was built for request-response patterns (model card generation, counter-examples). Streaming was never needed. The cognitive testing feature is the first streaming use case in this codebase.

**How to avoid:**
- Add a `stream_generate()` async generator method to `LLMService` before building the debate engine
- Keep it separate from `generate()` — don't try to make one method do both
- Test the streaming path with a simple endpoint before wiring it to the multi-agent orchestrator

**Warning signs:**
- First token latency equals total generation time (buffering, not streaming)
- UI shows blank screen for 10-15 seconds then all text appears at once

**Phase to address:** LLM service extension phase (first task in the milestone)

---

### Pitfall 9: Snapshot Taken After Every Round Bloats SQLite

**What goes wrong:**
ProdMind takes a full state snapshot after every round, storing the entire state tree as JSON in the `snapshots` table. For a learning session with 10 rounds and growing blind spot/turn history, each snapshot is 5-20KB. With many sessions, the SQLite file grows rapidly and queries slow down. Unlike Supabase (which handles this transparently), SQLite's file-based storage makes this visible and painful.

**Why it happens:**
Snapshots are cheap in Supabase with proper indexing. In SQLite, storing large JSON blobs in every row is a known performance issue — JSON columns aren't indexed and full-table scans become slow.

**How to avoid:**
- Snapshot only on explicit user action ("保存当前状态") and on session end, not every round
- Store incremental diffs rather than full state trees where possible
- If full snapshots are needed, compress the JSON (Python `zlib`) before storing
- Add a snapshot retention policy: keep last 5, delete older ones automatically

**Warning signs:**
- SQLite file size growing faster than expected
- Session load time increasing with session age
- `SELECT` on snapshots table taking >100ms

**Phase to address:** Data model design phase

---

## Minor Pitfalls

### Pitfall 10: Scheduler Logic Too Complex for 2-Agent System

**What goes wrong:**
ProdMind's `scheduler.ts` dynamically selects which of 6 agents to activate based on state conditions (unvalidated assumption ratio, risk count, round number). Porting this logic to a 2-agent system creates unnecessary complexity — the scheduler ends up always selecting both agents, making the conditional logic dead code that confuses future maintainers.

**How to avoid:**
For 2 agents, the scheduler is trivial: guide always goes first, challenger always goes second. Don't port the conditional scheduler. A simple ordered list `["guide", "challenger"]` is the entire scheduler. Add complexity only if a third agent is introduced later.

**Phase to address:** Backend architecture phase

---

### Pitfall 11: No Heartbeat Causes SSE Timeout at Proxies

**What goes wrong:**
Between agent turns (while the LLM is generating), there's silence on the SSE stream. Nginx, load balancers, and some browsers treat 30-60 seconds of silence as a dead connection and close it. The learner sees the stream cut off mid-session with no error message.

**How to avoid:**
Send a heartbeat comment every 15 seconds during silent periods:
```python
yield ": heartbeat\n\n"  # SSE comment, ignored by client but keeps connection alive
```
SSE comments (lines starting with `:`) are valid SSE syntax and don't trigger client event handlers.

**Phase to address:** SSE streaming implementation phase

---

### Pitfall 12: Cognitive Test Entry Point Buried in Model Card

**What goes wrong:**
The test is triggered from the model card, but if the trigger button is a small secondary action or hidden in a menu, learners never discover it. The feature ships but has near-zero usage because the entry point isn't visible enough.

**How to avoid:**
- Make the "开始认知测试" button a primary action on the model card detail view, not a secondary/overflow menu item
- Add a brief one-line description of what the test does next to the button
- Consider a first-time tooltip or empty state prompt on the model card

**Phase to address:** Frontend integration phase

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Copy ProdMind parsers.ts regex directly | Fast extraction implementation | Silent failures when LLM output varies; blind spot library unreliable | Never — use JSON-mode extraction instead |
| Store full session state in SSE generator closure | Avoids DB reads mid-stream | Memory leak if generator not cleaned up on disconnect | Only if disconnect detection is implemented |
| Single `generate()` method for both streaming and non-streaming | Simpler service interface | Buffering defeats SSE purpose; confusing API | Never — keep streaming as a separate method |
| Skip heartbeat in SSE | Less code | Proxy timeouts kill sessions silently | Never for production; acceptable for local dev only |
| Port ProdMind's confidence formula unchanged | Reuses existing logic | Meaningless score that erodes learner trust | Never — redesign for learning domain |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| agno LLM layer + streaming | Calling `generate()` and wrapping in fake stream | Add `stream_generate()` async generator to `LLMService` that passes `stream=True` to the underlying client |
| SQLAlchemy AsyncSession + SSE generator | Opening a DB session inside the generator and holding it open for the stream duration | Open session, load state, close session; pass state dict to generator; reopen session only for final write |
| Vue EventSource + Pinia store | Updating store directly from EventSource callbacks without cleanup | Use a composable that owns the EventSource lifecycle; store only receives finalized data |
| FastAPI StreamingResponse + auth middleware | Auth middleware reads request body, which conflicts with streaming | Use header-based auth (Bearer token) not body-based; verify token before creating the StreamingResponse |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full state load per agent call | Latency grows with round count | Load once per round, pass in-memory | Round 3+ with 3+ concurrent sessions |
| Snapshot every round | SQLite file bloat, slow session loads | Snapshot on demand + session end only | After ~50 sessions with 5+ rounds each |
| No disconnect detection | Memory/CPU grows with abandoned sessions | `request.is_disconnected()` checks | 5+ concurrent users with browser tab switching |
| Synchronous LLM calls in async context | Event loop blocked, all other requests stall | Use `asyncio.to_thread()` or async client | Any concurrent usage |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Session ID in SSE URL path without auth check | Any user can stream another user's session | Verify `session.user_id == current_user.id` before opening stream |
| LLM output rendered as raw HTML in Vue | XSS if LLM outputs `<script>` tags | Always use `v-text` or sanitize with DOMPurify; never `v-html` on LLM output |
| Cognitive diagnostic report exported without sanitization | Report contains injected content if LLM was manipulated | Sanitize all LLM-generated content before including in Markdown export |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No visual distinction between guide and challenger turns | Learner can't tell who is speaking; dialogue feels incoherent | Distinct avatar/color/label for each agent; consistent across all rounds |
| Score displayed as percentage without explanation | Learner fixates on number, not understanding | Show qualitative label ("深入探索中") with a brief tooltip explaining what it measures |
| No "stop and diagnose" affordance visible during session | Learner feels trapped; can't exit gracefully | Persistent "结束并查看诊断" button visible at all times during session |
| Streaming tokens cause layout reflow on each token | Jittery, unreadable text during generation | Use a fixed-height container with overflow scroll; append tokens to a pre-allocated text node |
| Both agents stream simultaneously | Overlapping text, impossible to read | Sequential streaming only: guide completes fully before challenger starts |

---

## "Looks Done But Isn't" Checklist

- [ ] **SSE streaming:** Tokens appear in UI — verify disconnect detection is implemented and tested by closing tab mid-stream
- [ ] **Blind spot extraction:** Blind spots appear in UI — verify DB rows are actually written, not just displayed from in-memory state
- [ ] **Understanding score:** Score changes between rounds — verify the formula produces meaningful values across edge cases (0 blind spots, all resolved, etc.)
- [ ] **Session stop:** "Stop" button works — verify the diagnostic report generates correctly from partial session data, not just from complete sessions
- [ ] **Diagnostic report export:** Markdown file downloads — verify the content is sanitized and the format is readable outside the app
- [ ] **Model card trigger:** Button appears on model card — verify it only appears for cards the user owns, not all cards

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Tutor drifts to answer-giver (discovered post-launch) | MEDIUM | Revise system prompts + add output validator; existing session data is still valid |
| Regex parser silently failing (discovered after data loss) | HIGH | Backfill extraction by re-running parser on stored raw outputs; add JSON-mode going forward |
| SSE orphan leak (discovered under load) | LOW | Add `is_disconnected()` checks; no data loss, just resource waste |
| Score formula meaningless (discovered from user feedback) | MEDIUM | Redesign formula; existing scores are invalid but sessions are not — recalculate from raw data |
| SQLite bloat from snapshots (discovered at scale) | LOW | Add retention policy + compression; run one-time cleanup migration |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Tutor drifts to answer-giver | Phase 1: Agent prompt design | Manual test: ask tutor "just tell me the answer" — it must refuse |
| SSE stream orphaned on disconnect | Phase 2: SSE streaming implementation | Test: close browser tab mid-stream, verify server logs show generator stopped |
| Regex parser silent failures | Phase 1: Agent output schema design | Unit test: feed malformed LLM output to parser, verify error is logged not swallowed |
| DB state load per agent call | Phase 2: Backend architecture | Load test: 5 concurrent sessions at round 5, verify <2s response time |
| Challenger feels hostile | Phase 1: Agent prompt design | User test: 3 learners complete 3 rounds, collect qualitative feedback on tone |
| EventSource not cleaned up | Phase 3: Frontend SSE integration | Test: navigate away mid-stream, verify Network tab shows connection closed |
| Score formula meaningless | Phase 1: Scoring design | Design review: walk through formula with 5 edge cases before implementing |
| LLM service lacks streaming | Phase 2: LLM service extension | Unit test: `stream_generate()` yields tokens incrementally, not all at once |
| Snapshot bloat | Phase 2: Data model design | Check SQLite file size after 20 simulated sessions with 10 rounds each |
| No SSE heartbeat | Phase 2: SSE streaming implementation | Test: simulate 60s LLM delay, verify connection stays open through Nginx |

---

## Sources

- jasoncameron.dev — "Stop Burning CPU on Dead FastAPI Streams" (FastAPI disconnect detection pattern) — MEDIUM confidence
- Galileo AI — "Why do Multi-Agent LLM Systems Fail" (coordination breakdown patterns) — MEDIUM confidence
- Brookings Institution — "What the research shows about generative AI in tutoring" (learner anxiety under adversarial questioning) — MEDIUM confidence
- MDN Web Docs — EventSource API (6-connection browser limit, cleanup requirements) — HIGH confidence
- ProdMind reference implementation `ref/prodmind2-web/src/lib/engine/` (direct code analysis of parsers, scheduler, context-builder) — HIGH confidence
- LAS backend `las_backend/app/services/llm_service.py` (direct code analysis confirming no streaming support) — HIGH confidence
- softcery.com — "The AI Agent Prompt Engineering Trap" (prompt engineering diminishing returns) — LOW confidence
- ithy.com — "Optimizing Server-Sent Events Resilience for Unreliable Connections" (SSE reliability patterns) — MEDIUM confidence

---
*Pitfalls research for: Cognitive Adversarial Testing — Socratic AI tutoring module*
*Researched: 2026-02-28*
