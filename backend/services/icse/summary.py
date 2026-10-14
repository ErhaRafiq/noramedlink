"""FE-2: the patient-level clinical summary for doctors, built by fixed rules.

Input: the patient's sources (reports with their entities, and vitals entered in the app), oldest
first, plus the medicine lists entered in the app. Output: fixed sections, each item tied to its
source (report id, title and date, or "entered in the app").

- Key findings: a sentence built from the counts below (the AI may reword it in Batch 4, from this
  content only, and never changes a flag).
- Abnormal results: result, persistent and trend flags (services/icse/flags.py).
- Conditions, allergies and medicines: as mentioned in reports ("mentioned in report", never a
  confirmed diagnosis), and medicines as entered in the app.
- Flags, values to check against the original report, and missing data.

Nothing here says a value is normal or a medicine is safe; when there is no data it says so.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services.icse.flags import build_flags

SUMMARY_VERSION = 1
SECTION_LIMIT = 5  # items shown per section before "show more"
RESULT_KINDS = ("result", "persistent", "trend")


def _ref(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_id": source["report_id"],
        "title": source.get("title"),
        "date": source.get("date"),
        "date_source": source.get("date_source"),
        "kind": source.get("kind", "report"),
    }


def _conditions(sources: list[dict]) -> tuple[list[dict], list[dict]]:
    """Conditions mentioned (not negated) and family history mentioned, each with its sources."""
    found: dict[str, dict] = {}
    family: dict[str, dict] = {}
    for source in sources:
        for entity in source.get("entities") or []:
            if entity.get("method") == "biobert":
                continue  # a model suggestion is never presented as a finding
            target = None
            if entity.get("type") == "condition" and entity.get("negated") is False:
                target = found
            elif entity.get("type") == "family_history" and entity.get("negated") is False:
                target = family
            if target is None:
                continue
            item = target.setdefault(
                entity["name"],
                {
                    "name": entity["name"],
                    "icd10": entity.get("icd10"),
                    "chronic": entity.get("chronic"),
                    "relatives": [],
                    "certainty": "mentioned in report",
                    "sources": [],
                },
            )
            if entity.get("relative") and entity["relative"] not in item["relatives"]:
                item["relatives"].append(entity["relative"])
            if all(s["report_id"] != source["report_id"] for s in item["sources"]):
                item["sources"].append(_ref(source))
    ordered = sorted(found.values(), key=lambda c: (not c["chronic"], c["name"]))
    return ordered, sorted(family.values(), key=lambda c: c["name"])


def _allergies(sources: list[dict]) -> dict[str, Any]:
    items: dict[str, dict] = {}
    none_recorded: list[dict] = []
    for source in sources:
        for entity in source.get("entities") or []:
            if entity.get("type") == "allergy":
                item = items.setdefault(
                    entity["name"],
                    {
                        "name": entity["name"],
                        "allergen_classes": entity.get("allergen_classes") or [],
                        "certainty": "mentioned in report",
                        "sources": [],
                    },
                )
                if all(s["report_id"] != source["report_id"] for s in item["sources"]):
                    item["sources"].append(_ref(source))
            elif entity.get("type") == "allergy_status":
                none_recorded.append(_ref(source))
    status = "listed" if items else "none_recorded" if none_recorded else "not_recorded"
    return {
        "status": status,
        "items": list(items.values()),
        # Kept even when allergies are listed elsewhere: conflicting reports are shown, not resolved.
        "no_known_allergies_in": none_recorded,
    }


def _app_medicines(medications: list[dict], today: date) -> list[dict]:
    current = []
    for medicine in medications:
        end = medicine.get("end_date")
        if end and end < today.isoformat():
            continue
        current.append({**medicine, "certainty": "entered in the app"})
    return current


def _missing(sources: list[dict], unreadable: list[dict], flags: dict, allergies: dict, medicines: dict) -> list[str]:
    reports = [s for s in sources if s.get("kind", "report") == "report"]
    vitals = [s for s in sources if s.get("kind") == "vitals"]
    missing = []
    if not reports and not unreadable:
        missing.append("No reports uploaded.")
    if unreadable:
        missing.append(f"{len(unreadable)} report(s) could not be read; their content is not in this summary.")
    if allergies["status"] == "not_recorded":
        missing.append("No allergy information in any report.")
    if not medicines["from_app"] and not medicines["from_reports"]:
        missing.append("No medicines entered in the app or listed in a report.")
    if not vitals:
        missing.append("No vitals entered in the app.")
    undated = [s for s in reports if not s.get("date")]
    if undated:
        missing.append(
            f"{len(undated)} report(s) have no printed date; their values are not used for persistent or trend flags."
        )
    if flags["check_original"]:
        missing.append(
            f"{len(flags['check_original'])} value(s) could not be checked: see 'Check against the original'."
        )
    return missing


def _key_findings(abnormal: list[dict], conditions: list[dict], medicines: dict, allergies: dict, checks: int) -> str:
    parts = []
    high_risk = sum(1 for f in abnormal if f["severity"] == "HIGH_RISK")
    results = sum(1 for f in abnormal if f["kind"] == "result")
    changing = sum(1 for f in abnormal if f["kind"] in ("persistent", "trend"))
    if results:
        parts.append(
            f"{results} result(s) outside the rules' ranges in the most recent reports"
            + (f", {high_risk} at a high-risk level" if high_risk else "")
        )
    if changing:
        parts.append(f"{changing} persistent or changing result(s) across dated reports")
    chronic = [c["name"] for c in conditions if c["chronic"]]
    if chronic:
        parts.append(
            f"long-term conditions mentioned: {', '.join(chronic[:4])}" + (" and more" if len(chronic) > 4 else "")
        )
    ongoing = len(medicines["from_reports"]) + len(medicines["from_app"])
    if ongoing:
        parts.append(f"{ongoing} medicine(s) listed")
    if allergies["status"] == "listed":
        parts.append(f"allergies mentioned: {', '.join(a['name'] for a in allergies['items'][:4])}")
    if checks:
        parts.append(f"{checks} value(s) to check against the original report")
    if not parts:
        return "No rule alerts and no conditions, medicines or allergies found in the available records."
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + ". For physician review."


def build_content(sources: list[dict], medications: list[dict], unreadable: list[dict], today: date) -> dict[str, Any]:
    """`sources`: oldest first, each {"report_id", "title", "kind" ("report"/"vitals"), "date",
    "date_source", "entities"}; `medications`: medicine lists entered in the app; `unreadable`:
    reports with no usable text."""
    flags = build_flags(sources)
    abnormal = [f for f in flags["flags"] if f["kind"] in RESULT_KINDS]
    other_flags = [f for f in flags["flags"] if f["kind"] not in RESULT_KINDS]
    conditions, family = _conditions(sources)
    allergies = _allergies(sources)
    treatment = next((f for f in flags["flags"] if f["kind"] == "ongoing_treatment"), None)
    medicines = {
        "from_app": _app_medicines(medications, today),
        "from_reports": treatment["sources"] if treatment else [],
        "stopped_in_reports": treatment.get("stopped", []) if treatment else [],
    }
    titles = {s["report_id"]: s for s in sources}
    for flag in flags["flags"] + flags["check_original"]:
        for item in flag.get("sources", []):
            source = titles.get(item.get("report_id"))
            if source:
                item.setdefault("title", source.get("title"))
                item.setdefault("kind", source.get("kind", "report"))
                item.setdefault("date_source", source.get("date_source"))
    return {
        "summary_version": SUMMARY_VERSION,
        "section_limit": SECTION_LIMIT,
        "key_findings": {
            "text": _key_findings(abnormal, conditions, medicines, allergies, len(flags["check_original"])),
            "source": "rule_based",
        },
        "abnormal_results": abnormal,
        "conditions": conditions,
        "family_history": family,
        "medications": medicines,
        "allergies": allergies,
        "flags": other_flags,
        "check_original": flags["check_original"],
        "missing_data": _missing(sources, unreadable, flags, allergies, medicines),
        "notes": flags["notes"],
        "sources": [_ref(s) for s in sources if s.get("kind", "report") == "report"],
        "unreadable_reports": unreadable,
    }


def render_text(content: dict[str, Any]) -> str:
    """The summary as plain text, section by section (stored with each version)."""
    lines = ["Key findings", content["key_findings"]["text"], ""]

    def section(title: str, items: list[str], empty: str) -> None:
        lines.append(title)
        lines.extend([f"- {item}" for item in items] or [empty])
        lines.append("")

    section("Abnormal results", [f["message"] for f in content["abnormal_results"]], "No rule alerts.")
    section(
        "Conditions mentioned in reports",
        [c["name"] + (" (long-term)" if c["chronic"] else "") for c in content["conditions"]],
        "None mentioned.",
    )
    medicines = content["medications"]
    section(
        "Medicines",
        [f"{m['name']} {m.get('dosage') or ''} (entered in the app)".replace("  ", " ") for m in medicines["from_app"]]
        + [
            f"{m['medicine']} {m.get('dose') or ''} {m.get('frequency') or ''} (mentioned in report)".replace("  ", " ")
            for m in medicines["from_reports"]
        ],
        "None recorded.",
    )
    allergies = content["allergies"]
    section(
        "Allergies",
        [f"{a['name']} (mentioned in report)" for a in allergies["items"]]
        + (["No known allergies (mentioned in report)"] if allergies["no_known_allergies_in"] else []),
        "Not recorded.",
    )
    section("Flags", [f["message"] for f in content["flags"]], "None.")
    section("Check against the original report", [c["message"] for c in content["check_original"]], "None.")
    section("Missing data", content["missing_data"], "None.")
    return "\n".join(lines).strip()
