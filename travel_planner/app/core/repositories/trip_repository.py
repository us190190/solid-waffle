"""Trip repository - SRP persistence. File: app/core/repositories/trip_repository.py:1"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

DB_PATH = Path(settings.db_path)

CREATE_TABLE_SQL = """
                   CREATE TABLE IF NOT EXISTS trips
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
                       origin
                       TEXT
                       NOT
                       NULL,
                       destination
                       TEXT
                       NOT
                       NULL,
                       start_date
                       TEXT
                       NOT
                       NULL,
                       end_date
                       TEXT
                       NOT
                       NULL,
                       budget
                       REAL
                       NOT
                       NULL,
                       travelers
                       INTEGER
                       NOT
                       NULL,
                       preferences
                       TEXT
                       NOT
                       NULL,
                       flights
                       TEXT
                       NOT
                       NULL,
                       hotels
                       TEXT
                       NOT
                       NULL,
                       itinerary
                       TEXT
                       NOT
                       NULL,
                       status
                       TEXT
                       NOT
                       NULL,
                       final_response
                       TEXT
                       NOT
                       NULL,
                       created_at
                       TEXT
                       NOT
                       NULL,
                       updated_at
                       TEXT
                       NOT
                       NULL
                   );
                   CREATE INDEX IF NOT EXISTS idx_trips_thread ON trips(thread_id);
                   CREATE INDEX IF NOT EXISTS idx_trips_created ON trips(created_at DESC);
                   CREATE INDEX IF NOT EXISTS idx_trips_destination ON trips(destination); \
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


def save_trip(
        thread_id: str,
        origin: str,
        destination: str,
        start_date: str,
        end_date: str,
        budget: float,
        travelers: int,
        preferences: Dict,
        flights: List[Dict],
        hotels: List[Dict],
        itinerary: Dict,
        status: str,
        final_response: str,
) -> int:
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO trips (thread_id, origin, destination, start_date, end_date, budget, travelers, preferences, flights, hotels, itinerary, status, final_response, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                thread_id,
                origin,
                destination,
                start_date,
                end_date,
                budget,
                travelers,
                json.dumps(preferences, ensure_ascii=False),
                json.dumps(flights, ensure_ascii=False),
                json.dumps(hotels, ensure_ascii=False),
                json.dumps(itinerary, ensure_ascii=False),
                status,
                final_response,
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_trip(
        trip_id: int,
        budget: Optional[float] = None,
        preferences: Optional[Dict] = None,
        flights: Optional[List[Dict]] = None,
        hotels: Optional[List[Dict]] = None,
        itinerary: Optional[Dict] = None,
        status: Optional[str] = None,
        final_response: Optional[str] = None,
) -> bool:
    fields = []
    values = []
    if budget is not None:
        fields.append("budget=?")
        values.append(budget)
    if preferences is not None:
        fields.append("preferences=?")
        values.append(json.dumps(preferences, ensure_ascii=False))
    if flights is not None:
        fields.append("flights=?")
        values.append(json.dumps(flights, ensure_ascii=False))
    if hotels is not None:
        fields.append("hotels=?")
        values.append(json.dumps(hotels, ensure_ascii=False))
    if itinerary is not None:
        fields.append("itinerary=?")
        values.append(json.dumps(itinerary, ensure_ascii=False))
    if status is not None:
        fields.append("status=?")
        values.append(status)
    if final_response is not None:
        fields.append("final_response=?")
        values.append(final_response)
    if not fields:
        return False
    fields.append("updated_at=?")
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(trip_id)
    conn = get_conn()
    try:
        cur = conn.execute(f"UPDATE trips SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _row_to_dict(r: sqlite3.Row) -> Dict:
    return {
        "id": r["id"],
        "thread_id": r["thread_id"],
        "origin": r["origin"],
        "destination": r["destination"],
        "start_date": r["start_date"],
        "end_date": r["end_date"],
        "budget": r["budget"],
        "travelers": r["travelers"],
        "preferences": json.loads(r["preferences"]),
        "flights": json.loads(r["flights"]),
        "hotels": json.loads(r["hotels"]),
        "itinerary": json.loads(r["itinerary"]),
        "status": r["status"],
        "final_response": r["final_response"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def get_by_id(trip_id: int) -> Optional[Dict]:
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        if not r:
            return None
        return _row_to_dict(r)
    finally:
        conn.close()


def get_history(limit: int = 50, offset: int = 0, thread_id: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    try:
        if thread_id:
            rows = conn.execute(
                "SELECT * FROM trips WHERE thread_id=? ORDER BY id DESC LIMIT ? OFFSET ?", (thread_id, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM trips ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def delete_by_id(trip_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM trips WHERE id=?", (trip_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_all(thread_id: Optional[str] = None) -> int:
    conn = get_conn()
    try:
        if thread_id:
            row = conn.execute("SELECT COUNT(*) as c FROM trips WHERE thread_id=?", (thread_id,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as c FROM trips").fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()
