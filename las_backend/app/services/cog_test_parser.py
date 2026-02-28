"""
Parser utility for cognitive test agent output.

Agents produce two parts in every response:
  1. Dialogue text (shown to user)
  2. <analysis>...</analysis> block (hidden, parsed here)

This module extracts and validates the analysis block.
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "factual_error",
    "incomplete_reasoning",
    "hidden_assumption",
    "surface_understanding",
}

VALID_UNDERSTANDING_LEVELS = {"low", "medium", "high"}


class BlindSpot(BaseModel):
    category: str
    description: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{v}'. Must be one of: {sorted(VALID_CATEGORIES)}"
            )
        return v


class AgentOutput(BaseModel):
    """Parsed output from a Guide or Challenger agent call."""

    dialogue_text: str
    blind_spots: list[BlindSpot]
    understanding_level: str
    reasoning: str
    parse_success: bool

    @field_validator("understanding_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in VALID_UNDERSTANDING_LEVELS:
            raise ValueError(
                f"Invalid understanding_level '{v}'. Must be one of: {sorted(VALID_UNDERSTANDING_LEVELS)}"
            )
        return v


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_agent_output(raw_output: str) -> AgentOutput:
    """
    Extract dialogue text and analysis JSON from a raw agent response.

    Expected format:
        <dialogue text>
        <analysis>
        { "blind_spots": [...], "understanding_level": "...", "reasoning": "..." }
        </analysis>

    Returns AgentOutput with parse_success=False (and empty blind_spots) if
    the analysis block is missing or malformed. Never raises — always returns
    a usable object so callers don't need try/except.
    """
    parts = raw_output.split("<analysis>", maxsplit=1)
    dialogue_text = parts[0].strip()

    if len(parts) < 2:
        logger.warning(
            "[cog_test_parser] No <analysis> block found. "
            "Raw output (first 200 chars): %s",
            raw_output[:200],
        )
        return AgentOutput(
            dialogue_text=dialogue_text,
            blind_spots=[],
            understanding_level="low",
            reasoning="",
            parse_success=False,
        )

    json_part = parts[1].replace("</analysis>", "").strip()

    try:
        data = json.loads(json_part)
    except json.JSONDecodeError as exc:
        logger.warning(
            "[cog_test_parser] JSON parse failed: %s. "
            "Raw JSON (first 200 chars): %s",
            exc,
            json_part[:200],
        )
        return AgentOutput(
            dialogue_text=dialogue_text,
            blind_spots=[],
            understanding_level="low",
            reasoning="",
            parse_success=False,
        )

    # Validate and coerce blind_spots
    raw_spots = data.get("blind_spots", [])
    blind_spots: list[BlindSpot] = []
    for spot in raw_spots:
        try:
            blind_spots.append(BlindSpot(**spot))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[cog_test_parser] Skipping invalid blind_spot entry %s: %s",
                spot,
                exc,
            )

    # Validate understanding_level — fall back to "low" if invalid
    raw_level: str = data.get("understanding_level", "low")
    if raw_level not in VALID_UNDERSTANDING_LEVELS:
        logger.warning(
            "[cog_test_parser] Invalid understanding_level '%s', defaulting to 'low'",
            raw_level,
        )
        raw_level = "low"

    return AgentOutput(
        dialogue_text=dialogue_text,
        blind_spots=blind_spots,
        understanding_level=raw_level,
        reasoning=data.get("reasoning", ""),
        parse_success=True,
    )


def extract_dialogue_only(raw_output: str) -> str:
    """
    Fast path: return only the dialogue text, stripping the analysis block.
    Used when the caller only needs the user-facing text.
    """
    return raw_output.split("<analysis>", maxsplit=1)[0].strip()
