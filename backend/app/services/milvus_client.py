"""
Milvus 客户端 — 向量数据库连接和操作

用于存储和检索长期记忆、RAG 文件块的向量。
"""

import uuid
from typing import List, Optional
from dataclasses import dataclass

from pymilvus import (
    connections, Collection, FieldSchema, CollectionSchema, DataType,
    utility
)

from app.config import settings


@dataclass
class VectorRecord:
    """向量记录"""
    id: str
    embedding: List[float]
    metadata: dict  # user_id, content, type, created_at, etc.


@dataclass
class SearchResult:
    """检索结果"""
    id: str
    score: float  # 相似度
    content: str
    metadata: dict


class MilvusClient:
    """
    Milvus 向量数据库客户端。

    Collections:
    - long_term_memory: 长期记忆向量
    - file_chunks: RAG 文件块向量
    """

    COLLECTION_MEMORY = "long_term_memory"
    COLLECTION_FILE_CHUNKS = "file_chunks"

    def __init__(self):
        self._connected = False
        self._memory_collection: Optional[Collection] = None
        self._file_collection: Optional[Collection] = None

    def connect(self):
        """连接 Milvus 服务器"""
        if self._connected:
            return

        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )
        self._connected = True

        # 确保 collections 存在
        self._ensure_collections()

    def _ensure_collections(self):
        """创建 collections（如果不存在）"""
        dim = settings.EMBEDDING_DIMENSION

        # 长期记忆 collection
        if not utility.has_collection(self.COLLECTION_MEMORY):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
                FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8000),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="created_at", dtype=DataType.INT64),  # timestamp
            ]
            schema = CollectionSchema(fields, description="长期记忆向量存储")
            collection = Collection(self.COLLECTION_MEMORY, schema)
            # 创建索引
            collection.create_index("embedding", {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}})

        # 文件块 collection
        if not utility.has_collection(self.COLLECTION_FILE_CHUNKS):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
                FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8000),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
            ]
            schema = CollectionSchema(fields, description="RAG 文件块向量存储")
            collection = Collection(self.COLLECTION_FILE_CHUNKS, schema)
            collection.create_index("embedding", {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}})

        # 加载 collections 到内存
        self._memory_collection = Collection(self.COLLECTION_MEMORY)
        self._file_collection = Collection(self.COLLECTION_FILE_CHUNKS)
        self._memory_collection.load()
        self._file_collection.load()

    # ─── 长期记忆操作 ─────────────────────────────────────────────

    async def insert_memory(self, user_id: str, embedding: List[float], content: str, category: str) -> str:
        """插入一条长期记忆向量"""
        import time
        self.connect()

        record_id = str(uuid.uuid4())
        data = [
            [record_id],
            [user_id],
            [embedding],
            [content[:8000]],  # 截断
            [category],
            [int(time.time())],
        ]

        def _insert():
            self._memory_collection.insert(data)
            self._memory_collection.flush()

        import asyncio
        await asyncio.to_thread(_insert)
        return record_id

    async def search_memory(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[SearchResult]:
        """检索相似记忆"""
        self.connect()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        expr = f'user_id == "{user_id}"'
        if category:
            expr += f' && category == "{category}"'

        def _search():
            results = self._memory_collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["content", "category", "created_at"],
            )
            return results[0] if results else []

        import asyncio
        hits = await asyncio.to_thread(_search)

        search_results = []
        for hit in hits:
            search_results.append(SearchResult(
                id=hit.id,
                score=hit.score,
                content=hit.entity.get("content", ""),
                metadata={
                    "category": hit.entity.get("category"),
                    "created_at": hit.entity.get("created_at"),
                },
            ))
        return search_results

    async def delete_memory(self, memory_id: str):
        """删除记忆向量"""
        import asyncio
        self.connect()
        expr = f'id == "{memory_id}"'
        await asyncio.to_thread(self._memory_collection.delete, expr)

    async def delete_user_memories(self, user_id: str):
        """删除用户所有记忆向量"""
        self.connect()
        expr = f'user_id == "{user_id}"'
        await asyncio.to_thread(self._memory_collection.delete, expr)

    # ─── 文件块操作 ───────────────────────────────────────────────

    async def insert_file_chunks(
        self,
        user_id: str,
        file_id: str,
        chunks: List[dict],  # [{"index": 0, "content": "...", "embedding": [...]}, ...]
    ):
        """插入文件块向量"""
        self.connect()

        ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_id}_{c['index']}")) for c in chunks]
        user_ids = [user_id] * len(chunks)
        file_ids = [file_id] * len(chunks)
        embeddings = [c["embedding"] for c in chunks]
        contents = [c["content"][:8000] for c in chunks]
        indices = [c["index"] for c in chunks]

        data = [ids, user_ids, file_ids, embeddings, contents, indices]

        def _insert():
            self._file_collection.insert(data)
            self._file_collection.flush()

        import asyncio
        await asyncio.to_thread(_insert)

    async def search_file_chunks(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        file_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """检索相似文件块"""
        self.connect()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        expr = f'user_id == "{user_id}"'
        if file_id:
            expr += f' && file_id == "{file_id}"'

        def _search():
            results = self._file_collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["content", "file_id", "chunk_index"],
            )
            return results[0] if results else []

        import asyncio
        hits = await asyncio.to_thread(_search)

        search_results = []
        for hit in hits:
            search_results.append(SearchResult(
                id=hit.id,
                score=hit.score,
                content=hit.entity.get("content", ""),
                metadata={
                    "file_id": hit.entity.get("file_id"),
                    "chunk_index": hit.entity.get("chunk_index"),
                },
            ))
        return search_results

    async def delete_file_chunks(self, file_id: str):
        """删除文件的所有块向量"""
        self.connect()
        expr = f'file_id == "{file_id}"'
        await asyncio.to_thread(self._file_collection.delete, expr)


# 全局单例
_milvus_client: Optional[MilvusClient] = None


def get_milvus_client() -> MilvusClient:
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusClient()
    return _milvus_client