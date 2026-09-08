"""SQLite storage for studio jobs. File: app/core/storage.py:1"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

DB_PATH = Path(settings.db_path)

CREATE_TABLE_SQL = """
                   CREATE TABLE IF NOT EXISTS jobs
                   (
                       job_id
                       TEXT
                       PRIMARY
                       KEY,
                       prompt
                       TEXT
                       NOT
                       NULL,
                       tone
                       TEXT,
                       content_type
                       TEXT,
                       status
                       TEXT
                       NOT
                       NULL,
                       iteration
                       INTEGER
                       NOT
                       NULL
                       DEFAULT
                       0,
                       score
                       INTEGER,
                       feedback
                       TEXT,
                       suggestions
                       TEXT,
                       drafts
                       TEXT
                       NOT
                       NULL
                       DEFAULT
                       '[]',
                       final_content
                       TEXT,
                       max_iterations
                       INTEGER
                       NOT
                       NULL
                       DEFAULT
                       3,
                       critic_threshold
                       INTEGER
                       NOT
                       NULL
                       DEFAULT
                       8,
                       created_at
                       TEXT
                       NOT
                       NULL,
                       updated_at
                       TEXT
                       NOT
                       NULL
                   );
                   CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
                   CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status); \
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(job_id: str, prompt: str, tone: str = "", content_type: str = "",
               max_iterations: int = 3, critic_threshold: int = 8) -> str:
    conn = get_conn()
    try:
        now = _now()
        conn.execute(
            "INSERT INTO jobs (job_id, prompt, tone, content_type, status, iteration, drafts, max_iterations, critic_threshold, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, prompt, tone or "", content_type or "", "pending", 0, "[]", max_iterations, critic_threshold, now,
             now),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[Dict]:
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not r:
            return None
        return {
            "job_id": r["job_id"],
            "prompt": r["prompt"],
            "tone": r["tone"],
            "content_type": r["content_type"],
            "status": r["status"],
            "iteration": r["iteration"],
            "score": r["score"],
            "feedback": r["feedback"],
            "suggestions": json.loads(r["suggestions"]) if r["suggestions"] else [],
            "drafts": json.loads(r["drafts"]) if r["drafts"] else [],
            "final_content": r["final_content"],
            "max_iterations": r["max_iterations"],
            "critic_threshold": r["critic_threshold"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
    finally:
        conn.close()


def update_job(job_id: str, **fields) -> bool:
    allowed = {"status", "iteration", "score", "feedback", "suggestions", "drafts", "final_content", "prompt", "tone",
               "content_type"}
    updates = {}
    for k, v in fields.items():
        if k in allowed:
            updates[k] = v
    if not updates:
        return False
    if "suggestions" in updates and isinstance(updates["suggestions"], list):
        updates["suggestions"] = json.dumps(updates["suggestions"], ensure_ascii=False)
    if "drafts" in updates and isinstance(updates["drafts"], list):
        updates["drafts"] = json.dumps(updates["drafts"], ensure_ascii=False)
    updates["updated_at"] = _now()
    set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
    vals = list(updates.values()) + [job_id]
    conn = get_conn()
    try:
        cur = conn.execute(f"UPDATE jobs SET {set_clause} WHERE job_id=?", vals)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def append_draft(job_id: str, draft_entry: Dict) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    drafts = job.get("drafts") or []
    drafts.append(draft_entry)
    fields: Dict = {"drafts": drafts}
    if "iteration" in draft_entry:
        fields["iteration"] = draft_entry["iteration"]
    if "score" in draft_entry:
        fields["score"] = draft_entry["score"]
    if "feedback" in draft_entry:
        fields["feedback"] = draft_entry["feedback"]
    if "suggestions" in draft_entry:
        fields["suggestions"] = draft_entry["suggestions"]
    return update_job(job_id, **fields)


def set_final(job_id: str, final_content: str, status: str = "completed") -> bool:
    return update_job(job_id, final_content=final_content, status=status)


def get_history(limit: int = 50, offset: int = 0, status: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        result = []
        for r in rows:
            result.append({
                "job_id": r["job_id"],
                "prompt": r["prompt"],
                "tone": r["tone"],
                "content_type": r["content_type"],
                "status": r["status"],
                "iteration": r["iteration"],
                "score": r["score"],
                "feedback": r["feedback"],
                "suggestions": json.loads(r["suggestions"]) if r["suggestions"] else [],
                "drafts": json.loads(r["drafts"]) if r["drafts"] else [],
                "final_content": r["final_content"],
                "max_iterations": r["max_iterations"],
                "critic_threshold": r["critic_threshold"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })
        return result
    finally:
        conn.close()


def delete_job(job_id: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_all(status: Optional[str] = None) -> int:
    conn = get_conn()
    try:
        if status:
            row = conn.execute("SELECT COUNT(*) as c FROM jobs WHERE status=?", (status,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as c FROM jobs").fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()
