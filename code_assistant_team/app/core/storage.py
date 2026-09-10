"""SQLite storage for Code Assistant Team jobs. File: app/core/storage.py:1"""
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
                       user_story
                       TEXT
                       NOT
                       NULL,
                       language
                       TEXT
                       DEFAULT
                       'python',
                       status
                       TEXT
                       NOT
                       NULL,
                       tasks
                       TEXT
                       DEFAULT
                       '[]',
                       code_artifacts
                       TEXT
                       DEFAULT
                       '[]',
                       test_artifacts
                       TEXT
                       DEFAULT
                       '[]',
                       docs_artifacts
                       TEXT
                       DEFAULT
                       '[]',
                       agent_status
                       TEXT
                       DEFAULT
                       '[]',
                       exec_results
                       TEXT
                       DEFAULT
                       '[]',
                       final_output
                       TEXT,
                       reviewer_notes
                       TEXT,
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
        # Migration: add columns if missing (for existing db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "exec_results" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN exec_results TEXT DEFAULT '[]'")
            conn.commit()
        if "reviewer_notes" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN reviewer_notes TEXT")
            conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(job_id: str, user_story: str, language: str = "python") -> str:
    conn = get_conn()
    try:
        now = _now()
        conn.execute(
            "INSERT INTO jobs (job_id, user_story, language, status, tasks, code_artifacts, test_artifacts, docs_artifacts, agent_status, exec_results, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, user_story, language or "python", "pending", "[]", "[]", "[]", "[]", "[]", "[]", now, now),
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
            "user_story": r["user_story"],
            "language": r["language"],
            "status": r["status"],
            "tasks": json.loads(r["tasks"]) if r["tasks"] else [],
            "code_artifacts": json.loads(r["code_artifacts"]) if r["code_artifacts"] else [],
            "test_artifacts": json.loads(r["test_artifacts"]) if r["test_artifacts"] else [],
            "docs_artifacts": json.loads(r["docs_artifacts"]) if r["docs_artifacts"] else [],
            "agent_status": json.loads(r["agent_status"]) if r["agent_status"] else [],
            "exec_results": json.loads(r["exec_results"]) if r["exec_results"] else [],
            "final_output": r["final_output"],
            "reviewer_notes": r["reviewer_notes"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
    finally:
        conn.close()


def update_job(job_id: str, **fields) -> bool:
    allowed = {"status", "tasks", "code_artifacts", "test_artifacts", "docs_artifacts", "agent_status", "exec_results",
               "final_output", "reviewer_notes", "user_story", "language"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    for k in ("tasks", "code_artifacts", "test_artifacts", "docs_artifacts", "agent_status", "exec_results"):
        if k in updates and isinstance(updates[k], list):
            updates[k] = json.dumps(updates[k], ensure_ascii=False)
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


def append_agent_status(job_id: str, entry: Dict) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    statuses = job.get("agent_status") or []
    statuses.append(entry)
    return update_job(job_id, agent_status=statuses)


def set_final(job_id: str, final_output: str, reviewer_notes: str = "", status: str = "completed") -> bool:
    return update_job(job_id, final_output=final_output, reviewer_notes=reviewer_notes, status=status)


def get_history(limit: int = 50, offset: int = 0, status: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    try:
        if status:
            rows = conn.execute("SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                (status, limit, offset)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                (limit, offset)).fetchall()
        result = []
        for r in rows:
            result.append({
                "job_id": r["job_id"],
                "user_story": r["user_story"],
                "language": r["language"],
                "status": r["status"],
                "tasks": json.loads(r["tasks"]) if r["tasks"] else [],
                "code_artifacts": json.loads(r["code_artifacts"]) if r["code_artifacts"] else [],
                "test_artifacts": json.loads(r["test_artifacts"]) if r["test_artifacts"] else [],
                "docs_artifacts": json.loads(r["docs_artifacts"]) if r["docs_artifacts"] else [],
                "agent_status": json.loads(r["agent_status"]) if r["agent_status"] else [],
                "exec_results": json.loads(r["exec_results"]) if r["exec_results"] else [],
                "final_output": r["final_output"],
                "reviewer_notes": r["reviewer_notes"],
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
