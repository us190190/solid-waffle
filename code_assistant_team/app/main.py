"""FastAPI entrypoint. File: app/main.py:1"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.api.routes import router
from app.core import storage
from app.core.config import has_gemini_key, settings


@asynccontextmanager
async def lifespan(application: FastAPI):
    storage.init_db()
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as saver:
            pass
    except Exception as e:
        print(f"Checkpoint setup warning: {e}")
    try:
        yield
    finally:
        print("Code Assistant Team shutdown - cleanup complete")


app = FastAPI(
    title="Code Assistant Team",
    description="Parallel Collaboration: Planner -> Fan-out (Send API) -> Coder/Tester/DocsWriter (subgraphs + reducers) -> Reviewer (HITL) + WebSocket/SSE real-time",
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
    return {"status": "ok", "gemini_configured": has_gemini_key(), "model": settings.gemini_model,
            "checkpointer": "AsyncSqliteSaver"}
