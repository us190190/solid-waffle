"""FastAPI entrypoint. File: app/main.py:1"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core import storage
from app.core.config import has_gemini_key, settings


@asynccontextmanager
async def lifespan(application: FastAPI):
    # startup
    storage.init_db()
    try:
        yield
    finally:
        # shutdown cleanup - no persistent connections to close (storage uses per-request sqlite3 connections)
        # placeholder for future async cleanup (e.g., aiosqlite pools, background tasks)
        print("Research Assistant shutdown - cleanup complete")


app = FastAPI(
    title="Research Assistant",
    description="Sequential multi-agent: Search (DuckDuckGo) -> Summarize (Gemini Flash) -> Cite (Gemini Flash) + SQLite history + minimal UI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router, prefix="/api")

# Static UI
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_ui():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "UI not found. API at /docs"}


@app.get("/health")
async def root_health():
    # also expose without /api prefix for convenience
    return {"status": "ok", "gemini_configured": has_gemini_key(), "model": settings.gemini_model}
