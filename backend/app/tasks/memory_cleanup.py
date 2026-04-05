"""
后台记忆清理任务

定期运行，执行：
1. 短期记忆衰减（降低低频访问记忆的重要性）
2. 过期短期记忆删除
3. 相似长期记忆合并（TODO: 复杂实现）
"""

import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session
from app.services.memory_service import MemoryService


scheduler = AsyncIOScheduler()


async def cleanup_expired_short_term():
    """删除过期的短期记忆"""
    async with async_session() as db:
        from sqlalchemy import delete
        from app.models.memory import Memory

        result = await db.execute(
            delete(Memory).where(
                Memory.type == "short_term",
                Memory.expires_at < datetime.utcnow(),
            )
        )
        await db.commit()
        print(f"[Memory Cleanup] Deleted {result.rowcount} expired short-term memories")


async def decay_memories():
    """衰减低频访问的记忆"""
    async with async_session() as db:
        from sqlalchemy import select
        from app.models.memory import Memory

        threshold = datetime.utcnow() - timedelta(days=30)

        result = await db.execute(
            select(Memory).where(
                Memory.type == "short_term",
                Memory.last_accessed_at < threshold,
                Memory.importance_score > 0.3,
            )
        )
        memories = result.scalars().all()

        for mem in memories:
            mem.importance_score *= 0.8

        await db.commit()
        print(f"[Memory Cleanup] Decayed {len(memories)} short-term memories")


async def merge_similar_long_term():
    """
    合并相似的长期记忆（简化版）。

    TODO: 实现基于向量相似度的合并
    """
    pass


def start_scheduler():
    """启动后台任务调度器"""
    # 每天凌晨 3 点运行
    scheduler.add_job(cleanup_expired_short_term, 'cron', hour=3, minute=0)
    # 每周日凌晨 4 点运行
    scheduler.add_job(decay_memories, 'cron', day_of_week='sun', hour=4, minute=0)

    scheduler.start()
    print("[Memory Cleanup] Scheduler started")


def stop_scheduler():
    """停止调度器"""
    scheduler.shutdown()
    print("[Memory Cleanup] Scheduler stopped")


# 在 main.py 中调用 start_scheduler() 启动