import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class SkillInstallGit(BaseModel):
    source: str = "git"
    url: str


class SkillResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    version: str
    source_type: str
    source_url: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillListResponse(BaseModel):
    skills: List[SkillResponse]
    total: int


class SkillGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    skill_ids: List[uuid.UUID] = []


class SkillGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    skill_ids: Optional[List[uuid.UUID]] = None


class SkillGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    skills: List[SkillResponse]
    created_at: datetime

    model_config = {"from_attributes": True}
