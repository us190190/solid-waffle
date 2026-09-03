"""SQLite storage for all questions asked. File: app/core/storage.py:1"""
import json
import sqlite3
from app.core.config import settings
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path(settings.db_path)

CREATE_TABLE_SQL = """
                   CREATE TABLE IF NOT EXISTS researches
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       query
                       TEXT
                       NOT
                       NULL,
                       summary
                       TEXT
                       NOT
                       NULL,
                       final_answer
                       TEXT
                       NOT
                       NULL,
                       citations
                       TEXT
                       NOT
                       NULL, -- JSON array
                       documents
                       TEXT
                       NOT
                       NULL, -- JSON array
                       created_at
                       TEXT
                       NOT
                       NULL
                   );
                   CREATE INDEX IF NOT EXISTS idx_researches_created_at ON researches(created_at DESC); \
                   """


def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def save_research(query: str, summary: str, final_answer: str, citations: List[Dict], documents: List[Dict]) -> int:
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO researches (query, summary, final_answer, citations, documents, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (query, summary, final_answer, json.dumps(citations, ensure_ascii=False),
             json.dumps(documents, ensure_ascii=False), now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_history(limit: int = 50, offset: int = 0) -> List[Dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, query, summary, final_answer, citations, documents, created_at FROM researches ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "query": r["query"],
                "summary": r["summary"],
                "final_answer": r["final_answer"],
                "citations": json.loads(r["citations"]),
                "documents": json.loads(r["documents"]),
                "created_at": r["created_at"],
                "documents_count": len(json.loads(r["documents"])),
            })
        return result
    finally:
        conn.close()


def get_by_id(research_id: int) -> Optional[Dict]:
    conn = get_conn()
    try:
        r = conn.execute(
            "SELECT id, query, summary, final_answer, citations, documents, created_at FROM researches WHERE id = ?",
            (research_id,),
        ).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "query": r["query"],
            "summary": r["summary"],
            "final_answer": r["final_answer"],
            "citations": json.loads(r["citations"]),
            "documents": json.loads(r["documents"]),
            "created_at": r["created_at"],
        }
    finally:
        conn.close()


def delete_by_id(research_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM researches WHERE id = ?", (research_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_all() -> int:
    conn = get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) as c FROM researches").fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()
