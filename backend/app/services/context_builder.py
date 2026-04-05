"""
上下文组装器 — 滑动窗口 + 摘要 + 记忆检索 + RAG 文件检索

负责将历史消息、记忆、文件 RAG 结果组装为发给 LLM 的 messages 列表，
同时控制总 token 数不超过预算。
"""

import json
import logging
import uuid
from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.message import Message
from app.models.memory import Memory
from app.models.uploaded_file import UploadedFile


# 粗略的 token 估算：中文约 2 char/token, 英文约 4 char/token
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    en_chars = len(text) - cn_chars
    return cn_chars // 2 + en_chars // 4 + 1


def estimate_message_tokens(msg: dict) -> int:
    content = msg.get("content", "")
    if isinstance(content, str):
        return estimate_tokens(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                total += estimate_tokens(json.dumps(block, ensure_ascii=False))
            else:
                total += estimate_tokens(str(block))
        return total
    return estimate_tokens(str(content))


async def build_context(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    user_message: str,
    system_prompt: str,
    max_context_tokens: int = 100000,
    file_ids: Optional[List[str]] = None,
) -> tuple[str, list[dict]]:
    """
    组装完整上下文。

    Args:
        db: 数据库会话
        conversation_id: 会话 ID
        user_id: 用户 ID
        user_message: 用户消息
        system_prompt: 基础 system prompt
        max_context_tokens: 最大 token 预算
        file_ids: 要检索的文件 ID 列表（可选）

    Returns:
        (system_prompt_enriched, messages_list)
    """
    # 1. 加载历史消息
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    history_msgs = result.scalars().all()

    # 转为 dict 格式
    history = []
    for msg in history_msgs:
        history.append({"role": msg.role, "content": msg.content})

    # 2. 加载短期记忆摘要（最近的偏好/上下文）
    mem_result = await db.execute(
        select(Memory)
        .where(Memory.user_id == uuid.UUID(user_id), Memory.type == "short_term")
        .order_by(desc(Memory.created_at))
        .limit(5)
    )
    short_memories = mem_result.scalars().all()

    # 3. 构建增强的 system prompt
    system_parts = [system_prompt]

    # 3.1 添加短期记忆
    if short_memories:
        system_parts.append("\n## 用户近期上下文（短期记忆）")
        for mem in short_memories:
            system_parts.append(f"- [{mem.category}] {mem.content}")

    # 3.2 检索长期记忆（Milvus 不可用时降级跳过）
    from app.services.memory_service import MemoryService
    memory_service = MemoryService(db, user_id)
    try:
        long_term_memories = await memory_service.search_long_term(
            query=user_message,
            top_k=3,
        )
        if long_term_memories:
            system_parts.append("\n## 相关长期记忆")
            for item, score in long_term_memories:
                system_parts.append(f"- [{item.category}] {item.content} (相关度: {score:.2f})")
    except Exception as e:
        logger.warning(f"[Context] Long-term memory search skipped (Milvus may be unavailable): {e}")

    # 3.3 RAG 文件检索（Milvus 不可用时降级跳过）
    file_context = ""
    if file_ids:
        from app.services.rag_service import RAGService
        rag_service = RAGService(db, user_id)
        try:
            file_context = await rag_service.get_context_from_files(
                query=user_message,
                file_ids=file_ids,
                max_tokens=4000,
            )
            if file_context:
                system_parts.append("\n## 上传文件相关内容")
                system_parts.append(file_context)
        except Exception as e:
            logger.warning(f"[Context] RAG file retrieval skipped: {e}")

    enriched_system = "\n".join(system_parts)

    # 4. 滑动窗口 + 摘要策略
    system_tokens = estimate_tokens(enriched_system)
    user_msg_tokens = estimate_tokens(user_message)
    output_reserve = 8192
    available = max_context_tokens - system_tokens - user_msg_tokens - output_reserve

    # 从最新消息开始往回取，直到用完预算
    messages_to_send = []
    tokens_used = 0

    for msg in reversed(history):
        msg_tokens = estimate_message_tokens(msg)
        if tokens_used + msg_tokens > available:
            break
        messages_to_send.insert(0, msg)
        tokens_used += msg_tokens

    # 如果历史被截断且有剩余空间，尝试生成早期摘要
    if len(messages_to_send) < len(history) and available - tokens_used > 500:
        truncated_count = len(history) - len(messages_to_send)
        summary_note = {
            "role": "system",
            "content": f"[系统注释: 本会话早期有 {truncated_count} 条消息已被省略以节省上下文空间。"
                       f"如需回顾早期内容，请告知用户。]",
        }
        messages_to_send.insert(0, summary_note)

    # 5. 添加当前用户消息
    # 如果有附件文件，尝试注入文件内容到消息中
    user_content = user_message
    if file_ids:
        file_texts = []
        from app.services.rag_service import RAGService
        from app.services.file_parser import FileParser
        from pathlib import Path
        rag_service = RAGService(db, user_id)
        for fid in file_ids:
            # 先尝试从已处理的 full_text 获取
            full_text = await rag_service.get_full_text(fid)

            if not full_text:
                # 降级：直接从磁盘读取原始文件（后台处理可能还未完成）
                try:
                    file_result = await db.execute(
                        select(UploadedFile).where(UploadedFile.id == uuid.UUID(fid))
                    )
                    uploaded_file = file_result.scalar_one_or_none()
                    if uploaded_file and uploaded_file.storage_path:
                        file_path = Path(uploaded_file.storage_path)
                        if file_path.exists():
                            parsed = FileParser.parse(file_path)
                            if parsed.text and not parsed.error:
                                full_text = parsed.text
                                logger.info(f"[Context] File {fid} read directly from disk (processing may be pending)")
                except Exception as e:
                    logger.warning(f"[Context] Failed to read file {fid} from disk: {e}")

            if full_text and estimate_tokens(full_text) < 3000:
                result = await db.execute(
                    select(UploadedFile.filename).where(UploadedFile.id == uuid.UUID(fid))
                )
                filename = result.scalar() or "unknown"
                file_texts.append(f"\n\n[附件: {filename}]\n{full_text}")
            elif full_text:
                # 文件太大，截取前部分内容
                truncated = full_text[:6000]
                result = await db.execute(
                    select(UploadedFile.filename).where(UploadedFile.id == uuid.UUID(fid))
                )
                filename = result.scalar() or "unknown"
                file_texts.append(f"\n\n[附件: {filename}（大文件，仅显示前部分）]\n{truncated}\n...[截断]")

        if file_texts:
            user_content = user_message + "".join(file_texts)

    messages_to_send.append({"role": "user", "content": user_content})

    return enriched_system, messages_to_send