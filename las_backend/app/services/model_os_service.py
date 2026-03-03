from typing import List, Dict, Any, Optional
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

    async def build_retrieval_context(
        self,
        db,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> str:
        from app.models.entities.user import ModelCard, Problem, Review

        sections: List[str] = []

        cards_result = await db.execute(
            select(ModelCard)
            .where(ModelCard.user_id == user_id)
            .order_by(ModelCard.updated_at.desc())
        )
        ranked_cards = self.rank_model_cards(list(cards_result.scalars().all()), query)[:3]
        for card in ranked_cards:
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

        problems_result = await db.execute(
            select(Problem)
            .where(Problem.user_id == user_id)
            .order_by(Problem.updated_at.desc())
        )
        scored_problems = []
        for problem in problems_result.scalars().all():
            problem_text = "\n".join(
                [
                    problem.title or "",
                    problem.description or "",
                    " ".join(problem.associated_concepts or []),
                ]
            )
            score = self._score_text_match(problem_text, query)
            if score > 0:
                scored_problems.append((score, problem))
        scored_problems.sort(key=lambda item: item[0], reverse=True)
        for _, problem in scored_problems[:2]:
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

        reviews_result = await db.execute(
            select(Review)
            .where(Review.user_id == user_id)
            .order_by(Review.created_at.desc())
        )
        for review in list(reviews_result.scalars().all())[:2]:
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

        return "\n\n".join(sections[:limit])

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
}}"""
        
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
        prompt = f"""You are the Contradiction Generation Module in Model OS.

Current Model: {model_title}
Model Concepts: {', '.join(model_concepts)}
User's Response/Understanding: {user_response}

Generate 2-3 counter-examples or challenging questions that:
1. Test the boundaries of the user's understanding
2. Challenge assumptions in the model
3. Highlight potential misunderstandings

Format as a JSON array of strings, each being a counter-example or challenging question."""
        
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
        prompt = f"""You are the Cross-Domain Migration Module in Model OS.

Current Model: {model_title}
Model Concepts: {', '.join(model_concepts)}

Suggest 2-3 other domains where this model could be applied, with brief explanations of how the concepts translate.

Return as JSON array:
[
    {{"domain": "domain name", "application": "how to apply", "key_adaptations": "what to adapt"}}
]"""
        
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
]"""
        
        result = await self.llm.generate(prompt)
        
        try:
            path = json.loads(_clean_json_str(result))
        except json.JSONDecodeError as e:
            with open("llm_debug_zh.log", "w", encoding="utf-8") as f:
                f.write(f"JSON ERROR: {e}\\nRAW:\\n{result}\\n---\\n")
            print(f"Failed to parse path json. Error: {e}")
            path = []
        
        return path
    
    async def generate_feedback(
        self,
        user_response: str,
        concept: str,
        model_examples: List[str],
    ) -> str:
        prompt = f"""Provide feedback on the user's understanding:

Concept: {concept}
User's Response: {user_response}
Model Examples: {', '.join(model_examples)}

        Analyze the response and provide:
1. Whether the understanding is correct
2. Specific gaps or misconceptions
3. Suggestions for improvement
4. A challenging question to test deeper understanding"""
        
        return await self.llm.generate(prompt)

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
  "next_question": "a challenging follow-up question"
}}
"""

        result = await self.llm.generate(prompt)

        try:
            parsed = json.loads(_clean_json_str(result))
            return {
                "correctness": parsed.get("correctness", ""),
                "misconceptions": parsed.get("misconceptions", []),
                "suggestions": parsed.get("suggestions", []),
                "next_question": parsed.get("next_question", ""),
            }
        except json.JSONDecodeError:
            return {
                "correctness": "",
                "misconceptions": [],
                "suggestions": [result.strip()] if result.strip() else [],
                "next_question": "",
            }

    def format_feedback_text(self, structured_feedback: Dict[str, Any]) -> str:
        misconceptions = structured_feedback.get("misconceptions", [])
        suggestions = structured_feedback.get("suggestions", [])
        next_question = structured_feedback.get("next_question", "")
        correctness = structured_feedback.get("correctness", "")

        lines = [
            f"Correctness: {correctness or 'N/A'}",
            f"Misconceptions: {' | '.join(misconceptions) if misconceptions else 'None'}",
            f"Suggestions: {' | '.join(suggestions) if suggestions else 'None'}",
            f"Next Question: {next_question or 'None'}",
        ]
        return "\n".join(lines)

    def parse_feedback_text(self, feedback_text: Optional[str]) -> Dict[str, Any]:
        if not feedback_text:
            return {
                "correctness": "",
                "misconceptions": [],
                "suggestions": [],
                "next_question": "",
            }

        structured = {
            "correctness": "",
            "misconceptions": [],
            "suggestions": [],
            "next_question": "",
        }

        patterns = {
            "correctness": r"Correctness:\s*(.*)",
            "misconceptions": r"Misconceptions:\s*(.*)",
            "suggestions": r"Suggestions:\s*(.*)",
            "next_question": r"Next Question:\s*(.*)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, feedback_text)
            if not match:
                continue
            value = match.group(1).strip()
            if key in ("misconceptions", "suggestions"):
                structured[key] = [] if value in ("None", "") else [item.strip() for item in value.split("|") if item.strip()]
            else:
                structured[key] = "" if value in ("None", "N/A") else value

        if (
            not structured["correctness"]
            and not structured["misconceptions"]
            and not structured["suggestions"]
            and not structured["next_question"]
        ):
            structured["suggestions"] = [feedback_text.strip()]

        return structured
    
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
        prompt = f"""Compare two versions of a cognitive model card and summarize the evolution:

Model: {card_title}
Previous state: {old_desc}
Current state: {str(new_snapshot)}

Provide a concise summary (2-3 sentences) of what changed and why it matters for the learner's understanding."""
        return await self.llm.generate(prompt)


model_os_service = ModelOSService()
