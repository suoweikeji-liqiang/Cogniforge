"""
CogTestEngine — orchestrates Guide/Challenger turn scheduling and scoring.
Phase 02-01: TurnScheduler, CogTestEngine skeleton, engine registry.
Full run() loop implemented in phase 02-02.
"""
from __future__ import annotations

import asyncio
from typing import Optional

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
    """

    def __init__(self, session_id: str, concept: str, max_rounds: int = 3) -> None:
        self.session_id = session_id
        self.concept = concept
        self.scheduler = TurnScheduler(max_rounds=max_rounds)
        self.history: list[dict] = []
        self._stop_event: asyncio.Event = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None
        self._turn_index: int = 0

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
    def calculate_round_score(guide_level: str, challenger_level: str) -> float:
        """
        Challenger-weighted blend: Guide 40%, Challenger 60%.
        Returns a float rounded to 2 decimal places.
        """
        g = _LEVEL_TO_FLOAT.get(guide_level, 0.0)
        c = _LEVEL_TO_FLOAT.get(challenger_level, 0.0)
        return round(g * 0.4 + c * 0.6, 2)

    @staticmethod
    def aggregate_session_score(round_scores: list[float]) -> float:
        """Simple average of round scores; returns 0.0 for empty list."""
        if not round_scores:
            return 0.0
        return round(sum(round_scores) / len(round_scores), 2)

    # ------------------------------------------------------------------
    # Main loop (stub — implemented in phase 02-02)
    # ------------------------------------------------------------------

    async def run(self, db):
        """Main engine loop — implemented in phase 02-02."""
        raise NotImplementedError


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
