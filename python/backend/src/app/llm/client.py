"""OpenAI-compatible LLM client.

Supports any provider with a /v1/chat/completions endpoint.
No module-level singleton — LLMManager manages instances.
"""

from __future__ import annotations

from openai import AsyncOpenAI, OpenAI


class LLMClient:
    """Stateless provider-agnostic LLM client."""

    def __init__(self, base_url: str, api_key: str, model: str = "") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    @property
    def async_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    @property
    def sync_client(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key)
