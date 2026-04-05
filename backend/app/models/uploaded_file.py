import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, csv, xlsx, png, jpg, txt, py, etc.
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    processing_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)  # full_text, rag
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    text_content: Mapped[str | None] = mapped_column(String, nullable=True)  # 小文件全文存储
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="uploaded_files")
