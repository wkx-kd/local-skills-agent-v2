"""
Embedding Service — 调用通义千问 text-embedding-v3 API

将文本转为向量，用于长期记忆和 RAG 文件检索。
"""

import asyncio
from typing import List
from dataclasses import dataclass

from app.config import settings


@dataclass
class EmbeddingResult:
    """单条文本的 embedding 结果"""
    text: str
    embedding: List[float]
    tokens: int


class EmbeddingService:
    """
    Embedding 服务，使用 DashScope text-embedding-v3 模型。
    支持批量 embedding，自动分批处理。
    """

    def __init__(self):
        self._client = None
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self._batch_size = 25  # DashScope 每批最大条数

    def _get_client(self):
        """延迟初始化 DashScope 客户端"""
        if self._client is None:
            import dashscope
            dashscope.api_key = settings.DASHSCOPE_API_KEY
            self._client = dashscope.TextEmbedding
        return self._client

    async def embed_single(self, text: str) -> EmbeddingResult:
        """将单条文本转为向量"""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """
        将多条文本转为向量（批量）。

        自动分批处理，每批最多 25 条。
        """
        if not texts:
            return []

        client = self._get_client()
        all_results = []

        # 分批处理
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]

            def _call():
                from http import HTTPStatus
                resp = client.call(
                    model=self.model,
                    input=batch,
                    dimension=self.dimension,
                    text_type="document",  # 用于存储/检索
                )
                if resp.status_code != HTTPStatus.OK:
                    raise Exception(f"Embedding API error: {resp.code} - {resp.message}")
                return resp

            # 在线程池中运行同步 API
            response = await asyncio.to_thread(_call)

            # 解析结果
            for item in response.output["embeddings"]:
                idx = item["text_index"]
                all_results.append(EmbeddingResult(
                    text=batch[idx],
                    embedding=item["embedding"],
                    tokens=response.usage.get("total_tokens", 0) // len(batch),
                ))

        return all_results

    def embedding_to_str(self, embedding: List[float]) -> str:
        """将 embedding 列表转为字符串（用于存储）"""
        import json
        return json.dumps(embedding)

    def str_to_embedding(self, s: str) -> List[float]:
        """将字符串转回 embedding 列表"""
        import json
        return json.loads(s)


# 全局单例
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service