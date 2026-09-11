"""Deprecated shim — use app.core.travel_policies instead. File: app/core/mock_data.py:1

Kept for backward compatibility only. Will be removed in next major version.
All symbols are re-exported from travel_policies.py (pure business rules).
"""
import warnings

from app.core.travel_policies import (
    filter_flights_by_budget,
    filter_hotels_by_budget,
    optimize_itinerary,
    rank_flights,
    rank_hotels,
)

warnings.warn(
    "app.core.mock_data is deprecated; use app.core.travel_policies instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "filter_flights_by_budget",
    "filter_hotels_by_budget",
    "optimize_itinerary",
    "rank_flights",
    "rank_hotels",
]
