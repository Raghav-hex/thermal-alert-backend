import httpx
from config import SIVAKASI_BBOX

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY_TEMPLATE = """
[out:json];
(
  node["amenity"="hospital"]({lat1},{lon1},{lat2},{lon2});
  node["amenity"="fire_station"]({lat1},{lon1},{lat2},{lon2});
  node["amenity"="police"]({lat1},{lon1},{lat2},{lon2});
  node["emergency"="fire_station"]({lat1},{lon1},{lat2},{lon2});
  way["amenity"="fire_station"]({lat1},{lon1},{lat2},{lon2});
  way["emergency"="fire_station"]({lat1},{lon1},{lat2},{lon2});
);
out center;
"""

FALLBACK_STATIONS = [
    {"id": "fb_hospital_1", "name": "Sivakasi Government Hospital", "type": "hospital", "lat": 9.4520, "lon": 77.8020, "amenity": "hospital", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_fire_1", "name": "Sivakasi Fire Station", "type": "fire_station", "lat": 9.4550, "lon": 77.8080, "amenity": "fire_station", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_police_1", "name": "Sivakasi Police Station", "type": "police", "lat": 9.4500, "lon": 77.8000, "amenity": "police", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_hospital_2", "name": "Meenakshi Hospital", "type": "hospital", "lat": 9.4480, "lon": 77.8100, "amenity": "hospital", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_hospital_3", "name": "Lakshmi Hospital", "type": "hospital", "lat": 9.4560, "lon": 77.8050, "amenity": "hospital", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_fire_2", "name": "Virudhunagar Fire Station", "type": "fire_station", "lat": 9.5800, "lon": 77.9600, "amenity": "fire_station", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_police_2", "name": "Malli Police Station", "type": "police", "lat": 9.4400, "lon": 77.7900, "amenity": "police", "phone": "", "address": "", "source": "fallback"},
    {"id": "fb_police_3", "name": "City Police HQ", "type": "police", "lat": 9.4540, "lon": 77.8060, "amenity": "police", "phone": "", "address": "", "source": "fallback"},
]


async def fetch_stations_from_osm():
    bbox = SIVAKASI_BBOX
    query = QUERY_TEMPLATE.format(
        lat1=bbox["lat1"], lon1=bbox["lon1"],
        lat2=bbox["lat2"], lon2=bbox["lon2"],
    )

    headers = {"User-Agent": "ThermalAlertSystem/1.0 (Sivakasi)"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query}, headers=headers)
            if resp.status_code == 406:
                resp = await client.get(OVERPASS_URL, params={"data": query}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return list(FALLBACK_STATIONS)

    stations = []
    seen_ids = set()

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        stype = _classify_station(tags)
        sid = f"osm_{el['id']}"
        if sid in seen_ids:
            continue
        seen_ids.add(sid)

        lat = el.get("lat") or (el.get("center", {}) or {}).get("lat")
        lon = el.get("lon") or (el.get("center", {}) or {}).get("lon")
        if lat is None or lon is None:
            continue

        stations.append({
            "id": sid,
            "name": tags.get("name", f"{stype.title()} #{el['id']}"),
            "type": stype,
            "lat": lat,
            "lon": lon,
            "amenity": tags.get("amenity", ""),
            "phone": tags.get("phone", ""),
            "address": tags.get("addr:full", "") or tags.get("addr:street", ""),
            "source": "osm",
        })

    if not stations:
        return list(FALLBACK_STATIONS)

    fire_stations = [s for s in stations if s["type"] == "fire_station"]
    if len(fire_stations) < 2:
        for fb in FALLBACK_STATIONS:
            if fb["type"] == "fire_station" and fb["id"] not in seen_ids:
                stations.append(fb)
                seen_ids.add(fb["id"])

    return stations


def _classify_station(tags):
    amenity = tags.get("amenity", "")
    emergency = tags.get("emergency", "")
    if amenity == "fire_station" or emergency == "fire_station":
        return "fire_station"
    if amenity == "hospital":
        return "hospital"
    if amenity == "police":
        return "police"
    return amenity
