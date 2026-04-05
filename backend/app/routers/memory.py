import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.memory import Memory
from app.core.security import get_current_user

router = APIRouter()


class MemoryResponse(BaseModel):
    id: uuid.UUID
    type: str
    category: str
    content: str
    importance_score: float
    access_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    memories: List[MemoryResponse]
    total: int


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    type: Optional[str] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(Memory).where(Memory.user_id == user.id)
    if type:
        base_query = base_query.where(Memory.type == type)
    if category:
        base_query = base_query.where(Memory.category == category)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        base_query.order_by(Memory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    memories = result.scalars().all()
    return MemoryListResponse(memories=memories, total=total)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == user.id)
    )
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记忆不存在")
    if mem.type == "long_term" and mem.milvus_id:
        from app.services.milvus_client import get_milvus_client
        milvus = get_milvus_client()
        await milvus.delete_memory(mem.milvus_id)
    await db.delete(mem)
