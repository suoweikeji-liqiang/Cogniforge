import asyncio
import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.entities.user import ModelCard, Problem, ResourceLink
from app.services.model_os_service import model_os_service


async def main():
    async with AsyncSessionLocal() as db:
        cards_result = await db.execute(
            select(ModelCard).order_by(ModelCard.created_at.asc())
        )
        cards = list(cards_result.scalars().all())
        for card in cards:
            model_os_service.refresh_card_embedding(card)

        problems_result = await db.execute(
            select(Problem).order_by(Problem.created_at.asc())
        )
        problems = list(problems_result.scalars().all())
        for problem in problems:
            model_os_service.refresh_problem_embedding(problem)

        resources_result = await db.execute(
            select(ResourceLink).order_by(ResourceLink.created_at.asc())
        )
        resources = list(resources_result.scalars().all())
        for resource in resources:
            model_os_service.refresh_resource_embedding(resource)

        await db.commit()
        print(
            f"Updated embeddings for {len(cards)} model cards, "
            f"{len(problems)} problems, {len(resources)} resources"
        )


if __name__ == "__main__":
    asyncio.run(main())
