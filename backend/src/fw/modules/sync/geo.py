import math
from typing import Any

from shapely.geometry import shape
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.polygon import Polygon


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters."""
    radius_earth_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_earth_m * c


def compute_geofence_circle(
    geojson: dict[str, Any] | None, extra_radius_m: float = 300.0
) -> dict[str, Any] | None:
    """Compute centroid and bounding circle radius (max vertex distance + extra_radius_m)."""
    if not geojson:
        return None

    try:
        geom = shape(geojson)
        if geom.is_empty:
            return None

        centroid = geom.centroid
        center_lat = float(centroid.y)
        center_lng = float(centroid.x)

        # Exterior coords are [lng, lat]
        max_dist = 0.0
        if isinstance(geom, Polygon):
            coords = list(geom.exterior.coords)
        elif isinstance(geom, MultiPolygon):
            coords = [c for p in geom.geoms for c in p.exterior.coords]
        else:
            coords = []

        for lng, lat in coords:
            dist = haversine_distance_m(center_lat, center_lng, lat, lng)
            if dist > max_dist:
                max_dist = dist

        return {
            "center": {
                "lat": round(center_lat, 6),
                "lng": round(center_lng, 6),
            },
            "radius_m": round(max_dist + extra_radius_m, 1),
        }
    except Exception:
        return None
