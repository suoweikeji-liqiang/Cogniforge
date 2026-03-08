from typing import List, Dict, Any, Optional
import asyncio
import hashlib
from app.services.llm_service import llm_service
from app.core.config import get_settings
from app.core.vector import cosine_similarity
from sqlalchemy import select
import json
import re

def _clean_json_str(text: str) -> str:
    # First try to find a markdown block
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    text = text.strip()
    # Strip any text before the first [ or {
    if not text.startswith('[') and not text.startswith('{'):
        start_idx = -1
        for i, c in enumerate(text):
            if c in ('[', '{'):
                start_idx = i
                break
        if start_idx != -1:
            closing = ']' if text[start_idx] == '[' else '}'
            end_idx = -1
            for i in range(len(text)-1, -1, -1):
                if text[i] == closing:
                    end_idx = i
                    break
            if end_idx != -1 and end_idx >= start_idx:
                return text[start_idx:end_idx+1].strip()
    return text


class ModelOSService:
    def __init__(self):
        self.llm = llm_service
        self.embedding_dimensions = get_settings().MODEL_CARD_EMBEDDING_DIMENSIONS

    def _tokenize_text(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())

    def _contains_cjk(self, text: Optional[str]) -> bool:
        if not text:
            return False
        return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))

    def _build_language_instruction(self, *texts: Optional[str], json_mode: bool = False) -> str:
        has_cjk = any(self._contains_cjk(text) for text in texts)
        if has_cjk:
            base = "Language requirement: Respond in Simplified Chinese."
        else:
            base = "Language requirement: Respond in the same language as the user's input."

        if json_mode:
            return f"{base} Keep JSON keys exactly as requested."
        return base

    def _build_fallback_learning_path(
        self,
        problem_title: str,
        problem_description: str,
        existing_knowledge: List[str],
    ) -> List[Dict[str, Any]]:
        knowledge_text = ", ".join(existing_knowledge) if existing_knowledge else "your current foundation"
        first_resource = "Existing notes and prior project docs"
        if problem_description:
            first_resource = problem_description[:120]

        return [
            {
                "step": 1,
                "concept": "Clarify goal and constraints",
                "description": (
                    f"Define success criteria for '{problem_title}' and list hard constraints. "
                    f"Anchor decisions using {knowledge_text}."
                ),
                "resources": [first_resource, "Problem statement"],
            },
            {
                "step": 2,
                "concept": "Create and validate a minimal solution",
                "description": (
                    "Build the smallest viable implementation, run one validation cycle, "
                    "and record open risks for the next iteration."
                ),
                "resources": ["Current codebase", "Test checklist"],
            },
        ]

    def normalize_concepts(self, concepts: List[str], limit: int = 8) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for raw in concepts or []:
            concept = re.sub(r"\s+", " ", str(raw or "")).strip(" \t\r\n,.;:|/-")
            if not concept:
                continue
            if len(concept) > 80:
                concept = concept[:80].rstrip()
            key = concept.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(concept)
            if len(normalized) >= limit:
                break
        return normalized

    def normalize_concept_key(self, concept: str) -> str:
        base = re.sub(r"\s+", " ", str(concept or "")).strip().casefold()
        if not base:
            return ""
        return re.sub(r"[^\w\u4e00-\u9fff\s-]", "", base).strip()

    def _normalize_float(self, value: Any, default: float, min_value: float, max_value: float) -> float:
        try:
            num = float(value)
        except (TypeError, ValueError):
            num = default
        return round(max(min_value, min(max_value, num)), 4)

    def _normalize_int(self, value: Any, default: int, min_value: int, max_value: int) -> int:
        try:
            num = int(round(float(value)))
        except (TypeError, ValueError):
            num = default
        return max(min_value, min(max_value, num))

    def _normalize_bool(self, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "y", "1"}:
                return True
            if lowered in {"false", "no", "n", "0"}:
                return False
        return default

    def _derive_mastery_defaults(self, correctness: str, misconception_count: int) -> tuple[int, bool]:
        verdict = correctness.strip().lower()
        if any(marker in verdict for marker in ("incorrect", "wrong", "not correct", "错误", "不正确")):
            return 35, False
        if any(marker in verdict for marker in ("partially", "mostly", "部分", "基本正确", "较为正确")):
            return (68 if misconception_count <= 1 else 60), misconception_count == 0
        if any(marker in verdict for marker in ("correct", "正确")):
            return (86 if misconception_count == 0 else 78), misconception_count <= 1
        return 55, False

    def normalize_feedback_structured(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        data = payload or {}
        correctness = str(data.get("correctness", "") or "").strip()
        misconceptions = [
            str(item).strip()
            for item in (data.get("misconceptions") or [])
            if str(item).strip()
        ]
        suggestions = [
            str(item).strip()
            for item in (data.get("suggestions") or [])
            if item is not None and str(item).strip()
        ]
        next_question = str(data.get("next_question", "") or "").strip()

        default_score, default_pass = self._derive_mastery_defaults(
            correctness=correctness,
            misconception_count=len(misconceptions),
        )
        mastery_score = self._normalize_int(data.get("mastery_score"), 0, 0, 100)
        confidence = self._normalize_float(data.get("confidence"), 0.0, 0.0, 1.0)
        pass_stage = self._normalize_bool(data.get("pass_stage"), False)

        raw_dimensions = data.get("dimension_scores")
        dimensions: Dict[str, int] = {}
        if isinstance(raw_dimensions, dict):
            for key in ("accuracy", "completeness", "transfer", "rigor"):
                dimensions[key] = self._normalize_int(raw_dimensions.get(key), mastery_score, 0, 100)
        else:
            dimensions = {
                "accuracy": mastery_score,
                "completeness": mastery_score,
                "transfer": mastery_score,
                "rigor": mastery_score,
            }

        decision_reason = str(data.get("decision_reason", "") or "").strip()
        if not decision_reason:
            decision_reason = (
                f"Mastery score={mastery_score}, confidence={confidence}, misconceptions={len(misconceptions)}"
            )

        return {
            "correctness": correctness,
            "misconceptions": misconceptions,
            "suggestions": suggestions,
            "next_question": next_question,
            "mastery_score": mastery_score,
            "dimension_scores": dimensions,
            "confidence": confidence,
            "pass_stage": pass_stage,
            "decision_reason": decision_reason,
        }

    def build_learning_answer_fallback(self, question: str, step_concept: str, mode: str = "direct") -> str:
        question = str(question or "").strip()
        step_concept = str(step_concept or "this concept").strip()
        if mode == "guided":
            return (
                f"Hint: focus on the core boundary of '{step_concept}'. "
                f"Try one concrete example for your question ({question or 'your question'}), "
                "then explain why an alternative interpretation would fail."
            )
        return (
            f"A concise starting point for '{step_concept}': define it in one sentence, "
            "contrast it with the closest confusing concept, then apply it in one concrete example."
        )

    def _hint_tokens(self, text: str) -> set[str]:
        tokens = set(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", (text or "").lower()))
        return {token for token in tokens if token.strip()}

    def _hint_similarity(self, left: str, right: str) -> float:
        left_tokens = self._hint_tokens(left)
        right_tokens = self._hint_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        inter = left_tokens.intersection(right_tokens)
        union = left_tokens.union(right_tokens)
        if not union:
            return 0.0
        return len(inter) / len(union)

    def _dedupe_hint_actions(
        self,
        actions: List[str],
        previous_texts: Optional[List[str]] = None,
        cjk_context: bool = False,
    ) -> List[str]:
        cleaned_previous = [str(item).strip() for item in (previous_texts or []) if str(item).strip()]
        output: List[str] = []
        seen_norms = set()

        for raw in actions:
            action = str(raw or "").strip()
            if not action:
                continue
            norm = re.sub(r"\s+", " ", action).strip().casefold()
            if norm in seen_norms:
                continue

            is_repetitive = False
            for previous in cleaned_previous:
                previous_norm = re.sub(r"\s+", " ", previous).strip().casefold()
                if not previous_norm:
                    continue
                if norm == previous_norm:
                    is_repetitive = True
                    break
                if len(norm) >= 8 and (norm in previous_norm or previous_norm in norm):
                    is_repetitive = True
                    break
                if self._hint_similarity(norm, previous_norm) >= 0.72:
                    is_repetitive = True
                    break

            if is_repetitive:
                continue

            seen_norms.add(norm)
            output.append(action)
            if len(output) >= 3:
                break

        if len(output) >= 2:
            return output

        fallback_actions = (
            [
                "先写出你已经确认正确的一点。",
                "再补一个具体例子来检验这一步。",
                "最后写出一个不确定点请求反馈。",
            ]
            if cjk_context
            else [
                "Write one thing you are confident about first.",
                "Add one concrete example to test this step.",
                "List one uncertainty you want feedback on.",
            ]
        )
        for item in fallback_actions:
            norm = re.sub(r"\s+", " ", item).strip().casefold()
            if norm in seen_norms:
                continue
            seen_norms.add(norm)
            output.append(item)
            if len(output) >= 3:
                break

        return output[:3]

    def _fallback_concepts_from_problem(
        self,
        problem_title: str,
        problem_description: str,
        limit: int = 8,
    ) -> List[str]:
        combined = "\n".join([problem_title or "", problem_description or ""])
        candidates: List[str] = [problem_title]

        if self._contains_cjk(combined):
            candidates.extend(re.findall(r"[\u4e00-\u9fff]{2,12}", combined))
        else:
            stop_words = {
                "what", "when", "where", "which", "with", "from", "into", "this", "that",
                "need", "want", "have", "has", "for", "and", "the", "you", "your", "about",
            }
            words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", combined)
            candidates.extend([word for word in words if word.casefold() not in stop_words])

        return self.normalize_concepts(candidates, limit=limit)

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

        result = await self.llm.generate(prompt)
        try:
            parsed = json.loads(_clean_json_str(result))
            if isinstance(parsed, dict):
                parsed = parsed.get("concepts", [])
            if not isinstance(parsed, list):
                return []
            return self.normalize_concepts([str(item) for item in parsed], limit=normalized_limit)
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

    def build_embedding_text(
        self,
        title: str,
        user_notes: Optional[str] = None,
        examples: Optional[List[str]] = None,
        counter_examples: Optional[List[str]] = None,
    ) -> str:
        sections = [
            title or "",
            user_notes or "",
            " ".join(examples or []),
            " ".join(counter_examples or []),
        ]
        return "\n".join(section for section in sections if section).strip()

    def build_problem_embedding_text(
        self,
        title: str,
        description: Optional[str] = None,
        associated_concepts: Optional[List[str]] = None,
    ) -> str:
        sections = [
            title or "",
            description or "",
            " ".join(associated_concepts or []),
        ]
        return "\n".join(section for section in sections if section).strip()

    def build_resource_embedding_text(
        self,
        title: Optional[str] = None,
        url: Optional[str] = None,
        link_type: Optional[str] = None,
        ai_summary: Optional[str] = None,
        status: Optional[str] = None,
    ) -> str:
        sections = [
            title or "",
            url or "",
            link_type or "",
            ai_summary or "",
            status or "",
        ]
        return "\n".join(section for section in sections if section).strip()

    def generate_embedding(self, text: str) -> List[float]:
        tokens = self._tokenize_text(text)
        if not tokens:
            return [0.0] * self.embedding_dimensions

        vector = [0.0] * self.embedding_dimensions
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.embedding_dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            magnitude = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * magnitude

        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0:
            return [0.0] * self.embedding_dimensions
        return [round(value / norm, 8) for value in vector]

    def generate_card_embedding(
        self,
        title: str,
        user_notes: Optional[str] = None,
        examples: Optional[List[str]] = None,
        counter_examples: Optional[List[str]] = None,
    ) -> List[float]:
        return self.generate_embedding(
            self.build_embedding_text(
                title=title,
                user_notes=user_notes,
                examples=examples,
                counter_examples=counter_examples,
            )
        )

    def serialize_embedding_for_pgvector(self, embedding: List[float]) -> str:
        normalized = embedding[:self.embedding_dimensions]
        return "[" + ",".join(f"{value:.8f}" for value in normalized) + "]"

    def refresh_card_embedding(self, card) -> List[float]:
        card.embedding = self.generate_card_embedding(
            title=card.title,
            user_notes=card.user_notes,
            examples=card.examples,
            counter_examples=card.counter_examples,
        )
        return card.embedding

    def refresh_problem_embedding(self, problem) -> List[float]:
        problem.embedding = self.generate_embedding(
            self.build_problem_embedding_text(
                title=problem.title,
                description=problem.description,
                associated_concepts=problem.associated_concepts,
            )
        )
        return problem.embedding

    def refresh_resource_embedding(self, resource) -> List[float]:
        resource.embedding = self.generate_embedding(
            self.build_resource_embedding_text(
                title=resource.title,
                url=resource.url,
                link_type=resource.link_type,
                ai_summary=resource.ai_summary,
                status=resource.status,
            )
        )
        return resource.embedding

    def score_model_card(self, card, query: str, query_embedding: List[float]) -> float:
        card_text = self.build_embedding_text(
            title=card.title,
            user_notes=card.user_notes,
            examples=card.examples,
            counter_examples=card.counter_examples,
        )
        haystack_tokens = set(self._tokenize_text(card_text))
        query_tokens = self._tokenize_text(query)
        lexical_score = 0.0
        if query_tokens:
            token_hits = sum(1 for token in query_tokens if token in haystack_tokens)
            lexical_score = token_hits / len(query_tokens)
        if query.lower() in card_text.lower():
            lexical_score += 0.5

        semantic_score = cosine_similarity(
            card.embedding or self.generate_embedding(card_text),
            query_embedding,
        )
        return (lexical_score * 0.7) + (max(semantic_score, 0.0) * 0.3)

    def score_problem(self, problem, query: str, query_embedding: List[float]) -> float:
        problem_text = self.build_problem_embedding_text(
            title=problem.title,
            description=problem.description,
            associated_concepts=problem.associated_concepts,
        )
        lexical_score = self._score_text_match(problem_text, query)
        semantic_score = cosine_similarity(
            problem.embedding or self.generate_embedding(problem_text),
            query_embedding,
        )
        return (lexical_score * 0.7) + (max(semantic_score, 0.0) * 0.3)

    def score_resource(self, resource, query: str, query_embedding: List[float]) -> float:
        resource_text = self.build_resource_embedding_text(
            title=resource.title,
            url=resource.url,
            link_type=resource.link_type,
            ai_summary=resource.ai_summary,
            status=resource.status,
        )
        lexical_score = self._score_text_match(resource_text, query)
        semantic_score = cosine_similarity(
            resource.embedding or self.generate_embedding(resource_text),
            query_embedding,
        )
        return (lexical_score * 0.7) + (max(semantic_score, 0.0) * 0.3)

    def rank_model_cards(self, cards: List[Any], query: str) -> List[Any]:
        query = query.strip()
        if not query:
            return cards

        query_embedding = self.generate_embedding(query)
        scored_cards = []
        for card in cards:
            score = self.score_model_card(card, query, query_embedding)
            if score >= 0.15:
                scored_cards.append((score, card))

        scored_cards.sort(
            key=lambda item: (
                item[0],
                getattr(item[1], "updated_at", None) or getattr(item[1], "created_at", None),
            ),
            reverse=True,
        )
        return [card for _, card in scored_cards]

    def rank_problems(self, problems: List[Any], query: str) -> List[Any]:
        query = query.strip()
        if not query:
            return problems

        query_embedding = self.generate_embedding(query)
        scored_problems = []
        for problem in problems:
            score = self.score_problem(problem, query, query_embedding)
            if score >= 0.15:
                scored_problems.append((score, problem))

        scored_problems.sort(
            key=lambda item: (
                item[0],
                getattr(item[1], "updated_at", None) or getattr(item[1], "created_at", None),
            ),
            reverse=True,
        )
        return [problem for _, problem in scored_problems]

    def rank_resources(self, resources: List[Any], query: str) -> List[Any]:
        query = query.strip()
        if not query:
            return resources

        query_embedding = self.generate_embedding(query)
        scored_resources = []
        for resource in resources:
            score = self.score_resource(resource, query, query_embedding)
            if score >= 0.15:
                scored_resources.append((score, resource))

        scored_resources.sort(
            key=lambda item: (
                item[0],
                getattr(item[1], "updated_at", None) or getattr(item[1], "created_at", None),
            ),
            reverse=True,
        )
        return [resource for _, resource in scored_resources]

    def _score_text_match(self, text: str, query: str) -> float:
        haystack = set(self._tokenize_text(text))
        query_tokens = self._tokenize_text(query)
        if not query_tokens:
            return 0.0
        token_hits = sum(1 for token in query_tokens if token in haystack)
        substring_bonus = 0.5 if query.lower() in text.lower() else 0.0
        return (token_hits / len(query_tokens)) + substring_bonus

    def _build_retrieval_item(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        score: float,
        preview: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "title": title,
            "score": round(max(score, 0.0), 4),
            "preview": (preview or "")[:240] or None,
        }

    def score_review(self, review, query: str) -> float:
        content = review.content or {}
        review_text = "\n".join(
            [
                review.review_type or "",
                review.period or "",
                str(content.get("summary", "")),
                str(content.get("insights", "")),
                str(content.get("next_steps", "")),
            ]
        )
        return self._score_text_match(review_text, query)

    async def build_retrieval_context(
        self,
        db,
        user_id: str,
        query: str,
        limit: int = 5,
        source: str = "unknown",
    ) -> str:
        from app.models.entities.user import ModelCard, Problem, RetrievalEvent, Review

        sections: List[str] = []
        items: List[Dict[str, Any]] = []
        normalized_limit = max(1, limit)
        query_embedding = self.generate_embedding(query)

        cards_result = await db.execute(
            select(ModelCard)
            .where(ModelCard.user_id == user_id)
            .order_by(ModelCard.updated_at.desc())
        )
        ranked_cards = self.rank_model_cards(list(cards_result.scalars().all()), query)[:3]
        for card in ranked_cards:
            score = self.score_model_card(card, query, query_embedding)
            sections.append(
                "\n".join(
                    [
                        f"[Model Card] {card.title}",
                        f"Notes: {card.user_notes or 'N/A'}",
                        f"Examples: {', '.join(card.examples or []) or 'N/A'}",
                        f"Counter Examples: {', '.join(card.counter_examples or []) or 'N/A'}",
                    ]
                )
            )
            items.append(
                self._build_retrieval_item(
                    entity_type="model_card",
                    entity_id=str(card.id),
                    title=card.title,
                    score=score,
                    preview=card.user_notes or ", ".join(card.examples or []),
                )
            )

        problems_result = await db.execute(
            select(Problem)
            .where(Problem.user_id == user_id)
            .order_by(Problem.updated_at.desc())
        )
        ranked_problems = self.rank_problems(list(problems_result.scalars().all()), query)[:2]
        for problem in ranked_problems:
            score = self.score_problem(problem, query, query_embedding)
            sections.append(
                "\n".join(
                    [
                        f"[Problem] {problem.title}",
                        f"Description: {problem.description or 'N/A'}",
                        f"Concepts: {', '.join(problem.associated_concepts or []) or 'N/A'}",
                        f"Status: {problem.status or 'N/A'}",
                    ]
                )
            )
            items.append(
                self._build_retrieval_item(
                    entity_type="problem",
                    entity_id=str(problem.id),
                    title=problem.title,
                    score=score,
                    preview=problem.description or ", ".join(problem.associated_concepts or []),
                )
            )

        reviews_result = await db.execute(
            select(Review)
            .where(Review.user_id == user_id)
            .order_by(Review.created_at.desc())
        )
        scored_reviews = []
        for review in reviews_result.scalars().all():
            score = self.score_review(review, query)
            if score > 0:
                scored_reviews.append((score, review))
        scored_reviews.sort(key=lambda item: item[0], reverse=True)

        for score, review in scored_reviews[:2]:
            content = review.content or {}
            sections.append(
                "\n".join(
                    [
                        f"[Review] {review.review_type} / {review.period}",
                        f"Summary: {content.get('summary', 'N/A')}",
                        f"Insights: {content.get('insights', 'N/A')}",
                        f"Next Steps: {content.get('next_steps', 'N/A')}",
                    ]
                )
            )
            items.append(
                self._build_retrieval_item(
                    entity_type="review",
                    entity_id=str(review.id),
                    title=f"{review.review_type} / {review.period}",
                    score=score,
                    preview=content.get("summary") or content.get("insights"),
                )
            )

        selected_sections = sections[:normalized_limit]
        selected_items = items[:normalized_limit]
        retrieval_context = "\n\n".join(selected_sections)

        if query.strip():
            db.add(
                RetrievalEvent(
                    user_id=user_id,
                    source=source,
                    query=query,
                    retrieval_context=retrieval_context or None,
                    items=selected_items,
                    result_count=len(selected_items),
                )
            )

        return retrieval_context

    def build_model_snapshot(self, card) -> Dict[str, Any]:
        return {
            "title": card.title,
            "user_notes": card.user_notes,
            "examples": card.examples or [],
            "counter_examples": card.counter_examples or [],
            "migration_attempts": card.migration_attempts or [],
            "concept_maps": card.concept_maps or {"nodes": [], "edges": []},
            "version": card.version,
        }
    
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
        
        result = await self.llm.generate(prompt)
        
        try:
            model_data = json.loads(_clean_json_str(result))
        except json.JSONDecodeError:
            model_data = {
                "concept_maps": {"nodes": [], "edges": []},
                "core_principles": [],
                "examples": [],
                "limitations": []
            }
        
        return model_data
    
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
        
        result = await self.llm.generate(prompt)
        
        try:
            counter_examples = json.loads(_clean_json_str(result))
        except json.JSONDecodeError:
            counter_examples = []
        
        return counter_examples
    
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
        
        result = await self.llm.generate(prompt)
        
        try:
            migrations = json.loads(_clean_json_str(result))
        except json.JSONDecodeError:
            migrations = []
        
        return migrations
    
    async def generate_learning_path(
        self,
        problem_title: str,
        problem_description: str,
        existing_knowledge: List[str],
    ) -> List[Dict[str, Any]]:
        language_instruction = self._build_language_instruction(
            problem_title,
            problem_description,
            ", ".join(existing_knowledge or []),
            json_mode=True,
        )
        prompt = f"""Generate an optimized learning path for:

Problem/Goal: {problem_title}
Description: {problem_description}
User's Existing Knowledge: {', '.join(existing_knowledge)}

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
        
        result = await self.llm.generate(prompt)
        
        try:
            path = json.loads(_clean_json_str(result))
        except json.JSONDecodeError as e:
            with open("llm_debug_zh.log", "w", encoding="utf-8") as f:
                f.write(f"JSON ERROR: {e}\\nRAW:\\n{result}\\n---\\n")
            print(f"Failed to parse path json. Error: {e}")
            path = []
        
        return path

    async def generate_learning_path_resilient(
        self,
        problem_title: str,
        problem_description: str,
        existing_knowledge: List[str],
        timeout_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        effective_timeout = timeout_seconds or get_settings().LEARNING_PATH_TIMEOUT_SECONDS
        try:
            path = await asyncio.wait_for(
                self.generate_learning_path(
                    problem_title=problem_title,
                    problem_description=problem_description,
                    existing_knowledge=existing_knowledge,
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
        
        return await self.llm.generate(prompt)

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

        result = await self.llm.generate(prompt)
        try:
            parsed = json.loads(_clean_json_str(result))
            if not isinstance(parsed, dict):
                raise ValueError("Step hint is not a JSON object")
            actions = parsed.get("next_actions", [])
            if not isinstance(actions, list):
                actions = []
            normalized_actions = [
                str(item).strip()
                for item in actions
                if str(item).strip()
            ][:3]
            deduped_actions = self._dedupe_hint_actions(
                actions=normalized_actions,
                previous_texts=previous_hint_texts,
                cjk_context=self._contains_cjk(
                    problem_title + problem_description + step_concept + step_description
                ),
            )
            return {
                "focus": str(parsed.get("focus", "")).strip(),
                "next_actions": deduped_actions,
                "starter": str(parsed.get("starter", "")).strip(),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            fallback_focus = (
                f"Focus on clarifying your understanding of '{step_concept}' in this step."
                if not self._contains_cjk(problem_title + problem_description + step_concept)
                else f"先聚焦澄清你对“{step_concept}”这一步的理解。"
            )
            fallback_actions = (
                [
                    "State what you already understand in 2-3 sentences.",
                    "Add one concrete example or mini attempt.",
                    "List one uncertainty you want feedback on.",
                ]
                if not self._contains_cjk(problem_title + problem_description + step_concept)
                else [
                    "先用 2-3 句话写出你已经理解的内容。",
                    "补一个具体例子或你的一次尝试。",
                    "写出一个最不确定的点，便于获得针对性反馈。",
                ]
            )
            fallback_actions = self._dedupe_hint_actions(
                actions=fallback_actions,
                previous_texts=previous_hint_texts,
                cjk_context=self._contains_cjk(problem_title + problem_description + step_concept),
            )
            fallback_starter = (
                f"My current understanding of {step_concept} is:"
                if not self._contains_cjk(problem_title + problem_description + step_concept)
                else f"我目前对“{step_concept}”的理解是："
            )
            return {
                "focus": fallback_focus,
                "next_actions": fallback_actions,
                "starter": fallback_starter,
            }

    def format_step_hint_text(self, structured_hint: Dict[str, Any]) -> str:
        focus = str(structured_hint.get("focus", "")).strip()
        actions = structured_hint.get("next_actions") or []
        starter = str(structured_hint.get("starter", "")).strip()

        action_lines = "\n".join(
            f"- {str(item).strip()}" for item in actions if str(item).strip()
        )
        blocks: List[str] = []
        if focus:
            blocks.append(f"Focus:\n{focus}")
        if action_lines:
            blocks.append(f"Next actions:\n{action_lines}")
        if starter:
            blocks.append(f"Starter sentence:\n{starter}")
        return "\n\n".join(blocks).strip()

    async def generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        retrieval_context: Optional[str] = None,
        provider_type: Optional[str] = None,
    ) -> str:
        return await self.llm.generate_with_context(
            prompt=prompt,
            context=context,
            retrieval_context=retrieval_context,
            provider_type=provider_type,
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

        result = await self.llm.generate(prompt)

        try:
            parsed = json.loads(_clean_json_str(result))
            return self.normalize_feedback_structured(parsed if isinstance(parsed, dict) else {})
        except json.JSONDecodeError:
            return self.normalize_feedback_structured({
                "correctness": "",
                "misconceptions": [],
                "suggestions": [result.strip()] if result.strip() else [],
                "next_question": "",
            })

    def format_feedback_text(self, structured_feedback: Dict[str, Any]) -> str:
        misconceptions = structured_feedback.get("misconceptions", [])
        suggestions = structured_feedback.get("suggestions", [])
        next_question = structured_feedback.get("next_question", "")
        correctness = structured_feedback.get("correctness", "")
        mastery_score = structured_feedback.get("mastery_score", 0)
        confidence = structured_feedback.get("confidence", 0.0)
        pass_stage = structured_feedback.get("pass_stage", False)
        decision_reason = structured_feedback.get("decision_reason", "")

        lines = [
            f"Correctness: {correctness or 'N/A'}",
            f"Mastery Score: {mastery_score}",
            f"Confidence: {confidence}",
            f"Pass Stage: {pass_stage}",
            f"Misconceptions: {' | '.join(misconceptions) if misconceptions else 'None'}",
            f"Suggestions: {' | '.join(suggestions) if suggestions else 'None'}",
            f"Next Question: {next_question or 'None'}",
            f"Decision Reason: {decision_reason or 'None'}",
        ]
        return "\n".join(lines)

    def parse_feedback_text(self, feedback_text: Optional[str]) -> Dict[str, Any]:
        if not feedback_text:
            return self.normalize_feedback_structured({
                "correctness": "",
                "misconceptions": [],
                "suggestions": [],
                "next_question": "",
            })

        structured = {
            "correctness": "",
            "mastery_score": 0,
            "confidence": 0.0,
            "pass_stage": False,
            "misconceptions": [],
            "suggestions": [],
            "next_question": "",
            "decision_reason": "",
        }

        patterns = {
            "correctness": r"Correctness:\s*(.*)",
            "mastery_score": r"Mastery Score:\s*(.*)",
            "confidence": r"Confidence:\s*(.*)",
            "pass_stage": r"Pass Stage:\s*(.*)",
            "misconceptions": r"Misconceptions:\s*(.*)",
            "suggestions": r"Suggestions:\s*(.*)",
            "next_question": r"Next Question:\s*(.*)",
            "decision_reason": r"Decision Reason:\s*(.*)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, feedback_text)
            if not match:
                continue
            value = match.group(1).strip()
            if key in ("misconceptions", "suggestions"):
                structured[key] = [] if value in ("None", "") else [item.strip() for item in value.split("|") if item.strip()]
            elif key == "mastery_score":
                structured[key] = self._normalize_int(value, 0, 0, 100)
            elif key == "confidence":
                structured[key] = self._normalize_float(value, 0.0, 0.0, 1.0)
            elif key == "pass_stage":
                structured[key] = self._normalize_bool(value, False)
            else:
                structured[key] = "" if value in ("None", "N/A") else value

        if (
            not structured["correctness"]
            and not structured["misconceptions"]
            and not structured["suggestions"]
            and not structured["next_question"]
        ):
            structured["suggestions"] = [feedback_text.strip()]

        return self.normalize_feedback_structured(structured)
    
    async def log_evolution(
        self,
        db,
        model_id: str,
        user_id: str,
        action: str,
        reason: str,
        snapshot: Optional[Dict[str, Any]] = None,
        previous_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.models.entities.user import EvolutionLog
        log = EvolutionLog(
            model_id=model_id,
            user_id=user_id,
            action_taken=action,
            reason_for_change=reason,
            snapshot=snapshot,
            previous_version_id=previous_version_id,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return {
            "id": log.id,
            "model_id": model_id,
            "action": action,
            "reason": reason,
        }

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
        return await self.llm.generate(prompt)


model_os_service = ModelOSService()
