from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator, UserDefinedType


def normalize_embedding(
    value: Optional[Sequence[float]],
    dimensions: int,
) -> Optional[list[float]]:
    if value is None:
        return None

    normalized = [float(item) for item in list(value)[:dimensions]]
    if len(normalized) < dimensions:
        normalized.extend([0.0] * (dimensions - len(normalized)))
    return normalized


def cosine_similarity(
    left: Optional[Sequence[float]],
    right: Optional[Sequence[float]],
) -> float:
    if not left or not right:
        return 0.0

    size = min(len(left), len(right))
    if size == 0:
        return 0.0

    dot_product = sum(float(left[i]) * float(right[i]) for i in range(size))
    left_norm = sum(float(left[i]) ** 2 for i in range(size)) ** 0.5
    right_norm = sum(float(right[i]) ** 2 for i in range(size)) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


class PGVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw):
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect):
        def process(value):
            normalized = normalize_embedding(value, self.dimensions)
            if normalized is None:
                return None
            return "[" + ",".join(f"{item:.8f}" for item in normalized) + "]"

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                stripped = value.strip().strip("[]")
                if not stripped:
                    return []
                return [float(item.strip()) for item in stripped.split(",") if item.strip()]
            if isinstance(value, (list, tuple)):
                return [float(item) for item in value]
            return value

        return process


class EmbeddingVector(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGVector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return normalize_embedding(value, self.dimensions)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return normalize_embedding(value, self.dimensions)
