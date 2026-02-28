---
phase: 1
plan: 03
subsystem: agent-prompts
tags: [prompts, parser, socratic, schema, pydantic]
requires: []
provides: [guide-prompt, challenger-prompt, agent-output-schema, parse_agent_output]
affects: [cog_test_prompts, cog_test_parser]
tech_stack_added: []
tech_stack_patterns: [Pydantic BaseModel, field_validator, json.loads, delimiter-extraction]
key_files_created:
  - las_backend/app/services/cog_test_prompts.py
  - las_backend/app/services/cog_test_parser.py
key_files_modified: []
decisions:
  - Used <analysis> delimiter tag (not pure JSON-mode) so agents can produce natural dialogue text followed by structured JSON
  - Guide temperature 0.4 (consistent/warm), Challenger temperature 0.6 (varied/creative)
  - parse_agent_output never raises — always returns AgentOutput with parse_success flag for safe caller handling
  - Pydantic field_validator used for category and understanding_level validation with explicit error messages
duration_minutes: 8
completed_date: 2026-02-28
---

# Phase 1 Plan 03: Agent Prompts + Output Schema Summary

**One-liner:** Guide + Challenger Socratic system prompts with Chinese output and `<analysis>` delimiter extraction via Pydantic-validated AgentOutput parser.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Guide + Challenger system prompts | 0bd56cd | cog_test_prompts.py |
| 2 | AgentOutput schema + parser utility | 5941cba | cog_test_parser.py |

## What Was Built

`cog_test_prompts.py` defines two system prompts and temperature constants. The Guide prompt enforces the Socratic contract via explicit forbidden phrases ("答案是", "正确答案", "其实是", "应该是") and required question words ("你觉得", "你认为", "如果", "为什么", "怎么"). Every response must end with a question. The Challenger prompt requires the first sentence to affirm what the learner got right, forbids hostile phrases ("你错了", "不对"), and frames challenges with curiosity ("有意思，不过…"). Both prompts share a `_OUTPUT_FORMAT` block that specifies the `<analysis>...</analysis>` delimiter and the exact JSON schema.

`cog_test_parser.py` provides `parse_agent_output()` which splits on `<analysis>`, calls `json.loads()`, and validates the result into a Pydantic `AgentOutput` model. Invalid category values and unknown understanding levels are caught with explicit `logger.warning()` calls — no silent failures. `extract_dialogue_only()` is a fast path for callers that only need the user-facing text. All four tests (happy path, missing block, malformed JSON, extract_dialogue_only) pass.

## Deviations from Plan

None — plan executed exactly as written. The plan file lacked a `<tasks>` section; tasks were derived from `must_haves` and `01-RESEARCH.md` Pattern 4 + Pattern 5.

## Self-Check: PASSED
