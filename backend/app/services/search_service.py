"""
Web Search 服务 — 支持 Tavily 和 SerpAPI

提供统一的搜索接口，返回结构化搜索结果。
"""

import asyncio
import json
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from app.config import settings


class SearchProvider(str, Enum):
    TAVILY = "tavily"
    SERPAPI = "serpapi"
    DUCKDUCKGO = "duckduckgo"


@dataclass
class SearchResult:
    """单条搜索结果"""
    title: str
    url: str
    snippet: str  # 摘要
    source: str   # 来源域名


@dataclass
class SearchResponse:
    """搜索响应"""
    query: str
    results: List[SearchResult]
    provider: str
    error: Optional[str] = None


class WebSearchService:
    """
    Web 搜索服务。

    支持两种提供商：
    - Tavily: 专为 AI 设计的搜索 API，返回结构化结果
    - SerpAPI: Google 搜索结果 API
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.SEARCH_PROVIDER
        self._tavily_client = None
        self._serpapi_client = None

    async def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """
        执行搜索。

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数

        Returns:
            SearchResponse 对象
        """
        if self.provider == SearchProvider.TAVILY.value:
            return await self._search_tavily(query, max_results)
        elif self.provider == SearchProvider.SERPAPI.value:
            return await self._search_serpapi(query, max_results)
        elif self.provider == SearchProvider.DUCKDUCKGO.value:
            return await self._search_duckduckgo(query, max_results)
        else:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.provider,
                error=f"不支持的搜索提供商: {self.provider}",
            )

    async def _search_tavily(self, query: str, max_results: int) -> SearchResponse:
        """使用 Tavily 搜索"""
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            return SearchResponse(
                query=query,
                results=[],
                provider="tavily",
                error="TAVILY_API_KEY 未配置",
            )

        def _call():
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",  # 或 "advanced" 获取更多细节
            )
            return response

        try:
            response = await asyncio.to_thread(_call)
            results = [
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source=item.get("url", "").split("/")[2] if "/" in item.get("url", "") else "",
                )
                for item in response.get("results", [])
            ]
            return SearchResponse(
                query=query,
                results=results,
                provider="tavily",
            )
        except Exception as e:
            return SearchResponse(
                query=query,
                results=[],
                provider="tavily",
                error=str(e),
            )

    async def _search_serpapi(self, query: str, max_results: int) -> SearchResponse:
        """使用 SerpAPI 搜索"""
        api_key = settings.SERPAPI_API_KEY
        if not api_key:
            return SearchResponse(
                query=query,
                results=[],
                provider="serpapi",
                error="SERPAPI_API_KEY 未配置",
            )

        def _call():
            import requests
            params = {
                "q": query,
                "api_key": api_key,
                "hl": "zh-CN",
                "gl": "cn",
                "num": max_results,
            }
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            return response.json()

        try:
            data = await asyncio.to_thread(_call)
            results = []

            # 解析 organic_results
            for item in data.get("organic_results", [])[:max_results]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source=item.get("displayed_link", ""),
                ))

            return SearchResponse(
                query=query,
                results=results,
                provider="serpapi",
            )
        except Exception as e:
            return SearchResponse(
                query=query,
                results=[],
                provider="serpapi",
                error=str(e),
            )

    async def _search_duckduckgo(self, query: str, max_results: int) -> SearchResponse:
        """使用 DuckDuckGo 搜索（免费，无需 API Key）"""

        def _call():
            from ddgs import DDGS
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        try:
            raw_results = await asyncio.to_thread(_call)
            results = [
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    snippet=item.get("body", ""),
                    source=item.get("href", "").split("/")[2] if "/" in item.get("href", "") else "",
                )
                for item in raw_results
            ]
            return SearchResponse(
                query=query,
                results=results,
                provider="duckduckgo",
            )
        except Exception as e:
            return SearchResponse(
                query=query,
                results=[],
                provider="duckduckgo",
                error=str(e),
            )

    def format_results_for_llm(self, response: SearchResponse) -> str:
        """
        将搜索结果格式化为适合 LLM 阅读的文本。

        Args:
            response: 搜索响应

        Returns:
            格式化的文本
        """
        if response.error:
            return f"搜索失败: {response.error}"

        if not response.results:
            return f"未找到与 '{response.query}' 相关的结果。"

        lines = [f"## 搜索结果: {response.query}\n"]
        for i, result in enumerate(response.results, 1):
            lines.append(f"### {i}. {result.title}")
            lines.append(f"来源: {result.source}")
            lines.append(f"链接: {result.url}")
            lines.append(f"摘要: {result.snippet}")
            lines.append("")

        return "\n".join(lines)


# 全局单例
_search_service: Optional[WebSearchService] = None


def get_search_service() -> WebSearchService:
    global _search_service
    if _search_service is None:
        _search_service = WebSearchService()
    return _search_service