# Phase 1: Foundation - Research

**Researched:** 2026-02-28
**Domain:** SQLAlchemy ORM schema migration, LLM async streaming, Socratic agent prompt engineering
**Confidence:** HIGH (codebase directly inspected; patterns verified against existing code)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Agent personas and tone:**
- Guide agent: warm companion style, patient and encouraging, uses "你觉得呢？" / "如果是这样的话…" to lead thinking
- Challenger agent: easygoing but precise, affirm before questioning, uses "有意思，不过如果换个角度看…"
- Both speak Chinese, conversational register, no academic tone
- Socratic contract: never state the answer directly, only guide through questions

**Agent output format:**
- User-facing reply: natural dialogue text (not structured markdown)
- System-facing analysis: JSON structured output (blind spot extraction, scoring) — invisible to user
- Every agent call produces two parts: dialogue text + hidden analysis JSON
- Use JSON-mode not regex for extraction (research flags regex silent failure as highest risk)

**Blind spot taxonomy:**
- `factual_error`: factual mistake (concept misunderstood)
- `incomplete_reasoning`: incomplete reasoning (logic chain broken)
- `hidden_assumption`: hidden assumption (untested premise)
- `surface_understanding`: surface understanding (can recite but cannot apply)

**Understanding score:**
- Coarse 3-level: `low` / `medium` / `high`
- Shown in reports as descriptive text, not percentage numbers
- Never shown during live session — report only

### Claude's Discretion

- DB table field design and index strategy
- LLM streaming implementation (AsyncOpenAI vs httpx streaming)
- Alembic migration vs auto-create choice
- Agent system prompt exact wording (must follow persona constraints above)
- sse-starlette specific integration approach

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFR-01 | 认知测试相关数据表合并到现有SQLAlchemy/SQLite数据库 | ORM model pattern from user.py; auto-create via `Base.metadata.create_all` in lifespan; Alembic 1.14.0 already in requirements.txt |
| INFR-02 | AI调用复用现有agno + LLM service层，不引入新的AI SDK | LLMService in llm_service.py confirmed; needs `stream_generate()` async generator added; all three providers (openai/anthropic/ollama) need streaming variants |
| INFR-03 | 后端新增sse-starlette依赖支持SSE事件流 | sse-starlette 1.8.2 compatible with FastAPI 0.115.0 / Starlette 0.40.x; not yet in requirements.txt |
</phase_requirements>

---

## Summary

Phase 1 locks three things before any implementation work begins: the database schema (four new ORM tables), the LLM streaming extension (one new method on the existing `LLMService`), and the agent system prompts (validated against the Socratic contract). These are the foundation everything else depends on — getting any of them wrong requires rewrites across all downstream phases.

The codebase inspection reveals the app uses `Base.metadata.create_all` in the FastAPI lifespan hook, not Alembic migrations. Alembic 1.14.0 is already in `requirements.txt` but no `alembic/` directory exists — the project has never run a migration. All tables were created via auto-create. For Phase 1, the simplest correct approach is to continue with auto-create: add the four new ORM models, register them in `entities/__init__.py`, and they will be created on next app startup. The success criterion says "Alembic migration applies cleanly" — this means Alembic must be initialized and a migration written, even though the project currently uses auto-create. Plan for both: write the ORM models first, then set up Alembic and generate the migration.

The `LLMService` currently uses synchronous OpenAI/Anthropic clients wrapped in async functions — this is not true async streaming. The `stream_generate()` method must use `AsyncOpenAI` with `stream=True` for OpenAI, `AsyncAnthropic` with `stream=True` for Anthropic, and `httpx.AsyncClient` with `stream=True` for Ollama. The method is an async generator yielding string tokens. This is the first task and blocks all subsequent phases.

Agent prompt engineering is the highest-risk deliverable. The Guide must end every response with exactly one question and never state the answer. The Challenger must acknowledge what the learner got right before raising a challenge. Both must produce a hidden JSON block after the dialogue text for blind spot extraction. The dual-output format must be validated with real test prompts before Phase 2 begins.

**Primary recommendation:** ORM models → Alembic init + migration → `stream_generate()` with test endpoint → Guide prompt → Challenger prompt → dual-output schema validation.

---

## Standard Stack

### Core (existing — reuse, do not replace)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy async | 2.0.35 | ORM + async DB sessions | Already in use; `AsyncSession` pattern established across all routes |
| aiosqlite | (transitive) | Async SQLite driver | Powers `sqlite+aiosqlite://` connection string in database.py |
| FastAPI | 0.115.0 | HTTP framework | Already in use; lifespan hook handles table creation |
| openai | 1.54.0 | OpenAI API client | Already installed; has `AsyncOpenAI` for true async streaming |
| anthropic | 0.37.0 | Anthropic API client | Already installed; has `AsyncAnthropic` for true async streaming |
| httpx | 0.27.2 | HTTP client for Ollama | Already installed; supports async streaming via `AsyncClient` |
| pydantic | 2.9.2 | Schema validation + JSON parsing | Already installed; use for agent output schema validation |
| alembic | 1.14.0 | DB migrations | Already in requirements.txt; needs `alembic init` to create directory |

### New Addition

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| sse-starlette | 1.8.2 | Named SSE event framing | Required for typed events (`turn_start`, `token`, `done`); compatible with FastAPI 0.115 / Starlette 0.40.x |

### Not Needed in Phase 1

| Library | Reason |
|---------|--------|
| agno | Phase 1 uses LLMService directly for prompt validation; agno Team orchestration is Phase 2 |
| python-statemachine | Turn scheduler is Phase 2 |

**Installation:**
```bash
pip install sse-starlette==1.8.2
# Add to requirements.txt: sse-starlette==1.8.2
```

---

## Architecture Patterns

### Pattern 1: ORM Model — Established Project Pattern

Follow the exact pattern from `user.py`. Every new model:
- Inherits from `Base` (from `app.core.database`)
- UUID string(36) PK with `default=lambda: str(uuid.uuid4())`
- `created_at` with `default=datetime.utcnow`
- FK columns as `String(36)` matching the PK type
- Relationships via `relationship()` + `back_populates`

New file: `las_backend/app/models/entities/cog_test.py`

Four tables:
- `CogTestSession`: root session (user_id FK, model_card_id FK, status, current_round, understanding_level)
- `CogTestTurn`: one agent utterance per turn (session_id FK, round, agent, content)
- `CogTestBlindSpot`: extracted cognitive gap (session_id FK, round, category, description, source_agent)
- `CogTestSnapshot`: per-round state tree JSON (session_id FK, version, trigger, state_tree JSON)

Index strategy (Claude discretion):
- `CogTestSession`: index on `user_id`, `model_card_id`
- `CogTestTurn`, `CogTestBlindSpot`, `CogTestSnapshot`: index on `session_id`

Register in `entities/__init__.py`:
```python
from app.models.entities.cog_test import CogTestSession, CogTestTurn, CogTestBlindSpot, CogTestSnapshot
```
Add all four to `__all__`.

### Pattern 2: Alembic Setup (first-time initialization)

`alembic==1.14.0` is in `requirements.txt` but no `alembic/` directory exists.
The success criterion explicitly requires "Alembic migration applies cleanly."

Steps:
```bash
cd las_backend
alembic init alembic
# Edit alembic/env.py — import Base and all models
# Edit alembic.ini — set sqlalchemy.url
alembic revision --autogenerate -m "add cog test tables"
alembic upgrade head
```

Critical `env.py` change: import all models before autogenerate runs, or the migration will be empty:
```python
from app.core.database import Base
from app.models.entities import *  # noqa — triggers all model imports
target_metadata = Base.metadata
```

The async SQLite driver requires `run_sync` in `env.py`. Use the standard async Alembic pattern:
```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

def run_migrations_online():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async def do_run():
        async with connectable.connect() as connection:
            await connection.run_sync(do_migrations)
    asyncio.run(do_run())
```

### Pattern 3: LLMService `stream_generate()` Method

The existing `generate()` uses synchronous clients (`openai.OpenAI`, not `AsyncOpenAI`).
The new method must use async clients and be an async generator yielding string tokens.

Method signature:
```python
async def stream_generate(
    self,
    prompt: str,
    system_prompt: Optional[str] = None,
    provider_type: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
```

Provider implementations:
- **OpenAI**: `AsyncOpenAI` + `client.chat.completions.stream()` -> iterate `stream.text_stream`
- **Anthropic**: `AsyncAnthropic` + `client.messages.stream()` -> iterate `stream.text_stream`
- **Ollama**: `httpx.AsyncClient` + `client.stream("POST", ...)` -> `aiter_lines()` -> parse JSON `response` field

Temperature guidance (Claude discretion):
- Guide agent: `0.4` (consistent, warm, predictable)
- Challenger agent: `0.6` (slightly more varied for creative questioning)

Test endpoint to verify before Phase 2:
```python
@router.get("/test-stream")
async def test_stream():
    from sse_starlette.sse import EventSourceResponse
    async def gen():
        async for token in llm_service.stream_generate("用一句话解释什么是递归"):
            yield {"data": token}
    return EventSourceResponse(gen())
```
Remove this endpoint after validation.

### Pattern 4: Agent Dual-Output Format

Every agent call produces dialogue text + hidden analysis JSON block.
The JSON block is extracted by the system and never shown to the user.

**Delimiter approach:** `<analysis>...</analysis>` tag appended after dialogue text.

Why not pure JSON-mode: LLM must produce natural dialogue text first, then structured JSON. Pure JSON-mode forces the entire output to be JSON, breaking the conversational text requirement.

Analysis JSON schema:
```json
{
  "blind_spots": [
    {
      "category": "factual_error",
      "description": "specific description of the cognitive gap"
    }
  ],
  "understanding_level": "low",
  "reasoning": "brief explanation of the score"
}
```

Valid `category` values: `factual_error`, `incomplete_reasoning`, `hidden_assumption`, `surface_understanding`

Valid `understanding_level` values: `low`, `medium`, `high`

Extraction logic:
```python
def parse_agent_output(raw_output: str) -> AgentOutput:
    parts = raw_output.split("<analysis>")
    dialogue_text = parts[0].strip()
    if len(parts) < 2:
        # Log warning — never silently swallow failures
        print(f"[WARN] No <analysis> block found. Raw: {raw_output[:200]}")
        return AgentOutput(dialogue_text=dialogue_text, blind_spots=[],
                           understanding_level="low", parse_success=False)
    json_part = parts[1].replace("</analysis>", "").strip()
    try:
        data = json.loads(json_part)
        return AgentOutput(
            dialogue_text=dialogue_text,
            blind_spots=data.get("blind_spots", []),
            understanding_level=data.get("understanding_level", "low"),
            reasoning=data.get("reasoning", ""),
            parse_success=True,
        )
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON parse failed: {e}. Raw: {json_part[:200]}")
        return AgentOutput(dialogue_text=dialogue_text, blind_spots=[],
                           understanding_level="low", parse_success=False)
```

### Pattern 5: Socratic Contract Enforcement in Prompts

The highest-risk prompt engineering requirement is preventing answer-drift.

**Guide agent hard constraints (include verbatim in system prompt):**
- Every response MUST end with exactly one question
- If learner asks for the answer directly, respond with another question
- Forbidden phrases: "答案是", "正确答案", "其实是", "应该是"
- Required: at least one of "你觉得", "你认为", "如果", "为什么", "怎么" per response

**Challenger agent hard constraints:**
- First sentence MUST acknowledge something the learner got right
- Forbidden: "你错了", "不对", "这是错误的"
- Required: affirmation phrase before any challenge
- Challenge framing: "有意思，不过...", "你说得有道理，我有个疑问..."

**Validation approach (Phase 1 deliverable):**
Write 5 adversarial test prompts that try to extract answers (e.g., "直接告诉我答案", "你就说对不对").
Verify Guide responds with a question, not an answer.
Write 3 test prompts with partially correct answers.
Verify Challenger affirms before questioning.
Document results before Phase 2 begins.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async LLM streaming | Custom httpx streaming wrapper from scratch | `AsyncOpenAI.chat.completions.stream()` / `AsyncAnthropic.messages.stream()` | Official async streaming APIs handle backpressure, error recovery, and token counting correctly |
| SSE event framing | Manual `data: ...\n\n` string formatting | `sse-starlette` `EventSourceResponse` | Handles retry headers, event IDs, named event types, and proper connection lifecycle |
| JSON extraction from LLM output | Regex patterns | `<analysis>` delimiter + `json.loads()` | Regex silently fails on whitespace variations; JSON parse raises explicit exceptions that can be logged |
| DB session management | Manual `AsyncSession` open/close | `AsyncSessionLocal()` context manager (already established) | Existing pattern handles commit/rollback/close correctly |
| UUID generation | `str(uuid.uuid4())` inline everywhere | `default=lambda: str(uuid.uuid4())` on Column | Consistent with all existing models; avoids forgetting to set ID |

**Key insight:** The LLM streaming APIs in `openai` 1.54.0 and `anthropic` 0.37.0 already support async streaming natively. Do not build a custom streaming layer — use `AsyncOpenAI` and `AsyncAnthropic` directly.

---

## Common Pitfalls

### Pitfall 1: Alembic autogenerate produces empty migration

**What goes wrong:** Running `alembic revision --autogenerate` generates a migration with empty `upgrade()` and `downgrade()` functions.
**Why it happens:** The models were not imported before autogenerate ran, so SQLAlchemy's metadata has no tables registered.
**How to avoid:** In `alembic/env.py`, import all model modules before `target_metadata = Base.metadata`. The import of `from app.models.entities import *` must happen at module level, not inside a function.
**Warning signs:** Migration file shows `pass` in both `upgrade()` and `downgrade()`.

### Pitfall 2: Sync OpenAI client inside async generator causes blocking

**What goes wrong:** Using `openai.OpenAI` (sync) inside an `async def` function. The call blocks the event loop during the entire LLM response, making SSE appear to hang until the full response is ready.
**Why it happens:** The existing `_generate_openai()` uses sync `openai.OpenAI` — easy to copy this pattern into the new streaming method.
**How to avoid:** Use `from openai import AsyncOpenAI` in `stream_generate()`. Never use the sync client in an async context.
**Warning signs:** Test endpoint returns all tokens at once after a long pause instead of streaming them progressively.

### Pitfall 3: Agent outputs analysis JSON without the delimiter tag

**What goes wrong:** The LLM produces the JSON block but without the `<analysis>` tag, or with a slightly different tag name. The parser splits on `<analysis>` and finds nothing, returning `parse_success=False` for every call.
**Why it happens:** LLMs sometimes paraphrase instructions. If the prompt says "output a JSON block" without specifying the exact delimiter, the model may use different formatting.
**How to avoid:** Include the exact delimiter string in the system prompt with an example. Test with 3-5 real prompts before locking the prompt.
**Warning signs:** Every call returns `parse_success=False` in logs.

### Pitfall 4: Guide agent drifts into answer-giving under pressure

**What goes wrong:** When the learner says "I don't know, just tell me," the Guide agent gives the answer.
**Why it happens:** LLMs are trained to be helpful. Without explicit negative constraints, helpfulness overrides the Socratic contract.
**How to avoid:** Include explicit forbidden phrases in the system prompt. Add a meta-instruction: "If the learner asks for the answer directly, respond with a question that helps them discover it themselves."
**Warning signs:** During validation testing, the agent produces sentences starting with "答案是" or "正确的理解是".

### Pitfall 5: Challenger agent sounds hostile instead of curious

**What goes wrong:** The Challenger's questions feel like accusations rather than genuine curiosity. Learner disengages.
**Why it happens:** "Challenge" framing in the prompt activates adversarial language patterns.
**How to avoid:** Frame the Challenger as "curious" not "challenging." Use "我有个疑问" not "你的理解有问题." Require affirmation before every challenge. Test with real learners if possible.
**Warning signs:** During validation, Challenger responses start with "但是" or "不对" without prior affirmation.

### Pitfall 6: CogTestSnapshot relationship points to wrong class

**What goes wrong:** `CogTestSnapshot.session` relationship uses `back_populates="snapshots"` but the target class name is wrong, causing SQLAlchemy mapper error on startup.
**Why it happens:** Copy-paste error when writing the ORM model.
**How to avoid:** Double-check that `relationship("CogTestSession", back_populates="snapshots")` matches the `snapshots` relationship name on `CogTestSession`.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError` on app startup.

---

## Code Examples

### ORM Model Registration Pattern (from existing codebase)

```python
# las_backend/app/models/entities/__init__.py — current pattern
from app.models.entities.user import User, Problem, ModelCard, EvolutionLog, Conversation, PracticeTask, PracticeSubmission, Review
from app.models.entities.email_config import EmailConfig
from app.models.entities.system_settings import SystemSettings
from app.models.entities.llm_provider import LLMProvider, LLMModel

__all__ = ["User", "Problem", ...]

# Add new line:
from app.models.entities.cog_test import CogTestSession, CogTestTurn, CogTestBlindSpot, CogTestSnapshot
# Add to __all__: "CogTestSession", "CogTestTurn", "CogTestBlindSpot", "CogTestSnapshot"
```

### Auto-create Pattern (from main.py lifespan)

```python
# main.py — existing pattern, no changes needed
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # creates all registered tables
    yield
```

New tables are created automatically once their models are imported and registered in `__init__.py`.

### Async Generator Type Hint

```python
from typing import AsyncGenerator, Optional

async def stream_generate(
    self,
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    # yield tokens
    yield "token"
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `openai.OpenAI` (sync) | `openai.AsyncOpenAI` with `.stream()` | True async streaming; non-blocking event loop |
| `anthropic.Anthropic` (sync) | `anthropic.AsyncAnthropic` with `.stream()` | Same — async streaming |
| Regex extraction from LLM output | Delimiter tag + `json.loads()` | Explicit failures vs silent empty results |
| Alembic not initialized | `alembic init` + autogenerate | Reproducible schema migrations |

**Deprecated/outdated in this codebase:**
- Sync `openai.OpenAI` client in async functions: works but blocks event loop; replace with `AsyncOpenAI` in `stream_generate()`
- `Base.metadata.create_all` only: sufficient for development but not for production schema management; Alembic migration is the explicit Phase 1 deliverable

---

## Open Questions

1. **Alembic async env.py pattern for SQLite**
   - What we know: Alembic 1.14.0 supports async engines; SQLite+aiosqlite requires `run_sync`
   - What's unclear: Whether the standard async Alembic template works out-of-the-box with `sqlite+aiosqlite://` or needs additional configuration
   - Recommendation: Use the `asyncio` run pattern in `env.py`; test with `alembic upgrade head` immediately after setup

2. **OpenAI streaming API method name in openai 1.54.0**
   - What we know: `AsyncOpenAI` exists in openai 1.54.0; streaming is supported
   - What's unclear: Whether the method is `.stream()` or `.create(stream=True)` in this exact version
   - Recommendation: Check `openai` 1.54.0 docs or test directly; both patterns exist across versions

3. **Agent prompt validation scope**
   - What we know: Prompts must be validated before Phase 2
   - What's unclear: How many test cases are sufficient to declare prompts "validated"
   - Recommendation: Minimum 5 adversarial prompts (answer-seeking) + 3 partial-answer prompts; document results

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `las_backend/app/services/llm_service.py` — confirmed sync clients, no streaming
- Direct codebase inspection: `las_backend/app/models/entities/user.py` — confirmed ORM patterns (UUID PK, datetime defaults, relationships)
- Direct codebase inspection: `las_backend/app/main.py` — confirmed auto-create via lifespan hook
- Direct codebase inspection: `las_backend/requirements.txt` — confirmed alembic 1.14.0, openai 1.54.0, anthropic 0.37.0, httpx 0.27.2
- Direct codebase inspection: `las_backend/app/core/database.py` — confirmed AsyncSession, sqlite+aiosqlite URL
- Project-level ARCHITECTURE.md — DB schema design, component boundaries, build order
- Project-level STACK.md — sse-starlette 1.8.2 compatibility verified

### Secondary (MEDIUM confidence)
- Project-level SUMMARY.md — pitfall analysis (answer-drift, silent extraction failure, hostile challenger)
- Project-level CONTEXT.md — locked decisions on agent personas, output format, blind spot taxonomy

### Tertiary (LOW confidence)
- None — all critical claims verified against direct codebase inspection or project research files

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries directly verified in requirements.txt and codebase
- Architecture: HIGH — ORM patterns verified from user.py; streaming patterns from official SDK docs
- Pitfalls: HIGH — most pitfalls derived from direct code inspection (sync clients, no Alembic dir)

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable libraries; openai/anthropic streaming APIs change infrequently)
