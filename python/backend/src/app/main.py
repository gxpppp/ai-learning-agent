"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import VERSION
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.routes.notes import router as notes_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    print(f"[server] AI Learning Backend v{VERSION} starting...")
    yield
    print("[server] shutting down...")


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


@app.get("/")
async def root():
    return {"service": "AI Learning Agent Backend", "version": VERSION}
