"""Everyday-wording benchmark for the patient summary (synthetic data only, no AI).

For every synthetic report (icse_samples/ and ocr_samples/), builds the rule-based patient summary
and measures:
- medical words left without everyday wording (target 0);
- numbers in the summary that are not in the report (target 0);
- reading level (Flesch-Kincaid grade) of the report text and of the summary's sentences.

    backend\\venv\\Scripts\\python.exe scripts\\plain_bench\\benchmark_plain.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.ai_guard import numbers_not_in_source  # noqa: E402
from services.icse.entities import extract_entities  # noqa: E402
from services.patient_summary import build_patient_summary  # noqa: E402
from services.plain_language import SECTION_HEADINGS, find_terms, unexplained_terms  # noqa: E402
from services.rule_validation_service import validate_medical_rules  # noqa: E402


def syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?()\"'")
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups) - (1 if word.endswith("e") and len(groups) > 1 else 0)
    return max(1, count)


def grade(text: str) -> float | None:
    """Flesch-Kincaid grade of the prose (headings and lines that are only data are left out)."""
    lines = [
        line.strip("- ").strip()
        for line in text.splitlines()
        if line.strip()
        and line.strip().lower() not in SECTION_HEADINGS
        and re.search(r"[a-z]{3,}", line)
    ]
    sentences = [
        s
        for s in re.split(r"(?<=[.!?])\s+|\n", "\n".join(lines))
        if re.search(r"[A-Za-z]", s)
    ]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", " ".join(sentences))]
    if not sentences or not words:
        return None
    return (
        0.39 * len(words) / len(sentences)
        + 11.8 * sum(syllables(w) for w in words) / len(words)
        - 15.59
    )


def reports() -> list[tuple[str, str]]:
    found = [
        (p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted((ROOT / "icse_samples").glob("icse-p*/*.txt"))
    ]
    found += [
        (p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted((ROOT / "ocr_samples").glob("lab*.txt"))
    ]
    if not found:
        raise SystemExit(
            "Generate the samples first (scripts/icse_bench, scripts/ocr_bench)."
        )
    return found


def main() -> None:
    rows = []
    for name, text in reports():
        validation = validate_medical_rules(text)
        summary = build_patient_summary(text, extract_entities(text), validation, "Lab")
        rows.append(
            {
                "name": name,
                "terms_in_report": len(find_terms(text)),
                "unexplained": unexplained_terms(summary),
                "invented_numbers": numbers_not_in_source(summary, text),
                "grade_report": grade(text),
                "grade_summary": grade(summary),
            }
        )
    unexplained = [r for r in rows if r["unexplained"]]
    invented = [r for r in rows if r["invented_numbers"]]
    report_grades = [r["grade_report"] for r in rows if r["grade_report"] is not None]
    summary_grades = [
        r["grade_summary"] for r in rows if r["grade_summary"] is not None
    ]
    lines = [
        "# Everyday-wording benchmark (synthetic reports, rule-based summary, no AI)",
        "",
        "| Reports | Medical words in the reports | Summaries with a word left unexplained | Summaries with a number not in the report | Reading grade: report | Reading grade: summary |",
        "|---|---|---|---|---|---|",
        f"| {len(rows)} | {sum(r['terms_in_report'] for r in rows)} | {len(unexplained)} | {len(invented)} | "
        f"{mean(report_grades):.1f} | {mean(summary_grades):.1f} |",
        "",
        "Reading grade is the Flesch-Kincaid grade level (lower is easier; about 6-8 is plain English).",
    ]
    for row in unexplained[:10]:
        lines.append(f"- {row['name']}: unexplained {row['unexplained']}")
    for row in invented[:10]:
        lines.append(
            f"- {row['name']}: numbers not in the report {row['invented_numbers']}"
        )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
