"""FastAPI entrypoint. File: app/main.py:1"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core import storage

app = FastAPI(
    title="Customer Support Triage",
    description="Supervisor (structured output) -> Router (conditional edges) -> Specialist tools -> Responder -> HumanHandoff (AsyncSqliteSaver interrupt_before). Stateless vs stateful at POST /support/chat",
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
    # ensure checkpoint dir exists and run setup
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from app.core.config import settings
        async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as saver:
            pass  # from_conn_string handles setup
    except Exception as e:
        print(f"Checkpoint setup warning: {e}")


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
    from app.core.config import settings, has_gemini_key
    return {"status": "ok", "gemini_configured": has_gemini_key(), "model": settings.gemini_model,
            "checkpointer": "AsyncSqliteSaver"}
