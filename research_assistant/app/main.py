"""FastAPI entrypoint. File: app/main.py:1"""
from app.api.routes import router
from app.core import storage
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(
    title="LangGraph Research Assistant (Idea 1)",
    description="Sequential multi-agent: Search (DuckDuckGo) -> Summarize (Gemini Flash) -> Cite (Gemini Flash) + SQLite history + minimal UI",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    storage.init_db()


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
    from app.core.config import settings, has_gemini_key
    return {"status": "ok", "gemini_configured": has_gemini_key(), "model": settings.gemini_model}
