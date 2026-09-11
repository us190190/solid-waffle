"""Nominatim geocoding with cache and rate-limit. File: app/core/api_clients/geocode.py:1"""
import asyncio
import time
from typing import Dict, Optional, Tuple

import httpx

from app.core.config import settings

_cache: Dict[str, Tuple[float, Tuple[float, float, str]]] = {}
_last_request_ts: float = 0.0
_lock = asyncio.Lock()

# City mapping for IATA → city name (for Nominatim) + fallback coords
_IATA_CITY: Dict[str, str] = {
    "DEL": "Delhi", "BOM": "Mumbai", "BLR": "Bengaluru", "MAA": "Chennai", "CCU": "Kolkata", "HYD": "Hyderabad",
    "GOI": "Goa", "GOX": "Goa", "GOA": "Goa", "PNQ": "Pune", "AMD": "Ahmedabad", "COK": "Kochi",
    "TRV": "Thiruvananthapuram",
    "NAG": "Nagpur", "JAI": "Jaipur", "LKO": "Lucknow", "PAT": "Patna", "BBI": "Bhubaneswar", "IXC": "Chandigarh",
    "IXB": "Bagdogra", "GAU": "Guwahati", "IMF": "Imphal", "IXR": "Ranchi", "RPR": "Raipur", "UDR": "Udaipur",
    "JDH": "Jodhpur", "VNS": "Varanasi", "IXJ": "Jammu", "SXR": "Srinagar", "IXE": "Mangalore", "IXM": "Madurai",
    "TIR": "Tirupati", "VIZ": "Visakhapatnam", "IXZ": "Port Blair", "IXA": "Agartala", "IXD": "Prayagraj",
    "HBX": "Hubli", "IDR": "Indore", "JLR": "Jabalpur", "CNN": "Kannur", "CCJ": "Kozhikode", "STV": "Surat",
    "VTZ": "Visakhapatnam",
    "DXB": "Dubai", "SIN": "Singapore", "DOH": "Doha", "BKK": "Bangkok", "KUL": "Kuala Lumpur", "HND": "Tokyo",
    "NRT": "Tokyo",
    "ICN": "Seoul", "LHR": "London", "CDG": "Paris", "FRA": "Frankfurt", "AMS": "Amsterdam", "IST": "Istanbul",
    "JFK": "New York", "LAX": "Los Angeles", "SFO": "San Francisco", "ORD": "Chicago", "YYZ": "Toronto",
    "YVR": "Vancouver",
    "SYD": "Sydney", "MEL": "Melbourne", "JNB": "Johannesburg", "CPT": "Cape Town", "KTM": "Kathmandu",
    "CMB": "Colombo",
    "MLE": "Male", "DAC": "Dhaka",
}
_FALLBACK_COORDS: Dict[str, Tuple[float, float]] = {
    "GOA": (15.2993, 74.1240), "GOI": (15.2993, 74.1240), "GOX": (15.2993, 74.1240),
    "BOM": (19.0760, 72.8777), "MUMBAI": (19.0760, 72.8777),
    "DEL": (28.6139, 77.2090), "DELHI": (28.6139, 77.2090),
    "BLR": (12.9716, 77.5946), "BANGALORE": (12.9716, 77.5946),
    "JAI": (26.9124, 75.7873), "JAIPUR": (26.9124, 75.7873),
    "MAA": (13.0827, 80.2707), "CHENNAI": (13.0827, 80.2707),
    "CCU": (22.5726, 88.3639), "KOLKATA": (22.5726, 88.3639),
    "HYD": (17.3850, 78.4867), "HYDERABAD": (17.3850, 78.4867),
    "PNQ": (18.5204, 73.8567), "PUNE": (18.5204, 73.8567),
    "AMD": (23.0225, 72.5714), "AHMEDABAD": (23.0225, 72.5714),
    "COK": (9.9312, 76.2673), "KOCHI": (9.9312, 76.2673),
    "TRV": (8.5241, 76.9366), "THIRUVANANTHAPURAM": (8.5241, 76.9366),
    "NAG": (21.1458, 79.0882), "NAGPUR": (21.1458, 79.0882),
    "LKO": (26.8467, 80.9462), "LUCKNOW": (26.8467, 80.9462),
    "PAT": (25.5941, 85.1376), "PATNA": (25.5941, 85.1376),
    "BBI": (20.2961, 85.8245), "BHUBANESWAR": (20.2961, 85.8245),
    "IXC": (30.7333, 76.7794), "CHANDIGARH": (30.7333, 76.7794),
    "GAU": (26.1445, 91.7362), "GUWAHATI": (26.1445, 91.7362),
    "VNS": (25.3176, 82.9739), "VARANASI": (25.3176, 82.9739),
    "SXR": (34.0837, 74.7973), "SRINAGAR": (34.0837, 74.7973),
    "IXE": (12.9611, 74.6361), "MANGALORE": (12.9611, 74.6361),
    "DXB": (25.2048, 55.2708), "DUBAI": (25.2048, 55.2708),
    "SIN": (1.3644, 103.9915), "SINGAPORE": (1.3644, 103.9915),
    "LHR": (51.4700, -0.4543), "LONDON": (51.4700, -0.4543),
    "JFK": (40.6413, -73.7781), "NEW YORK": (40.6413, -73.7781),
    "BKK": (13.6900, 100.7501), "BANGKOK": (13.6900, 100.7501),
    "SYD": (-33.9399, 151.1753), "SYDNEY": (-33.9399, 151.1753),
}


async def geocode_city(city: str) -> Optional[Tuple[float, float, str]]:
    """Return (lat, lon, display_name) for city/IATA via Nominatim, cached. No key required."""
    key = city.upper().strip()
    # translate IATA → city name for Nominatim
    query_city = _IATA_CITY.get(key, city)
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < settings.geocode_cache_ttl:
            return val
    async with _lock:
        global _last_request_ts
        elapsed = now - _last_request_ts
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        try:
            async with httpx.AsyncClient(timeout=settings.api_timeout,
                                         headers={"User-Agent": settings.nominatim_user_agent}) as client:
                resp = await client.get(
                    settings.nominatim_url,
                    params={"q": query_city, "format": "json", "limit": 1},
                )
                _last_request_ts = time.time()
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        display = data[0].get("display_name", city)
                        _cache[key] = (now, (lat, lon, display))
                        return (lat, lon, display)
        except Exception:
            _last_request_ts = time.time()
            pass
    # fallback to known coords
    if key in _FALLBACK_COORDS:
        lat, lon = _FALLBACK_COORDS[key]
        return (lat, lon, city)
    return None
