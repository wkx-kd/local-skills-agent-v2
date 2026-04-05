import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: Any  # JSONB content
    token_count: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
