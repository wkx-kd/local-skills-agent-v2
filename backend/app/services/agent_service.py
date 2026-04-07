"""
Agent Service — 核心 Agent 循环（异步 + WebSocket 推送）

负责执行多轮对话，通过 WebSocket 实时推送执行状态。
集成三层记忆系统（工作/短期/长期）。
"""

import asyncio
import json
import logging
import uuid
from typing import Callable, Awaitable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as create_session
from app.services.llm_client import create_message_stream, StreamEvent, content_to_history
from app.services.context_builder import build_context
from app.services.skill_manager import SkillManager
from app.services.memory_service import MemoryService
from app.core.executor import dispatch_tool

# 工具定义
TOOLS = [
    {
        "name": "read_file",
        "description": "读取本地文件的内容。用于读取 Skill 指令文件（SKILL.md）或其他参考文件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要读取的文件的绝对路径或相对路径"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "创建或覆盖写入一个文件。用于保存生成的代码、数据或报告。",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "要写入的文件路径"},
                "content": {"type": "string", "description": "要写入的文件内容"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "execute_python",
        "description": "执行一段 Python 代码。代码在本地运行，可以使用 pandas、matplotlib、numpy 等已安装的库。",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "要执行的 Python 代码"}},
            "required": ["code"],
        },
    },
    {
        "name": "execute_bash",
        "description": "执行一条 Bash 命令。",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "要执行的 Bash 命令"}},
            "required": ["command"],
        },
    },
    {
        "name": "list_directory",
        "description": "列出指定目录下的文件和子目录。",
        "input_schema": {
            "type": "object",
            "properties": {"dir_path": {"type": "string", "description": "要列出内容的目录路径"}},
            "required": ["dir_path"],
        },
    },
    {
        "name": "web_search",
        "description": "搜索互联网获取实时信息。当用户询问最新事件、实时数据、或你不确定的事实时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": "将重要信息保存到长期记忆。当你发现用户偏好、重要事实、或需要长期记住的信息时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["preference", "knowledge", "fact", "task"], "description": "记忆类型"},
                "content": {"type": "string", "description": "要保存的记忆内容"},
                "importance": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.7, "description": "重要性评分 0-1"},
            },
            "required": ["category", "content"],
        },
    },
    {
        "name": "recall_memory",
        "description": "从长期记忆中检索相关信息。当你需要回忆之前的内容、用户偏好或历史信息时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题"},
                "top_k": {"type": "integer", "default": 5, "description": "返回结果数量"},
            },
            "required": ["query"],
        },
    },
]

MAX_ITERATIONS = 20


async def _extract_memory_background(conversation_id: str, user_id: str, messages: list[dict]):
    """后台任务：从会话消息中提取记忆，使用独立 db session，不阻塞响应。"""
    try:
        async with create_session() as db:
            memory_service = MemoryService(db, user_id)
            await memory_service.extract_and_save_from_conversation(
                conversation_id=conversation_id,
                messages=messages,
            )
            await db.commit()
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"[Memory] Background extraction failed for conv {conversation_id}: {e}"
        )


class AgentRunner:
    """
    Agent 执行器，支持流式输出和 WebSocket 推送。
    集成三层记忆系统。
    """

    def __init__(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        model: str,
        skill_manager: SkillManager,
        send_callback: Callable[[dict], Awaitable[None]],
        skill_names: list[str] | None = None,
        enable_web_search: bool = False,
    ):
        self.db = db
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.model = model
        self.skill_manager = skill_manager
        self.send = send_callback
        self.skill_names = skill_names
        self.cancelled = False
        self.memory_service = MemoryService(db, user_id)
        self.enable_web_search = enable_web_search

    async def cancel(self):
        self.cancelled = True

    async def dispatch_tool_with_memory(self, tool_name: str, tool_input: dict) -> str:
        """
        分发工具调用，包括记忆相关工具。
        """
        # 记忆工具
        if tool_name == "save_memory":
            try:
                memory = await self.memory_service.save_long_term(
                    category=tool_input.get("category", "knowledge"),
                    content=tool_input.get("content", ""),
                    importance=min(1.0, max(0.0, tool_input.get("importance", 0.7))),
                    conversation_id=self.conversation_id,
                )
                return json.dumps({"success": True, "memory_id": str(memory.id)}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

        elif tool_name == "recall_memory":
            try:
                results = await self.memory_service.search_long_term(
                    query=tool_input.get("query", ""),
                    top_k=tool_input.get("top_k", 5),
                )
                memories = [
                    {"content": item.content, "category": item.category, "relevance": score}
                    for item, score in results
                ]
                return json.dumps({"memories": memories}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"memories": [], "error": str(e)}, ensure_ascii=False)

        # web_search 工具
        elif tool_name == "web_search":
            try:
                from app.services.search_service import get_search_service
                search_service = get_search_service()
                response = await search_service.search(
                    query=tool_input.get("query", ""),
                    max_results=tool_input.get("max_results", 5),
                )
                if response.error:
                    return json.dumps({
                        "success": False,
                        "error": response.error,
                        "results": [],
                    }, ensure_ascii=False)
                return json.dumps({
                    "success": True,
                    "query": response.query,
                    "formatted": search_service.format_results_for_llm(response),
                }, ensure_ascii=False)
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "results": [],
                }, ensure_ascii=False)

        # 其他工具委托给 executor
        return await dispatch_tool(tool_name, tool_input)

    async def run(self, user_message: str, file_ids: list[str] | None = None):
        """执行完整的 Agent 循环"""
        from app.models.message import Message
        from app.models.conversation import Conversation

        # 类型安全：统一转为 UUID 供 SQLAlchemy 使用
        conv_uuid = uuid.UUID(self.conversation_id)

        # 1. 构建上下文
        system_prompt = self.skill_manager.build_system_prompt(self.skill_names)
        enriched_system, messages = await build_context(
            self.db, self.conversation_id, self.user_id,
            user_message, system_prompt,
            file_ids=file_ids,
        )

        # 用户明确开启 web_search：追加提示让模型主动搜索
        if self.enable_web_search:
            enriched_system += (
                "\n\n## Web 搜索已启用\n"
                "用户已明确开启 Web 搜索。当问题涉及实时信息、最新事件、当前价格/数据或你不确定的"
                "事实时，请主动调用 web_search 工具进行搜索，而不是仅凭训练数据作答。"
            )

        # 2. 保存用户消息
        user_msg = Message(
            conversation_id=conv_uuid,
            role="user",
            content=[{"type": "text", "text": user_message}],
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 3. Agent 循环
        full_response_text = ""

        for iteration in range(MAX_ITERATIONS):
            if self.cancelled:
                await self.send({"type": "stopped"})
                break

            # 每轮重置
            current_text = ""          # 本轮累积文本
            pending_tools: list[dict] = []   # 本轮所有 tool calls
            current_tool_idx = -1      # 当前正在流式接收的 tool 的索引
            stop_reason = "end_turn"

            try:
                tools_to_use = list(TOOLS)
                if not self.enable_web_search:
                    tools_to_use = [t for t in tools_to_use if t["name"] != "web_search"]

                async for event in create_message_stream(
                    model=self.model,
                    max_tokens=8192,
                    system=enriched_system,
                    messages=messages,
                    tools=tools_to_use,
                ):
                    if self.cancelled:
                        break

                    if event.event_type == "text_delta":
                        current_text += event.text
                        full_response_text += event.text
                        await self.send({"type": "text_delta", "content": event.text})

                    elif event.event_type == "tool_use_start":
                        tool_entry = {
                            "id": event.tool_id or str(uuid.uuid4()),
                            "name": event.tool_name,
                            "input_json": "",
                        }
                        pending_tools.append(tool_entry)
                        current_tool_idx = len(pending_tools) - 1
                        await self.send({
                            "type": "tool_call",
                            "name": event.tool_name,
                            "tool_id": tool_entry["id"],
                        })

                    elif event.event_type == "tool_use_delta":
                        if current_tool_idx >= 0:
                            pending_tools[current_tool_idx]["input_json"] = event.tool_input_json

                    elif event.event_type == "done":
                        stop_reason = event.stop_reason or "end_turn"

            except Exception as e:
                await self.send({"type": "error", "detail": str(e)})
                break

            # 构建本轮 assistant_content（合并文本为单一 text block）
            assistant_content = []
            if current_text:
                assistant_content.append({"type": "text", "text": current_text})

            # 执行所有 pending tool calls
            iteration_tool_results = []
            for tool in pending_tools:
                try:
                    tool_input = json.loads(tool["input_json"]) if tool["input_json"] else {}
                except json.JSONDecodeError:
                    tool_input = {}

                result_str = await self.dispatch_tool_with_memory(tool["name"], tool_input)
                tool_id = tool["id"]

                await self.send({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "output": result_str[:2000],  # 截断显示（完整结果用于 LLM）
                })

                assistant_content.append({
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool["name"],
                    "input": tool_input,
                })
                iteration_tool_results.append((tool_id, tool["name"], tool_input, result_str))

            # 检查是否完成
            if stop_reason == "end_turn" or not iteration_tool_results:
                # 任务完成，保存 assistant 消息
                assistant_msg = Message(
                    conversation_id=conv_uuid,
                    role="assistant",
                    content=assistant_content if assistant_content else [{"type": "text", "text": full_response_text}],
                )
                self.db.add(assistant_msg)

                # 更新会话时间 + 自动生成标题
                conv = await self.db.get(Conversation, conv_uuid)
                if conv:
                    conv.updated_at = datetime.utcnow()
                    if conv.title == "新对话":
                        raw = user_message.replace('\n', ' ')[:50]
                        conv.title = raw + "…" if len(user_message.replace('\n', ' ')) > 50 else raw

                await self.db.flush()
                await self.send({"type": "done", "message_id": str(assistant_msg.id)})

                # 后台提取记忆（非阻塞）
                asyncio.create_task(
                    _extract_memory_background(self.conversation_id, self.user_id, messages)
                )
                break

            # 继续循环：将 assistant 回复和所有 tool_result 加入 messages
            messages.append({"role": "assistant", "content": assistant_content})
            tool_results_msg = [
                {"type": "tool_result", "tool_use_id": tid, "content": result}
                for tid, _, _, result in iteration_tool_results
            ]
            messages.append({"role": "user", "content": tool_results_msg})

        else:
            # 达到最大迭代次数
            await self.send({"type": "error", "detail": f"达到最大迭代次数 {MAX_ITERATIONS}"})