"""
pv/geo.py
─────────
Pure geographic / trigonometric helpers.
No tkinter dependency — safe to unit-test standalone.
Angles in degrees (compass: 0 = North, clockwise positive).
Distances in metres.
"""
import math

_DEG = 111_320.0      # metres per degree of latitude (approx.)
_R   = 6_371_000.0    # Earth radius (m)


def local_to_latlon(x, y, lat0, lon0, bearing_deg):
    """Convert AB Dynamics local (x, y) metres → (lat, lon).
    bearing_deg = compass bearing of the +X axis in the world frame."""
    b = math.radians(bearing_deg)
    north_m = x * math.cos(b) - y * math.sin(b)
    east_m  = x * math.sin(b) + y * math.cos(b)
    return (lat0 + north_m / _DEG,
            lon0 + east_m  / (_DEG * math.cos(math.radians(lat0))))


def latlon_to_local(lat, lon, lat0, lon0, bearing_deg):
    """Inverse of local_to_latlon."""
    b = math.radians(bearing_deg)
    north_m = (lat - lat0) * _DEG
    east_m  = (lon - lon0) * _DEG * math.cos(math.radians(lat0))
    return ( north_m * math.cos(b) + east_m * math.sin(b),
            -north_m * math.sin(b) + east_m * math.cos(b))


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(df/2)**2 + math.cos(f1)*math.cos(f2)*math.sin(dl/2)**2
    return _R * 2 * math.asin(math.sqrt(min(a, 1.0)))


def heading_between(lat1, lon1, lat2, lon2):
    """Compass bearing (0–360°) from point 1 toward point 2."""
    north_m = (lat2 - lat1) * _DEG
    east_m  = (lon2 - lon1) * _DEG * math.cos(math.radians(lat1))
    return math.degrees(math.atan2(east_m, north_m)) % 360.0


def endpoint_from_bearing(lat1, lon1, heading_deg, length_m):
    """Return (lat2, lon2) at distance length_m along heading_deg from (lat1, lon1)."""
    b = math.radians(heading_deg)
    north_m = length_m * math.cos(b)
    east_m  = length_m * math.sin(b)
    return (lat1 + north_m / _DEG,
            lon1 + east_m  / (_DEG * math.cos(math.radians(lat1))))


def rect_corners(clat, clon, w_m, h_m, heading_deg=0.0):
    """4 (lat, lon) corners of a rectangle centred at (clat, clon).

    heading_deg = compass bearing of the forward / height axis.
      0°  → height N–S, width E–W  (axis-aligned)
      90° → height E–W, width N–S
    Order: front-left → front-right → rear-right → rear-left.
    """
    b = math.radians(heading_deg)
    hh, hw = h_m / 2, w_m / 2
    cos_b, sin_b = math.cos(b), math.sin(b)
    corners = []
    for u, v in [(hh, -hw), (hh, hw), (-hh, hw), (-hh, -hw)]:
        north_m = u * cos_b - v * sin_b
        east_m  = u * sin_b + v * cos_b
        corners.append((
            clat + north_m / _DEG,
            clon + east_m  / (_DEG * math.cos(math.radians(clat))),
        ))
    return corners
