import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class FileResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    processing_status: str
    processing_strategy: Optional[str]
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    files: List[FileResponse]
    total: int
