import asyncio
import os
import re
from functools import lru_cache
from typing import Any


BIOBERT_MODEL = os.getenv("BIOBERT_MODEL", "d4data/biomedical-ner-all")

LABEL_MAP = {
    "disease_disorder": "Disease",
    "disease": "Disease",
    "problem": "Disease",
    "medication": "Medicine",
    "drug": "Medicine",
    "chemical": "Medicine",
    "sign_symptom": "Symptom",
    "symptom": "Symptom",
    "lab_value": "Lab Value",
    "diagnostic_procedure": "Lab Value",
    "test": "Lab Value",
    "biological_structure": "Anatomy",
    "anatomy": "Anatomy",
}

DISEASE_TERMS = [
    "diabetes",
    "hypertension",
    "asthma",
    "anemia",
    "anaemia",
    "kidney disease",
    "renal disease",
    "infection",
    "fracture",
    "arthritis",
    "cholesterol",
    "hyperlipidemia",
]

SYMPTOM_TERMS = [
    "fever",
    "cough",
    "pain",
    "chest pain",
    "shortness of breath",
    "dizziness",
    "swelling",
    "rash",
    "weakness",
    "vomiting",
    "nausea",
]

MEDICINE_TERMS = [
    "metformin",
    "insulin",
    "aspirin",
    "warfarin",
    "ibuprofen",
    "paracetamol",
    "acetaminophen",
    "atorvastatin",
    "amlodipine",
    "lisinopril",
    "sildenafil",
    "nitroglycerin",
    "glimepiride",
]

LAB_FIELD_HINTS = {
    "glucose",
    "hba1c",
    "hemoglobin",
    "haemoglobin",
    "platelets",
    "creatinine",
    "urea",
    "egfr",
    "cholesterol",
    "ldl",
    "hdl",
    "triglycerides",
    "troponin",
    "blood_pressure",
}


def _normalize_label(label: str) -> str:
    cleaned = re.sub(r"^(B|I)-", "", label or "", flags=re.IGNORECASE)
    cleaned = cleaned.replace("-", "_").replace(" ", "_").lower()
    return LABEL_MAP.get(cleaned, cleaned.replace("_", " ").title() or "Medical Entity")


def _entity_key(entity: dict[str, Any]) -> tuple[str, str]:
    return (str(entity.get("text") or "").strip().lower(), str(entity.get("label") or "").lower())


def _merge_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for entity in entities:
        text = str(entity.get("text") or "").strip(" ,.;:\n\t")
        label = str(entity.get("label") or "Medical Entity").strip()
        if len(text) < 2:
            continue
        key = (text.lower(), label.lower())
        confidence = float(entity.get("confidence") or 0)
        current = merged.get(key)
        if not current or confidence > float(current.get("confidence") or 0):
            merged[key] = {
                "text": text[:160],
                "label": label,
                "confidence": round(max(0.0, min(confidence, 1.0)), 3),
                "source": entity.get("source") or "biobert",
            }
    return sorted(merged.values(), key=lambda item: (-float(item["confidence"]), item["label"], item["text"]))[:80]


def _extract_regex_terms(text: str, terms: list[str], label: str, confidence: float) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    normalized = f" {text.lower()} "
    for term in terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", normalized):
            entities.append(
                {
                    "text": term,
                    "label": label,
                    "confidence": confidence,
                    "source": "rule_fallback",
                }
            )
    return entities


def _extract_allergies(text: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    patterns = [
        r"\ballerg(?:y|ic|ies)\s*(?:to|:|-)?\s*([a-z][a-z0-9 /+-]{2,60})",
        r"\bno known drug allergies\b",
        r"\bnkda\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = match.group(1) if match.lastindex else match.group(0)
            entities.append(
                {
                    "text": value.strip(" .,:;")[:120],
                    "label": "Allergy",
                    "confidence": 0.78,
                    "source": "rule_fallback",
                }
            )
    return entities


def _entities_from_structured_fields(structured_fields: dict[str, Any] | None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for key, value in (structured_fields or {}).items():
        if value is None:
            continue
        normalized_key = str(key).strip().lower()
        if normalized_key in LAB_FIELD_HINTS:
            entities.append(
                {
                    "text": f"{normalized_key.replace('_', ' ')}: {str(value).strip()[:80]}",
                    "label": "Lab Value",
                    "confidence": 0.86,
                    "source": "structured_fields",
                }
            )
    return entities


def fallback_entities(text: str, structured_fields: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    entities.extend(_extract_regex_terms(text, DISEASE_TERMS, "Disease", 0.72))
    entities.extend(_extract_regex_terms(text, SYMPTOM_TERMS, "Symptom", 0.68))
    entities.extend(_extract_regex_terms(text, MEDICINE_TERMS, "Medicine", 0.76))
    entities.extend(_extract_allergies(text))
    entities.extend(_entities_from_structured_fields(structured_fields))
    return _merge_entities(entities)


@lru_cache(maxsize=1)
def _load_pipeline():
    try:
        from transformers import pipeline
    except Exception as exc:  # pragma: no cover - depends on optional runtime deps.
        raise RuntimeError("BioBERT dependencies are not installed. Install transformers and torch.") from exc

    return pipeline(
        "ner",
        model=BIOBERT_MODEL,
        tokenizer=BIOBERT_MODEL,
        aggregation_strategy="simple",
    )


def _run_biobert(text: str) -> list[dict[str, Any]]:
    ner = _load_pipeline()
    model_results = ner(text[:8000])
    entities: list[dict[str, Any]] = []
    for item in model_results:
        word = str(item.get("word") or item.get("entity_group") or "").replace(" ##", "").strip()
        label = _normalize_label(str(item.get("entity_group") or item.get("entity") or "Medical Entity"))
        confidence = float(item.get("score") or 0)
        entities.append(
            {
                "text": word,
                "label": label,
                "confidence": confidence,
                "source": "biobert",
            }
        )
    return _merge_entities(entities)


async def extract_medical_entities(
    text: str,
    structured_fields: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cleaned_text = " ".join((text or "").split())
    if not cleaned_text:
        return [], {"model": BIOBERT_MODEL, "source": "none", "warning": "No OCR text was available for entity extraction."}

    try:
        entities = await asyncio.to_thread(_run_biobert, cleaned_text)
        source = "biobert"
        warning = None
    except Exception as exc:
        entities = []
        source = "rule_fallback"
        warning = str(exc)

    if structured_fields:
        entities = _merge_entities([*entities, *_entities_from_structured_fields(structured_fields)])

    if not entities:
        entities = fallback_entities(cleaned_text, structured_fields)

    return entities, {
        "model": BIOBERT_MODEL,
        "source": source,
        "warning": warning,
        "entity_count": len(entities),
    }
