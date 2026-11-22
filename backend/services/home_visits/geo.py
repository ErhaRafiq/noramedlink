"""Distances and coordinate checks. Browser location only: no map, geocoding or routing service is used.

The distance is the straight line over the earth (Haversine), never a road distance or a travel time, and
it is always worded that way. Doctors see it rounded to 0.5 km before they accept.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088
ROUND_TO_KM = 0.5
MAX_ACCURACY_M = 100_000.0


class InvalidLocation(ValueError):
    """A coordinate that is not a real place on earth (the message is safe to show)."""


def validate_coordinates(latitude: object, longitude: object) -> tuple[float, float]:
    """The pair as floats, or InvalidLocation. Latitude -90 to 90, longitude -180 to 180, finite."""
    try:
        lat, lon = float(latitude), float(longitude)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise InvalidLocation("Enter the latitude and longitude as numbers.") from None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise InvalidLocation("Enter the latitude and longitude as numbers.")
    if not -90 <= lat <= 90:
        raise InvalidLocation("Latitude must be between -90 and 90.")
    if not -180 <= lon <= 180:
        raise InvalidLocation("Longitude must be between -180 and 180.")
    return lat, lon


def validate_accuracy(accuracy_m: object) -> float | None:
    """The browser's accuracy radius in metres (None when typed by hand), or InvalidLocation."""
    if accuracy_m is None:
        return None
    try:
        value = float(accuracy_m)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise InvalidLocation("The location accuracy must be a number of metres.") from None
    if not math.isfinite(value) or value < 0 or value > MAX_ACCURACY_M:
        raise InvalidLocation("The location accuracy is not a sensible number of metres.")
    return value


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line (great-circle) distance in km between two points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def round_to_half_km(km: float) -> float:
    """Nearest 0.5 km (a half km rounds up, not to even)."""
    return math.floor(km / ROUND_TO_KM + 0.5) * ROUND_TO_KM


def distance_label(km: float) -> str:
    """The doctor-facing wording: rounded, and clear that it is a straight line."""
    rounded = round_to_half_km(km)
    if rounded == 0:
        return "straight-line distance, less than 0.5 km"
    return f"straight-line distance, about {rounded:g} km"


def accuracy_label(accuracy_m: float | None) -> str:
    """What the patient sees under 'Use my current location'."""
    if accuracy_m is None:
        return "Typed by you"
    metres = round(accuracy_m)
    return f"accurate to about {metres} m" if metres < 1000 else f"accurate to about {metres / 1000:.1f} km"
