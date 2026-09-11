"""FastAPI routes: POST /trips, GET /trips/{id}, POST /trips/{id}/refine with checkpoint resumption. File: app/api/routes.py:1"""
import sqlite3
import uuid
from datetime import datetime as _dt
from typing import Optional

from app.agents.tools.travel_data import filter_flights_by_budget, filter_hotels_by_budget, rank_flights, rank_hotels
from fastapi import APIRouter, HTTPException, Query
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore

from app.agents.classifiers import generate_trip_summary
from app.core import storage
from app.core.config import has_gemini_key, settings
from app.graph.builder import build_stateful_graph
from app.models.schemas import HealthResponse, TripCreateRequest, TripRefineRequest
from app.models.state import TravelPlannerState

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        gemini_configured=has_gemini_key(),
        model=settings.gemini_model,
        checkpointer="AsyncSqliteSaver",
        store="InMemoryStore",
    )


def _trip_to_response(item: dict):
    return {
        "id": item["id"],
        "thread_id": item["thread_id"],
        "origin": item["origin"],
        "destination": item["destination"],
        "start_date": item["start_date"],
        "end_date": item["end_date"],
        "budget": item["budget"],
        "travelers": item["travelers"],
        "preferences": item["preferences"],
        "flights": item["flights"],
        "hotels": item["hotels"],
        "itinerary": item["itinerary"],
        "status": item["status"],
        "final_response": item["final_response"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


@router.post("/trips")
async def create_trip(req: TripCreateRequest):
    if not has_gemini_key():
        raise HTTPException(status_code=500,
                            detail="GOOGLE_API_KEY is not configured. Set it in .env to use Travel Planner.")
    thread_id = req.thread_id or f"trip-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: TravelPlannerState = {
        "thread_id": thread_id,
        "origin": req.origin.upper().strip(),
        "destination": req.destination.upper().strip(),
        "start_date": req.start_date,
        "end_date": req.end_date,
        "budget": req.budget,
        "travelers": req.travelers,
        "preferences": req.preferences or {},
        "messages": [],
        "flights": [],
        "hotels": [],
        "itinerary": {},
        "tool_outputs": [],
        "status": "planning",
        "final_response": "",
    }

    store = InMemoryStore()
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer, store)
        try:
            result = await graph_stateful.ainvoke(initial_state, config=config)
        except RuntimeError as e:
            if "GOOGLE_API_KEY" in str(e):
                raise HTTPException(status_code=500, detail=str(e))
            raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e) or repr(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e) or repr(e)}")

        snapshot = await graph_stateful.aget_state(config)
        is_paused = bool(snapshot and snapshot.next) or ("__interrupt__" in result)

        if is_paused:
            vals = snapshot.values if snapshot and snapshot.values else result
            flights = vals.get("flights", [])
            hotels = vals.get("hotels", [])
            itinerary = vals.get("itinerary", {})
            tid = storage.save_trip(
                thread_id, req.origin.upper().strip(), req.destination.upper().strip(), req.start_date, req.end_date,
                req.budget, req.travelers, req.preferences or {}, flights, hotels, itinerary, "awaiting_refine",
                "Paused before summarize. Call POST /api/trips/{id}/refine or /resume to continue.",
            )
            item = storage.get_by_id(tid)
            return _trip_to_response(item)

        flights = result.get("flights", []) or result.get("ranked_flights", [])
        hotels = result.get("hotels", []) or result.get("ranked_hotels", [])
        itinerary = result.get("itinerary", {})
        final_response = result.get("final_response", "")
        status = result.get("status", "completed")

        tid = storage.save_trip(
            thread_id, req.origin.upper().strip(), req.destination.upper().strip(), req.start_date, req.end_date,
            req.budget, req.travelers, req.preferences or {}, flights, hotels, itinerary, status, final_response,
        )
        item = storage.get_by_id(tid)
        return _trip_to_response(item)


@router.get("/trips")
async def list_trips(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     thread_id: Optional[str] = None):
    items = storage.get_history(limit=limit, offset=offset, thread_id=thread_id)
    total = storage.count_all(thread_id=thread_id)
    return {"total": total, "items": items}


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: int):
    item = storage.get_by_id(trip_id)
    if not item:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _trip_to_response(item)


@router.delete("/trips/{trip_id}")
async def delete_trip(trip_id: int):
    ok = storage.delete_by_id(trip_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"deleted": trip_id}


@router.delete("/trips")
async def clear_trips():
    conn = sqlite3.connect(settings.db_path)
    conn.execute("DELETE FROM trips")
    conn.commit()
    conn.close()
    return {"cleared": True}


@router.post("/trips/{trip_id}/refine")
async def refine_trip(trip_id: int, req: TripRefineRequest):
    if not has_gemini_key():
        raise HTTPException(status_code=500,
                            detail="GOOGLE_API_KEY is not configured. Set it in .env to use Travel Planner.")
    item = storage.get_by_id(trip_id)
    if not item:
        raise HTTPException(status_code=404, detail="Trip not found")
    thread_id = item["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Merge preferences patch
    current_prefs = item["preferences"] or {}
    new_prefs = {**current_prefs}
    if req.preferences:
        new_prefs.update(req.preferences)
    if req.refinement_query:
        # store refinement query as preference hint
        new_prefs["refinement_query"] = req.refinement_query
        lowered = req.refinement_query.lower()
        if "cheap" in lowered or "budget" in lowered:
            new_prefs["prefer_cheap"] = True
        if "luxury" in lowered or "5 star" in lowered:
            new_prefs["prefer_luxury"] = True
        if "nonstop" in lowered or "direct" in lowered:
            new_prefs["prefer_nonstop"] = True
    new_budget = req.budget if req.budget is not None else item["budget"]

    # Cheap re-invoke: Filter+Rank only without re-searching
    # We also resume checkpoint if paused before summarize
    store = InMemoryStore()
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer, store)
        snapshot = await graph_stateful.aget_state(config)
        if snapshot and snapshot.next:
            try:
                flights = item["flights"] or []
                hotels = item["hotels"] or []
                filtered_flights = filter_flights_by_budget(flights, new_budget) if flights else []
                ranked_flights = rank_flights(filtered_flights or flights, new_prefs) if flights else []
                try:
                    s = _dt.fromisoformat(item["start_date"])
                    e = _dt.fromisoformat(item["end_date"])
                    nights = max(1, (e - s).days)
                except Exception:
                    nights = 2
                filtered_hotels = filter_hotels_by_budget(hotels, new_budget, nights) if hotels else []
                ranked_hotels = rank_hotels(filtered_hotels or hotels, new_prefs) if hotels else []

                # Update checkpoint state then resume (cheap Filter+Rank path)
                try:
                    await graph_stateful.aupdate_state(config, {"budget": new_budget, "preferences": new_prefs,
                                                                "flights": ranked_flights, "hotels": ranked_hotels})
                except Exception:
                    pass
                result = await graph_stateful.ainvoke(None, config=config)
                if "__interrupt__" in result:
                    result = await graph_stateful.ainvoke(None, config=config)
            except RuntimeError as e:
                if "GOOGLE_API_KEY" in str(e):
                    raise HTTPException(status_code=500, detail=str(e))
                raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e) or repr(e)}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e) or repr(e)}")
            vals = result
            snapshot2 = await graph_stateful.aget_state(config)
            if snapshot2 and snapshot2.values:
                vals = snapshot2.values
            flights_out = vals.get("flights", ranked_flights) if isinstance(vals, dict) else ranked_flights
            hotels_out = vals.get("hotels", ranked_hotels) if isinstance(vals, dict) else ranked_hotels
            itinerary_out = vals.get("itinerary", item["itinerary"]) if isinstance(vals, dict) else item["itinerary"]
            final_response = vals.get("final_response", item["final_response"]) if isinstance(vals, dict) else item[
                "final_response"]
            status = vals.get("status", "completed") if isinstance(vals, dict) else "completed"
        else:
            # No paused state: do cheap filter+rank locally and re-summarize via LLM
            flights = item["flights"] or []
            hotels = item["hotels"] or []
            filtered_flights = filter_flights_by_budget(flights, new_budget) if flights else []
            ranked_flights = rank_flights(filtered_flights or flights, new_prefs) if flights else []
            try:
                s = _dt.fromisoformat(item["start_date"])
                e = _dt.fromisoformat(item["end_date"])
                nights = max(1, (e - s).days)
            except Exception:
                nights = 2
            filtered_hotels = filter_hotels_by_budget(hotels, new_budget, nights) if hotels else []
            ranked_hotels = rank_hotels(filtered_hotels or hotels, new_prefs) if hotels else []
            # Re-summarize with new ranking
            try:
                new_state = {**item, "budget": new_budget, "preferences": new_prefs, "flights": ranked_flights,
                             "hotels": ranked_hotels}
                final_response = await generate_trip_summary(new_state)
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e))
            flights_out = ranked_flights
            hotels_out = ranked_hotels
            itinerary_out = item["itinerary"]
            status = "completed"

        storage.update_trip(trip_id, budget=new_budget, preferences=new_prefs, flights=flights_out, hotels=hotels_out,
                            itinerary=itinerary_out, status=status, final_response=final_response)
        updated = storage.get_by_id(trip_id)
        return _trip_to_response(updated)


@router.post("/trips/{trip_id}/resume")
async def resume_trip(trip_id: int, thread_id: str = Query(..., description="Thread to resume after interrupt")):
    if not has_gemini_key():
        raise HTTPException(status_code=500,
                            detail="GOOGLE_API_KEY is not configured. Set it in .env to use Travel Planner.")
    item = storage.get_by_id(trip_id)
    if not item:
        raise HTTPException(status_code=404, detail="Trip not found")
    if item["thread_id"] != thread_id:
        raise HTTPException(status_code=400, detail="thread_id does not match trip")
    config = {"configurable": {"thread_id": thread_id}}
    store = InMemoryStore()
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer, store)
        snapshot = await graph_stateful.aget_state(config)
        if not snapshot or not snapshot.next:
            raise HTTPException(status_code=404, detail="No paused thread found for this thread_id")
        result = await graph_stateful.ainvoke(None, config=config)
        snapshot2 = await graph_stateful.aget_state(config)
        vals = snapshot2.values if snapshot2 and snapshot2.values else result
        flights = vals.get("flights", item["flights"]) if isinstance(vals, dict) else item["flights"]
        hotels = vals.get("hotels", item["hotels"]) if isinstance(vals, dict) else item["hotels"]
        itinerary = vals.get("itinerary", item["itinerary"]) if isinstance(vals, dict) else item["itinerary"]
        final_response = vals.get("final_response", "") if isinstance(vals, dict) else ""
        status = vals.get("status", "completed") if isinstance(vals, dict) else "completed"
        storage.update_trip(trip_id, flights=flights, hotels=hotels, itinerary=itinerary, status=status,
                            final_response=final_response)
        updated = storage.get_by_id(trip_id)
        return _trip_to_response(updated)


@router.get("/trips/{trip_id}/state/{thread_id}")
async def get_trip_state(trip_id: int, thread_id: str):
    item = storage.get_by_id(trip_id)
    if not item:
        raise HTTPException(status_code=404, detail="Trip not found")
    config = {"configurable": {"thread_id": thread_id}}
    store = InMemoryStore()
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path) as checkpointer:
        graph_stateful = build_stateful_graph(checkpointer, store)
        snapshot = await graph_stateful.aget_state(config)
        if not snapshot:
            raise HTTPException(status_code=404, detail="No state for thread_id")
        return {"trip_id": trip_id, "thread_id": thread_id, "values": snapshot.values, "next": snapshot.next,
                "created_at": str(snapshot.created_at) if snapshot.created_at else None}
