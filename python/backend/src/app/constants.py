"""Shared constants for the AI Learning Agent.

All paths and magic values that are used across multiple modules live here.
"""

# Vault subdirectory for all agent data
VAULT_DOT_DIR = ".ai-tutor"

# Sub-paths
LANCEDB_DIR = f"{VAULT_DOT_DIR}/lancedb"
EVOLUTION_DIR = f"{VAULT_DOT_DIR}/evolution"
UPLOADS_DIR = f"{VAULT_DOT_DIR}/uploads"
INDEX_STATE_FILE = "index_state.json"
TFIDF_DB_FILE = "tfidf.db"

# Database
VECTOR_TABLE_NAME = "chunks"

# Indexing
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64

# Streaming
SSE_HEARTBEAT_INTERVAL_SEC = 15
DEFAULT_RAG_TEMPERATURE = 0.7
DEFAULT_RAG_MAX_TOKENS = 2048
RAG_TOP_K = 5

# Agent
AGENT_MAX_TOOL_ITERATIONS = 8

# Upload
UPLOAD_MAX_SIZE_MB = 100
ALLOWED_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".pdf"}

# CORS
CORS_ORIGINS = ["app://obsidian.md", "http://localhost:*"]
