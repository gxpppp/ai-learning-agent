"""FastAPI application entry point."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    AUTO_INDEX,
    EMBEDDING_MODEL,
    OBSIDIAN_VAULT_PATH,
    PROVIDERS_JSON,
    RAG_ENABLED,
    TOOL_PERMISSIONS,
    VERSION,
)
from app.routes.agent import router as agent_router
from app.routes.upload import router as upload_router
from app.routes.feedback import router as feedback_router
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.routes.notes import router as notes_router
from app.routes.ocr import router as ocr_router
from app.routes.rag import init_rag
from app.routes.rag import router as rag_router
from app.routes.tags import init_tags
from app.routes.tags import router as tags_router
from app.routes.vault import init_vault
from app.routes.vault import router as vault_router
from app.routes.wordcloud import init_wordcloud
from app.routes.wordcloud import router as wordcloud_router
from app.routes.models import router as models_router

embedding_client = None
vector_store = None
file_watcher = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    global embedding_client, vector_store, file_watcher

    print(f"[server] AI Learning Backend v{VERSION} starting...")

    # Initialize LLM Manager
    print(f"[server] Initializing LLM Manager...")
    from app.services.llm_manager import LLMManager, llm_manager as _llm_global
    _llm = LLMManager(PROVIDERS_JSON)
    import app.services.llm_manager as _lmm
    _lmm.llm_manager = _llm
    print(f"[server] LLM Manager ready ({len(_llm.providers)} providers).")

    if RAG_ENABLED and OBSIDIAN_VAULT_PATH:
        print(f"[server] Initializing embedding model: {EMBEDDING_MODEL}...")
        from app.services.embedding import EmbeddingClient
        embedding_client = EmbeddingClient(EMBEDDING_MODEL)
        print(f"[server] Embedding dim={embedding_client.dimension} loaded.")

        print(f"[server] Initializing vector store at {OBSIDIAN_VAULT_PATH}/.ai-tutor/lancedb")
        from app.services.vector_store import VectorStore
        vector_store = VectorStore(OBSIDIAN_VAULT_PATH)
        print(f"[server] Vector store ready ({vector_store.count()} chunks).")

        init_rag(embedding_client, vector_store)
        init_tags(embedding_client, vector_store, OBSIDIAN_VAULT_PATH)
        init_vault(embedding_client, vector_store, OBSIDIAN_VAULT_PATH)
        init_wordcloud(OBSIDIAN_VAULT_PATH)

        # Start file watcher
        if AUTO_INDEX:
            from app.services.file_watcher import FileWatcher
            from app.services.indexer import index_note, remove_note
            from app.services.wordcloud_service import update_word_db

            def on_vault_change(action: str, rel_path: str) -> None:
                if action == "delete":
                    remove_note(rel_path, OBSIDIAN_VAULT_PATH, vector_store)
                    update_word_db(OBSIDIAN_VAULT_PATH, rel_path, "delete")
                else:
                    index_note(
                        os.path.join(OBSIDIAN_VAULT_PATH, rel_path),
                        OBSIDIAN_VAULT_PATH,
                        embedding_client,
                        vector_store,
                    )
                    update_word_db(OBSIDIAN_VAULT_PATH, rel_path, "add")

            file_watcher = FileWatcher(OBSIDIAN_VAULT_PATH, on_vault_change)
            file_watcher.start()

    yield

    print("[server] shutting down...")
    if file_watcher:
        file_watcher.stop()


app = FastAPI(
    title="AI Learning Agent Backend",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["app://obsidian.md", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(notes_router)
app.include_router(ocr_router)
app.include_router(rag_router)
app.include_router(tags_router)
app.include_router(vault_router)
app.include_router(wordcloud_router)
app.include_router(models_router)
app.include_router(agent_router)
app.include_router(upload_router)
app.include_router(feedback_router)


@app.get("/")
async def root() -> dict[str, Any]:
    return {"service": "AI Learning Agent Backend", "version": VERSION}
