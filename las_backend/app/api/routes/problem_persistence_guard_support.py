from typing import Awaitable, Callable, List, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def run_optional_persist(
    *,
    db: AsyncSession,
    fallback_reasons: List[str],
    label: str,
    operation: Callable[[], Awaitable[T]],
    default: T,
) -> T:
    """Isolate secondary persistence so core turn saving can still complete."""
    try:
        async with db.begin_nested():
            return await operation()
    except Exception:
        fallback_reasons.append(f"error:{label}")
        return default
