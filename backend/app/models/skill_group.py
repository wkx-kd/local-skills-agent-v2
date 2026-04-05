import uuid
from datetime import datetime

from sqlalchemy import String, Column, Table, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 多对多关联表
skill_group_members = Table(
    "skill_group_members",
    Base.metadata,
    Column("skill_group_id", UUID(as_uuid=True), ForeignKey("skill_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class SkillGroup(Base):
    __tablename__ = "skill_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="skill_groups")
    skills = relationship("Skill", secondary=skill_group_members, lazy="selectin")
