import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import (
    ConversationCreate, ConversationUpdate,
    ConversationResponse, ConversationListResponse,
)
from app.schemas.message import MessageListResponse, MessageResponse
from app.core.security import get_current_user

router = APIRouter()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(user_id=user.id, title=data.title, model=data.model, skill_group_id=data.skill_group_id)
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(Conversation).where(Conversation.user_id == user.id)
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        base_query.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = result.scalars().all()
    return ConversationListResponse(conversations=conversations, total=total)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return conv


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(conv, field, value)
    await db.flush()
    await db.refresh(conv)
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    await db.delete(conv)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证会话归属
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    base_query = select(Message).where(Message.conversation_id == conversation_id)
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        base_query.order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = result.scalars().all()
    return MessageListResponse(messages=messages, total=total)
