"""Storage facade delegating to trip_repository. File: app/core/storage.py:1"""
from typing import Dict, List, Optional

from app.core.repositories import trip_repository


def init_db():
    trip_repository.init_db()


def save_trip(*args, **kwargs) -> int:
    return trip_repository.save_trip(*args, **kwargs)


def update_trip(*args, **kwargs) -> bool:
    return trip_repository.update_trip(*args, **kwargs)


def get_by_id(trip_id: int) -> Optional[Dict]:
    return trip_repository.get_by_id(trip_id)


def get_history(limit: int = 50, offset: int = 0, thread_id: Optional[str] = None) -> List[Dict]:
    return trip_repository.get_history(limit=limit, offset=offset, thread_id=thread_id)


def delete_by_id(trip_id: int) -> bool:
    return trip_repository.delete_by_id(trip_id)


def count_all(thread_id: Optional[str] = None) -> int:
    return trip_repository.count_all(thread_id=thread_id)
