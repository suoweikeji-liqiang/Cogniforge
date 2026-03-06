"""
FlowTest Architecture - Complete Test Coverage
Based on: .agents/skills/flowtest-architect

System: Cogniforge Learning Assistant
Focus: Button-triggered operations across all flows
"""

# ============================================================================
# SYSTEM INVENTORY
# ============================================================================

ROLES = ["anonymous", "user", "admin"]

RESOURCES = [
    "problems", "model_cards", "reviews", "conversations",
    "practice_submissions", "srs_reviews", "concepts"
]

ACTIONS = ["create", "read", "update", "delete", "generate", "submit"]

STATE_MACHINES = {
    "problem": ["new", "in_progress", "completed"],
    "review": ["draft", "published"],
    "practice": ["pending", "submitted", "graded"]
}

# ============================================================================
# BUSINESS FLOW TEST CASES
# ============================================================================

BF_01 = {
    "id": "BF-01",
    "purpose": "User generates daily review via dashboard button",
    "preconditions": ["User logged in", "No existing daily review for today"],
    "test_data": {"review_type": "daily", "period": "2026-03-06"},
    "steps": [
        "1. Navigate to /dashboard",
        "2. Click 'Generate Review' button",
        "3. Wait for LLM generation",
        "4. Review is created and saved"
    ],
    "expected": [
        "Button becomes disabled during generation",
        "Success message displayed",
        "Review appears in history"
    ],
    "tags": ["business:review", "data:create", "auth:user"],
    "negative_cases": [
        "Duplicate review for same period rejected",
        "Unauthenticated user blocked",
        "LLM timeout handled gracefully"
    ]
}

BF_02 = {
    "id": "BF-02",
    "purpose": "User creates new problem",
    "preconditions": ["User logged in"],
    "test_data": {"title": "Learn FastAPI", "description": "Build REST API"},
    "steps": [
        "1. Navigate to /problems",
        "2. Click 'New Problem' button",
        "3. Fill form and submit",
        "4. Problem created with embedding"
    ],
    "expected": [
        "Problem saved to database",
        "Embedding generated",
        "Redirected to problem detail"
    ],
    "tags": ["business:problem", "data:create", "auth:user"]
}

# ============================================================================
# DATA FLOW TEST CASES
# ============================================================================

DF_01 = {
    "id": "DF-01",
    "purpose": "Problem lifecycle validation",
    "stages": [
        "Create: title required, description optional",
        "Update: status transitions (new -> in_progress -> completed)",
        "Delete: cascade to responses and learning_path"
    ],
    "validation_rules": [
        "title: required, max 500 chars",
        "status: enum validation",
        "user_id: foreign key constraint"
    ],
    "consistency": [
        "Deleting problem deletes all responses",
        "Problem count matches user.problems relationship"
    ]
}

DF_02 = {
    "id": "DF-02",
    "purpose": "Review data integrity",
    "stages": [
        "Generate: LLM creates content",
        "Save: unique constraint (user_id, review_type, period)",
        "Read: only owner can access"
    ],
    "validation_rules": [
        "review_type: enum (daily, weekly, monthly)",
        "period: date format validation",
        "content: required, non-empty"
    ]
}

# ============================================================================
# AUTHORIZATION FLOW TEST CASES
# ============================================================================

AZ_01 = {
    "id": "AZ-01",
    "purpose": "Problem CRUD authorization matrix",
    "matrix": {
        "anonymous": {"create": False, "read": False, "update": False, "delete": False},
        "user": {"create": True, "read": "own", "update": "own", "delete": "own"},
        "admin": {"create": True, "read": "all", "update": "all", "delete": "all"}
    },
    "idor_tests": [
        "User A cannot read User B's problem",
        "User A cannot update User B's problem",
        "User A cannot delete User B's problem"
    ]
}

AZ_02 = {
    "id": "AZ-02",
    "purpose": "Admin endpoint authorization",
    "tests": [
        "Regular user blocked from /admin/users",
        "Regular user blocked from /admin/llm-config",
        "Admin can access all admin endpoints"
    ]
}

# ============================================================================
# COVERAGE MATRIX
# ============================================================================

COVERAGE_MATRIX = """
| Business Flow      | Data Stage | Auth Role | Test Case | Status |
|--------------------|------------|-----------|-----------|--------|
| Review Generation  | Create     | User      | BF-01     | ✅     |
| Review Generation  | Create     | Anonymous | AZ-01     | ✅     |
| Review Generation  | Read       | User      | DF-02     | ✅     |
| Problem Creation   | Create     | User      | BF-02     | ✅     |
| Problem Creation   | Validate   | User      | DF-01     | ✅     |
| Problem Update     | Update     | User      | AZ-01     | ✅     |
| Problem Delete     | Delete     | User      | AZ-01     | ✅     |
| Problem IDOR       | Read       | User      | AZ-01     | ✅     |
| Admin Access       | Read       | User      | AZ-02     | ✅     |
| Admin Access       | Read       | Admin     | AZ-02     | ✅     |
"""

# ============================================================================
# AUTOMATION PLAN
# ============================================================================

AUTOMATION_PRIORITY = {
    "high": [
        "API contract tests (test_api_contract.py)",
        "Authorization tests (test_security_threats.py)",
        "Data integrity tests (test_data_integrity.py)"
    ],
    "medium": [
        "UI regression tests (ui-regression-buttons.spec.ts)",
        "Chaos resilience tests (test_chaos_resilience.py)"
    ],
    "low": [
        "Visual regression snapshots",
        "Performance benchmarks"
    ]
}

# ============================================================================
# RISK ASSESSMENT
# ============================================================================

CRITICAL_RISKS = [
    "IDOR: User accessing other user's data",
    "Auth bypass: Unauthenticated access to protected endpoints",
    "Data loss: Cascade delete without confirmation",
    "LLM timeout: Review generation hanging indefinitely",
    "XSS: Unsanitized user input in reviews/problems"
]

MITIGATION_STATUS = {
    "IDOR": "✅ Tested in AZ-01",
    "Auth bypass": "✅ Tested in ST-01-01",
    "Data loss": "✅ Tested in DI-03-01",
    "LLM timeout": "✅ Tested in CR-01-01",
    "XSS": "✅ Tested in ST-02-02"
}
