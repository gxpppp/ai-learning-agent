"""Context assembler — build system prompts with RAG, memory, and history."""

from __future__ import annotations

from app.llm.prompts import AGENT_SYSTEM_PROMPT


def build_agent_system_prompt(vault_path: str, permission_mode: str = "readonly") -> str:
    """Build the agent system prompt with vault context."""
    return AGENT_SYSTEM_PROMPT.format(
        vault_path=vault_path,
        permission_mode=permission_mode,
    )


def build_tutor_system_prompt() -> str:
    """Build the tutor system prompt."""
    from app.llm.prompts import TUTOR_SYSTEM_PROMPT
    return TUTOR_SYSTEM_PROMPT


def inject_rag_context(system_prompt: str, rag_results: list[dict]) -> str:
    """Inject RAG search results into the system prompt."""
    if not rag_results:
        return system_prompt

    context_lines = ["\n\n## Relevant Notes from Vault\n"]
    for i, result in enumerate(rag_results, 1):
        excerpt = result.get("excerpt", result.get("content", ""))[:500]
        path = result.get("path", result.get("note_path", "unknown"))
        score = result.get("score", 0)
        context_lines.append(f"[Source {i}] {path} (score: {score:.2f}):\n{excerpt}\n")

    return system_prompt + "\n".join(context_lines)


def inject_web_context(system_prompt: str, web_results: list[dict]) -> str:
    """Inject web search results into the system prompt."""
    if not web_results:
        return system_prompt

    context_lines = ["\n\n## Latest Web Search Results\n"]
    for i, result in enumerate(web_results, 1):
        title = result.get("title", "Untitled")
        content = result.get("content", "")[:500]
        url = result.get("url", "")
        context_lines.append(f"[Web {i}] {title}\n{url}\n{content}\n")

    return system_prompt + "\n".join(context_lines)
