"""OpenAI-compatible LLM client.

Supports any provider with a /v1/chat/completions endpoint:
  - DeepSeek: https://api.deepseek.com/v1
  - OpenAI:   https://api.openai.com/v1
  - Ollama:   http://localhost:11434/v1
  - Groq:     https://api.groq.com/openai/v1
  - vLLM:     http://localhost:8000/v1

Configure via environment variables:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
"""

from __future__ import annotations

from openai import AsyncOpenAI, OpenAI

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


class LLMClient:
    """Stateless provider-agnostic LLM client."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url or LLM_BASE_URL
        self.api_key = api_key or LLM_API_KEY
        self.model = model or LLM_MODEL

    @property
    def async_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    @property
    def sync_client(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key)


# Module-level singleton for convenience
client = LLMClient()
