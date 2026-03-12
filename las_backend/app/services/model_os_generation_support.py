import asyncio
import json
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services import model_os_structured_support as structured_support


def _clean_json_str(text: str) -> str:
    return structured_support.clean_json_str(text)


async def generate_socratic_question(
    self,
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    question_kind: str,
    recent_responses: Optional[List[str]] = None,
    latest_feedback: Optional[Dict[str, Any]] = None,
) -> str:
    prompt = self._build_socratic_question_prompt(
        problem_title,
        problem_description,
        step_concept,
        step_description,
        question_kind,
        recent_responses,
        latest_feedback,
    )
    result = await self.generate_text_for_lane(prompt, lane="interactive")
    question = str(result or "").strip()
    if not question:
        return self.build_socratic_question_fallback(
            step_concept=step_concept,
            question_kind=question_kind,
            latest_feedback=latest_feedback,
            problem_title=problem_title,
            problem_description=problem_description,
            step_description=step_description,
        )
    return question


async def stream_socratic_question(
    self,
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    question_kind: str,
    recent_responses: Optional[List[str]] = None,
    latest_feedback: Optional[Dict[str, Any]] = None,
):
    prompt = self._build_socratic_question_prompt(
        problem_title,
        problem_description,
        step_concept,
        step_description,
        question_kind,
        recent_responses,
        latest_feedback,
    )
    route = await self.resolve_task_route("interactive")
    async for token in self.llm.stream_generate(
        messages=[{"role": "user", "content": prompt}],
        provider_id=route.provider_id,
        provider_type=route.provider_type,
        model_id=route.model_id,
    ):
        yield token


async def extract_related_concepts(
    self,
    problem_title: str,
    problem_description: str,
    limit: int = 8,
) -> List[str]:
    language_instruction = self._build_language_instruction(
        problem_title,
        problem_description,
        json_mode=True,
    )
    normalized_limit = max(3, min(limit, 12))
    prompt = f"""Extract key learning concepts from the user's question.

Question title: {problem_title}
Question description: {problem_description}

Requirements:
1. Return {normalized_limit} or fewer concrete concepts.
2. Prefer domain concepts, methods, and principles; avoid generic words.
3. Keep each concept short (1-6 words).
4. Do not include numbering or explanations.

Return ONLY a JSON array of strings, e.g.:
["concept A", "concept B"]

{language_instruction}"""

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._related_concepts_schema(normalized_limit),
            schema_name="related_concepts",
            lane="structured_heavy",
        )
    except Exception:
        structured_result = None

    if isinstance(structured_result, dict):
        structured_result = structured_result.get("concepts", [])
    if isinstance(structured_result, list):
        normalized = self.filter_low_signal_concepts(
            [str(item) for item in structured_result],
            limit=normalized_limit,
        )
        if normalized:
            return normalized

    result = await self.generate_text_for_lane(prompt, lane="structured_heavy")
    try:
        parsed = json.loads(_clean_json_str(result))
        if isinstance(parsed, dict):
            parsed = parsed.get("concepts", [])
        if not isinstance(parsed, list):
            return []
        return self.filter_low_signal_concepts([str(item) for item in parsed], limit=normalized_limit)
    except json.JSONDecodeError:
        return []


async def extract_related_concepts_resilient(
    self,
    problem_title: str,
    problem_description: str,
    limit: int = 8,
    timeout_seconds: Optional[int] = None,
) -> List[str]:
    effective_timeout = timeout_seconds or max(4, min(get_settings().LLM_REQUEST_TIMEOUT_SECONDS, 12))
    try:
        concepts = await asyncio.wait_for(
            self.extract_related_concepts(
                problem_title=problem_title,
                problem_description=problem_description,
                limit=limit,
            ),
            timeout=max(1, int(effective_timeout)),
        )
        if concepts:
            return concepts
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    return self._fallback_concepts_from_problem(
        problem_title=problem_title,
        problem_description=problem_description,
        limit=limit,
    )


async def build_problem_concepts_resilient(
    self,
    problem_title: str,
    problem_description: str,
    seed_concepts: Optional[List[str]] = None,
    max_concepts: int = 8,
) -> List[str]:
    normalized_limit = max(3, min(max_concepts, 12))
    seed = self.normalize_concepts(seed_concepts or [], limit=normalized_limit)
    if len(seed) >= min(4, normalized_limit):
        return seed

    inferred = await self.extract_related_concepts_resilient(
        problem_title=problem_title,
        problem_description=problem_description,
        limit=normalized_limit,
    )
    return self.normalize_concepts(seed + inferred, limit=normalized_limit)


async def create_model_card(
    self,
    user_id: str,
    title: str,
    description: str,
    associated_concepts: List[str],
) -> Dict[str, Any]:
    language_instruction = self._build_language_instruction(
        title,
        description,
        ", ".join(associated_concepts or []),
        json_mode=True,
    )
    prompt = f"""Based on the following learning content, create a structured cognitive model card:

Title: {title}
Description: {description}
Associated Concepts: {', '.join(associated_concepts)}

Please generate:
1. A concept map with key nodes and relationships
2. Core principles and assumptions
3. Key examples that illustrate the model
4. Potential edge cases or limitations

Return the response as a JSON object with the following structure:
{{
    "concept_maps": {{
        "nodes": [{{"id": "x", "label": "concept name", "type": "concept/principle/example"}}],
        "edges": [{{"source": "x", "target": "y", "label": "relationship"}}]
    }},
    "core_principles": ["principle 1", "principle 2"],
    "examples": ["example 1", "example 2"],
    "limitations": ["limitation 1"]
}}

{language_instruction}"""

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._model_card_schema(),
            schema_name="model_card",
            lane="structured_heavy",
        )
    except Exception:
        structured_result = None

    normalized_structured = self.normalize_model_card_payload(structured_result)
    if normalized_structured != self._default_model_card_payload():
        return normalized_structured

    result = await self.generate_text_for_lane(prompt, lane="structured_heavy")

    try:
        model_data = json.loads(_clean_json_str(result))
    except json.JSONDecodeError:
        model_data = {}

    return self.normalize_model_card_payload(model_data)


async def generate_counter_examples(
    self,
    model_title: str,
    model_concepts: List[str],
    user_response: str,
) -> List[str]:
    language_instruction = self._build_language_instruction(
        model_title,
        ", ".join(model_concepts or []),
        user_response,
        json_mode=True,
    )
    prompt = f"""You are the Contradiction Generation Module in Model OS.

Current Model: {model_title}
Model Concepts: {', '.join(model_concepts)}
User's Response/Understanding: {user_response}

Generate 2-3 counter-examples or challenging questions that:
1. Test the boundaries of the user's understanding
2. Challenge assumptions in the model
3. Highlight potential misunderstandings

Format as a JSON array of strings, each being a counter-example or challenging question.

{language_instruction}"""

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._counter_examples_schema(),
            schema_name="counter_examples",
            lane="structured_heavy",
        )
    except Exception:
        structured_result = None

    normalized_structured = self._normalize_string_items(structured_result, limit=5)
    if normalized_structured:
        return normalized_structured

    result = await self.generate_text_for_lane(prompt, lane="structured_heavy")

    try:
        counter_examples = json.loads(_clean_json_str(result))
    except json.JSONDecodeError:
        counter_examples = []

    return self._normalize_string_items(counter_examples, limit=5)


async def suggest_migration(
    self,
    model_title: str,
    model_concepts: List[str],
) -> List[Dict[str, str]]:
    language_instruction = self._build_language_instruction(
        model_title,
        ", ".join(model_concepts or []),
        json_mode=True,
    )
    prompt = f"""You are the Cross-Domain Migration Module in Model OS.

Current Model: {model_title}
Model Concepts: {', '.join(model_concepts)}

Suggest 2-3 other domains where this model could be applied, with brief explanations of how the concepts translate.

Return as JSON array:
[
    {{"domain": "domain name", "application": "how to apply", "key_adaptations": "what to adapt"}}
]

{language_instruction}"""

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._migration_schema(),
            schema_name="migrations",
            lane="structured_heavy",
        )
    except Exception:
        structured_result = None

    normalized_structured = self.normalize_migration_payload(structured_result)
    if normalized_structured:
        return normalized_structured

    result = await self.generate_text_for_lane(prompt, lane="structured_heavy")

    try:
        migrations = json.loads(_clean_json_str(result))
    except json.JSONDecodeError:
        migrations = []

    return self.normalize_migration_payload(migrations)


async def generate_learning_path(
    self,
    problem_title: str,
    problem_description: str,
    existing_knowledge: List[str],
    associated_concepts: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    language_instruction = self._build_language_instruction(
        problem_title,
        problem_description,
        ", ".join(existing_knowledge or []),
        ", ".join(associated_concepts or []),
        json_mode=True,
    )
    prompt = f"""Generate an optimized learning path for:

Problem/Goal: {problem_title}
Description: {problem_description}
User's Existing Knowledge: {', '.join(existing_knowledge)}
Associated Concepts: {', '.join(associated_concepts or []) or 'N/A'}

Create a step-by-step learning path that:
1. Builds on existing knowledge
2. Introduces new concepts in logical order
3. Includes opportunities for model collision (testing understanding with counter-examples). These MUST be placed directly inside the "description" field, NEVER as a standalone string.

Return ONLY a valid JSON array of steps exactly matching this format (with NO extra keys or standalone strings):
[
    {{
        "step": 1,
        "concept": "concept name",
        "description": "what to learn, including model collisions if applicable",
        "resources": ["resource 1", "resource 2"]
    }}
]

{language_instruction}"""

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._learning_path_schema(),
            schema_name="learning_path",
            lane="structured_heavy",
        )
    except Exception:
        structured_result = None

    normalized_structured = self.normalize_learning_path_payload(structured_result)
    if normalized_structured:
        return normalized_structured

    result = await self.generate_text_for_lane(prompt, lane="structured_heavy")

    try:
        path = json.loads(_clean_json_str(result))
    except json.JSONDecodeError as error:
        with open("llm_debug_zh.log", "w", encoding="utf-8") as handle:
            handle.write(f"JSON ERROR: {error}\\nRAW:\\n{result}\\n---\\n")
        print(f"Failed to parse path json. Error: {error}")
        path = []

    return self.normalize_learning_path_payload(path)


async def generate_learning_path_resilient(
    self,
    problem_title: str,
    problem_description: str,
    existing_knowledge: List[str],
    associated_concepts: Optional[List[str]] = None,
    timeout_seconds: Optional[int] = None,
) -> List[Dict[str, Any]]:
    effective_timeout = timeout_seconds or get_settings().LEARNING_PATH_TIMEOUT_SECONDS
    try:
        path = await asyncio.wait_for(
            self.generate_learning_path(
                problem_title=problem_title,
                problem_description=problem_description,
                existing_knowledge=existing_knowledge,
                associated_concepts=associated_concepts,
            ),
            timeout=max(1, int(effective_timeout)),
        )
        if isinstance(path, list) and path:
            return path
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    return self._build_fallback_learning_path(
        problem_title=problem_title,
        problem_description=problem_description,
        existing_knowledge=existing_knowledge,
        associated_concepts=associated_concepts,
    )


async def generate_feedback(
    self,
    user_response: str,
    concept: str,
    model_examples: List[str],
) -> str:
    language_instruction = self._build_language_instruction(
        user_response,
        concept,
        ", ".join(model_examples or []),
    )
    prompt = f"""Provide feedback on the user's understanding:

Concept: {concept}
User's Response: {user_response}
Model Examples: {', '.join(model_examples)}

        Analyze the response and provide:
1. Whether the understanding is correct
2. Specific gaps or misconceptions
3. Suggestions for improvement
4. A challenging question to test deeper understanding

{language_instruction}"""

    return await self.generate_text_for_lane(prompt, lane="interactive")


async def generate_step_hint(
    self,
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    recent_responses: Optional[List[str]] = None,
    latest_feedback: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    recent_block = ""
    if recent_responses:
        recent_block = "\nRecent learner responses:\n" + "\n".join(
            f"- {item}" for item in recent_responses if item
        )
    feedback_block = ""
    previous_hint_texts = list(recent_responses or [])
    if latest_feedback:
        misconceptions = latest_feedback.get("misconceptions") or []
        suggestions = latest_feedback.get("suggestions") or []
        next_question = str(latest_feedback.get("next_question") or "").strip()
        misconception_text = "; ".join(str(item).strip() for item in misconceptions if str(item).strip())
        suggestion_text = "; ".join(str(item).strip() for item in suggestions if str(item).strip())
        previous_hint_texts.extend(str(item).strip() for item in suggestions if str(item).strip())
        previous_hint_texts.extend(str(item).strip() for item in misconceptions if str(item).strip())
        if next_question:
            previous_hint_texts.append(next_question)
        feedback_block = (
            "\nLatest feedback context:"
            f"\n- Misconceptions: {misconception_text or 'N/A'}"
            f"\n- Suggestions: {suggestion_text or 'N/A'}"
            f"\n- Next question: {next_question or 'N/A'}"
        )
    language_instruction = self._build_language_instruction(
        problem_title,
        problem_description,
        step_concept,
        step_description,
        "\n".join(recent_responses or []),
        str(latest_feedback or ""),
        json_mode=True,
    )
    prompt = f"""You are guiding the learner on one focused learning step.

Problem: {problem_title}
Problem description: {problem_description}
Current step concept: {step_concept}
Current step description: {step_description}
{recent_block}
{feedback_block}

Return ONLY valid JSON in this shape:
{{
  "focus": "one sentence on what to focus on now",
  "next_actions": ["action 1", "action 2", "action 3"],
  "starter": "one sentence the learner can copy to start writing"
}}

Constraints:
1. Keep guidance practical and concrete.
2. Do not give final answer directly.
3. next_actions must contain 2-3 items.
4. Avoid repeating previous suggestions verbatim.

{language_instruction}"""

    cjk_context = self._contains_cjk(
        problem_title + problem_description + step_concept + step_description
    )

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._step_hint_schema(),
            schema_name="step_hint",
            lane="interactive",
        )
    except Exception:
        structured_result = None

    if isinstance(structured_result, dict):
        return self._normalize_step_hint_structured(
            structured_result,
            previous_hint_texts=previous_hint_texts,
            cjk_context=cjk_context,
        )

    result = await self.generate_text_for_lane(prompt, lane="interactive")
    try:
        parsed = json.loads(_clean_json_str(result))
        if not isinstance(parsed, dict):
            raise ValueError("Step hint is not a JSON object")
        return self._normalize_step_hint_structured(
            parsed,
            previous_hint_texts=previous_hint_texts,
            cjk_context=cjk_context,
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return self._build_fallback_step_hint(
            step_concept=step_concept,
            previous_hint_texts=previous_hint_texts,
            cjk_context=cjk_context,
        )


async def generate_feedback_structured(
    self,
    user_response: str,
    concept: str,
    model_examples: List[str],
    retrieval_context: Optional[str] = None,
) -> Dict[str, Any]:
    language_instruction = self._build_language_instruction(
        user_response,
        concept,
        ", ".join(model_examples or []),
        retrieval_context,
        json_mode=True,
    )
    retrieval_block = f"\nRelevant learner context:\n{retrieval_context}\n" if retrieval_context else ""
    prompt = f"""Evaluate the user's understanding and return ONLY valid JSON.

Concept: {concept}
User's Response: {user_response}
Model Examples: {', '.join(model_examples)}
{retrieval_block}

Return this exact JSON shape:
{{
  "correctness": "correct / partially correct / incorrect",
  "misconceptions": ["specific misconception"],
  "suggestions": ["specific suggestion"],
  "next_question": "a challenging follow-up question",
  "mastery_score": 0,
  "dimension_scores": {{"accuracy": 0, "completeness": 0, "transfer": 0, "rigor": 0}},
  "confidence": 0.0,
  "pass_stage": false,
  "decision_reason": "why pass_stage is true/false"
}}

{language_instruction}
"""

    try:
        structured_result = await self.generate_structured_for_lane(
            prompt,
            self._feedback_structured_schema(),
            schema_name="structured_feedback",
            lane="interactive",
        )
    except Exception:
        structured_result = None

    if isinstance(structured_result, dict):
        return self.normalize_feedback_structured(structured_result)

    result = await self.generate_text_for_lane(prompt, lane="interactive")

    try:
        parsed = json.loads(_clean_json_str(result))
        return self.normalize_feedback_structured(parsed if isinstance(parsed, dict) else {})
    except json.JSONDecodeError:
        return self.normalize_feedback_structured(
            {
                "correctness": "",
                "misconceptions": [],
                "suggestions": [result.strip()] if result.strip() else [],
                "next_question": "",
            }
        )


async def generate_evolution_summary(
    self,
    card_title: str,
    old_snapshot: Optional[Dict],
    new_snapshot: Dict,
) -> str:
    """AI-generated summary of how a model card evolved."""
    old_desc = str(old_snapshot) if old_snapshot else "Initial creation"
    language_instruction = self._build_language_instruction(
        card_title,
        old_desc,
        str(new_snapshot),
    )
    prompt = f"""Compare two versions of a cognitive model card and summarize the evolution:

Model: {card_title}
Previous state: {old_desc}
Current state: {str(new_snapshot)}

Provide a concise summary (2-3 sentences) of what changed and why it matters for the learner's understanding.

{language_instruction}"""
    return await self.generate_text_for_lane(prompt, lane="structured_heavy")
