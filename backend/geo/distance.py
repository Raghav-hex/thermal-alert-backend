import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_nearest_stations(
    disaster_lat: float,
    disaster_lon: float,
    stations: list,
    radius_km: float = 10.0,
    max_results: int = 5,
):
    result = []
    for s in stations:
        d = haversine(disaster_lat, disaster_lon, s["lat"], s["lon"])
        if d <= radius_km:
            result.append({**s, "distance_km": round(d, 2)})
    result.sort(key=lambda x: x["distance_km"])
    return result[:max_results]
