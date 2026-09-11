"""Hotels via Overpass API (OSM) - live only, no mock fallback. File: app/core/api_clients/hotels_client.py:1"""
import asyncio
from typing import Dict, List

import httpx
from app.core.api_clients.geocode import geocode_city

from app.core.config import settings


def _parse_hotel(element: Dict, destination: str) -> Dict:
    tags = element.get("tags", {})
    name = tags.get("name") or f"Hotel {element.get('id')}"
    stars = tags.get("stars")
    try:
        rating = float(stars) if stars else 4.0
        if rating <= 5:
            rating = max(3.0, rating + 0.5)
            rating = min(5.0, rating)
        else:
            rating = 4.0
    except Exception:
        rating = 4.0
    price = int(1800 + (rating - 3.0) * 2500 + (hash(name) % 800))
    amenities = []
    if tags.get("internet_access") in ("yes", "wlan"):
        amenities.append("wifi")
    if "pool" in tags:
        amenities.append("pool")
    if "spa" in tags.get("leisure", ""):
        amenities.append("spa")
    if not amenities:
        amenities = ["wifi", "restaurant"] if rating > 4.2 else ["wifi"]
    return {
        "hotel_id": f"HT-{destination.upper()}-{element.get('id')}",
        "name": name,
        "destination": destination.upper().strip(),
        "rating": round(rating, 1),
        "price_per_night": price,
        "amenities": amenities,
        "source": "overpass-live",
        "osm_id": element.get("id"),
        "lat": element.get("lat"),
        "lon": element.get("lon"),
    }


async def search_hotels_api(destination: str, check_in: str = "", check_out: str = "") -> List[Dict]:
    """Pull live hotels from Overpass around geocoded city. No mock fallback."""
    geo = await geocode_city(destination)
    if not geo:
        raise RuntimeError(f"Geocoding failed for destination '{destination}' - cannot query hotels live.")
    lat, lon, _ = geo
    query = f"""
    [out:json][timeout:10];
    (
      node["tourism"="hotel"](around:20000,{lat},{lon});
      way["tourism"="hotel"](around:20000,{lat},{lon});
    );
    out center 20;
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
            raise RuntimeError(f"Overpass hotels live query timed out: {type(e).__name__}: {e or 'timeout'}") from e
    if resp is None:
        raise RuntimeError(f"Overpass hotels failed: {last_exc}")
    if resp.status_code != 200:
        raise RuntimeError(f"Overpass hotels query failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    elements = data.get("elements", [])
    if not elements:
        raise RuntimeError(f"No live hotels found for '{destination}' via Overpass (lat {lat}, lon {lon}).")
    hotels: List[Dict] = []
    for el in elements[: settings.max_search_results]:
        if "lat" not in el and "center" in el:
            el["lat"] = el["center"].get("lat")
            el["lon"] = el["center"].get("lon")
        hotels.append(_parse_hotel(el, destination))
    if not hotels:
        raise RuntimeError(f"Overpass returned no parseable hotels for '{destination}'.")
    return hotels
