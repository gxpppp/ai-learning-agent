"""Request dispatcher — classify user intent and route to appropriate handler.

Uses keyword scoring for Chinese/English intent classification.
"""

from __future__ import annotations

from enum import Enum


class TaskComplexity(Enum):
    SIMPLE = "simple"      # Single tool call, execute directly
    SEARCH = "search"      # Needs RAG or web search
    COMPLEX = "complex"    # Multi-step, needs agent orchestration


# ── Keyword scoring ──

# High-confidence multi-step indicators
_COMPLEX_EXACT = [
    "整理", "归类", "分类", "批量", "所有", "全部", "每篇",
    "organize", "classify", "batch", "all of", "every note",
    "帮我把", "给我把", "重构", "迁移", "同步",
    "创建目录", "创建文件夹", "移动到",
]

# Medium-confidence indicators (need ≥2 matches)
_COMPLEX_PARTIAL = [
    "总结", "汇总", "summarize all", "generate summary",
    "打标签", "加标签", "tag all", "apply tags",
    "关联", "链接", "connect", "link",
]

# Search indicators
_SEARCH_EXACT = [
    "搜索", "查找", "找一下", "搜一下",
    "search", "find", "look for", "tell me about",
    "是什么", "什么是", "介绍一下", "讲讲",
    "介绍", "说明", "解释",
]

_SEARCH_PARTIAL = [
    "最新", "最近", "latest", "news", "网上",
    "有没有", "什么是", "what is", "how to",
    "教程", "tutorial", "文档", "documentation",
]


def classify(message: str) -> TaskComplexity:
    """Classify user message by task complexity using keyword scoring."""
    lower = message.lower()

    # Strong indicators: single match = COMPLEX
    complex_exact = sum(1 for kw in _COMPLEX_EXACT if kw.lower() in lower)
    if complex_exact > 0:
        return TaskComplexity.COMPLEX

    # Medium indicators: need ≥2 matches
    complex_partial = sum(1 for kw in _COMPLEX_PARTIAL if kw.lower() in lower)
    if complex_partial >= 2:
        return TaskComplexity.COMPLEX

    # Multi-action patterns (e.g., "create X then search Y")
    action_words = ["然后", "接着", "再", "and then", "after that", "then"]
    has_chain = any(aw.lower() in lower for aw in action_words)
    if has_chain and (
        "创建" in lower or "create" in lower or
        "搜索" in lower or "search" in lower
    ):
        return TaskComplexity.COMPLEX

    # Strong search indicators
    search_exact = sum(1 for kw in _SEARCH_EXACT if kw.lower() in lower)
    if search_exact > 0:
        return TaskComplexity.SEARCH

    # Partial search indicators
    search_partial = sum(1 for kw in _SEARCH_PARTIAL if kw.lower() in lower)
    if search_partial >= 1:
        return TaskComplexity.SEARCH

    # Default: simple
    return TaskComplexity.SIMPLE


def should_use_local_rag(message: str) -> bool:
    """Determine if the query should use local RAG."""
    lower = message.lower()
    vault_keywords = [
        "笔记", "note", "vault", "我的", "我的笔记", "本地",
        "我的vault", "knowledge base",
    ]
    # Only search vault for explicit vault mentions or all search queries
    return any(kw.lower() in lower for kw in vault_keywords) or "搜索" in lower


def should_use_web_search(message: str) -> bool:
    """Determine if the query should use web search."""
    lower = message.lower()
    web_keywords = [
        "最新", "最近", "news", "latest", "网上",
        "search the web", "查找一下", "查一下",
        "tutorial", "教程", "documentation", "文档",
    ]
    return any(kw.lower() in lower for kw in web_keywords)
