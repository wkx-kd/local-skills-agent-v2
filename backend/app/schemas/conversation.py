import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"
    model: Optional[str] = "qwen3.6-plus"
    skill_group_id: Optional[uuid.UUID] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    skill_group_id: Optional[uuid.UUID] = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    model: str
    skill_group_id: Optional[uuid.UUID]
    summary: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int
