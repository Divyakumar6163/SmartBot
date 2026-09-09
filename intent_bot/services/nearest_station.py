# services/nearest_station.py

import math
from datetime import datetime
import openrouteservice
from intent_bot.db import fetch_all

# =====================================================
# CONFIG
# =====================================================

ORS_API_KEY = "ORS_API_KEY"   # keep empty string if not using ORS
TOP_K = 5

QUERY_TIME = datetime.now().time()   # TIME ONLY

INDIA_LAT_RANGE = (8, 37)
INDIA_LON_RANGE = (68, 98)

# =====================================================
# OPTIONAL ORS CLIENT
# =====================================================

ors_client = None
if ORS_API_KEY and ORS_API_KEY != "ORS_API_KEY":
    try:
        ors_client = openrouteservice.Client(key=ORS_API_KEY)
    except Exception:
        ors_client = None


# =====================================================
# HELPERS
# =====================================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2 +
        math.cos(phi1) * math.cos(phi2) *
        math.sin(dlambda / 2) ** 2
    )
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def valid_india(lat, lon):
    return (
        isinstance(lat, (int, float)) and
        isinstance(lon, (int, float)) and
        INDIA_LAT_RANGE[0] <= lat <= INDIA_LAT_RANGE[1] and
        INDIA_LON_RANGE[0] <= lon <= INDIA_LON_RANGE[1]
    )


def road_distance_km(lat1, lon1, lat2, lon2):
    """
    Returns road distance in km using ORS.
    Falls back to infinity if ORS fails.
    """
    if not ors_client:
        return float("inf")

    try:
        route = ors_client.directions(
            coordinates=[(lon1, lat1), (lon2, lat2)],
            profile="driving-car",
            format="json"
        )
        return route["routes"][0]["summary"]["distance"] / 1000
    except Exception:
        return float("inf")


# =====================================================
# CORE FUNCTION
# =====================================================

def get_nearest_station(user_lat: float, user_lon: float):
    """
    Returns:
    {
      lat: float,
      lon: float,
      distance_km: float,
      battery_count: int
    }
    or None
    """

    if not valid_india(user_lat, user_lon):
        return None

    # -------------------------------------------------
    # LOAD EVENTS FROM DB
    # -------------------------------------------------
    rows = fetch_all("""
        SELECT
            deviceid,
            lat,
            lon,
            charge_start_time,
            discharging_time
        FROM charging_events
    """)

    if not rows:
        return None

    # -------------------------------------------------
    # STEP 1: BUILD EVENTS
    # -------------------------------------------------
    events = []

    for device_id, lat, lon, start_ts, end_ts in rows:
        if not valid_india(lat, lon):
            continue

        events.append({
            "deviceid": device_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "start_t": start_ts.time(),
            "end_t": end_ts.time()
        })

    if not events:
        return None

    # -------------------------------------------------
    # STEP 2: FILTER PRESENT BATTERIES (MIDNIGHT SAFE)
    # -------------------------------------------------
    present = []

    for e in events:
        if (
            (e["start_t"] <= QUERY_TIME < e["end_t"]) or
            (
                e["start_t"] > e["end_t"] and
                (QUERY_TIME >= e["start_t"] or QUERY_TIME < e["end_t"])
            )
        ):
            present.append(e)

    if not present:
        return None

    # -------------------------------------------------
    # STEP 3: GROUP BY STATION (lat, lon)
    # -------------------------------------------------
    station_map = {}

    for e in present:
        key = (e["lat"], e["lon"])
        station_map.setdefault(key, set()).add(e["deviceid"])

    stations = [
        {
            "lat": lat,
            "lon": lon,
            "battery_count": len(devices)
        }
        for (lat, lon), devices in station_map.items()
        if len(devices) > 0
    ]

    if not stations:
        return None

    # -------------------------------------------------
    # STEP 4: HAVERSINE TOP-K
    # -------------------------------------------------
    for s in stations:
        s["air_km"] = haversine(user_lat, user_lon, s["lat"], s["lon"])

    stations.sort(key=lambda x: x["air_km"])
    candidates = stations[:TOP_K]

    # -------------------------------------------------
    # STEP 5: ROAD DISTANCE (WITH FALLBACK)
    # -------------------------------------------------
    for c in candidates:
        c["road_km"] = road_distance_km(
            user_lat,
            user_lon,
            c["lat"],
            c["lon"]
        )

        # 🚑 fallback to air distance if ORS fails
        if c["road_km"] == float("inf"):
            c["final_km"] = c["air_km"]
        else:
            c["final_km"] = c["road_km"]

    nearest = min(candidates, key=lambda x: x["final_km"])

    # -------------------------------------------------
    # FINAL OUTPUT
    # -------------------------------------------------
    return {
        "lat": nearest["lat"],
        "lon": nearest["lon"],
        "distance_km": round(nearest["final_km"], 2),
        "battery_count": nearest["battery_count"]
    }
