"""
本地代码执行器 — 异步包装版

迁移自 local_skills_agent.py 的 LocalCodeExecutor，增加异步支持。
通过 subprocess 在本地执行 Python/Bash，带路径白名单和安全过滤。
"""

import sys
import json
import asyncio
import subprocess
from pathlib import Path

from app.config import settings

OUTPUT_DIR = settings.PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_READ_DIRS = [settings.PROJECT_DIR]
ALLOWED_WRITE_DIRS = [OUTPUT_DIR]

TIMEOUT = 180

BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf ~", "rm -rf $HOME",
    "mkfs", "dd if=",
    ":(){", "fork bomb",
    ">/dev/sda", ">/dev/sdb",
    "/dev/tcp", "nc -e", "ncat -e",
]

MPL_PREAMBLE = (
    "import matplotlib as _mpl\n"
    "_mpl.use('Agg')\n"
    "_mpl.rcParams['font.sans-serif'] = ['PingFang HK', 'Heiti TC', 'Arial Unicode MS', 'STHeiti', 'SimSong']\n"
    "_mpl.rcParams['axes.unicode_minus'] = False\n"
)

REPORTLAB_PREAMBLE = (
    "from reportlab.pdfbase import pdfmetrics as _pm\n"
    "from reportlab.pdfbase.ttfonts import TTFont as _TTFont\n"
    "try:\n"
    "    _pm.registerFont(_TTFont('ChineseFont', '/Library/Fonts/Arial Unicode.ttf'))\n"
    "    _pm.registerFont(_TTFont('ChineseFontBold', '/System/Library/Fonts/STHeiti Medium.ttc'))\n"
    "except: pass\n"
)


def _safe_path(file_path: str, allowed_dirs: list) -> Path | None:
    try:
        resolved = Path(file_path).resolve()
        for d in allowed_dirs:
            if resolved.is_relative_to(d.resolve()):
                return resolved
        return None
    except Exception:
        return None


def _is_blocked(text: str) -> str | None:
    for blocked in BLOCKED_COMMANDS:
        if blocked in text:
            return blocked
    return None


async def execute_python(code: str) -> dict:
    blocked = _is_blocked(code)
    if blocked:
        return {"stdout": "", "stderr": f"安全限制：禁止执行包含 '{blocked}' 的代码", "return_code": 1}

    if "matplotlib" in code or "plt" in code:
        code = MPL_PREAMBLE + "\n" + code
        code = code.replace("plt.show()", "# plt.show() removed - non-interactive")

    if "reportlab" in code:
        code = REPORTLAB_PREAMBLE + "\n" + code

    def _run():
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=TIMEOUT, cwd=str(OUTPUT_DIR),
            )
            return {
                "stdout": result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout,
                "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"执行超时（{TIMEOUT}秒）", "return_code": 1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "return_code": 1}

    return await asyncio.to_thread(_run)


async def execute_bash(command: str) -> dict:
    blocked = _is_blocked(command)
    if blocked:
        return {"stdout": "", "stderr": f"安全限制：禁止执行包含 '{blocked}' 的命令", "return_code": 1}

    def _run():
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True, text=True, timeout=TIMEOUT, cwd=str(OUTPUT_DIR),
            )
            return {
                "stdout": result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout,
                "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"执行超时（{TIMEOUT}秒）", "return_code": 1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "return_code": 1}

    return await asyncio.to_thread(_run)


async def read_file(file_path: str) -> dict:
    safe = _safe_path(file_path, ALLOWED_READ_DIRS)
    if safe is None:
        return {"content": "", "error": f"安全限制：路径 '{file_path}' 不在允许的读取目录内"}
    try:
        if not safe.exists():
            return {"content": "", "error": f"文件不存在: {file_path}"}
        content = safe.read_text(encoding="utf-8")
        if len(content) > 20000:
            content = content[:20000] + "\n\n... [文件过大，已截断] ..."
        return {"content": content, "error": ""}
    except Exception as e:
        return {"content": "", "error": str(e)}


async def write_file(file_path: str, content: str) -> dict:
    safe = _safe_path(file_path, ALLOWED_WRITE_DIRS)
    if safe is None:
        return {"success": False, "path": file_path, "error": f"安全限制：路径 '{file_path}' 不在允许的写入目录内"}
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(safe), "error": ""}
    except Exception as e:
        return {"success": False, "path": file_path, "error": str(e)}


async def list_directory(dir_path: str) -> dict:
    safe = _safe_path(dir_path, ALLOWED_READ_DIRS)
    if safe is None:
        return {"entries": [], "error": f"安全限制：路径 '{dir_path}' 不在允许的目录内"}
    try:
        if not safe.exists():
            return {"entries": [], "error": f"目录不存在: {dir_path}"}
        entries = []
        for item in sorted(safe.iterdir()):
            entries.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
        return {"entries": entries, "error": ""}
    except Exception as e:
        return {"entries": [], "error": str(e)}


async def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """根据工具名分发到对应的异步执行函数，返回 JSON 字符串"""
    if tool_name == "read_file":
        result = await read_file(tool_input["file_path"])
    elif tool_name == "write_file":
        result = await write_file(tool_input["file_path"], tool_input["content"])
    elif tool_name == "execute_python":
        result = await execute_python(tool_input["code"])
    elif tool_name == "execute_bash":
        result = await execute_bash(tool_input["command"])
    elif tool_name == "list_directory":
        result = await list_directory(tool_input["dir_path"])
    else:
        result = {"error": f"未知工具: {tool_name}"}
    return json.dumps(result, ensure_ascii=False)
