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


@pytest.mark.asyncio
async def test_generate_feedback_structured_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "structured_feedback"
        assert json_schema["type"] == "object"
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": ["Tight explanation."],
            "next_question": "What is the boundary case?",
            "mastery_score": 91,
            "dimension_scores": {"accuracy": 92, "completeness": 90, "transfer": 89, "rigor": 93},
            "confidence": 0.88,
            "pass_stage": True,
            "decision_reason": "Provider-native structured output met the contract",
        }

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    feedback = await service.generate_feedback_structured(
        user_response="Vector retrieval uses embeddings.",
        concept="Vector retrieval",
        model_examples=["embedding", "similarity"],
    )

    assert feedback["correctness"] == "correct"
    assert feedback["mastery_score"] == 91
    assert feedback["pass_stage"] is True
    assert feedback["decision_reason"] == "Provider-native structured output met the contract"


@pytest.mark.asyncio
async def test_generate_feedback_structured_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return """
        {
          "correctness": "partially correct",
          "misconceptions": ["Confused distance with ranking."],
          "suggestions": ["State how similarity is computed."],
          "next_question": "When does cosine similarity fail here?",
          "mastery_score": 67,
          "dimension_scores": {"accuracy": 70, "completeness": 65, "transfer": 66, "rigor": 68},
          "confidence": 0.61,
          "pass_stage": false,
          "decision_reason": "Needs one clearer boundary explanation"
        }
        """

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    feedback = await service.generate_feedback_structured(
        user_response="Cosine similarity sorts the vectors.",
        concept="Vector retrieval",
        model_examples=["embedding", "similarity"],
    )

    assert feedback["correctness"] == "partially correct"
    assert feedback["misconceptions"] == ["Confused distance with ranking."]
    assert feedback["mastery_score"] == 67
    assert feedback["pass_stage"] is False


@pytest.mark.asyncio
async def test_generate_step_hint_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "step_hint"
        assert json_schema["type"] == "object"
        return {
            "focus": "Clarify how similarity ranking differs from distance calculation.",
            "next_actions": [
                "Write one sentence defining the ranking signal.",
                "Add a concrete retrieval example.",
                "Name one case where your current explanation breaks.",
            ],
            "starter": "My current explanation of ranking is:",
        }

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    hint = await service.generate_step_hint(
        problem_title="Vector retrieval",
        problem_description="Understand how semantic search ranks results.",
        step_concept="Similarity ranking",
        step_description="Explain how candidate vectors are ordered.",
        recent_responses=["I think distance and ranking are the same."],
        latest_feedback={
            "misconceptions": ["Distance metric is not the ranking output."],
            "suggestions": ["State what gets compared first."],
            "next_question": "What gets ranked after similarity is computed?",
        },
    )

    assert hint["focus"] == "Clarify how similarity ranking differs from distance calculation."
    assert hint["next_actions"] == [
        "Write one sentence defining the ranking signal.",
        "Add a concrete retrieval example.",
        "Name one case where your current explanation breaks.",
    ]
    assert hint["starter"] == "My current explanation of ranking is:"


@pytest.mark.asyncio
async def test_generate_step_hint_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return """
        {
          "focus": "Explain what signal is being ranked.",
          "next_actions": [
            "State what object is compared first.",
            "Add one short example.",
            "Ask one follow-up question."
          ],
          "starter": "The ranked signal in this step is:"
        }
        """

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    hint = await service.generate_step_hint(
        problem_title="Vector retrieval",
        problem_description="Understand how semantic search ranks results.",
        step_concept="Similarity ranking",
        step_description="Explain how candidate vectors are ordered.",
        recent_responses=["I think distance and ranking are the same."],
    )

    assert hint["focus"] == "Explain what signal is being ranked."
    assert hint["next_actions"] == [
        "State what object is compared first.",
        "Add one short example.",
        "Ask one follow-up question.",
    ]
    assert hint["starter"] == "The ranked signal in this step is:"


@pytest.mark.asyncio
async def test_generate_learning_path_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "learning_path"
        assert json_schema["type"] == "array"
        return [
            {
                "step": 1,
                "concept": "Embedding fundamentals",
                "description": "Explain what an embedding represents in retrieval.",
                "resources": ["embedding", "vector space"],
            },
            {
                "step": 2,
                "concept": "Similarity ranking",
                "description": "Compare cosine similarity with another ranking signal.",
                "resources": ["cosine similarity", "ranking"],
            },
        ]

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    path = await service.generate_learning_path(
        problem_title="Vector retrieval",
        problem_description="Understand how semantic search ranks results.",
        existing_knowledge=["basic linear algebra"],
        associated_concepts=["embedding", "similarity"],
    )

    assert path == [
        {
            "step": 1,
            "concept": "Embedding fundamentals",
            "description": "Explain what an embedding represents in retrieval.",
            "resources": ["embedding", "vector space"],
        },
        {
            "step": 2,
            "concept": "Similarity ranking",
            "description": "Compare cosine similarity with another ranking signal.",
            "resources": ["cosine similarity", "ranking"],
        },
    ]


@pytest.mark.asyncio
async def test_generate_learning_path_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return """
        {
          "steps": [
            {
              "step": 1,
              "concept": "Embedding fundamentals",
              "description": "Explain what an embedding represents in retrieval.",
              "resources": ["embedding", "vector space"]
            },
            {
              "step": 2,
              "concept": "Similarity ranking",
              "description": "Compare cosine similarity with another ranking signal.",
              "resources": ["cosine similarity", "ranking"]
            }
          ]
        }
        """

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    path = await service.generate_learning_path(
        problem_title="Vector retrieval",
        problem_description="Understand how semantic search ranks results.",
        existing_knowledge=["basic linear algebra"],
        associated_concepts=["embedding", "similarity"],
    )

    assert path == [
        {
            "step": 1,
            "concept": "Embedding fundamentals",
            "description": "Explain what an embedding represents in retrieval.",
            "resources": ["embedding", "vector space"],
        },
        {
            "step": 2,
            "concept": "Similarity ranking",
            "description": "Compare cosine similarity with another ranking signal.",
            "resources": ["cosine similarity", "ranking"],
        },
    ]


@pytest.mark.asyncio
async def test_extract_related_concepts_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "related_concepts"
        assert json_schema["type"] == "array"
        return ["embedding", "semantic search", "cosine similarity"]

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    concepts = await service.extract_related_concepts(
        problem_title="Vector retrieval",
        problem_description="Understand embedding ranking for semantic search.",
        limit=5,
    )

    assert concepts == ["embedding", "semantic search", "cosine similarity"]


@pytest.mark.asyncio
async def test_extract_related_concepts_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return '{"concepts": ["embedding", "semantic search", "cosine similarity"]}'

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    concepts = await service.extract_related_concepts(
        problem_title="Vector retrieval",
        problem_description="Understand embedding ranking for semantic search.",
        limit=5,
    )

    assert concepts == ["embedding", "semantic search", "cosine similarity"]


@pytest.mark.asyncio
async def test_create_model_card_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "model_card"
        assert json_schema["type"] == "object"
        return {
            "concept_maps": {
                "nodes": [
                    {"id": "embed", "label": "Embedding", "type": "concept"},
                    {"id": "rank", "label": "Ranking", "type": "principle"},
                ],
                "edges": [
                    {"source": "embed", "target": "rank", "label": "supports"},
                ],
            },
            "core_principles": ["Similarity preserves semantics."],
            "examples": ["Rank neighbors in vector space."],
            "limitations": ["Breaks when embeddings collapse."],
        }

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    card = await service.create_model_card(
        user_id="test-user",
        title="Vector retrieval",
        description="Understand embedding-based retrieval.",
        associated_concepts=["embedding", "ranking"],
    )

    assert card["concept_maps"]["nodes"][0]["label"] == "Embedding"
    assert card["concept_maps"]["edges"][0]["label"] == "supports"
    assert card["core_principles"] == ["Similarity preserves semantics."]
    assert card["examples"] == ["Rank neighbors in vector space."]
    assert card["limitations"] == ["Breaks when embeddings collapse."]


@pytest.mark.asyncio
async def test_create_model_card_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return """
        {
          "concept_maps": {
            "nodes": [{"id": "embed", "label": "Embedding", "type": "concept"}],
            "edges": []
          },
          "core_principles": ["Similarity preserves semantics."],
          "examples": ["Rank neighbors in vector space."],
          "limitations": ["Breaks when embeddings collapse."]
        }
        """

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    card = await service.create_model_card(
        user_id="test-user",
        title="Vector retrieval",
        description="Understand embedding-based retrieval.",
        associated_concepts=["embedding", "ranking"],
    )

    assert card["concept_maps"]["nodes"][0]["label"] == "Embedding"
    assert card["core_principles"] == ["Similarity preserves semantics."]
    assert card["examples"] == ["Rank neighbors in vector space."]
    assert card["limitations"] == ["Breaks when embeddings collapse."]


@pytest.mark.asyncio
async def test_generate_counter_examples_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "counter_examples"
        assert json_schema["type"] == "array"
        return [
            "What fails if the retrieval threshold is fixed too early?",
            "How would noise change the nearest neighbor result?",
        ]

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    counter_examples = await service.generate_counter_examples(
        model_title="Vector retrieval",
        model_concepts=["embedding", "ranking"],
        user_response="I compare query and document vectors.",
    )

    assert counter_examples == [
        "What fails if the retrieval threshold is fixed too early?",
        "How would noise change the nearest neighbor result?",
    ]


@pytest.mark.asyncio
async def test_generate_counter_examples_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return """
        [
          "What fails if the retrieval threshold is fixed too early?",
          "How would noise change the nearest neighbor result?"
        ]
        """

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    counter_examples = await service.generate_counter_examples(
        model_title="Vector retrieval",
        model_concepts=["embedding", "ranking"],
        user_response="I compare query and document vectors.",
    )

    assert counter_examples == [
        "What fails if the retrieval threshold is fixed too early?",
        "How would noise change the nearest neighbor result?",
    ]


@pytest.mark.asyncio
async def test_suggest_migration_prefers_provider_native_result(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        assert kwargs["schema_name"] == "migrations"
        assert json_schema["type"] == "array"
        return [
            {
                "domain": "biology",
                "application": "Transfer ranking logic to gene similarity search.",
                "key_adaptations": "Adjust the feature space.",
            }
        ]

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("prompt-only fallback should not run when structured output succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    migrations = await service.suggest_migration(
        model_title="Vector retrieval",
        model_concepts=["embedding", "ranking"],
    )

    assert migrations == [
        {
            "domain": "biology",
            "application": "Transfer ranking logic to gene similarity search.",
            "key_adaptations": "Adjust the feature space.",
        }
    ]


@pytest.mark.asyncio
async def test_suggest_migration_falls_back_when_provider_native_path_fails(monkeypatch):
    service = ModelOSService()

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        raise RuntimeError("provider-native structured output unavailable")

    async def fake_generate(prompt, **kwargs):
        return """
        [
          {
            "domain": "biology",
            "application": "Transfer ranking logic to gene similarity search.",
            "key_adaptations": "Adjust the feature space."
          }
        ]
        """

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", fake_generate)

    migrations = await service.suggest_migration(
        model_title="Vector retrieval",
        model_concepts=["embedding", "ranking"],
    )

    assert migrations == [
        {
            "domain": "biology",
            "application": "Transfer ranking logic to gene similarity search.",
            "key_adaptations": "Adjust the feature space.",
        }
    ]
