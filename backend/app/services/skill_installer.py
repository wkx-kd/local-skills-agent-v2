"""
Skill 安装服务 — 支持 Git clone 和 ZIP 上传两种方式

安装流程：
1. Git clone / ZIP 解压到 skills/ 目录
2. 验证 SKILL.md 存在且格式正确
3. 解析 YAML frontmatter
4. 注册到 PostgreSQL
"""

import os
import shutil
import tempfile
import uuid
import yaml
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.skill import Skill
from app.models.skill_group import SkillGroup, skill_group_members


@dataclass
class SkillMeta:
    """Skill 元数据"""
    name: str
    description: str
    version: str = "1.0.0"


@dataclass
class InstallResult:
    """安装结果"""
    success: bool
    skill_id: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class SkillInstaller:
    """
    Skill 安装器。

    安装源：
    - Git 仓库：git clone 到 skills/ 目录
    - ZIP 文件：解压到 skills/ 目录
    """

    def __init__(self, db: AsyncSession, skills_dir: Optional[Path] = None):
        self.db = db
        self.skills_dir = skills_dir or settings.SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _parse_skill_md(self, skill_md_path: Path) -> Optional[SkillMeta]:
        """
        解析 SKILL.md 文件，提取元数据。

        Args:
            skill_md_path: SKILL.md 文件路径

        Returns:
            SkillMeta 对象，解析失败返回 None
        """
        if not skill_md_path.exists():
            return None

        content = skill_md_path.read_text(encoding="utf-8")

        # 检查 YAML frontmatter
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            meta = yaml.safe_load(parts[1])
            if not meta or not meta.get("name"):
                return None

            return SkillMeta(
                name=meta.get("name", ""),
                description=meta.get("description", ""),
                version=meta.get("version", "1.0.0"),
            )
        except yaml.YAMLError:
            return None

    async def install_from_git(
        self,
        git_url: str,
        user_id: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> InstallResult:
        """
        从 Git 仓库安装 Skill。

        Args:
            git_url: Git 仓库 URL
            user_id: 安装用户 ID（可选）
            branch: 分支名（可选，默认主分支）

        Returns:
            InstallResult
        """
        # 从 URL 提取目录名
        repo_name = git_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        # 检查是否已存在同名目录
        target_dir = self.skills_dir / repo_name
        if target_dir.exists():
            return InstallResult(
                success=False,
                error=f"Skill 目录已存在: {repo_name}，请先卸载或使用不同名称",
            )

        # Git clone
        def _clone():
            import subprocess
            cmd = ["git", "clone", git_url, str(target_dir)]
            if branch:
                cmd.extend(["-b", branch])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise Exception(f"Git clone 失败: {result.stderr}")
            return True

        try:
            await asyncio.to_thread(_clone)
        except Exception as e:
            # 清理可能创建的目录
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return InstallResult(success=False, error=str(e))

        # 验证 SKILL.md
        skill_md_path = target_dir / "SKILL.md"
        meta = self._parse_skill_md(skill_md_path)

        if not meta:
            # 删除克隆的目录
            shutil.rmtree(target_dir, ignore_errors=True)
            return InstallResult(
                success=False,
                error="SKILL.md 不存在或格式错误（需要 YAML frontmatter 包含 name 和 description）",
            )

        # 检查数据库中是否已存在同名 Skill
        from sqlalchemy import select
        result = await self.db.execute(select(Skill).where(Skill.name == meta.name))
        if result.scalar_one_or_none():
            shutil.rmtree(target_dir, ignore_errors=True)
            return InstallResult(
                success=False,
                error=f"Skill 名称已存在: {meta.name}",
            )

        # 注册到数据库
        skill = Skill(
            name=meta.name,
            description=meta.description,
            version=meta.version,
            source_type="git",
            source_url=git_url,
            install_path=str(target_dir),
            installed_by=uuid.UUID(user_id) if user_id else None,
        )
        self.db.add(skill)
        await self.db.flush()
        await self.db.refresh(skill)

        return InstallResult(
            success=True,
            skill_id=str(skill.id),
            name=skill.name,
        )

    async def install_from_zip(
        self,
        zip_path: Path,
        user_id: Optional[str] = None,
        skill_name: Optional[str] = None,
    ) -> InstallResult:
        """
        从 ZIP 文件安装 Skill。

        Args:
            zip_path: ZIP 文件路径
            user_id: 安装用户 ID（可选）
            skill_name: 指定 Skill 目录名（可选，默认使用 ZIP 文件名）

        Returns:
            InstallResult
        """
        # 确定 Skill 目录名
        if not skill_name:
            skill_name = zip_path.stem

        # 清理目录名（只保留字母数字下划线横线）
        skill_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in skill_name)

        target_dir = self.skills_dir / skill_name
        if target_dir.exists():
            return InstallResult(
                success=False,
                error=f"Skill 目录已存在: {skill_name}，请先卸载或使用不同名称",
            )

        # 解压 ZIP
        def _unzip():
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 过滤 macOS 元数据文件
                all_names = [
                    n for n in zf.namelist()
                    if not n.startswith('__MACOSX/')
                    and not n.endswith('/.DS_Store')
                    and Path(n).name != '.DS_Store'
                ]
                if not all_names:
                    raise Exception("ZIP 文件为空或仅包含元数据")

                # 统计所有条目的顶层路径组件
                top_levels = set()
                for name in all_names:
                    first = name.split('/', 1)[0]
                    if first:
                        top_levels.add(first)

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    # 仅解压过滤后的条目
                    for name in all_names:
                        zf.extract(name, tmp_path)

                    if len(top_levels) == 1:
                        # 所有条目共享同一顶层目录：将其内容作为 skill 目录
                        only_top = next(iter(top_levels))
                        src = tmp_path / only_top
                        if src.is_dir():
                            shutil.move(str(src), str(target_dir))
                        else:
                            # 只有一个文件
                            target_dir.mkdir()
                            shutil.move(str(src), str(target_dir / src.name))
                    else:
                        # 多个顶层条目：直接作为 skill 目录
                        target_dir.mkdir()
                        for item in tmp_path.iterdir():
                            shutil.move(str(item), str(target_dir / item.name))

        try:
            await asyncio.to_thread(_unzip)
        except Exception as e:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return InstallResult(success=False, error=f"解压失败: {e}")

        # 验证 SKILL.md
        skill_md_path = target_dir / "SKILL.md"
        meta = self._parse_skill_md(skill_md_path)

        if not meta:
            # 列出目标目录的内容帮助排查
            try:
                entries = ", ".join(p.name for p in target_dir.iterdir())
            except Exception:
                entries = "(无法读取)"
            shutil.rmtree(target_dir, ignore_errors=True)
            if not skill_md_path.exists():
                return InstallResult(
                    success=False,
                    error=f"SKILL.md 不存在。目录内容: [{entries}]。请确保 SKILL.md 位于 ZIP 根目录或单一顶层子目录内",
                )
            return InstallResult(
                success=False,
                error="SKILL.md 格式错误：需要 YAML frontmatter 包含 name 和 description 字段",
            )

        # 检查数据库中是否已存在同名 Skill
        from sqlalchemy import select
        result = await self.db.execute(select(Skill).where(Skill.name == meta.name))
        if result.scalar_one_or_none():
            shutil.rmtree(target_dir, ignore_errors=True)
            return InstallResult(
                success=False,
                error=f"Skill 名称已存在: {meta.name}",
            )

        # 注册到数据库
        skill = Skill(
            name=meta.name,
            description=meta.description,
            version=meta.version,
            source_type="local",
            source_url=None,
            install_path=str(target_dir),
            installed_by=uuid.UUID(user_id) if user_id else None,
        )
        self.db.add(skill)
        await self.db.flush()
        await self.db.refresh(skill)

        return InstallResult(
            success=True,
            skill_id=str(skill.id),
            name=skill.name,
        )

    async def uninstall(self, skill_id: str) -> bool:
        """
        卸载 Skill。

        Args:
            skill_id: Skill ID

        Returns:
            是否成功
        """
        from sqlalchemy import select

        result = await self.db.execute(
            select(Skill).where(Skill.id == uuid.UUID(skill_id))
        )
        skill = result.scalar_one_or_none()
        if not skill:
            return False

        # 删除目录
        skill_path = Path(skill.install_path)
        if skill_path.exists():
            shutil.rmtree(skill_path, ignore_errors=True)

        # 删除数据库记录
        await self.db.delete(skill)
        return True

    async def refresh_skills(self):
        """
        刷新 Skill 注册表：扫描 skills/ 目录，注册新的 Skill。
        """
        if not self.skills_dir.exists():
            return

        from sqlalchemy import select

        # 获取已注册的 Skill
        result = await self.db.execute(select(Skill))
        registered = {s.name: s for s in result.scalars().all()}

        # 扫描目录
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            meta = self._parse_skill_md(skill_md)
            if not meta:
                continue

            # 检查是否已注册
            if meta.name in registered:
                # 更新版本和描述
                registered[meta.name].version = meta.version
                registered[meta.name].description = meta.description
            else:
                # 新 Skill，注册
                skill = Skill(
                    name=meta.name,
                    description=meta.description,
                    version=meta.version,
                    source_type="local",
                    install_path=str(skill_dir),
                )
                self.db.add(skill)

        await self.db.commit()