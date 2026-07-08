"""Request dispatcher — classify user intent and route to appropriate handler."""

from __future__ import annotations

from enum import Enum


class TaskComplexity(Enum):
    SIMPLE = "simple"      # Single tool call, execute directly
    SEARCH = "search"      # Needs RAG or web search
    COMPLEX = "complex"    # Multi-step, needs agent orchestration


# Keywords that indicate multi-step tasks
_COMPLEX_KEYWORDS = [
    "整理", "归类", "总结全部", "批量", "所有",
    "organize", "classify", "summarize all", "batch", "all of",
    "帮我把", "给我把", "全部", "每篇",
    "重构", "迁移", "同步",
]

# Keywords that indicate search intent
_SEARCH_KEYWORDS = [
    "搜索", "查找", "找一下", "搜一下", "有没有",
    "search", "find", "look for", "what is", "tell me about",
    "最新", "最近", "latest", "news",
    "是什么", "什么是", "介绍一下",
]


def classify(message: str) -> TaskComplexity:
    """Classify user message by task complexity."""
    lower = message.lower()

    # Multi-step indicators
    complex_score = sum(1 for kw in _COMPLEX_KEYWORDS if kw.lower() in lower)
    if complex_score > 0:
        return TaskComplexity.COMPLEX

    # Search indicators
    search_score = sum(1 for kw in _SEARCH_KEYWORDS if kw.lower() in lower)
    if search_score > 0:
        return TaskComplexity.SEARCH

    # Default: simple single-step
    return TaskComplexity.SIMPLE


def should_use_local_rag(message: str) -> bool:
    """Determine if the query should use local RAG."""
    vault_keywords = ["笔记", "note", "vault", "我的", "我的笔记", "本地"]
    return any(kw.lower() in message.lower() for kw in vault_keywords)


def should_use_web_search(message: str) -> bool:
    """Determine if the query should use web search."""
    web_keywords = [
        "最新", "最近", "news", "latest", "网上", "搜索",
        "search the web", "查找一下", "查一下",
    ]
    return any(kw.lower() in message.lower() for kw in web_keywords)
