import uuid
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.skill import Skill
from app.models.skill_group import SkillGroup
from app.schemas.skill import (
    SkillInstallGit, SkillResponse, SkillListResponse,
    SkillGroupCreate, SkillGroupUpdate, SkillGroupResponse,
)
from app.core.security import get_current_user
from app.services.skill_installer import SkillInstaller

router = APIRouter()


# ─── Skill CRUD ─────────────────────────────────────────────

@router.get("", response_model=SkillListResponse)
async def list_skills(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Skill).order_by(Skill.name))
    skills = result.scalars().all()
    return SkillListResponse(skills=skills, total=len(skills))


@router.post("/install/git", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def install_skill_git(
    data: SkillInstallGit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    installer = SkillInstaller(db)
    result = await installer.install_from_git(
        git_url=data.url,
        user_id=str(user.id),
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    # 返回新创建的 Skill
    skill_result = await db.execute(select(Skill).where(Skill.id == uuid.UUID(result.skill_id)))
    return skill_result.scalar_one()


@router.post("/install/upload", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def install_skill_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 检查文件类型
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 ZIP 文件",
        )

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        installer = SkillInstaller(db)
        result = await installer.install_from_zip(
            zip_path=tmp_path,
            user_id=str(user.id),
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error,
            )

        # 返回新创建的 Skill
        skill_result = await db.execute(
            select(Skill).where(Skill.id == uuid.UUID(result.skill_id))
        )
        return skill_result.scalar_one()
    finally:
        # 删除临时文件
        tmp_path.unlink(missing_ok=True)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    installer = SkillInstaller(db)
    success = await installer.uninstall(str(skill_id))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill不存在")


@router.put("/{skill_id}/toggle", response_model=SkillResponse)
async def toggle_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill不存在")
    skill.is_active = not skill.is_active
    await db.flush()
    await db.refresh(skill)
    return skill


@router.post("/refresh", response_model=SkillListResponse)
async def refresh_skills(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刷新 Skill 注册表（扫描 skills/ 目录）"""
    installer = SkillInstaller(db)
    await installer.refresh_skills()

    result = await db.execute(select(Skill).order_by(Skill.name))
    skills = result.scalars().all()
    return SkillListResponse(skills=skills, total=len(skills))


# ─── Skill Group CRUD ───────────────────────────────────────

@router.post("/groups", response_model=SkillGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_skill_group(
    data: SkillGroupCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skills = []
    if data.skill_ids:
        result = await db.execute(select(Skill).where(Skill.id.in_(data.skill_ids)))
        skills = list(result.scalars().all())

    group = SkillGroup(
        user_id=user.id,
        name=data.name,
        description=data.description,
        skills=skills
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


@router.get("/groups", response_model=list[SkillGroupResponse])
async def list_skill_groups(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SkillGroup).where(SkillGroup.user_id == user.id).order_by(SkillGroup.name)
    )
    return result.scalars().all()


@router.get("/groups/{group_id}", response_model=SkillGroupResponse)
async def get_skill_group(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SkillGroup).where(SkillGroup.id == group_id, SkillGroup.user_id == user.id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组不存在")
    return group


@router.put("/groups/{group_id}", response_model=SkillGroupResponse)
async def update_skill_group(
    group_id: uuid.UUID,
    data: SkillGroupUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SkillGroup).where(SkillGroup.id == group_id, SkillGroup.user_id == user.id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组不存在")

    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    if data.skill_ids is not None:
        skill_result = await db.execute(select(Skill).where(Skill.id.in_(data.skill_ids)))
        group.skills = list(skill_result.scalars().all())

    await db.flush()
    await db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill_group(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SkillGroup).where(SkillGroup.id == group_id, SkillGroup.user_id == user.id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组不存在")
    await db.delete(group)