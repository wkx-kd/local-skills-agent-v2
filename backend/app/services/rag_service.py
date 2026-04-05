"""
RAG 服务 — 文件分块、向量化、检索

处理流程：
1. 文件上传后，解析文本
2. 判断策略：小文件 full_text，大文件 RAG 分块
3. 分块后生成 embedding，存入 Milvus
4. 对话时根据问题检索相关 chunks 注入上下文
"""

import uuid
import asyncio
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.uploaded_file import UploadedFile
from app.services.file_parser import FileParser, ParsedFile
from app.services.embedding_service import get_embedding_service
from app.services.milvus_client import get_milvus_client


@dataclass
class RAGChunk:
    """RAG 检索结果"""
    file_id: str
    filename: str
    chunk_index: int
    content: str
    score: float  # 相似度


class RAGService:
    """
    RAG 服务：文件内容向量化存储和检索。
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self.embedding_service = get_embedding_service()
        self.milvus = get_milvus_client()

    async def process_uploaded_file(self, file_id: str) -> dict:
        """
        处理上传的文件：解析 → 分块 → 向量化 → 存储。

        Args:
            file_id: 文件 ID

        Returns:
            处理结果 {"status": "completed"|"failed", "chunk_count": n, ...}
        """
        # 1. 获取文件记录
        result = await self.db.execute(
            select(UploadedFile).where(UploadedFile.id == uuid.UUID(file_id))
        )
        uploaded = result.scalar_one_or_none()
        if not uploaded:
            return {"status": "failed", "error": "文件记录不存在"}

        # 更新状态为处理中
        uploaded.processing_status = "processing"
        await self.db.flush()

        try:
            # 2. 解析文件
            from pathlib import Path
            file_path = Path(uploaded.storage_path)
            parsed = FileParser.parse(file_path)

            if parsed.error:
                uploaded.processing_status = "failed"
                return {"status": "failed", "error": parsed.error}

            # 3. 决定策略
            strategy = FileParser.get_processing_strategy(parsed.char_count)
            uploaded.processing_strategy = strategy

            if strategy == "full_text":
                # 小文件：直接存储全文
                uploaded.text_content = parsed.text
                uploaded.chunk_count = 0
                uploaded.processing_status = "completed"
                await self.db.flush()
                return {
                    "status": "completed",
                    "strategy": "full_text",
                    "char_count": parsed.char_count,
                }

            # 4. 大文件：分块
            chunks = FileParser.chunk_text(parsed.text)
            uploaded.chunk_count = len(chunks)

            # 5. 批量生成 embedding
            texts = [c["content"] for c in chunks]
            embedding_results = await self.embedding_service.embed_batch(texts)

            # 6. 存入 Milvus
            chunks_with_embeddings = [
                {
                    "index": c["index"],
                    "content": c["content"],
                    "embedding": er.embedding,
                }
                for c, er in zip(chunks, embedding_results)
            ]

            await self.milvus.insert_file_chunks(
                user_id=self.user_id,
                file_id=file_id,
                chunks=chunks_with_embeddings,
            )

            uploaded.processing_status = "completed"
            await self.db.flush()

            return {
                "status": "completed",
                "strategy": "rag",
                "char_count": parsed.char_count,
                "chunk_count": len(chunks),
            }

        except Exception as e:
            uploaded.processing_status = "failed"
            await self.db.flush()
            return {"status": "failed", "error": str(e)}

    async def search_relevant_chunks(
        self,
        query: str,
        top_k: int = 5,
        file_ids: Optional[List[str]] = None,
    ) -> List[RAGChunk]:
        """
        根据问题检索相关的文件内容块。

        Args:
            query: 用户问题
            top_k: 返回结果数
            file_ids: 限制在这些文件中检索（可选）

        Returns:
            RAGChunk 列表
        """
        # 1. 生成查询向量
        embedding_result = await self.embedding_service.embed_single(query)

        # 2. 从 Milvus 检索
        # 如果指定了 file_ids，逐个文件检索并合并结果
        if file_ids:
            all_results = []
            for file_id in file_ids:
                results = await self.milvus.search_file_chunks(
                    user_id=self.user_id,
                    query_embedding=embedding_result.embedding,
                    top_k=top_k,
                    file_id=file_id,
                )
                all_results.extend(results)
            # 按分数排序取 top_k
            all_results.sort(key=lambda x: x.score, reverse=True)
            search_results = all_results[:top_k]
        else:
            search_results = await self.milvus.search_file_chunks(
                user_id=self.user_id,
                query_embedding=embedding_result.embedding,
                top_k=top_k,
            )

        # 3. 获取文件名
        file_names = {}
        for sr in search_results:
            fid = sr.metadata.get("file_id")
            if fid and fid not in file_names:
                result = await self.db.execute(
                    select(UploadedFile).where(UploadedFile.id == uuid.UUID(fid))
                )
                uf = result.scalar_one_or_none()
                file_names[fid] = uf.filename if uf else "unknown"

        # 4. 组装结果
        rag_chunks = []
        for sr in search_results:
            rag_chunks.append(RAGChunk(
                file_id=sr.metadata.get("file_id", ""),
                filename=file_names.get(sr.metadata.get("file_id", ""), "unknown"),
                chunk_index=sr.metadata.get("chunk_index", 0),
                content=sr.content,
                score=sr.score,
            ))

        return rag_chunks

    async def get_full_text(self, file_id: str) -> Optional[str]:
        """
        获取小文件的全文内容。

        Args:
            file_id: 文件 ID

        Returns:
            文件全文，如果文件是大文件或不存在返回 None
        """
        result = await self.db.execute(
            select(UploadedFile).where(UploadedFile.id == uuid.UUID(file_id))
        )
        uploaded = result.scalar_one_or_none()
        if not uploaded:
            return None
        if uploaded.processing_strategy != "full_text":
            return None
        return uploaded.text_content

    async def delete_file_chunks(self, file_id: str):
        """
        删除文件的向量数据。

        Args:
            file_id: 文件 ID
        """
        await self.milvus.delete_file_chunks(file_id)

    async def get_context_from_files(
        self,
        query: str,
        file_ids: List[str],
        max_tokens: int = 4000,
    ) -> str:
        """
        根据问题从指定文件中提取相关上下文。

        混合策略：
        - 小文件：直接取全文
        - 大文件：RAG 检索相关块

        Args:
            query: 用户问题
            file_ids: 文件 ID 列表
            max_tokens: 最大 token 预算

        Returns:
            组装好的上下文字符串
        """
        context_parts = []
        tokens_used = 0

        # 估算 token 数（中文约 2 char/token）
        def estimate_tokens(text: str) -> int:
            return len(text) // 2 + 1

        for file_id in file_ids:
            # 检查是否是小文件
            full_text = await self.get_full_text(file_id)
            if full_text:
                # 小文件取全文
                tokens = estimate_tokens(full_text)
                if tokens_used + tokens > max_tokens:
                    # 截断
                    remaining = (max_tokens - tokens_used) * 2
                    full_text = full_text[:remaining] + "\n...[截断]"

                # 获取文件名
                result = await self.db.execute(
                    select(UploadedFile.filename).where(UploadedFile.id == uuid.UUID(file_id))
                )
                filename = result.scalar() or "unknown"

                context_parts.append(f"### 文件: {filename}\n{full_text}")
                tokens_used += estimate_tokens(full_text)
            else:
                # 大文件：RAG 检索
                chunks = await self.search_relevant_chunks(
                    query=query,
                    top_k=3,
                    file_ids=[file_id],
                )
                for chunk in chunks:
                    chunk_text = f"[{chunk.filename} 片段 {chunk.chunk_index}]\n{chunk.content}"
                    tokens = estimate_tokens(chunk_text)
                    if tokens_used + tokens > max_tokens:
                        break
                    context_parts.append(chunk_text)
                    tokens_used += tokens

            if tokens_used >= max_tokens:
                break

        return "\n\n---\n\n".join(context_parts) if context_parts else ""


# 异步任务处理函数（用于后台任务）
async def process_file_task(file_id: str, user_id: str):
    """
    后台任务：处理上传的文件。

    在文件上传后触发，异步执行解析和向量化。
    """
    from app.database import async_session

    async with async_session() as db:
        rag = RAGService(db, user_id)
        result = await rag.process_uploaded_file(file_id)
        await db.commit()
        print(f"[RAG] File {file_id} processed: {result}")