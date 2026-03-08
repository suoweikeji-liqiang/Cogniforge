# Comprehensive Test Report

**Date**: 2026-03-08
**Environment**: macOS (Darwin 25.2.0), PostgreSQL@17, Python 3.14.3
**Test Duration**: ~23 seconds (backend) + ~1 minute (frontend build)

---

## Executive Summary

| Test Suite | Status | Passed | Failed | Skipped | Notes |
|------------|--------|--------|--------|---------|-------|
| Backend (pytest) | ✅ PASS | 85 | 0 | 1 | 688 deprecation warnings |
| LLM Integration | ✅ PASS | 2 | 0 | 0 | Using Qwen/Alibaba API |
| Frontend (Playwright) | ❌ FAIL | 0 | 1 | 0 | Strict mode violation |

**Overall Result**: Backend fully functional, frontend e2e test needs fix

---

## 1. Backend Test Results (pytest)

### Summary
- **Total Tests**: 86
- **Passed**: 85 (98.8%)
- **Skipped**: 1 (1.2%)
- **Failed**: 0
- **Duration**: 22.76 seconds
- **Warnings**: 688 (mostly deprecation warnings)

### Test Categories

#### 1.1 API Contract Tests (4/4 passed)
- ✅ `test_review_generate_request_validation`
- ✅ `test_review_generate_missing_fields`
- ✅ `test_problem_create`
- ✅ `test_problems_list`

#### 1.2 API Smoke Tests (13/13 passed)
- ✅ `test_auth_refresh_and_logout_flow`
- ✅ `test_model_card_search_and_similar`
- ✅ `test_problem_and_resource_search`
- ✅ `test_retrieval_logs_and_summary`
- ✅ `test_login_rate_limit`
- ✅ `test_reviews_generate_export_and_delete`
- ✅ `test_srs_schedule_due_and_review_flow`
- ✅ `test_practice_tasks_and_submissions_flow`
- ✅ `test_challenges_generate_answer_and_filter`
- ✅ `test_conversations_and_chat_flow`
- ✅ `test_admin_users_and_llm_config_flow`
- ✅ `test_password_reset_flow`
- ✅ `test_cog_test_session_stop_and_report_flow`

#### 1.3 Auto-Advance Logic Tests (24/24 passed)
**V1 Tests (12/12)**:
- ✅ Conservative mode: full correct (no/with misconceptions), partial correct
- ✅ Balanced mode: full correct (1-2 misconceptions), partial correct (no/with misconceptions)
- ✅ Aggressive mode: full correct, partial correct
- ✅ Incorrect never advances
- ✅ Chinese language support (correct/incorrect)

**V2 Tests (12/12)**:
- ✅ Conservative: threshold tests (1st/2nd attempt), score/confidence thresholds, misconception limits
- ✅ Balanced: threshold tests, misconception tolerance
- ✅ Aggressive: immediate threshold meeting
- ✅ Pass stage blocking
- ✅ Reason includes all metrics

#### 1.4 Chaos & Resilience Tests (1/2 passed, 1 skipped)
- ⏭️ `test_llm_timeout_handling` (SKIPPED - requires specific setup)
- ✅ `test_concurrent_requests`

#### 1.5 Concept Governance Tests (6/6 passed)
- ✅ `test_concept_candidate_auto_accept_high_confidence`
- ✅ `test_list_concept_candidates_by_status`
- ✅ `test_accept_concept_candidate`
- ✅ `test_reject_concept_candidate`
- ✅ `test_rollback_accepted_concept`
- ✅ `test_concept_candidate_max_limit`

#### 1.6 Data Integrity Tests (3/3 passed)
- ✅ `test_problem_required_fields`
- ✅ `test_problem_status_transitions`
- ✅ `test_cascade_delete_user_problems`

#### 1.7 Edge Cases Tests (4/4 passed)
- ✅ `test_problem_with_empty_title`
- ✅ `test_problem_with_very_long_description`
- ✅ `test_invalid_problem_id`
- ✅ `test_duplicate_concept_candidate`

#### 1.8 Feedback Contract Tests (9/9 passed)
- ✅ Normalize complete feedback
- ✅ Normalize missing fields (uses defaults)
- ✅ Normalize clamps mastery score
- ✅ Normalize clamps confidence
- ✅ Normalize dimension scores (defaults/partial)
- ✅ Normalize filters empty misconceptions/suggestions
- ✅ Format and parse roundtrip

#### 1.9 LLM Integration Tests (2/2 passed) ⭐
- ✅ `test_problem_response_with_real_llm` - **Real Qwen API call**
- ✅ `test_conversation_with_real_llm` - **Real Qwen API call**

**LLM Configuration**:
- Provider: Qwen (Alibaba DashScope)
- API Key: Configured in test.env
- Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
- Model: qwen3.5-plus

#### 1.10 Missing APIs Tests (2/2 passed)
- ✅ `test_notes_create_and_list`
- ✅ `test_statistics_overview`

#### 1.11 Problem Learning Flow Tests (5/5 passed)
- ✅ `test_problem_response_records_mastery_and_events`
- ✅ `test_problem_auto_advance_v2_requires_streak`
- ✅ `test_problem_concept_candidates_accept_and_rollback`
- ✅ `test_problem_ask_updates_candidates_and_logs_event`
- ✅ `test_problem_response_budget_guard_skips_low_priority_calls`

#### 1.12 Scripts Smoke Tests (2/2 passed)
- ✅ `test_backfill_embeddings_script_populates_all_supported_entities`
- ✅ `test_sqlite_migration_script_copies_core_rows`

#### 1.13 Security Threat Tests (3/3 passed)
- ✅ `test_unauthorized_review_generation`
- ✅ `test_sql_injection_problem_title`
- ✅ `test_xss_in_problem_description`

#### 1.14 Services Unit Tests (3/3 passed)
- ✅ `test_model_os_extract_concepts`
- ✅ `test_srs_service_schedule_calculation`
- ✅ `test_model_os_feedback_structure`

#### 1.15 Timeout & Degradation Tests (5/5 passed)
- ✅ `test_llm_timeout_triggers_fallback`
- ✅ `test_llm_call_budget_enforcement`
- ✅ `test_low_priority_calls_skipped_when_time_low`
- ✅ `test_observability_fields_present`
- ✅ `test_ask_endpoint_observability`

---

## 2. Frontend Test Results (Playwright)

### Summary
- **Status**: ❌ FAILED
- **Build**: ✅ SUCCESS (629ms, 163 modules)
- **Test Execution**: ❌ FAILED (strict mode violation)

### Build Output
```
✓ 163 modules transformed
✓ built in 629ms
dist/index.html: 0.47 kB
dist/assets/index-Dm4pnE2I.js: 230.64 kB (gzip: 85.46 kB)
```

### Error Details
```
locator.fill: Error: strict mode violation:
locator('textarea') resolved to 2 elements:
  1) <textarea rows="5" required="" placeholder="Write what you understood...">
  2) <textarea rows="3" required="" placeholder="For example: Why should we...">
```

**Root Cause**: The Playwright test script uses a non-specific `locator('textarea')` selector that matches multiple elements on the page. This violates Playwright's strict mode, which requires selectors to match exactly one element.

**Location**: `/Users/asteroida/work/Cogniforge/las_frontend/scripts/dashboard-smoke.mjs:588:36`

---

## 3. Warnings Analysis

### 3.1 Deprecation Warnings (688 total)

**Primary Issue**: `datetime.utcnow()` deprecation
- **Count**: ~650 warnings
- **Severity**: Low (will break in future Python versions)
- **Recommendation**: Replace with `datetime.now(datetime.UTC)`

**Affected Files**:
- `app/api/routes/auth.py` (lines 131, 145, 51)
- `app/api/routes/password_reset.py` (lines 38, 102, 138)
- `app/api/routes/problems.py` (lines 982, 1074, 1145)
- `app/services/review_service.py` (line 57)
- `app/services/srs_service.py` (lines 19, 49, 50, 61)
- `app/api/routes/statistics.py` (line 45)
- `app/core/database.py` (SQLAlchemy schema)

**Secondary Issue**: SQLite datetime adapter deprecation
- **Count**: ~38 warnings
- **Severity**: Low
- **Source**: `aiosqlite/core.py:63`

---

## 4. Test Coverage Analysis

### 4.1 Well-Covered Areas ✅
- Authentication & authorization flows
- Problem creation and learning paths
- Concept governance and candidate management
- SRS (Spaced Repetition System) scheduling
- Auto-advance logic (both V1 and V2)
- Security (SQL injection, XSS, unauthorized access)
- LLM integration with real API calls
- Admin configuration (users, LLM, email)
- Practice submissions and reviews
- Cognitive testing system
- Database migrations and embeddings

### 4.2 Areas Needing Attention ⚠️
1. **LLM Timeout Handling**: Test skipped, needs proper setup
2. **Frontend E2E Tests**: Selector specificity issue
3. **Datetime Deprecation**: 688 warnings need addressing

---

## 5. Performance Metrics

### Backend
- **Total Duration**: 22.76 seconds
- **Average per Test**: ~0.26 seconds
- **Slowest Category**: API smoke tests (integration tests with database)
- **Fastest Category**: Unit tests (services, feedback normalization)

### Frontend
- **Build Time**: 629ms
- **Bundle Size**: 230.64 kB (85.46 kB gzipped)
- **Modules**: 163 transformed

---

## 6. Recommendations

### Priority 1 (High)
1. **Fix Playwright E2E Test**: Update `dashboard-smoke.mjs:588` to use specific selectors
   ```javascript
   // Instead of: locator('textarea')
   // Use: locator('textarea[placeholder*="Write what you understood"]')
   ```

### Priority 2 (Medium)
2. **Address Datetime Deprecations**: Create migration script to replace `datetime.utcnow()` with `datetime.now(datetime.UTC)` across all files
3. **Enable Skipped Test**: Configure and enable `test_llm_timeout_handling`

### Priority 3 (Low)
4. **SQLite Adapter Warning**: Update to recommended datetime handling for SQLite
5. **Add More E2E Tests**: Expand Playwright coverage beyond dashboard smoke test

---

## 7. Conclusion

The Cogniforge backend is **production-ready** with comprehensive test coverage across all critical paths:
- ✅ 85/86 tests passing (98.8% pass rate)
- ✅ Real LLM integration verified with Qwen API
- ✅ Security, data integrity, and edge cases covered
- ✅ Auto-advance logic thoroughly tested (24 test cases)
- ✅ Concept governance and SRS systems validated

The frontend build is stable, but the e2e test suite needs a minor selector fix to resume automated testing.

**Recommended Action**: Fix the Playwright selector issue and address datetime deprecations in the next sprint.
