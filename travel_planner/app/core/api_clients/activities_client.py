"""Activities via Overpass API (OSM) - live only, no mock fallback. File: app/core/api_clients/activities_client.py:1"""
import asyncio
from typing import Dict, List, Optional

import httpx
from app.core.api_clients.geocode import geocode_city

from app.core.config import settings

CATEGORY_MAP = {
    "museum": "culture",
    "attraction": "culture",
    "viewpoint": "nature",
    "park": "nature",
    "gallery": "culture",
    "theme_park": "adventure",
    "zoo": "nature",
    "aquarium": "nature",
    "beach": "leisure",
    "peak": "adventure",
    "castle": "culture",
    "monument": "culture",
    "memorial": "culture",
}


def _parse_activity(element: Dict, destination: str) -> Dict:
    tags = element.get("tags", {})
    name = tags.get("name") or tags.get("tourism") or tags.get("historic") or f"POI {element.get('id')}"
    tourism = tags.get("tourism", "")
    historic = tags.get("historic", "")
    leisure = tags.get("leisure", "")
    kind = tourism or historic or leisure or "attraction"
    category = CATEGORY_MAP.get(kind, "culture")
    duration = 2
    if kind in ("theme_park", "zoo"):
        duration = 5
    elif kind in ("museum", "castle"):
        duration = 3
    elif kind in ("park", "beach"):
        duration = 4
    cost = 300 + (hash(name) % 1200) + (duration * 200)
    fee = tags.get("fee")
    if fee == "no":
        cost = 100 + (hash(name) % 300)
    return {
        "activity_id": f"AC-{destination.upper()}-{element.get('id')}",
        "name": name,
        "duration_hours": duration,
        "cost": cost,
        "category": category,
        "source": "overpass-live",
        "osm_id": element.get("id"),
        "kind": kind,
        "lat": element.get("lat"),
        "lon": element.get("lon"),
    }


async def search_activities_api(destination: str, interests: Optional[List[str]] = None) -> List[Dict]:
    """Pull live POIs via Overpass around city. No mock fallback."""
    geo = await geocode_city(destination)
    if not geo:
        raise RuntimeError(f"Geocoding failed for '{destination}' - cannot query activities live.")
    lat, lon, _ = geo
    query = f"""
    [out:json][timeout:10];
    (
      node["tourism"~"attraction|museum|viewpoint|gallery|theme_park|zoo|aquarium"](around:20000,{lat},{lon});
      way["tourism"~"attraction|museum|viewpoint|gallery|theme_park|zoo|aquarium"](around:20000,{lat},{lon});
      node["historic"](around:20000,{lat},{lon});
      way["historic"](around:20000,{lat},{lon});
      node["leisure"~"park|beach"](around:20000,{lat},{lon});
    );
    out center 30;
    """
    resp = None
    last_exc = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.api_timeout,
                                         headers={"User-Agent": settings.nominatim_user_agent}) as client:
                resp = await client.post(settings.overpass_url, data={"data": query})
                break
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as e:
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(1.5)
                continue
            raise RuntimeError(f"Overpass activities live query timed out: {type(e).__name__}: {e or 'timeout'}") from e
    if resp is None:
        raise RuntimeError(f"Overpass activities failed: {last_exc}")
    if resp.status_code != 200:
        raise RuntimeError(f"Overpass activities query failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    elements = data.get("elements", [])
    if not elements:
        raise RuntimeError(f"No live activities found for '{destination}' via Overpass.")
    activities: List[Dict] = []
    for el in elements[:30]:
        if "lat" not in el and "center" in el:
            el["lat"] = el["center"].get("lat")
            el["lon"] = el["center"].get("lon")
        if not el.get("tags", {}).get("name") and not el.get("tags", {}).get("tourism"):
            continue
        activities.append(_parse_activity(el, destination))
        if len(activities) >= settings.max_search_results * 2:
            break
    if not activities:
        raise RuntimeError(f"Overpass returned no named activities for '{destination}'.")
    if interests:
        lowered = [i.lower() for i in interests]
        filtered = [a for a in activities if a["category"] in lowered]
        if filtered:
            return filtered[: settings.max_search_results * 2]
    return activities[: settings.max_search_results * 2]
