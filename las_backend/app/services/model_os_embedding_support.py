from __future__ import annotations

import hashlib
from typing import Any, Callable, List, Optional

from app.core.vector import cosine_similarity


TokenizeFn = Callable[[str], List[str]]
GenerateEmbeddingFn = Callable[[str], List[float]]


def build_embedding_text(
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


def generate_embedding(
    text: str,
    *,
    embedding_dimensions: int,
    tokenize_text: TokenizeFn,
) -> List[float]:
    tokens = tokenize_text(text)
    if not tokens:
        return [0.0] * embedding_dimensions

    vector = [0.0] * embedding_dimensions
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % embedding_dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        magnitude = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * magnitude

    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return [0.0] * embedding_dimensions
    return [round(value / norm, 8) for value in vector]


def serialize_embedding_for_pgvector(
    embedding: List[float],
    *,
    embedding_dimensions: int,
) -> str:
    normalized = embedding[:embedding_dimensions]
    return "[" + ",".join(f"{value:.8f}" for value in normalized) + "]"


def score_text_match(
    text: str,
    query: str,
    *,
    tokenize_text: TokenizeFn,
) -> float:
    haystack = set(tokenize_text(text))
    query_tokens = tokenize_text(query)
    if not query_tokens:
        return 0.0
    token_hits = sum(1 for token in query_tokens if token in haystack)
    substring_bonus = 0.5 if query.lower() in text.lower() else 0.0
    return (token_hits / len(query_tokens)) + substring_bonus


def score_model_card(
    card: Any,
    query: str,
    query_embedding: List[float],
    *,
    tokenize_text: TokenizeFn,
    generate_embedding_fn: GenerateEmbeddingFn,
) -> float:
    card_text = build_embedding_text(
        title=card.title,
        user_notes=card.user_notes,
        examples=card.examples,
        counter_examples=card.counter_examples,
    )
    haystack_tokens = set(tokenize_text(card_text))
    query_tokens = tokenize_text(query)
    lexical_score = 0.0
    if query_tokens:
        token_hits = sum(1 for token in query_tokens if token in haystack_tokens)
        lexical_score = token_hits / len(query_tokens)
    if query.lower() in card_text.lower():
        lexical_score += 0.5

    semantic_score = cosine_similarity(
        card.embedding or generate_embedding_fn(card_text),
        query_embedding,
    )
    return (lexical_score * 0.7) + (max(semantic_score, 0.0) * 0.3)


def score_problem(
    problem: Any,
    query: str,
    query_embedding: List[float],
    *,
    tokenize_text: TokenizeFn,
    generate_embedding_fn: GenerateEmbeddingFn,
) -> float:
    problem_text = build_problem_embedding_text(
        title=problem.title,
        description=problem.description,
        associated_concepts=problem.associated_concepts,
    )
    lexical_score = score_text_match(problem_text, query, tokenize_text=tokenize_text)
    semantic_score = cosine_similarity(
        problem.embedding or generate_embedding_fn(problem_text),
        query_embedding,
    )
    return (lexical_score * 0.7) + (max(semantic_score, 0.0) * 0.3)


def score_resource(
    resource: Any,
    query: str,
    query_embedding: List[float],
    *,
    tokenize_text: TokenizeFn,
    generate_embedding_fn: GenerateEmbeddingFn,
) -> float:
    resource_text = build_resource_embedding_text(
        title=resource.title,
        url=resource.url,
        link_type=resource.link_type,
        ai_summary=resource.ai_summary,
        status=resource.status,
    )
    lexical_score = score_text_match(resource_text, query, tokenize_text=tokenize_text)
    semantic_score = cosine_similarity(
        resource.embedding or generate_embedding_fn(resource_text),
        query_embedding,
    )
    return (lexical_score * 0.7) + (max(semantic_score, 0.0) * 0.3)


def _rank_items(items: List[Any], scored_items: List[tuple[float, Any]]) -> List[Any]:
    if not scored_items:
        return []
    scored_items.sort(
        key=lambda item: (
            item[0],
            getattr(item[1], "updated_at", None) or getattr(item[1], "created_at", None),
        ),
        reverse=True,
    )
    return [item for _, item in scored_items]


def rank_model_cards(
    cards: List[Any],
    query: str,
    *,
    tokenize_text: TokenizeFn,
    generate_embedding_fn: GenerateEmbeddingFn,
) -> List[Any]:
    query = query.strip()
    if not query:
        return cards

    query_embedding = generate_embedding_fn(query)
    scored_cards = []
    for card in cards:
        score = score_model_card(
            card,
            query,
            query_embedding,
            tokenize_text=tokenize_text,
            generate_embedding_fn=generate_embedding_fn,
        )
        if score >= 0.15:
            scored_cards.append((score, card))
    return _rank_items(cards, scored_cards)


def rank_problems(
    problems: List[Any],
    query: str,
    *,
    tokenize_text: TokenizeFn,
    generate_embedding_fn: GenerateEmbeddingFn,
) -> List[Any]:
    query = query.strip()
    if not query:
        return problems

    query_embedding = generate_embedding_fn(query)
    scored_problems = []
    for problem in problems:
        score = score_problem(
            problem,
            query,
            query_embedding,
            tokenize_text=tokenize_text,
            generate_embedding_fn=generate_embedding_fn,
        )
        if score >= 0.15:
            scored_problems.append((score, problem))
    return _rank_items(problems, scored_problems)


def rank_resources(
    resources: List[Any],
    query: str,
    *,
    tokenize_text: TokenizeFn,
    generate_embedding_fn: GenerateEmbeddingFn,
) -> List[Any]:
    query = query.strip()
    if not query:
        return resources

    query_embedding = generate_embedding_fn(query)
    scored_resources = []
    for resource in resources:
        score = score_resource(
            resource,
            query,
            query_embedding,
            tokenize_text=tokenize_text,
            generate_embedding_fn=generate_embedding_fn,
        )
        if score >= 0.15:
            scored_resources.append((score, resource))
    return _rank_items(resources, scored_resources)
