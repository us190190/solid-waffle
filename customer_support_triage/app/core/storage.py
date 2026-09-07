"""SQLite storage for conversations. File: app/core/storage.py:1"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

DB_PATH = Path(settings.db_path)

CREATE_TABLE_SQL = """
                   CREATE TABLE IF NOT EXISTS conversations
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       thread_id
                       TEXT
                       NOT
                       NULL,
                       user_input
                       TEXT
                       NOT
                       NULL,
                       intent
                       TEXT
                       NOT
                       NULL,
                       sentiment
                       TEXT
                       NOT
                       NULL,
                       response
                       TEXT
                       NOT
                       NULL,
                       tool_outputs
                       TEXT
                       NOT
                       NULL,
                       escalated
                       INTEGER
                       NOT
                       NULL
                       DEFAULT
                       0,
                       created_at
                       TEXT
                       NOT
                       NULL
                   );
                   CREATE INDEX IF NOT EXISTS idx_conversations_thread ON conversations(thread_id);
                   CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC); \
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


def save_conversation(thread_id: str, user_input: str, intent: str, sentiment: str, response: str,
                      tool_outputs: List[Dict], escalated: bool) -> int:
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO conversations (thread_id, user_input, intent, sentiment, response, tool_outputs, escalated, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (thread_id, user_input, intent, sentiment, response, json.dumps(tool_outputs, ensure_ascii=False),
             1 if escalated else 0, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_history(limit: int = 50, offset: int = 0, thread_id: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    try:
        if thread_id:
            rows = conn.execute(
                "SELECT id, thread_id, user_input, intent, sentiment, response, tool_outputs, escalated, created_at FROM conversations WHERE thread_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (thread_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, thread_id, user_input, intent, sentiment, response, tool_outputs, escalated, created_at FROM conversations ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "thread_id": r["thread_id"],
                "user_input": r["user_input"],
                "intent": r["intent"],
                "sentiment": r["sentiment"],
                "response": r["response"],
                "tool_outputs": json.loads(r["tool_outputs"]),
                "escalated": bool(r["escalated"]),
                "created_at": r["created_at"],
            })
        return result
    finally:
        conn.close()


def get_by_id(cid: int) -> Optional[Dict]:
    conn = get_conn()
    try:
        r = conn.execute(
            "SELECT id, thread_id, user_input, intent, sentiment, response, tool_outputs, escalated, created_at FROM conversations WHERE id=?",
            (cid,)).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "thread_id": r["thread_id"],
            "user_input": r["user_input"],
            "intent": r["intent"],
            "sentiment": r["sentiment"],
            "response": r["response"],
            "tool_outputs": json.loads(r["tool_outputs"]),
            "escalated": bool(r["escalated"]),
            "created_at": r["created_at"],
        }
    finally:
        conn.close()


def delete_by_id(cid: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_all(thread_id: Optional[str] = None) -> int:
    conn = get_conn()
    try:
        if thread_id:
            row = conn.execute("SELECT COUNT(*) as c FROM conversations WHERE thread_id=?", (thread_id,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as c FROM conversations").fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()
