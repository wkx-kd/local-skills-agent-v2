"""
Skill 管理器 — 扫描、加载、构建 system prompt

迁移自 local_skills_agent.py 的 SkillManager，增加按分组过滤能力。
"""

from pathlib import Path
import yaml

from app.config import settings
from app.core.executor import OUTPUT_DIR


class SkillManager:
    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or settings.SKILLS_DIR
        self.skills: dict[str, dict] = {}
        self._scan()

    def _scan(self):
        if not self.skills_dir.exists():
            return
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            content = skill_md.read_text(encoding="utf-8")
            meta = self._parse_frontmatter(content)
            if meta:
                self.skills[meta["name"]] = {
                    "name": meta["name"],
                    "description": meta.get("description", ""),
                    "version": meta.get("version", "1.0.0"),
                    "path": str(skill_dir),
                    "skill_md_path": str(skill_md),
                    "content": content,
                }

    def _parse_frontmatter(self, content: str) -> dict | None:
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            meta = yaml.safe_load(parts[1])
            if not meta or not meta.get("name"):
                return None
            return meta
        except yaml.YAMLError:
            return None

    def list_skills(self) -> list[dict]:
        return list(self.skills.values())

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        构建 system prompt。

        Args:
            skill_names: 只包含这些 skill 的元数据。None 表示全部。
        """
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt_parts = [
            f"当前日期和时间: {current_time}",
            "",
            "你是一个强大的 AI 助手，具备代码执行和文件操作能力。",
            "注意：你的训练数据可能存在截止日期，当前时间以上方标注为准。",
            "对于涉及时效性的问题（如最新事件、当前版本、最近动态等），请优先使用 web_search 工具获取最新信息，不要依赖训练数据中的过时信息。",
            "",
            "你可以使用以下工具来完成任务：",
            "- read_file: 读取本地文件内容",
            "- write_file: 创建或写入文件",
            "- execute_python: 执行 Python 代码",
            "- execute_bash: 执行 Bash 命令",
            "- list_directory: 列出目录内容",
            "- web_search: 搜索互联网获取实时信息",
            "",
            "## 重要：execute_python 使用规则",
            "**每次 execute_python 调用都是独立进程，变量不会在多次调用之间共享。**",
            "因此你必须：",
            "1. 在每次 execute_python 调用中包含完整的 import 和数据定义",
            "2. 如果需要多步操作，把所有代码写在同一次调用中",
            "3. 或者通过文件（CSV/JSON/PNG）在多次调用之间传递数据",
            "",
            f"生成的文件请保存到: {OUTPUT_DIR}",
            "",
            "## 中文支持",
            "- matplotlib 图表中文字体已自动配置",
            "- reportlab PDF 中文字体已注册为 'ChineseFont' 和 'ChineseFontBold'",
            "",
        ]

        # 过滤 skill
        if skill_names is not None:
            active_skills = {k: v for k, v in self.skills.items() if k in skill_names}
        else:
            active_skills = self.skills

        if active_skills:
            prompt_parts.append("## 可用的 Agent Skills")
            prompt_parts.append("")
            prompt_parts.append(
                "以下是已安装的 Skills。当用户请求匹配某个 Skill 的描述时，"
                "请先使用 read_file 工具读取对应的 SKILL.md 获取详细指令，"
                "然后按照指令执行。"
            )
            prompt_parts.append("")
            for skill in active_skills.values():
                prompt_parts.append(f"### {skill['name']}")
                prompt_parts.append(f"- 描述: {skill['description']}")
                prompt_parts.append(f"- 指令文件: {skill['skill_md_path']}")
                prompt_parts.append("")

        return "\n".join(prompt_parts)
