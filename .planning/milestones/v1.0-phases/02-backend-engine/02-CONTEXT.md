# Phase 2: Backend Engine - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Full backend dialogue engine running end-to-end: session creation, turn scheduling between Guide and Challenger agents, blind spot extraction, understanding score calculation, and SSE streaming of typed events to any HTTP client. Frontend UI and report export are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Turn Scheduling
- Fixed alternation per round: Guide → user → Challenger → user
- Default 3 rounds per session, with optional "Continue" after round 3
- Guide opens the session by prompting with the concept name: "What do you know about X?"
- Full conversation history passed to each agent every turn (no sliding window)

### SSE Event Protocol
- Rich event vocabulary: session_start, turn_start, token, turn_complete, round_complete, session_complete
- Token events carry text only — role info comes from the preceding turn_start event
- Analysis data (blind spots, scores) stays server-side, only surfaces in the final report
- LLM failures: silent retry up to 2 attempts, then send error event and close stream

### Session Lifecycle
- "Stop and Diagnose": immediate cancel of in-flight LLM call, generate summary from accumulated data, send session_complete
- No timeout for abandoned sessions — sessions stay active until explicitly stopped
- Sessions are resumable — user can return to an active session and continue dialogue
- One active session per user at a time — starting a new session auto-stops the previous one

### Scoring & Analysis
- Blind spots extracted from every agent turn (both Guide and Challenger), stored immediately in CogTestBlindSpot
- CogTestSnapshot created per round + one final aggregated snapshot at session end
- Round-level understanding_score: Challenger-weighted average (Challenger ~60%, Guide ~40%)
- Duplicate blind spots stored as-is — deduplication happens at report generation time

### Claude's Discretion
- Exact retry backoff strategy for LLM failures
- How to aggregate the final session-level understanding score from round snapshots
- Internal data structures for managing the turn scheduler state
- How to detect and cancel in-flight LLM calls on stop

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cog_test_prompts.py`: Guide and Challenger system prompts with temperatures (0.4, 0.6) — ready to use
- `cog_test_parser.py`: `parse_agent_output()` extracts dialogue + analysis JSON, `extract_dialogue_only()` for fast path — never raises
- `llm_service.stream_generate()`: async generator yielding tokens, supports OpenAI and Anthropic providers
- `EventSourceResponse` from sse-starlette: already used in test endpoint pattern

### Established Patterns
- FastAPI router with `APIRouter(prefix="/cog-test")` already registered at `/api/cog-test`
- Auth via `Depends(get_current_user)` on all endpoints
- SQLAlchemy async models with UUID string PKs, `relationship()` for navigation
- JWT auth via query param for SSE (EventSource cannot send custom headers)

### Integration Points
- `cog_test.py` router: currently has test endpoint, will be expanded with session CRUD and stream endpoints
- DB models in `user.py`: CogTestSession (status, agent_mode), CogTestTurn (turn_index, role, dialogue_text, analysis_json), CogTestBlindSpot, CogTestSnapshot
- `api/__init__.py`: cog_test_router already included in api_router

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-backend-engine*
*Context gathered: 2026-02-28*
