import math
from intent_bot.db import fetch_all

# =====================================================
# CONFIG
# =====================================================
TOP_K = 5

INDIA_LAT_RANGE = (8, 37)
INDIA_LON_RANGE = (68, 98)

# =====================================================
# HELPERS
# =====================================================

def valid_india(lat, lon):
    return (
        INDIA_LAT_RANGE[0] <= lat <= INDIA_LAT_RANGE[1] and
        INDIA_LON_RANGE[0] <= lon <= INDIA_LON_RANGE[1]
    )


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
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =====================================================
# CORE SERVICE
# =====================================================

def get_nearest_active_dsk(user_lat, user_lon):
    """
    Returns nearest active DSK using haversine distance
    """

    if not valid_india(user_lat, user_lon):
        return None

    rows = fetch_all("""
        SELECT id, latitude, longitude, available_batteries
        FROM dsk_centers
        WHERE is_active_dsk = true
          AND available_batteries > 0
    """)

    if not rows:
        return None

    stations = []

    for dsk_id, lat, lon, batteries in rows:
        lat = float(lat)
        lon = float(lon)

        if not valid_india(lat, lon):
            continue
        dist = haversine(
        float(user_lat),
        float(user_lon),
        lat,
        lon
        )


        stations.append({
            "station_id": dsk_id,
            "lat": lat,
            "lon": lon,
            "distance_km": round(dist, 2),
            "available_batteries": batteries
        })

    if not stations:
        return None

    stations.sort(key=lambda x: x["distance_km"])
    best = stations[:TOP_K][0]

    return best
