from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.models.entities.user import User, ResourceLink
from app.schemas.resource_link import ResourceLinkCreate, ResourceLinkUpdate, ResourceLinkResponse
from app.api.routes.auth import get_current_user
from app.services.llm_service import llm_service

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.post("/", response_model=ResourceLinkResponse, status_code=201)
async def create_resource(
    data: ResourceLinkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resource = ResourceLink(
        user_id=current_user.id,
        url=data.url,
        title=data.title,
        link_type=data.link_type,
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


@router.get("/", response_model=List[ResourceLinkResponse])
async def list_resources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResourceLink)
        .where(ResourceLink.user_id == current_user.id)
        .order_by(ResourceLink.created_at.desc())
    )
    return result.scalars().all()


@router.put("/{resource_id}", response_model=ResourceLinkResponse)
async def update_resource(
    resource_id: UUID,
    data: ResourceLinkUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResourceLink).where(
            ResourceLink.id == str(resource_id),
            ResourceLink.user_id == current_user.id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if data.title is not None:
        resource.title = data.title
    if data.status is not None:
        resource.status = data.status
    await db.commit()
    await db.refresh(resource)
    return resource


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResourceLink).where(
            ResourceLink.id == str(resource_id),
            ResourceLink.user_id == current_user.id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    await db.delete(resource)
    await db.commit()


@router.post("/{resource_id}/interpret", response_model=ResourceLinkResponse)
async def interpret_resource(
    resource_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResourceLink).where(
            ResourceLink.id == str(resource_id),
            ResourceLink.user_id == current_user.id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    prompt = (
        f"Please analyze and summarize the following {'video' if resource.link_type == 'video' else 'web page'} link. "
        f"Title: {resource.title or 'Unknown'}. URL: {resource.url}. "
        "Provide a concise summary of what this resource is about, key takeaways, "
        "and how it might be useful for learning. Respond in the same language as the title if provided."
    )
    resource.ai_summary = await llm_service.generate(prompt)
    await db.commit()
    await db.refresh(resource)
    return resource
