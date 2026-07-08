"""Application configuration from environment variables."""
import os

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-placeholder")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

SERVER_PORT = int(os.getenv("SERVER_PORT", "8765"))
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")

OCR_SERVER_URL = os.getenv("OCR_SERVER_URL", "http://127.0.0.1:8080/v1")
OCR_MODEL = os.getenv("OCR_MODEL", "PaddleOCR-VL-0.9B")
OCR_ENABLED = os.getenv("OCR_ENABLED", "false").lower() == "true"

VERSION = "0.2.0"
