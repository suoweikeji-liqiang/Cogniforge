# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — Cognitive Adversarial Testing MVP

**Shipped:** 2026-03-01
**Phases:** 4 | **Plans:** 12 | **Sessions:** ~8
**Timeline:** 13 days (2026-02-16 → 2026-03-01)
**Files changed:** 50 | **LOC added:** ~7,500

### What Was Built
- Full `CogTestEngine.run()` async generator with dual-layer retry (LLM exception inner, Socratic contract outer) and SSE event sequencing
- Guide + Challenger Socratic agent system prompts with `<analysis>` delimiter for structured output extraction
- FastAPI HTTP surface: 5 routes including SSE stream endpoint with query-param JWT auth
- Vue3 streaming dialogue UI with Pinia SSE store using `addEventListener` for named events
- Markdown diagnostic report export via in-memory `Response(content=)` — no disk writes
- Dual SRS elevation path: stop endpoint (guaranteed) + `_stream_with_elevation` wrapper (stream completion)

### What Worked
- **Out-of-order execution** — Phases 3 (Frontend) and 4 (Report) were executed before Phase 2 (Backend Engine). GSD's wave-based execution and SUMMARY.md tracking handled resume cleanly.
- **Additive module pattern** — Building entirely on top of existing FastAPI+agno+Vue3 stack with zero new framework dependencies (only sse-starlette added) kept integration complexity low.
- **`<analysis>` delimiter over pure JSON mode** — Natural dialogue text + structured JSON in one LLM response. `parse_agent_output` never raises; callers inspect `parse_success` flag.
- **Plain coroutine for `_run_agent_turn`** — Avoided Python limitation that async generators cannot `return` a value while yielding. Returns `(AgentOutput, events, llm_failed)` tuple cleanly.
- **Stop endpoint as guaranteed SRS trigger** — Recognizing `EventSourceResponse` lifecycle unreliability for post-stream DB access prevented a subtle correctness bug. `_stream_with_elevation` added as supplement.
- **Phase verification agents** — Phase 2 verification caught the `category == "gap"` filter bug and dead code before they became production issues.

### What Was Inefficient
- **Requirements.md tracking not updated during execution** — Checkboxes weren't ticked as phases completed. Traceability table showed 14/19 as "Pending" at milestone end despite all being implemented. Root cause: plan execution agents don't update REQUIREMENTS.md.
- **Phase 3 marked complete before Phase 2** — Execution order mismatch (phases built without dependent backend) created confusion at milestone start. Required manual ROADMAP.md state reconciliation.
- **Duplicate `db` parameter discovery late** — The two-independent-db-params pattern for `stream_session` was discovered during Phase 2 Plan 03 execution, not during planning. Could have been caught in plan review.
- **ROADMAP.md Phase 3 checkbox** — Phase 3 was executed and verified but not checked off in ROADMAP.md. Required manual fix during Phase 3 execute-phase run.

### Patterns Established
- **SSE JWT via query param** — `EventSource` cannot send custom headers; JWT must be passed as `?token=` query param. `get_current_user_from_query` is the reusable pattern.
- **Async generator wrapping for SSE cleanup** — Use `try/finally` in the wrapper generator to guarantee cleanup actions (SRS elevation, session status updates) run even on client disconnect.
- **Frontend SSE named events** — Use `eventSource.addEventListener('event-name', handler)` not `onmessage` — backend sends named SSE events via `event:` field, `onmessage` only catches unnamed events.
- **Module-level non-reactive EventSource** — Store EventSource as module-level variable outside Pinia state to avoid Vue reactivity overhead on DOM objects.
- **Idempotent stop design** — Stop endpoint returns 200 even for non-active sessions. `create_session` stops any existing active session first. Prevents state confusion on retry.

### Key Lessons
1. **Track requirement completion at plan execution time, not milestone end** — The gap between "all plans have SUMMARY.md" and "all requirements checked off" caused confusion at milestone close. Requirements should be ticked when their phase verification passes.
2. **Phase execution order can diverge from dependency order** — GSD handles this well via SUMMARY.md filtering, but ROADMAP.md checkbox state can lag. Consider adding a ROADMAP sync step to execute-phase.
3. **Post-stream async DB access is unreliable with EventSourceResponse** — Always use the stop endpoint (or a try/finally wrapper) as the guaranteed cleanup path. Don't rely on code after `yield from` in an SSE generator.
4. **`<analysis>` delimiter pattern is robust for structured LLM output** — More reliable than JSON mode for dialogue agents that need natural text output alongside structured data. Parser-safe design (never raises) is essential.
5. **Verification agents surface architectural mismatches** — The `category == "gap"` bug was caught by the verifier, not during execution. Run verifiers even for phases that "obviously worked."

### Cost Observations
- Model mix: ~100% sonnet (claude-sonnet-4-6), 0% opus, 0% haiku
- Profile: balanced
- Notable: yolo mode throughout — no confirmation gates. All phase verifications passed on first run. Zero retries needed across 12 plans.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~8 | 4 | First milestone — baseline established |

### Cumulative Quality

| Milestone | Verifications | All Passed | Zero Retries |
|-----------|---------------|------------|--------------|
| v1.0 | 4 phase + 12 plan | ✓ | ✓ |

### Top Lessons (Verified Across Milestones)

1. Post-stream async DB access is unreliable with SSE — always use stop endpoint or try/finally wrapper
2. Requirements tracking should happen at execution time, not milestone close

