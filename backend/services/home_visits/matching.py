"""Ranking doctors for a home-visit request: proximity, specialty match, availability and suitability.

Rules decide, no AI. The weights are in home_visit_weights.csv (a demo knowledge base). A doctor is offered
only if they switched home visits on, have a base location and a service radius, the request lies inside
that radius, their listed specialty is for home visits and matches the reason (or is a General Physician),
they are not already on another visit, and their own weekly hours cover now or the next 2 hours.
Distance is the straight line (Haversine); it is never presented as road distance or travel time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

from services.home_visits import suitability
from services.home_visits.geo import haversine_km
from services.knowledge.tables import records

HORIZON_KM = 25.0
AVAILABLE_NOW, AVAILABLE_SOON, UNAVAILABLE = "now", "soon", "none"
AVAILABILITY_SCORE = {AVAILABLE_NOW: 1.0, AVAILABLE_SOON: 0.5}
GENERALIST_SCORE = 0.5


@dataclass(frozen=True)
class Candidate:
    doctor_id: int
    listed_specialty: str
    latitude: float | None
    longitude: float | None
    radius_km: float | None
    availability: str = UNAVAILABLE
    busy: bool = False


@dataclass(frozen=True)
class Ranked:
    doctor_id: int
    specialty: str
    distance_km: float
    score: float
    parts: dict[str, float] = field(default_factory=dict)


@cache
def weights() -> dict[str, float]:
    return {row["factor"]: float(row["weight"]) for row in records("home_visit_weights")}


def specialty_score(doctor_specialty: str, request_specialty: str) -> float:
    if doctor_specialty == request_specialty:
        return 1.0
    return GENERALIST_SCORE if doctor_specialty == suitability.FALLBACK else 0.0


def evaluate(candidate: Candidate, lat: float, lon: float, request_specialty: str) -> Ranked | None:
    """The ranked entry for one doctor, or None when they cannot be offered this request."""
    if candidate.latitude is None or candidate.longitude is None or not candidate.radius_km:
        return None
    if candidate.radius_km <= 0 or candidate.busy or candidate.availability not in AVAILABILITY_SCORE:
        return None
    specialty = suitability.specialty_of(candidate.listed_specialty)
    if specialty is None or not suitability.is_suitable(specialty):
        return None
    match = specialty_score(specialty, request_specialty)
    if match == 0:
        return None
    distance = haversine_km(lat, lon, candidate.latitude, candidate.longitude)
    if distance > candidate.radius_km:
        return None
    parts = {
        "proximity": max(0.0, 1 - distance / HORIZON_KM),
        "specialty": match,
        "availability": AVAILABILITY_SCORE[candidate.availability],
        "suitability": suitability.suitability(specialty),
    }
    score = sum(weights()[name] * value for name, value in parts.items())
    return Ranked(candidate.doctor_id, specialty, distance, round(score, 6), parts)


def rank(
    candidates: list[Candidate], lat: float, lon: float, request_specialty: str, limit: int | None = None
) -> list[Ranked]:
    """Eligible doctors, best first: highest score, then nearest, then lowest id (so ties are stable)."""
    found = [r for c in candidates if (r := evaluate(c, lat, lon, request_specialty))]
    found.sort(key=lambda r: (-r.score, r.distance_km, r.doctor_id))
    return found[:limit] if limit is not None else found
