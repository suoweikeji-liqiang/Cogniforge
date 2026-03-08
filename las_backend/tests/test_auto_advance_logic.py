"""
Auto-Advance Logic Tests
Tests for V1 and V2 auto-advance decision logic
"""

import pytest
from app.api.routes.problems import _should_auto_advance, _should_auto_advance_v2


class TestAutoAdvanceV1:
    """Test V1 keyword-based auto-advance logic"""

    def test_conservative_full_correct_no_misconceptions(self):
        feedback = {"correctness": "correct", "misconceptions": []}
        assert _should_auto_advance(feedback, "conservative") is True

    def test_conservative_full_correct_with_misconception(self):
        feedback = {"correctness": "correct", "misconceptions": ["minor issue"]}
        assert _should_auto_advance(feedback, "conservative") is False

    def test_conservative_partial_correct(self):
        feedback = {"correctness": "partially correct", "misconceptions": []}
        assert _should_auto_advance(feedback, "conservative") is False

    def test_balanced_full_correct_one_misconception(self):
        feedback = {"correctness": "correct", "misconceptions": ["minor"]}
        assert _should_auto_advance(feedback, "balanced") is True

    def test_balanced_full_correct_two_misconceptions(self):
        feedback = {"correctness": "correct", "misconceptions": ["issue1", "issue2"]}
        assert _should_auto_advance(feedback, "balanced") is False

    def test_balanced_partial_correct_no_misconceptions(self):
        feedback = {"correctness": "partially correct", "misconceptions": []}
        assert _should_auto_advance(feedback, "balanced") is True

    def test_balanced_partial_correct_with_misconception(self):
        feedback = {"correctness": "partially correct", "misconceptions": ["issue"]}
        assert _should_auto_advance(feedback, "balanced") is False

    def test_aggressive_full_correct(self):
        feedback = {"correctness": "correct", "misconceptions": []}
        assert _should_auto_advance(feedback, "aggressive") is True

    def test_aggressive_partial_correct(self):
        feedback = {"correctness": "partially correct", "misconceptions": []}
        assert _should_auto_advance(feedback, "aggressive") is True

    def test_incorrect_never_advances(self):
        feedback = {"correctness": "incorrect", "misconceptions": []}
        assert _should_auto_advance(feedback, "conservative") is False
        assert _should_auto_advance(feedback, "balanced") is False
        assert _should_auto_advance(feedback, "aggressive") is False

    def test_chinese_correct(self):
        feedback = {"correctness": "正确", "misconceptions": []}
        assert _should_auto_advance(feedback, "balanced") is True

    def test_chinese_incorrect(self):
        feedback = {"correctness": "错误", "misconceptions": []}
        assert _should_auto_advance(feedback, "balanced") is False


class TestAutoAdvanceV2:
    """Test V2 mastery-score-based auto-advance logic"""

    def test_conservative_meets_threshold_first_attempt(self):
        feedback = {
            "mastery_score": 85,
            "confidence": 0.8,
            "pass_stage": True,
            "misconceptions": [],
        }
        should_advance, reason = _should_auto_advance_v2(feedback, "conservative", pass_streak=0)
        assert should_advance is False  # Requires streak=2
        assert "pass_streak=1/2" in reason

    def test_conservative_meets_threshold_second_attempt(self):
        feedback = {
            "mastery_score": 85,
            "confidence": 0.8,
            "pass_stage": True,
            "misconceptions": [],
        }
        should_advance, reason = _should_auto_advance_v2(feedback, "conservative", pass_streak=1)
        assert should_advance is True
        assert "pass_streak=2/2" in reason

    def test_conservative_below_score_threshold(self):
        feedback = {
            "mastery_score": 84,
            "confidence": 0.8,
            "pass_stage": True,
            "misconceptions": [],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "conservative", pass_streak=1)
        assert should_advance is False

    def test_conservative_below_confidence_threshold(self):
        feedback = {
            "mastery_score": 85,
            "confidence": 0.79,
            "pass_stage": True,
            "misconceptions": [],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "conservative", pass_streak=1)
        assert should_advance is False

    def test_conservative_too_many_misconceptions(self):
        feedback = {
            "mastery_score": 85,
            "confidence": 0.8,
            "pass_stage": True,
            "misconceptions": ["issue"],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "conservative", pass_streak=1)
        assert should_advance is False

    def test_balanced_meets_threshold_first_attempt(self):
        feedback = {
            "mastery_score": 75,
            "confidence": 0.7,
            "pass_stage": True,
            "misconceptions": [],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "balanced", pass_streak=0)
        assert should_advance is False  # Requires streak=2

    def test_balanced_meets_threshold_second_attempt(self):
        feedback = {
            "mastery_score": 75,
            "confidence": 0.7,
            "pass_stage": True,
            "misconceptions": [],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "balanced", pass_streak=1)
        assert should_advance is True

    def test_balanced_one_misconception_allowed(self):
        feedback = {
            "mastery_score": 75,
            "confidence": 0.7,
            "pass_stage": True,
            "misconceptions": ["minor"],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "balanced", pass_streak=1)
        assert should_advance is True

    def test_aggressive_meets_threshold_immediately(self):
        feedback = {
            "mastery_score": 65,
            "confidence": 0.6,
            "pass_stage": True,
            "misconceptions": ["issue1", "issue2"],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "aggressive", pass_streak=0)
        assert should_advance is True  # Only requires streak=1

    def test_pass_stage_false_blocks_advance(self):
        feedback = {
            "mastery_score": 100,
            "confidence": 1.0,
            "pass_stage": False,
            "misconceptions": [],
        }
        should_advance, _ = _should_auto_advance_v2(feedback, "aggressive", pass_streak=5)
        assert should_advance is False

    def test_reason_includes_all_metrics(self):
        feedback = {
            "mastery_score": 75,
            "confidence": 0.7,
            "pass_stage": True,
            "misconceptions": [],
        }
        _, reason = _should_auto_advance_v2(feedback, "balanced", pass_streak=1)
        assert "score=75" in reason
        assert "confidence=0.70" in reason
        assert "misconceptions=0" in reason
        assert "pass_streak=2" in reason
        assert "pass_stage=True" in reason
