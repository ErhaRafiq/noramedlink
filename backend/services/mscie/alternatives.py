"""MSCIE FE-3, FE-4, FE-5: safer alternatives, ranked, with the reasoning behind each score.

For a proposed medicine with a high-risk alert, candidates come from alternatives.csv (same use,
documented reason, source). Each candidate is re-checked against the same patient with the same
engine; a contraindicated candidate is never suggested. The rest are ranked by a transparent
weighted score (ranking_weights.csv):

    score = sum(weight x factor), factors in [0, 1]:
      safety            worst alert for this patient (none 1.0 ... major 0.2)
      renal_fit         1.0, or 0.6 when a kidney or potassium rule applies
      previous_response 1.0 taken before without a recorded problem, 0.6 never, 0.2 stopped/side effect
      simplicity        1.0 once daily, 0.8 twice, 0.6 three or more times

Every factor's value and the reason for it are returned, so the physician sees why one candidate
ranks above another. Nothing is chosen automatically.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from services.knowledge.tables import records
from services.mscie.engine import RANK, Med, PatientContext, Proposed, check_item, matches, resolve, worst

SAFETY = {None: 1.0, "info": 0.9, "minor": 0.9, "moderate": 0.6, "major": 0.2}
FREQUENCY_SCORE = {"OD": 1.0, "BD": 0.8, "TDS": 0.6, "QID": 0.6}
LAB_RULES = ("eGFR", "Potassium")


@cache
def weights() -> dict[str, float]:
    return {row["factor"]: float(row["weight"]) for row in records("ranking_weights")}


def _previous(generic: str, context: PatientContext) -> tuple[float, str]:
    history = [p for p in context.previous if p["generic"] == generic]
    if any(p["problem"] for p in history):
        note = next(p["note"] for p in history if p["problem"])
        return 0.2, f"stopped or a side effect recorded before ({note})"
    if history or any(generic in m.generics for m in context.medicines):
        return 1.0, "taken before with no problem recorded"
    return 0.6, "not taken before (no response data)"


def _simplicity(generic: str) -> tuple[float, str]:
    usual = {row["generic"]: row["usual_frequency"] for row in records("dose_limits")}.get(generic)
    if usual is None:
        return 0.8, "usual dosing frequency not in the knowledge base"
    return FREQUENCY_SCORE[usual], f"usually {usual}"


def score(candidate: Med, alerts: list[dict], context: PatientContext) -> dict[str, Any]:
    severity = worst(alerts)
    renal = [a for a in alerts if a["kind"] == "contraindication" and a["id"].split(":")[-1] in LAB_RULES]
    previous, previous_reason = _previous(candidate.generics[0], context)
    simple, simple_reason = _simplicity(candidate.generics[0])
    factors = {
        "safety": (SAFETY[severity], f"worst alert for this patient: {severity or 'none'}"),
        "renal_fit": (0.6 if renal else 1.0, renal[0]["title"] if renal else "no kidney or potassium rule applies"),
        "previous_response": (previous, previous_reason),
        "simplicity": (simple, simple_reason),
    }
    w = weights()
    breakdown = [
        {"factor": name, "value": value, "weight": w[name], "contribution": round(value * w[name], 3), "reason": reason}
        for name, (value, reason) in factors.items()
    ]
    return {"score": round(sum(item["contribution"] for item in breakdown), 3), "breakdown": breakdown}


def alternatives_for(proposed: Proposed, item: Med, others: list[Med], context: PatientContext) -> list[dict[str, Any]]:
    """Ranked, re-checked alternatives for one proposed medicine (best first)."""
    seen: set[str] = set()
    out = []
    for row in records("alternatives"):
        if not row["alternative"] or not matches(row["for_drug"], item) or row["alternative"] in item.generics:
            continue
        if row["alternative"] in seen:
            continue
        seen.add(row["alternative"])
        candidate = resolve(row["alternative"], "suggested alternative")
        alerts = check_item(candidate, Proposed(row["alternative"]), others, context)
        if worst(alerts) == "contraindicated":
            continue  # never suggest a medicine the rules contraindicate for this patient
        out.append({
            "medicine": candidate.label,
            "classes": list(candidate.classes),
            "use": row["use"],
            "reason": row["reason"],
            "sources": [{"label": row["source"]}],
            "alerts": alerts,
            **score(candidate, alerts, context),
        })  # fmt: skip
    out.sort(key=lambda c: (-c["score"], RANK.get(worst(c["alerts"]) or "info", 0), c["medicine"]))
    for rank, candidate in enumerate(out, start=1):
        candidate["rank"] = rank
    return out
