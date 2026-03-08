"""
Structured Feedback Contract Tests
Tests for LLM feedback JSON schema validation
"""

import pytest
from app.services.model_os_service import ModelOSService


class TestFeedbackNormalization:
    """Test feedback structure normalization and validation"""

    def test_normalize_complete_feedback(self):
        """Complete feedback should be normalized correctly"""
        service = ModelOSService()
        raw = {
            "correctness": "correct",
            "misconceptions": ["issue1", "issue2"],
            "suggestions": ["tip1"],
            "next_question": "What about X?",
            "mastery_score": 85,
            "dimension_scores": {"accuracy": 90, "completeness": 80, "transfer": 85, "rigor": 85},
            "confidence": 0.9,
            "pass_stage": True,
            "decision_reason": "Met all criteria",
        }

        normalized = service.normalize_feedback_structured(raw)

        assert normalized["correctness"] == "correct"
        assert len(normalized["misconceptions"]) == 2
        assert normalized["mastery_score"] == 85
        assert normalized["confidence"] == 0.9
        assert normalized["pass_stage"] is True
        assert "decision_reason" in normalized

    def test_normalize_missing_fields_uses_defaults(self):
        """Missing fields should get default values"""
        service = ModelOSService()
        raw = {"correctness": "partially correct"}

        normalized = service.normalize_feedback_structured(raw)

        assert normalized["correctness"] == "partially correct"
        assert normalized["misconceptions"] == []
        assert normalized["suggestions"] == []
        assert normalized["mastery_score"] == 0
        assert normalized["confidence"] == 0.0
        assert normalized["pass_stage"] is False

    def test_normalize_clamps_mastery_score(self):
        """Mastery score should be clamped to 0-100"""
        service = ModelOSService()

        high = service.normalize_feedback_structured({"mastery_score": 150})
        assert high["mastery_score"] == 100

        low = service.normalize_feedback_structured({"mastery_score": -10})
        assert low["mastery_score"] == 0

    def test_normalize_clamps_confidence(self):
        """Confidence should be clamped to 0.0-1.0"""
        service = ModelOSService()

        high = service.normalize_feedback_structured({"confidence": 2.5})
        assert high["confidence"] == 1.0

        low = service.normalize_feedback_structured({"confidence": -0.5})
        assert low["confidence"] == 0.0

    def test_normalize_dimension_scores_defaults(self):
        """Dimension scores should default to mastery_score"""
        service = ModelOSService()
        raw = {"mastery_score": 75}

        normalized = service.normalize_feedback_structured(raw)

        assert normalized["dimension_scores"]["accuracy"] == 75
        assert normalized["dimension_scores"]["completeness"] == 75
        assert normalized["dimension_scores"]["transfer"] == 75
        assert normalized["dimension_scores"]["rigor"] == 75

    def test_normalize_dimension_scores_partial(self):
        """Partial dimension scores should fill missing with mastery_score"""
        service = ModelOSService()
        raw = {
            "mastery_score": 80,
            "dimension_scores": {"accuracy": 90, "completeness": 85},
        }

        normalized = service.normalize_feedback_structured(raw)

        assert normalized["dimension_scores"]["accuracy"] == 90
        assert normalized["dimension_scores"]["completeness"] == 85
        assert normalized["dimension_scores"]["transfer"] == 80
        assert normalized["dimension_scores"]["rigor"] == 80

    def test_normalize_filters_empty_misconceptions(self):
        """Empty strings in misconceptions should be filtered"""
        service = ModelOSService()
        raw = {"misconceptions": ["real issue", "", "  ", "another issue"]}

        normalized = service.normalize_feedback_structured(raw)

        assert len(normalized["misconceptions"]) == 2
        assert "real issue" in normalized["misconceptions"]
        assert "another issue" in normalized["misconceptions"]

    def test_normalize_filters_empty_suggestions(self):
        """Empty strings in suggestions should be filtered"""
        service = ModelOSService()
        raw = {"suggestions": ["good tip", "", None, "another tip"]}

        normalized = service.normalize_feedback_structured(raw)

        assert len(normalized["suggestions"]) == 2

    def test_format_and_parse_roundtrip(self):
        """Format to text and parse back should preserve structure"""
        service = ModelOSService()
        original = {
            "correctness": "correct",
            "misconceptions": ["issue"],
            "suggestions": ["tip"],
            "next_question": "What next?",
            "mastery_score": 85,
            "confidence": 0.9,
            "pass_stage": True,
            "decision_reason": "Good work",
        }

        text = service.format_feedback_text(original)
        parsed = service.parse_feedback_text(text)

        assert parsed["correctness"] == original["correctness"]
        assert parsed["mastery_score"] == original["mastery_score"]
        assert parsed["confidence"] == original["confidence"]
        assert parsed["pass_stage"] == original["pass_stage"]
