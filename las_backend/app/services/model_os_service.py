from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.entities.llm_provider import LLMProvider, LLMModel
from app.models.entities.system_settings import SystemSettings
from app.services.llm_service import llm_service
from app.core.config import get_settings

from app.services import model_os_embedding_support as embedding_support
from app.services import model_os_generation_support as generation_support
from app.services import model_os_structured_support as structured_support


LLM_TASK_ROUTES_KEY = "llm_task_routes"


@dataclass(frozen=True)
class LLMTaskRoute:
    provider_id: Optional[int] = None
    provider_type: Optional[str] = None
    model_id: Optional[str] = None


class ModelOSService:
    def __init__(self):
        self.llm = llm_service
        self.settings = get_settings()
        self.embedding_dimensions = self.settings.MODEL_CARD_EMBEDDING_DIMENSIONS

    _feedback_structured_schema = staticmethod(structured_support.feedback_structured_schema)
    _step_hint_schema = staticmethod(structured_support.step_hint_schema)
    _learning_path_schema = staticmethod(structured_support.learning_path_schema)
    _related_concepts_schema = staticmethod(structured_support.related_concepts_schema)
    _model_card_schema = staticmethod(structured_support.model_card_schema)
    _counter_examples_schema = staticmethod(structured_support.counter_examples_schema)
    _migration_schema = staticmethod(structured_support.migration_schema)
    _tokenize_text = staticmethod(structured_support.tokenize_text)
    _contains_cjk = staticmethod(structured_support.contains_cjk)
    _count_cjk_chars = staticmethod(structured_support.count_cjk_chars)
    _build_language_instruction = staticmethod(structured_support.build_language_instruction)
    _build_fallback_learning_path = staticmethod(structured_support.build_fallback_learning_path)
    build_fallback_learning_path = staticmethod(structured_support.build_fallback_learning_path)
    sanitize_concept_candidate_text = staticmethod(structured_support.sanitize_concept_candidate_text)
    normalize_concepts = staticmethod(structured_support.normalize_concepts)
    is_low_signal_concept_candidate = staticmethod(structured_support.is_low_signal_concept_candidate)
    filter_low_signal_concepts = staticmethod(structured_support.filter_low_signal_concepts)
    normalize_concept_key = staticmethod(structured_support.normalize_concept_key)
    should_align_answer_language = staticmethod(structured_support.should_align_answer_language)
    build_answer_language_rewrite_prompt = staticmethod(structured_support.build_answer_language_rewrite_prompt)
    _normalize_float = staticmethod(structured_support.normalize_float)
    _normalize_int = staticmethod(structured_support.normalize_int)
    _normalize_bool = staticmethod(structured_support.normalize_bool)
    _derive_mastery_defaults = staticmethod(structured_support.derive_mastery_defaults)
    normalize_feedback_structured = staticmethod(structured_support.normalize_feedback_structured)
    build_learning_answer_fallback = staticmethod(structured_support.build_learning_answer_fallback)
    build_socratic_question_fallback = staticmethod(structured_support.build_socratic_question_fallback)
    _build_socratic_question_prompt = staticmethod(structured_support.build_socratic_question_prompt)
    _hint_tokens = staticmethod(structured_support.hint_tokens)
    _hint_similarity = staticmethod(structured_support.hint_similarity)
    _dedupe_hint_actions = staticmethod(structured_support.dedupe_hint_actions)
    _normalize_step_hint_structured = staticmethod(structured_support.normalize_step_hint_structured)
    _build_fallback_step_hint = staticmethod(structured_support.build_fallback_step_hint)
    _fallback_concepts_from_problem = staticmethod(structured_support.fallback_concepts_from_problem)
    build_problem_concepts_local = staticmethod(structured_support.build_problem_concepts_local)
    normalize_learning_path_payload = staticmethod(structured_support.normalize_learning_path_payload)
    _normalize_string_items = staticmethod(structured_support.normalize_string_items)
    _default_model_card_payload = staticmethod(structured_support.default_model_card_payload)
    normalize_model_card_payload = staticmethod(structured_support.normalize_model_card_payload)
    normalize_migration_payload = staticmethod(structured_support.normalize_migration_payload)
    format_step_hint_text = staticmethod(structured_support.format_step_hint_text)
    format_feedback_text = staticmethod(structured_support.format_feedback_text)
    parse_feedback_text = staticmethod(structured_support.parse_feedback_text)
    generate_socratic_question = generation_support.generate_socratic_question
    stream_socratic_question = generation_support.stream_socratic_question
    extract_related_concepts = generation_support.extract_related_concepts
    extract_related_concepts_resilient = generation_support.extract_related_concepts_resilient
    build_problem_concepts_resilient = generation_support.build_problem_concepts_resilient
    create_model_card = generation_support.create_model_card
    generate_counter_examples = generation_support.generate_counter_examples
    suggest_migration = generation_support.suggest_migration
    generate_learning_path = generation_support.generate_learning_path
    generate_learning_path_resilient = generation_support.generate_learning_path_resilient
    generate_feedback = generation_support.generate_feedback
    generate_step_hint = generation_support.generate_step_hint
    generate_feedback_structured = generation_support.generate_feedback_structured
    generate_evolution_summary = generation_support.generate_evolution_summary

    def _normalize_route_value(self, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None

    def _build_route(
        self,
        provider_id: Optional[int],
        provider_type: Optional[str],
        model_id: Optional[str],
    ) -> LLMTaskRoute:
        return LLMTaskRoute(
            provider_id=provider_id,
            provider_type=self._normalize_route_value(provider_type),
            model_id=self._normalize_route_value(model_id),
        )

    def _build_env_task_route(self, lane: str) -> LLMTaskRoute:
        if lane == "structured_heavy":
            return self._build_route(
                None,
                self.settings.LLM_STRUCTURED_HEAVY_PROVIDER_TYPE,
                self.settings.LLM_STRUCTURED_HEAVY_MODEL_ID,
            )
        return self._build_route(
            None,
            self.settings.LLM_INTERACTIVE_PROVIDER_TYPE,
            self.settings.LLM_INTERACTIVE_MODEL_ID,
        )

    def _build_env_fallback_route(self) -> LLMTaskRoute:
        return self._build_route(
            None,
            self.settings.LLM_FALLBACK_PROVIDER_TYPE,
            self.settings.LLM_FALLBACK_MODEL_ID,
        )

    async def _load_route_payloads(self) -> Dict[str, Any]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SystemSettings).where(SystemSettings.key == LLM_TASK_ROUTES_KEY)
            )
            setting = result.scalar_one_or_none()
            value = setting.value if setting and isinstance(setting.value, dict) else {}
            return value if isinstance(value, dict) else {}

    async def _resolve_db_route(self, lane: str) -> Optional[LLMTaskRoute]:
        payloads = await self._load_route_payloads()
        assignment = payloads.get(lane)
        if not isinstance(assignment, dict):
            return None

        provider_id = assignment.get("provider_id")
        model_record_id = assignment.get("model_record_id")
        if provider_id is None:
            return None

        try:
            normalized_provider_id = int(provider_id)
        except (TypeError, ValueError):
            return None

        normalized_model_record_id: Optional[int]
        if model_record_id is None:
            normalized_model_record_id = None
        else:
            try:
                normalized_model_record_id = int(model_record_id)
            except (TypeError, ValueError):
                return None

        async with AsyncSessionLocal() as db:
            provider = await db.get(LLMProvider, normalized_provider_id)
            if not provider or not provider.enabled:
                return None

            resolved_model_id: Optional[str] = None
            if normalized_model_record_id is not None:
                model = await db.get(LLMModel, normalized_model_record_id)
                if not model or not model.enabled or model.provider_id != provider.id:
                    return None
                resolved_model_id = model.model_id

            return self._build_route(
                provider.id,
                provider.provider_type,
                resolved_model_id,
            )

    async def resolve_task_route(self, lane: str) -> LLMTaskRoute:
        db_route = await self._resolve_db_route(lane)
        return db_route or self._build_env_task_route(lane)

    async def resolve_fallback_route(self) -> LLMTaskRoute:
        db_route = await self._resolve_db_route("fallback")
        return db_route or self._build_env_fallback_route()

    def _routes_match(self, left: LLMTaskRoute, right: LLMTaskRoute) -> bool:
        return (
            left.provider_id == right.provider_id
            and
            left.provider_type == right.provider_type
            and left.model_id == right.model_id
        )

    def _has_explicit_route(self, route: LLMTaskRoute) -> bool:
        return bool(route.provider_id is not None or route.provider_type or route.model_id)

    def _looks_like_llm_error(self, result: Any) -> bool:
        text = str(result or "").strip()
        return not text or text.startswith("Error:")

    async def generate_text_for_lane(
        self,
        prompt: str,
        *,
        lane: str = "interactive",
        allow_fallback: bool = True,
    ) -> str:
        primary = await self.resolve_task_route(lane)
        result = await self.llm.generate(
            prompt,
            provider_id=primary.provider_id,
            provider_type=primary.provider_type,
            model_id=primary.model_id,
        )
        if not allow_fallback or not self._looks_like_llm_error(result):
            return result

        fallback = await self.resolve_fallback_route()
        if not self._has_explicit_route(fallback) or self._routes_match(primary, fallback):
            return result

        fallback_result = await self.llm.generate(
            prompt,
            provider_id=fallback.provider_id,
            provider_type=fallback.provider_type,
            model_id=fallback.model_id,
        )
        return fallback_result if not self._looks_like_llm_error(fallback_result) else result

    async def generate_structured_for_lane(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        *,
        schema_name: str,
        lane: str = "interactive",
        allow_fallback: bool = True,
    ) -> Optional[Dict[str, Any] | List[Any]]:
        primary = await self.resolve_task_route(lane)
        structured = await self.llm.generate_structured_json(
            prompt,
            json_schema,
            schema_name=schema_name,
            provider_id=primary.provider_id,
            provider_type=primary.provider_type,
            model_id=primary.model_id,
        )
        if structured is not None or not allow_fallback:
            return structured

        fallback = await self.resolve_fallback_route()
        if not self._has_explicit_route(fallback) or self._routes_match(primary, fallback):
            return structured

        return await self.llm.generate_structured_json(
            prompt,
            json_schema,
            schema_name=schema_name,
            provider_id=fallback.provider_id,
            provider_type=fallback.provider_type,
            model_id=fallback.model_id,
        )

    def build_embedding_text(
        self,
        title: str,
        user_notes: Optional[str] = None,
        examples: Optional[List[str]] = None,
        counter_examples: Optional[List[str]] = None,
    ) -> str:
        return embedding_support.build_embedding_text(
            title=title,
            user_notes=user_notes,
            examples=examples,
            counter_examples=counter_examples,
        )

    def build_problem_embedding_text(
        self,
        title: str,
        description: Optional[str] = None,
        associated_concepts: Optional[List[str]] = None,
    ) -> str:
        return embedding_support.build_problem_embedding_text(
            title=title,
            description=description,
            associated_concepts=associated_concepts,
        )

    def build_resource_embedding_text(
        self,
        title: Optional[str] = None,
        url: Optional[str] = None,
        link_type: Optional[str] = None,
        ai_summary: Optional[str] = None,
        status: Optional[str] = None,
    ) -> str:
        return embedding_support.build_resource_embedding_text(
            title=title,
            url=url,
            link_type=link_type,
            ai_summary=ai_summary,
            status=status,
        )

    def generate_embedding(self, text: str) -> List[float]:
        return embedding_support.generate_embedding(
            text,
            embedding_dimensions=self.embedding_dimensions,
            tokenize_text=self._tokenize_text,
        )

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
        return embedding_support.serialize_embedding_for_pgvector(
            embedding,
            embedding_dimensions=self.embedding_dimensions,
        )

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
        return embedding_support.score_model_card(
            card,
            query,
            query_embedding,
            tokenize_text=self._tokenize_text,
            generate_embedding_fn=self.generate_embedding,
        )

    def score_problem(self, problem, query: str, query_embedding: List[float]) -> float:
        return embedding_support.score_problem(
            problem,
            query,
            query_embedding,
            tokenize_text=self._tokenize_text,
            generate_embedding_fn=self.generate_embedding,
        )

    def score_resource(self, resource, query: str, query_embedding: List[float]) -> float:
        return embedding_support.score_resource(
            resource,
            query,
            query_embedding,
            tokenize_text=self._tokenize_text,
            generate_embedding_fn=self.generate_embedding,
        )

    def rank_model_cards(self, cards: List[Any], query: str) -> List[Any]:
        return embedding_support.rank_model_cards(
            cards,
            query,
            tokenize_text=self._tokenize_text,
            generate_embedding_fn=self.generate_embedding,
        )

    def rank_problems(self, problems: List[Any], query: str) -> List[Any]:
        return embedding_support.rank_problems(
            problems,
            query,
            tokenize_text=self._tokenize_text,
            generate_embedding_fn=self.generate_embedding,
        )

    def rank_resources(self, resources: List[Any], query: str) -> List[Any]:
        return embedding_support.rank_resources(
            resources,
            query,
            tokenize_text=self._tokenize_text,
            generate_embedding_fn=self.generate_embedding,
        )

    def _score_text_match(self, text: str, query: str) -> float:
        return embedding_support.score_text_match(
            text,
            query,
            tokenize_text=self._tokenize_text,
        )

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
            "lifecycle_stage": getattr(card, "lifecycle_stage", "active"),
            "user_notes": card.user_notes,
            "examples": card.examples or [],
            "counter_examples": card.counter_examples or [],
            "migration_attempts": card.migration_attempts or [],
            "concept_maps": card.concept_maps or {"nodes": [], "edges": []},
            "version": card.version,
        }

    async def generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        retrieval_context: Optional[str] = None,
        provider_type: Optional[str] = None,
        provider_id: Optional[int] = None,
        model_id: Optional[str] = None,
        lane: str = "interactive",
    ) -> str:
        route = await self.resolve_task_route(lane)
        return await self.llm.generate_with_context(
            prompt=prompt,
            context=context,
            retrieval_context=retrieval_context,
            provider_id=provider_id or route.provider_id,
            provider_type=provider_type or route.provider_type,
            model_id=model_id or route.model_id,
        )

    async def stream_generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        retrieval_context: Optional[str] = None,
        provider_type: Optional[str] = None,
        provider_id: Optional[int] = None,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        lane: str = "interactive",
    ):
        route = await self.resolve_task_route(lane)
        async for token in self.llm.stream_generate_with_context(
            prompt=prompt,
            context=context,
            retrieval_context=retrieval_context,
            provider_id=provider_id or route.provider_id,
            provider_type=provider_type or route.provider_type,
            model_id=model_id or route.model_id,
            temperature=temperature,
        ):
            yield token

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


model_os_service = ModelOSService()
