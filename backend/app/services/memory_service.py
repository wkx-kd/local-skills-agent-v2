"""
Memory Service — 三层记忆管理

工作记忆（内存）：当前会话的完整 messages，WebSocket 断开时释放
短期记忆（PostgreSQL）：近期会话摘要、用户临时偏好、任务上下文，30 天过期
长期记忆（Milvus + PostgreSQL）：语义化知识片段、结论、用户长期偏好，永久存储

写入策略：混合模式
- 实时：Agent 判断为重要信息时，通过 save_memory tool 主动存储
- 异步：会话结束后后台提取关键信息
- 定期：后台任务去重、合并、衰减
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.models.conversation import Conversation
from app.services.embedding_service import get_embedding_service, EmbeddingResult
from app.services.milvus_client import get_milvus_client, SearchResult


@dataclass
class MemoryItem:
    """记忆条目"""
    id: str
    type: str  # short_term, long_term
    category: str  # summary, preference, task, knowledge, fact
    content: str
    importance: float
    created_at: datetime


class MemoryService:
    """
    三层记忆管理服务。
    """

    # 短期记忆过期天数
    SHORT_TERM_EXPIRE_DAYS = 30
    # 长期记忆重要性阈值（低于此值可被衰减）
    IMPORTANCE_THRESHOLD = 0.3

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self.embedding_service = get_embedding_service()
        self.milvus = get_milvus_client()

    # ─── 短期记忆 ─────────────────────────────────────────────────────

    async def save_short_term(
        self,
        category: str,
        content: str,
        conversation_id: Optional[str] = None,
        importance: float = 0.5,
    ) -> Memory:
        """
        保存短期记忆到 PostgreSQL。

        Args:
            category: summary / preference / task / context
            content: 记忆内容
            conversation_id: 关联的会话 ID（可选）
            importance: 重要性评分 0-1
        """
        expires_at = datetime.utcnow() + timedelta(days=self.SHORT_TERM_EXPIRE_DAYS)

        memory = Memory(
            user_id=uuid.UUID(self.user_id),
            type="short_term",
            category=category,
            content=content,
            importance_score=importance,
            conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
            expires_at=expires_at,
        )
        self.db.add(memory)
        await self.db.flush()
        await self.db.refresh(memory)
        return memory

    async def get_short_term(self, limit: int = 10) -> List[MemoryItem]:
        """获取用户的短期记忆列表（按重要性降序）"""
        result = await self.db.execute(
            select(Memory)
            .where(
                Memory.user_id == uuid.UUID(self.user_id),
                Memory.type == "short_term",
                Memory.expires_at > datetime.utcnow(),
            )
            .order_by(Memory.importance_score.desc())
            .limit(limit)
        )
        memories = result.scalars().all()
        return [
            MemoryItem(
                id=str(m.id),
                type=m.type,
                category=m.category,
                content=m.content,
                importance=m.importance_score,
                created_at=m.created_at,
            )
            for m in memories
        ]

    async def update_short_term_access(self, memory_id: str):
        """更新短期记忆的访问时间和次数"""
        result = await self.db.execute(
            select(Memory).where(Memory.id == uuid.UUID(memory_id))
        )
        memory = result.scalar_one_or_none()
        if memory:
            memory.last_accessed_at = datetime.utcnow()
            memory.access_count += 1

    # ─── 长期记忆 ─────────────────────────────────────────────────────

    async def save_long_term(
        self,
        category: str,
        content: str,
        importance: float = 0.7,
        conversation_id: Optional[str] = None,
    ) -> Memory:
        """
        保存长期记忆：PostgreSQL 元数据 + Milvus 向量。
        """
        # 1. 生成 embedding
        embedding_result = await self.embedding_service.embed_single(content)

        # 2. 存入 Milvus
        milvus_id = await self.milvus.insert_memory(
            user_id=self.user_id,
            embedding=embedding_result.embedding,
            content=content,
            category=category,
        )

        # 3. 存入 PostgreSQL
        memory = Memory(
            user_id=uuid.UUID(self.user_id),
            type="long_term",
            category=category,
            content=content,
            importance_score=importance,
            milvus_id=milvus_id,
            conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
        )
        self.db.add(memory)
        await self.db.flush()
        await self.db.refresh(memory)
        return memory

    async def search_long_term(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[tuple[MemoryItem, float]]:
        """
        语义检索长期记忆。

        Returns:
            [(MemoryItem, similarity_score), ...]
        """
        # 1. 生成查询向量
        embedding_result = await self.embedding_service.embed_single(query)

        # 2. 从 Milvus 检索
        search_results = await self.milvus.search_memory(
            user_id=self.user_id,
            query_embedding=embedding_result.embedding,
            top_k=top_k,
            category=category,
        )

        # 3. 组装结果
        results = []
        for sr in search_results:
            results.append((
                MemoryItem(
                    id=sr.id,
                    type="long_term",
                    category=sr.metadata.get("category", "unknown"),
                    content=sr.content,
                    importance=sr.score,  # 用相似度作为 importance
                    created_at=datetime.fromtimestamp(sr.metadata.get("created_at", 0)),
                ),
                sr.score,
            ))

        return results

    async def delete_long_term(self, memory_id: str):
        """删除长期记忆（同时删除 Milvus 向量）"""
        result = await self.db.execute(
            select(Memory).where(Memory.id == uuid.UUID(memory_id))
        )
        memory = result.scalar_one_or_none()
        if memory and memory.milvus_id:
            await self.milvus.delete_memory(memory.milvus_id)
        if memory:
            await self.db.delete(memory)

    # ─── 工作记忆 ─────────────────────────────────────────────────────
    # 工作记忆在 agent_service 中管理（内存中的 messages 列表）
    # 这里只提供辅助方法

    def build_working_memory_context(self, messages: List[dict], max_tokens: int = 80000) -> List[dict]:
        """
        构建工作记忆上下文（滑动窗口截断）。

        Args:
            messages: 当前会话的完整消息列表
            max_tokens: 最大 token 预算

        Returns:
            截断后的消息列表
        """
        # 粗略估算：中文约 2 char/token，英文约 4 char/token
        def estimate_tokens(text: str) -> int:
            if not text:
                return 0
            cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            en_chars = len(text) - cn_chars
            return cn_chars // 2 + en_chars // 4 + 1

        tokens_used = 0
        result = []

        # 从最新消息开始往回取
        for msg in reversed(messages):
            msg_tokens = estimate_tokens(json.dumps(msg.get("content", ""), ensure_ascii=False))
            if tokens_used + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            tokens_used += msg_tokens

        return result

    # ─── 会话结束时的记忆提取 ─────────────────────────────────────────

    async def extract_and_save_from_conversation(
        self,
        conversation_id: str,
        messages: List[dict],
    ):
        """
        会话结束后，从对话中提取关键信息并保存记忆。

        这里使用启发式规则：
        1. 检测用户偏好声明（"我喜欢..."、"我不喜欢..."）
        2. 检测事实性结论（"总结："、"结论是..."）
        3. 检测任务上下文（"我们正在做..."）
        """
        # 简单规则提取
        user_preferences = []
        facts = []
        summaries = []

        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join(
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                text = str(content)

            # 检测偏好
            pref_keywords = ["我喜欢", "我偏好", "我希望", "请记住", "我喜欢用"]
            for kw in pref_keywords:
                if kw in text:
                    # 提取包含关键词的句子
                    sentences = text.split("。")
                    for s in sentences:
                        if kw in s:
                            user_preferences.append(s.strip())
                    break

            # 检测事实/结论
            fact_keywords = ["结论是", "总结：", "结果是", "重要：", "注意："]
            for kw in fact_keywords:
                if kw in text:
                    idx = text.find(kw)
                    facts.append(text[idx:idx + 200])
                    break

        # 保存提取的记忆
        for pref in user_preferences[:3]:  # 最多 3 条偏好
            await self.save_short_term(
                category="preference",
                content=pref,
                conversation_id=conversation_id,
                importance=0.7,
            )

        for fact in facts[:2]:  # 最多 2 条事实
            await self.save_long_term(
                category="knowledge",
                content=fact,
                importance=0.6,
                conversation_id=conversation_id,
            )

    # ─── 记忆衰减和清理 ───────────────────────────────────────────────

    async def decay_memories(self):
        """
        衰减低频访问的记忆。
        - 短期记忆：30 天未访问，降低重要性
        - 长期记忆：合并相似内容
        """
        # 衰减短期记忆
        threshold_date = datetime.utcnow() - timedelta(days=30)
        result = await self.db.execute(
            select(Memory).where(
                Memory.user_id == uuid.UUID(self.user_id),
                Memory.type == "short_term",
                Memory.last_accessed_at < threshold_date,
                Memory.importance_score > self.IMPORTANCE_THRESHOLD,
            )
        )
        to_decay = result.scalars().all()
        for memory in to_decay:
            memory.importance_score *= 0.8  # 降低 20%

        # 删除重要性过低的记忆
        await self.db.execute(
            delete(Memory).where(
                Memory.user_id == uuid.UUID(self.user_id),
                Memory.importance_score < self.IMPORTANCE_THRESHOLD,
            )
        )