"""Application configuration from environment variables."""
import json as _json
import os

# LLM Providers (JSON array from env)
_PROVIDERS_DEFAULT = _json.dumps([{
    "id": "deepseek",
    "name": "DeepSeek",
    "baseUrl": "https://api.deepseek.com/v1",
    "apiKey": "",
    "models": ["deepseek-chat"],
}])
PROVIDERS_JSON = os.getenv("PROVIDERS_JSON", _PROVIDERS_DEFAULT)

# Active model assignments
ACTIVE_PROVIDER_ID = os.getenv("ACTIVE_PROVIDER_ID", "deepseek")
ACTIVE_CHAT_MODEL = os.getenv("ACTIVE_CHAT_MODEL", "deepseek-chat")
ACTIVE_AGENT_MODEL = os.getenv("ACTIVE_AGENT_MODEL", "deepseek-chat")

# Legacy compat (for routes using old single-provider config)
_parsed = _json.loads(PROVIDERS_JSON)
_first = _parsed[0] if _parsed else {}
LLM_BASE_URL = os.getenv("LLM_BASE_URL", _first.get("baseUrl", "https://api.deepseek.com/v1"))
LLM_API_KEY = os.getenv("LLM_API_KEY", _first.get("apiKey", "sk-placeholder"))
LLM_MODEL = os.getenv("LLM_MODEL", ACTIVE_CHAT_MODEL)

SERVER_PORT = int(os.getenv("SERVER_PORT", "8765"))
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")

OCR_ENABLED = os.getenv("OCR_ENABLED", "false").lower() == "true"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "false").lower() == "true"
AUTO_INDEX = os.getenv("AUTO_INDEX", "false").lower() == "true"

TOOL_PERMISSIONS = os.getenv("TOOL_PERMISSIONS", "readonly")

REASONING_ENABLED = os.getenv("REASONING_ENABLED", "false").lower() == "true"
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "high")

VERSION = "0.5.0"
