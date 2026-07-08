"""Multi-provider LLM manager.

Manages multiple OpenAI-compatible providers, each with its own client.
Supports fetching available models from /v1/models.
"""

from __future__ import annotations

import json
import logging

from app.llm.client import LLMClient

logger = logging.getLogger(__name__)


class LLMManager:
    def __init__(self, providers_json: str = "[]") -> None:
        raw = json.loads(providers_json) if providers_json else []
        self.providers: list[dict] = raw if isinstance(raw, list) else []
        self.clients: dict[str, LLMClient] = {}
        for p in self.providers:
            self.clients[p["id"]] = LLMClient(
                base_url=p.get("baseUrl", p.get("base_url", "")),
                api_key=p.get("apiKey", p.get("api_key", "")),
                model=p.get("models", [""])[0] if p.get("models") else "",
            )

    def get_client(self, provider_id: str) -> LLMClient:
        if provider_id not in self.clients:
            raise ValueError(f"Provider '{provider_id}' not found")
        return self.clients[provider_id]

    async def fetch_models(self, provider_id: str) -> list[str]:
        client = self.get_client(provider_id)
        try:
            models = await client.async_client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            logger.warning("Failed to fetch models for %s: %s", provider_id, e)
            return self._cached_models(provider_id)

    def get_provider(self, provider_id: str) -> dict:
        for p in self.providers:
            if p["id"] == provider_id:
                return p
        raise ValueError(f"Provider '{provider_id}' not found")

    def get_chat_client(self, provider_id: str, model: str) -> LLMClient:
        p = self.get_provider(provider_id)
        return LLMClient(
            base_url=p.get("baseUrl", p.get("base_url", "")),
            api_key=p.get("apiKey", p.get("api_key", "")),
            model=model,
        )

    def _cached_models(self, provider_id: str) -> list[str]:
        for p in self.providers:
            if p["id"] == provider_id:
                return p.get("models", [])
        return []


# Module-level singleton, initialized in main.py lifespan
llm_manager: LLMManager | None = None
