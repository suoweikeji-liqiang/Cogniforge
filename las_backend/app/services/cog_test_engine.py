"""
CogTestEngine — orchestrates Guide/Challenger turn scheduling and scoring.
Phase 02-01: TurnScheduler, CogTestEngine skeleton, engine registry.
Full run() loop implemented in phase 02-02.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.user import (
    CogTestBlindSpot,
    CogTestSession,
    CogTestSnapshot,
    CogTestTurn,
)
from app.services.cog_test_parser import AgentOutput, parse_agent_output
from app.services.cog_test_prompts import (
    CHALLENGER_SYSTEM_PROMPT,
    CHALLENGER_TEMPERATURE,
    GUIDE_SYSTEM_PROMPT,
    GUIDE_TEMPERATURE,
)
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LEVEL_TO_FLOAT: dict[str, float] = {
    "low": 0.33,
    "medium": 0.66,
    "high": 1.0,
}

_SOCRATIC_FORBIDDEN: list[str] = [
    "答案是",
    "正确答案",
    "其实是",
    "应该是",
    "正确的理解是",
    "the answer is",
    "correct answer",
]


# ---------------------------------------------------------------------------
# Scoring helpers (module-level for backward-compat imports)
# ---------------------------------------------------------------------------

def calculate_round_score(guide_level: str, challenger_level: str) -> float:
    """
    Challenger-weighted blend: Guide 40%, Challenger 60%.
    Returns a float rounded to 2 decimal places.
    """
    g = _LEVEL_TO_FLOAT.get(guide_level, 0.0)
    c = _LEVEL_TO_FLOAT.get(challenger_level, 0.0)
    return round(g * 0.4 + c * 0.6, 2)


def aggregate_session_score(round_scores: list[float]) -> float:
    """Simple average of round scores; returns 0.0 for empty list."""
    if not round_scores:
        return 0.0
    return round(sum(round_scores) / len(round_scores), 2)


# ---------------------------------------------------------------------------
# TurnScheduler
# ---------------------------------------------------------------------------

class TurnScheduler:
    """
    Tracks which agent should speak next and which round we are in.

    Alternation within a round:
        Guide speaks → user responds → Challenger speaks → user responds
        → round_number increments → repeat

    round_number starts at 1.
    is_session_complete is True when round_number > max_rounds.
    """

    def __init__(self, max_rounds: int = 3) -> None:
        self.max_rounds = max_rounds
        self.round_number: int = 1
        self._agent_is_guide: bool = True   # Guide goes first

    def current_agent(self) -> str:
        """Return 'guide' or 'challenger'."""
        return "guide" if self._agent_is_guide else "challenger"

    def advance(self) -> None:
        """
        Flip to the other agent.
        When Challenger finishes (i.e. we were NOT on guide), increment round.
        """
        was_guide = self._agent_is_guide
        self._agent_is_guide = not self._agent_is_guide
        if not was_guide:
            # Challenger just finished — new round begins
            self.round_number += 1

    @property
    def is_session_complete(self) -> bool:
        return self.round_number > self.max_rounds


# ---------------------------------------------------------------------------
# CogTestEngine
# ---------------------------------------------------------------------------

class CogTestEngine:
    """
    Orchestrates a single cognitive-test session.

    Attributes:
        session_id  — DB session UUID
        concept     — topic being tested
        scheduler   — TurnScheduler instance
        history     — list of message dicts passed to LLM
        _stop_event — asyncio.Event; set to request graceful stop
        _current_task — asyncio.Task for the in-flight LLM call
        _turn_index — monotonically increasing turn counter
        _user_input_queue — asyncio.Queue for user text submissions
    """

    def __init__(self, session_id: str, concept: str, max_rounds: int = 3) -> None:
        self.session_id = session_id
        self.concept = concept
        self.scheduler = TurnScheduler(max_rounds=max_rounds)
        self.history: list[dict] = []
        self._stop_event: asyncio.Event = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None
        self._turn_index: int = 0
        self._user_input_queue: asyncio.Queue = asyncio.Queue()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Signal the engine to stop and cancel any in-flight LLM task."""
        self._stop_event.set()
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

    async def submit_user_turn(self, text: str) -> None:
        """
        Enqueue user text so run() can advance.

        Also appends the user message to history so the LLM has context
        for the next agent turn.
        """
        self.history.append({"role": "user", "content": text})
        await self._user_input_queue.put(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _violates_socratic_contract(self, dialogue_text: str) -> bool:
        """Return True if the text contains any forbidden direct-answer phrase."""
        lower = dialogue_text.lower()
        for phrase in _SOCRATIC_FORBIDDEN:
            if phrase.lower() in lower:
                return True
        return False

    @staticmethod
    def _make_sse(event: str, data: str) -> dict:
        """Build an SSE event dict."""
        return {"event": event, "data": data}

    # ------------------------------------------------------------------
    # Private: LLM turn execution (plain coroutine)
    # ------------------------------------------------------------------

    async def _run_agent_turn(
        self,
        db: AsyncSession,
        role: str,
    ) -> tuple[Optional[AgentOutput], list[dict], bool]:
        """
        Run one agent turn.

        Returns (parsed_output, token_events, llm_failed).

        token_events is a list of SSE dicts {"event": "token", "data": "..."}.
        If the LLM fails after all retries, llm_failed=True, parsed_output=None,
        and token_events contains a single error SSE event.

        LLM exception retry is the inner loop (up to 3 attempts with exponential
        backoff).  Socratic contract retry is the OUTER loop (in run()) that
        re-calls this method.
        """
        system_prompt = GUIDE_SYSTEM_PROMPT if role == "guide" else CHALLENGER_SYSTEM_PROMPT
        temperature = GUIDE_TEMPERATURE if role == "guide" else CHALLENGER_TEMPERATURE

        buffer: list[str] = []
        token_events: list[dict] = []

        for llm_attempt in range(3):  # Layer 1: LLM exception retry
            buffer = []
            token_events = []
            try:
                async for token in llm_service.stream_generate(
                    messages=self.history,
                    system_prompt=system_prompt,
                    temperature=temperature,
                ):
                    buffer.append(token)
                    token_events.append(self._make_sse("token", token))
                break  # stream completed without exception — exit retry loop
            except Exception as exc:
                if llm_attempt < 2:
                    wait = (2 ** llm_attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "stream_generate failed (attempt %d/3), retrying in %.1fs: %s",
                        llm_attempt + 1,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "stream_generate failed after 3 attempts, session=%s: %s",
                        self.session_id,
                        exc,
                    )
                    error_event = self._make_sse(
                        "error",
                        json.dumps({"message": "LLM unavailable, session ended"}),
                    )
                    return None, [error_event], True

        full_response = "".join(buffer)
        parsed = parse_agent_output(full_response)
        await self._persist_turn(db, role, self.scheduler.round_number, parsed, full_response)
        return parsed, token_events, False

    # ------------------------------------------------------------------
    # Private: DB persistence
    # ------------------------------------------------------------------

    async def _persist_turn(
        self,
        db: AsyncSession,
        role: str,
        round_number: int,
        parsed: AgentOutput,
        raw_text: str,
    ) -> None:
        """Persist one agent turn + its blind spots to the DB."""
        turn = CogTestTurn(
            session_id=self.session_id,
            turn_index=self._turn_index,
            round_number=round_number,
            role=role,
            dialogue_text=parsed.dialogue_text,
            analysis_json=raw_text,
            understanding_level=parsed.understanding_level,
        )
        db.add(turn)
        # Flush to get turn.id before adding blind spots
        await db.flush()

        for spot in parsed.blind_spots:
            blind_spot = CogTestBlindSpot(
                session_id=self.session_id,
                turn_id=turn.id,
                category=spot.category,
                description=spot.description,
            )
            db.add(blind_spot)

        # Append agent dialogue to history
        self.history.append({"role": "assistant", "content": parsed.dialogue_text})
        self._turn_index += 1

        await db.commit()

    async def _save_snapshot(
        self,
        db: AsyncSession,
        round_number: Optional[int],
        round_scores: list[float],
        guide_level: Optional[str] = None,
        challenger_level: Optional[str] = None,
    ) -> None:
        """
        Persist a CogTestSnapshot.

        If round_number is not None: calculate per-round score using
        guide_level + challenger_level for that round.
        If round_number is None (final): use aggregate_session_score.
        """
        if round_number is not None and guide_level and challenger_level:
            score = calculate_round_score(guide_level, challenger_level)
        else:
            score = aggregate_session_score(round_scores)

        # Count blind spots for this session so far
        blind_spot_count = sum(
            len(m.get("blind_spots", [])) for m in []
        )
        # Query DB for blind spot count
        from sqlalchemy import select, func
        result = await db.execute(
            select(func.count(CogTestBlindSpot.id)).where(
                CogTestBlindSpot.session_id == self.session_id
            )
        )
        blind_spot_count = result.scalar_one() or 0

        snapshot_data = {
            "session_id": self.session_id,
            "round_number": round_number,
            "score": score,
            "blind_spot_count": blind_spot_count,
            "round_scores": round_scores,
        }

        snapshot = CogTestSnapshot(
            session_id=self.session_id,
            round_number=round_number,
            understanding_score=str(score),
            blind_spot_count=blind_spot_count,
            snapshot_json=json.dumps(snapshot_data),
        )
        db.add(snapshot)
        await db.commit()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, db: AsyncSession) -> AsyncGenerator:
        """
        Main engine loop — yields SSE event dicts.

        Event sequence:
            session_start
            [per round]:
                turn_start (guide)
                token... (guide)
                turn_complete (guide)
                [wait for user input]
                turn_start (challenger)
                token... (challenger)
                turn_complete (challenger)
                [wait for user input]
                round_complete
            session_complete
        """
        # Track per-round understanding levels for scoring
        round_guide_levels: dict[int, str] = {}
        round_challenger_levels: dict[int, str] = {}
        round_scores: list[float] = []
        session_completed_normally = False

        try:
            # --- session_start ---
            yield self._make_sse(
                "session_start",
                json.dumps({
                    "session_id": self.session_id,
                    "concept": self.concept,
                    "max_rounds": self.scheduler.max_rounds,
                }),
            )

            while not self.scheduler.is_session_complete and not self._stop_event.is_set():
                role = self.scheduler.current_agent()
                current_round = self.scheduler.round_number

                # --- turn_start ---
                yield self._make_sse(
                    "turn_start",
                    json.dumps({"role": role, "round": current_round}),
                )

                # --- Layer 2: Socratic contract retry (outer loop) ---
                parsed: Optional[AgentOutput] = None
                for socratic_attempt in range(3):
                    agent_parsed, token_events, llm_failed = await self._run_agent_turn(db, role)

                    # Re-yield all token events from this attempt
                    for evt in token_events:
                        yield evt

                    if llm_failed:
                        # LLM exhausted — error event already yielded inside token_events
                        return  # close generator cleanly

                    parsed = agent_parsed

                    # Check Socratic contract
                    if not self._violates_socratic_contract(parsed.dialogue_text):
                        break  # Contract satisfied

                    if socratic_attempt < 2:
                        wait = (2 ** socratic_attempt) + random.uniform(0, 0.5)
                        logger.warning(
                            "Socratic contract violated (attempt %d/3), "
                            "retrying in %.1fs, session=%s",
                            socratic_attempt + 1,
                            wait,
                            self.session_id,
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.warning(
                            "Socratic contract violated after 2 retries, "
                            "proceeding anyway, session=%s",
                            self.session_id,
                        )

                if parsed is None:
                    # Should not happen — but guard defensively
                    yield self._make_sse(
                        "error",
                        json.dumps({"message": "Agent turn failed unexpectedly"}),
                    )
                    return

                # Track understanding level per role per round
                if role == "guide":
                    round_guide_levels[current_round] = parsed.understanding_level
                else:
                    round_challenger_levels[current_round] = parsed.understanding_level

                # --- turn_complete ---
                yield self._make_sse(
                    "turn_complete",
                    json.dumps({
                        "role": role,
                        "round": current_round,
                        "turn_index": self._turn_index - 1,
                    }),
                )

                # Advance scheduler (flips agent, increments round after Challenger)
                self.scheduler.advance()

                # If Challenger just finished — round is complete
                # The advance() call already incremented round_number
                round_just_finished = (role == "challenger")

                if round_just_finished:
                    # Calculate and persist round snapshot
                    guide_lvl = round_guide_levels.get(current_round, "low")
                    challenger_lvl = round_challenger_levels.get(current_round, "low")
                    round_score = calculate_round_score(guide_lvl, challenger_lvl)
                    round_scores.append(round_score)

                    await self._save_snapshot(
                        db,
                        round_number=current_round,
                        round_scores=round_scores,
                        guide_level=guide_lvl,
                        challenger_level=challenger_lvl,
                    )

                    yield self._make_sse(
                        "round_complete",
                        json.dumps({"round": current_round}),
                    )

                # Wait for user input before next agent turn
                # (unless session is now complete or stop requested)
                if not self.scheduler.is_session_complete and not self._stop_event.is_set():
                    await self._user_input_queue.get()

            # --- Session completed normally ---
            session_completed_normally = True
            rounds_completed = self.scheduler.round_number - 1

            # Final aggregated snapshot
            await self._save_snapshot(
                db,
                round_number=None,
                round_scores=round_scores,
            )

            yield self._make_sse(
                "session_complete",
                json.dumps({
                    "status": "completed",
                    "rounds_completed": rounds_completed,
                }),
            )

        except asyncio.CancelledError:
            # Propagate — finally block handles cleanup
            raise

        finally:
            if not session_completed_normally:
                rounds_completed = max(0, self.scheduler.round_number - 1)
                try:
                    await self._save_snapshot(
                        db,
                        round_number=None,
                        round_scores=round_scores,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to save final snapshot on stop, session=%s: %s",
                        self.session_id,
                        exc,
                    )

                yield self._make_sse(
                    "session_complete",
                    json.dumps({
                        "status": "stopped",
                        "rounds_completed": rounds_completed,
                    }),
                )

            unregister_engine(self.session_id)


# ---------------------------------------------------------------------------
# Engine registry
# ---------------------------------------------------------------------------

_engines: dict[str, CogTestEngine] = {}


def get_engine(session_id: str) -> Optional[CogTestEngine]:
    """Return the engine for session_id, or None if not registered."""
    return _engines.get(session_id)


def register_engine(session_id: str, engine: CogTestEngine) -> None:
    """Register an engine under session_id."""
    _engines[session_id] = engine


def unregister_engine(session_id: str) -> None:
    """Remove the engine for session_id (no-op if not present)."""
    _engines.pop(session_id, None)
