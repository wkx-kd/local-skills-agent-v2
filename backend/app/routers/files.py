import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.uploaded_file import UploadedFile
from app.schemas.file import FileResponse as FileResponseSchema, FileListResponse
from app.core.security import get_current_user

router = APIRouter()


async def process_file_background(file_id: str, user_id: str):
    """后台任务：处理上传的文件（解析 + RAG）"""
    from app.services.rag_service import process_file_task
    await process_file_task(file_id, user_id)


@router.post("/upload", response_model=FileResponseSchema, status_code=status.HTTP_201_CREATED)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    conversation_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 检查文件大小
    content = await file.read()
    file_size = len(content)
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制",
        )

    # 存储文件
    user_dir = Path(settings.UPLOAD_DIR) / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4()
    suffix = Path(file.filename).suffix
    storage_path = user_dir / f"{file_id}{suffix}"
    storage_path.write_bytes(content)

    # 确定文件类型
    file_type = suffix.lstrip(".").lower() if suffix else "unknown"

    uploaded = UploadedFile(
        id=file_id,
        user_id=user.id,
        conversation_id=conversation_id,
        filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        storage_path=str(storage_path),
        processing_status="pending",
    )
    db.add(uploaded)
    await db.flush()
    await db.refresh(uploaded)

    # 触发后台任务处理文件（解析 + RAG 分块）
    background_tasks.add_task(
        process_file_background,
        str(file_id),
        str(user.id),
    )

    return uploaded


@router.get("", response_model=FileListResponse)
async def list_files(
    conversation_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(UploadedFile).where(UploadedFile.user_id == user.id)
    if conversation_id:
        base_query = base_query.where(UploadedFile.conversation_id == conversation_id)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        base_query.order_by(UploadedFile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    files = result.scalars().all()
    return FileListResponse(files=files, total=total)


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id, UploadedFile.user_id == user.id)
    )
    uploaded = result.scalar_one_or_none()
    if not uploaded:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    path = Path(uploaded.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已被删除")

    return FileResponse(path=str(path), filename=uploaded.filename)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.id == file_id, UploadedFile.user_id == user.id)
    )
    uploaded = result.scalar_one_or_none()
    if not uploaded:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 删除物理文件
    path = Path(uploaded.storage_path)
    if path.exists():
        path.unlink()

    # 删除 Milvus 向量（如果是 RAG 文件）
    if uploaded.processing_strategy == "rag":
        from app.services.milvus_client import get_milvus_client
        milvus = get_milvus_client()
        await milvus.delete_file_chunks(str(file_id))

    await db.delete(uploaded)