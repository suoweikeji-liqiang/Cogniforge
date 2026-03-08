# Learning Loop Hardening - Implementation Status

**Last Updated**: 2026-03-08

## Overview

This document tracks the implementation status of the Learning Loop Hardening Plan (2026-03-05).

## Implementation Status Summary

### ✅ P0: Observability + Cost Guards + Degradation (COMPLETE)

**Status**: Fully implemented and operational

**Delivered Features**:
1. **Trace ID tracking** - Every `/responses` and `/ask` request generates a unique `trace_id`
2. **Observability metrics** - All responses include:
   - `llm_calls`: Number of LLM calls made
   - `llm_latency_ms`: Total LLM latency in milliseconds
   - `fallback_reason`: Semicolon-separated list of fallback triggers
3. **Request-level budget guards**:
   - `PROBLEM_MAX_LLM_CALLS_PER_REQUEST=3` - Limits LLM calls per request
   - `PROBLEM_RESPONSE_TIMEOUT_SECONDS=20` - Overall request timeout
4. **Degradation logic** via `guarded_llm_call()`:
   - Timeout budget enforcement
   - Low-priority call skipping when time is running out
   - Budget exceeded handling
   - Graceful fallback on errors
5. **Metrics persistence** - All metrics logged to `learning_events` table with:
   - `event_type`: "problem_response_evaluated" or "problem_inline_qa"
   - `trace_id`: Request correlation ID
   - `payload_json`: Contains llm_calls, llm_latency_ms, fallback_reason

**Key Files**:
- `las_backend/app/api/routes/problems.py:654-680` - guarded_llm_call implementation
- `las_backend/app/api/routes/problems.py:842-859` - learning event logging
- `las_backend/app/schemas/problem.py:56-59` - observability fields in response schemas
- `las_backend/app/core/config.py:39-42` - configuration parameters

---

### ✅ P1: Mastery Score Feedback V2 (COMPLETE)

**Status**: Fully implemented with feature flag

**Delivered Features**:
1. **Extended feedback structure** - LLM now returns:
   - `mastery_score`: 0-100 overall mastery score
   - `dimension_scores`: {accuracy, completeness, transfer, rigor} - each 0-100
   - `confidence`: 0.0-1.0 confidence in the assessment
   - `pass_stage`: boolean indicating if learner passed this stage
   - `decision_reason`: explanation of the pass/fail decision
2. **V2 auto-advance logic** with `_should_auto_advance_v2()`:
   - Threshold-based scoring (conservative/balanced/aggressive modes)
   - Pass streak tracking (requires consecutive passes)
   - Multi-dimensional evaluation
3. **Feature flag**: `PROBLEM_AUTO_ADVANCE_V2_ENABLED=false` (default off)
4. **Mastery event tracking** - All responses create `ProblemMasteryEvent` records with:
   - mastery_score, confidence, pass_stage, auto_advanced, decision_reason

**Key Files**:
- `las_backend/app/services/model_os_service.py:1209-1243` - LLM prompt with mastery fields
- `las_backend/app/api/routes/problems.py:113-154` - V2 auto-advance logic
- `las_backend/app/api/routes/problems.py:772-819` - V2 decision integration
- `las_backend/app/models/entities/user.py:148-166` - ProblemMasteryEvent model

---

### ✅ P2: Concept Governance (COMPLETE)

**Status**: Fully implemented with candidate workflow

**Delivered Features**:
1. **Concept candidate pool** - New concepts go to `problem_concept_candidates` table:
   - Status: pending → accepted/rejected/reverted
   - Source tracking: "response", "ask", "manual"
   - Confidence scoring: 0.0-1.0
   - Evidence snippets
2. **Auto-accept threshold**: `PROBLEM_CONCEPT_AUTO_ACCEPT_CONFIDENCE=0.85`
3. **Manual review endpoints**:
   - `GET /{problem_id}/concept-candidates` - List candidates with status filter
   - `POST /{problem_id}/concept-candidates/{id}/accept` - Accept candidate
   - `POST /{problem_id}/concept-candidates/{id}/reject` - Reject candidate
4. **Concept rollback**: `POST /{problem_id}/concepts/rollback` - Remove accepted concept
5. **Concept entity system** - Normalized concepts stored in:
   - `concepts` - Canonical concept records
   - `concept_aliases` - Alternative names for concepts
   - `concept_relations` - Relationships between concepts
   - `concept_evidences` - Evidence snippets linking concepts to sources

**Key Files**:
- `las_backend/app/api/routes/problems.py:302-400` - Candidate registration logic
- `las_backend/app/api/routes/problems.py:917-1047` - Candidate review endpoints
- `las_backend/app/api/routes/problems.py:1098-1170` - Concept rollback
- `las_backend/app/models/entities/user.py:88-146` - Concept entity models
- `alembic/versions/007_add_learning_governance_tables.py` - Database schema

---

### ✅ P3: /ask Fusion (COMPLETE)

**Status**: Fully integrated with concept pipeline

**Delivered Features**:
1. **Concept extraction from Q&A** - `/ask` endpoint extracts concepts from:
   - User question
   - LLM answer
   - Current step context
2. **Unified candidate pipeline** - Q&A concepts flow through same governance:
   - Source marked as "ask"
   - Auto-accept based on confidence threshold
   - Manual review available for pending concepts
3. **Learning event logging** - Q&A interactions logged with:
   - event_type: "problem_inline_qa"
   - Includes accepted_concepts, pending_concepts
   - Full observability metrics (trace_id, llm_calls, etc.)

**Key Files**:
- `las_backend/app/api/routes/problems.py:1348-1375` - Q&A concept extraction
- `las_backend/app/api/routes/problems.py:1378-1393` - Q&A event logging

---

### ✅ P4: Knowledge Graph Entityification (COMPLETE)

**Status**: Entity layer implemented, dual-write active

**Delivered Features**:
1. **Concept entity records** - All concepts now stored in normalized form:
   - `concepts` table with canonical_name and normalized_name
   - Unique constraint on (user_id, normalized_name)
2. **Alias tracking** - Multiple names for same concept:
   - `concept_aliases` table
   - Unique constraint on (concept_id, normalized_alias)
3. **Relationship tracking** - Concept connections:
   - `concept_relations` table with source/target concept IDs
   - Relation types: "related" (extensible)
   - Weight and version fields for future ranking
4. **Evidence tracking** - Source attribution:
   - `concept_evidences` table
   - Links concepts to problems, responses, Q&A
   - Confidence scores per evidence
5. **Dual-write mode** - Both old and new systems active:
   - `problem.associated_concepts` (legacy JSON array) still updated
   - New entity records created in parallel
   - Enables gradual migration

**Key Files**:
- `las_backend/app/api/routes/problems.py:206-268` - _ensure_concept_record
- `las_backend/app/api/routes/problems.py:270-299` - _ensure_concept_relation
- `las_backend/app/models/entities/user.py:88-146` - Entity models

---

### ⚠️ P5: Testing & Regression (PARTIAL)

**Status**: Basic tests exist, comprehensive coverage needed

**Existing Tests**:
- `test_problem_learning_flow.py` - Basic learning flow tests
- `test_chaos_resilience.py` - Has 1 skipped test (CR-01-01) and 1 basic concurrency test

**Missing Coverage**:
- Auto-advance boundary tests (V1 vs V2, different modes, streak logic)
- Concept candidate workflow tests (accept/reject/rollback)
- Timeout/budget degradation path tests
- Structured feedback contract tests (JSON shape validation)

**Recommendation**: Add comprehensive test suite covering all P0-P4 features.

---

## Configuration Reference

```bash
# P0: Observability & Guards
PROBLEM_MAX_LLM_CALLS_PER_REQUEST=3
PROBLEM_RESPONSE_TIMEOUT_SECONDS=20

# P1: Mastery Scoring
PROBLEM_AUTO_ADVANCE_V2_ENABLED=false  # Feature flag
PROBLEM_AUTO_ADVANCE_MODE=balanced     # conservative|balanced|aggressive

# P2: Concept Governance
PROBLEM_CONCEPT_AUTO_ACCEPT_CONFIDENCE=0.85
PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN=5
PROBLEM_MAX_ASSOCIATED_CONCEPTS=16
```

---

## Next Steps

1. **Enable V2 auto-advance** - Set `PROBLEM_AUTO_ADVANCE_V2_ENABLED=true` after validation
2. **Add comprehensive tests** - Complete P5 test coverage
3. **Monitor metrics** - Query `learning_events` table for observability data
4. **Migrate statistics** - Update graph/stats endpoints to use entity tables instead of JSON parsing
5. **Deprecate legacy fields** - After migration, remove `problem.associated_concepts` JSON field

---

## Database Schema

Key tables added in migration 007:
- `problem_mastery_events` - Mastery score tracking
- `problem_concept_candidates` - Concept approval workflow
- `concepts` - Canonical concept records
- `concept_aliases` - Concept name variations
- `concept_relations` - Concept relationships
- `concept_evidences` - Source attribution
- `learning_events` - Observability event log
