"""Tavily web search service."""

from __future__ import annotations

import logging

from app.config import TAVILY_API_KEY, WEB_SEARCH_ENABLED

logger = logging.getLogger(__name__)


class SearchResult:
    """A single web search result."""

    def __init__(self, title: str, url: str, content: str, score: float = 0.0):
        self.title = title
        self.url = url
        self.content = content
        self.score = score

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "content": self.content, "score": self.score}


async def search_web(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[SearchResult]:
    """Search the web using Tavily API."""
    if not WEB_SEARCH_ENABLED or not TAVILY_API_KEY:
        logger.warning("Web search not enabled or API key missing")
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
            )
            for r in response.get("results", [])
        ]
    except Exception:
        logger.exception("Web search failed")
        return []


def search_web_sync(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[SearchResult]:
    """Synchronous wrapper for web search."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                fut = pool.submit(lambda: asyncio.run(search_web(query, max_results, search_depth)))
                return fut.result()
        return asyncio.run(search_web(query, max_results, search_depth))
    except RuntimeError:
        return asyncio.run(search_web(query, max_results, search_depth))
