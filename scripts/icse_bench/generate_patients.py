"""Synthetic patients for the clinical-summary (ICSE) benchmark. NOT REAL PATIENT DATA.

Each patient gets several reports over time (clinic notes, discharge summaries, lab reports) with
the things real reports contain: brand names, doses, stopped medicines, negations ("no history
of asthma", "TB ruled out"), allergies or NKDA, abbreviations (DM, HTN, Hb, K), repeated tests,
and some conditions and medicines that the demo knowledge base does not know (so recall is
measured honestly). The ground truth for every report is written next to it.

    python scripts/icse_bench/generate_patients.py      -> icse_samples/ (gitignored)
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "icse_samples"
SEED = 20261014

# (text written in the report, ground-truth name). Ground-truth names are the knowledge-base names;
# the ones marked None are deliberately outside the demo knowledge base.
CONDITIONS = [
    ("type 2 diabetes mellitus", "diabetes mellitus"),
    ("T2DM", "diabetes mellitus"),
    ("DM", "diabetes mellitus"),
    ("HTN", "hypertension"),
    ("hypertension", "hypertension"),
    ("bronchial asthma", "asthma"),
    ("IHD", "ischaemic heart disease"),
    ("CKD", "chronic kidney disease"),
    ("hypothyroidism", "hypothyroidism"),
    ("dyslipidemia", "dyslipidaemia"),
    ("iron deficiency anaemia", "anaemia"),
    ("chronic hepatitis C", "chronic hepatitis C"),
    ("osteoarthritis", "osteoarthritis"),
    ("COPD", "chronic obstructive pulmonary disease"),
    ("atrial fibrillation", "atrial fibrillation"),
    ("epilepsy", "epilepsy"),
    ("fatty liver", "fatty liver disease"),
]
UNKNOWN_CONDITIONS = ["sarcoidosis", "myasthenia gravis", "Graves ophthalmopathy", "benign prostatic hyperplasia"]
NEGATABLE = [
    ("asthma", "asthma"),
    ("TB", "tuberculosis"),
    ("tuberculosis", "tuberculosis"),
    ("hepatitis B", "chronic hepatitis B"),
    ("diabetes", "diabetes mellitus"),
    ("stroke", "stroke"),
    ("epilepsy", "epilepsy"),
]

# (text, generic(s) joined by " + ", dose, frequency)
MEDICATIONS = [
    ("Glucophage", "metformin", "500 mg", "BD"),
    ("Metformin", "metformin", "850 mg", "BD"),
    ("Norvasc", "amlodipine", "5 mg", "OD"),
    ("Amlodipine", "amlodipine", "10 mg", "OD"),
    ("Lipitor", "atorvastatin", "20 mg", "at night"),
    ("Concor", "bisoprolol", "2.5 mg", "OD"),
    ("Lasix", "furosemide", "40 mg", "OD"),
    ("Risek", "omeprazole", "20 mg", "OD"),
    ("Panadol", "paracetamol", "500 mg", "TDS"),
    ("Brufen", "ibuprofen", "400 mg", "TDS"),
    ("Augmentin", "amoxicillin and clavulanic acid", "625 mg", "BD"),
    ("Flagyl", "metronidazole", "400 mg", "TDS"),
    ("Disprin", "aspirin", "75 mg", "OD"),
    ("Warfarin", "warfarin", "5 mg", "OD"),
    ("Amaryl", "glimepiride", "2 mg", "OD"),
    ("Insulin glargine", "insulin", "18 units", "at night"),
    ("Levothyroxine", "levothyroxine", "50 mcg", "OD"),
    ("Ventolin", "salbutamol", "100 mcg", "PRN"),
    ("Losartan", "losartan", "50 mg", "OD"),
    ("Clopidogrel", "clopidogrel", "75 mg", "OD"),
]
UNKNOWN_PRESCRIBED = [("Rifaximin", "550 mg", "BD"), ("Ivabradine", "5 mg", "BD"), ("Ursodiol", "250 mg", "TDS")]
UNKNOWN_FREE_TEXT = [("ranolazine", "500 mg", "BD"), ("tamsulosin", "0.4 mg", "OD")]
ALLERGIES = [("penicillin", "penicillin"), ("sulfa drugs", "sulfa drugs"), ("NSAIDs", "nsaids"), ("aspirin", "aspirin")]

# (printed name, KB name, unit, low, high, decimals)
LABS = [
    ("Hemoglobin", "Hemoglobin", "g/dL", 12.0, 17.5, 1),
    ("Hb", "Hemoglobin", "g/dL", 12.0, 17.5, 1),
    ("WBC Count", "WBC Count", "x10^9/L", 4.0, 11.0, 1),
    ("Platelet Count", "Platelet Count", "x10^9/L", 150, 450, 0),
    ("Fasting Blood Sugar", "Fasting Blood Sugar", "mg/dL", 70, 100, 0),
    ("Random Blood Sugar", "Random Blood Sugar", "mg/dL", 70, 140, 0),
    ("HbA1c", "HbA1c", "%", 4.0, 5.6, 1),
    ("Serum Creatinine", "Creatinine", "mg/dL", 0.6, 1.3, 2),
    ("Urea", "Urea", "mg/dL", 15, 45, 0),
    ("eGFR", "eGFR", "mL/min/1.73m2", 90, 120, 0),
    ("Sodium", "Sodium", "mmol/L", 135, 145, 0),
    ("K", "Potassium", "mmol/L", 3.5, 5.1, 1),
    ("Total Cholesterol", "Total Cholesterol", "mg/dL", 0, 200, 0),
    ("LDL Cholesterol", "LDL Cholesterol", "mg/dL", 0, 130, 0),
    ("ALT (SGPT)", "ALT", "U/L", 7, 56, 0),
    ("TSH", "TSH", "mIU/L", 0.4, 4.0, 2),
]


def fmt(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


class Report:
    def __init__(self, kind: str, day: date):
        self.kind, self.day = kind, day
        self.lines: list[str] = []
        self.truth: list[dict] = []
        self.out_of_kb: list[dict] = []  # present in the text, deliberately unknown to the knowledge base

    def add(self, line: str) -> None:
        self.lines.append(line)

    def expect(self, kind: str, name: str, **attrs) -> None:
        self.truth.append({"type": kind, "name": name, **attrs})


def condition_list(rng: random.Random, report: Report, picks) -> str:
    parts = []
    for text, name in picks:
        parts.append(text)
        report.expect("condition", name, negated=False)
    return ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]


def note(rng: random.Random, patient: dict, day: date, kind: str) -> Report:
    report = Report(kind, day)
    title = {"clinic": "OUTPATIENT CLINIC NOTE", "discharge": "DISCHARGE SUMMARY"}[kind]
    report.add("Example General Hospital, Islamabad")
    report.add(title)
    report.add(f"Date: {day:%d-%b-%Y} | MR No: SYN-{rng.randint(10000, 99999)}")
    report.add("")

    history = condition_list(rng, report, patient["conditions"])
    lead = rng.choice(["Known case of", "K/C/O", "Patient with a history of", "Diagnosed with"])
    unknown = patient["unknown_condition"]
    report.add(f"CLINICAL HISTORY: {lead} {history}. Also has {unknown}.")
    report.out_of_kb.append({"type": "condition", "name": unknown.lower()})
    negated = rng.sample([n for n in NEGATABLE if n[1] not in {c[1] for c in patient["conditions"]}], 2)
    first, second = negated
    report.add(f"No history of {first[0]}. {second[0][0].upper() + second[0][1:]} ruled out on previous workup.")
    report.expect("condition", first[1], negated=True)
    report.expect("condition", second[1], negated=True)
    report.add(
        rng.choice(["Denies chest pain or fever.", "Complains of fatigue for two weeks.", "No shortness of breath."])
    )

    if patient["allergies"]:
        report.add(
            rng.choice(["Allergies: ", "Drug allergy: ", "Allergic to "])
            + ", ".join(a[0] for a in patient["allergies"])
            + "."
        )
        for _, name in patient["allergies"]:
            report.expect("allergy", name)
    else:
        report.add(rng.choice(["Allergies: NKDA.", "No known drug allergies.", "Allergies: none known."]))
        report.expect("allergy_status", "no known allergies")

    report.add("")
    report.add("CURRENT MEDICATIONS:" if kind == "clinic" else "DISCHARGE MEDICATIONS:")
    for text, generic, dose, freq in patient["medications"]:
        prefix = rng.choice(["Tab ", "Tab. ", ""]) if not text.startswith("Insulin") else "Inj "
        report.add(f"- {prefix}{text} {dose} {freq}")
        report.expect("medication", generic, status="mentioned", dose=dose, frequency=freq)
    name, dose, freq = patient["unknown_prescribed"]
    report.add(f"- Tab {name} {dose} {freq}")
    report.expect("medication", name.lower(), status="mentioned", dose=dose, frequency=freq)
    free_name, free_dose, free_freq = patient["unknown_free_text"]
    report.add(f"- {free_name} {free_dose} {free_freq}")
    report.out_of_kb.append({"type": "medication", "name": free_name})
    if patient["stopped"]:
        text, generic, _, _ = patient["stopped"]
        report.add(f"{text} stopped {rng.choice(['last month', 'two weeks ago', 'due to side effects'])}.")
        report.expect("medication", generic, status="stopped")

    report.add("")
    bp = f"{rng.randint(110, 165)}/{rng.randint(70, 100)}"
    report.add(f"VITALS: BP {bp} mmHg, Pulse {rng.randint(64, 104)} /min, Temp 98.{rng.randint(2, 9)} F")
    report.add(f"PLAN: Review in {rng.choice(['two weeks', 'one month', '6 weeks'])}. Continue current treatment.")
    report.add("SYNTHETIC TEST REPORT - NOT REAL PATIENT DATA")
    return report


def lab(rng: random.Random, day: date, panel: list[tuple], repeat: bool) -> Report:
    report = Report("lab", day)
    report.add("Example Diagnostics Laboratory")
    report.add("LABORATORY REPORT")
    report.add(f"Collected: {day:%d-%b-%Y} 09:30 AM | Reported: {day:%d-%b-%Y} 03:15 PM")
    report.add("Test | Result | Unit | Reference Range | Flag")
    rows = list(panel)
    if repeat:
        rows.append(rng.choice(panel))  # a repeated test: a second reading of the same test
    for printed, name, unit, low, high, decimals in rows:
        value = rng.uniform(low * 0.7 if low else high * 0.4, high * 1.35)
        value_text = fmt(value, decimals)
        flag = "H" if float(value_text) > high else "L" if float(value_text) < low else ""
        reference = f"{fmt(low, decimals)} - {fmt(high, decimals)}" if low else f"< {fmt(high, decimals)}"
        report.add(" | ".join(p for p in [printed, value_text, unit, reference, flag] if p))
        report.expect("test_result", name, value=value_text, unit=unit, report_flag=flag or None)
    report.add("Comments: Results flagged H or L are outside the reference range.")
    report.add("SYNTHETIC TEST REPORT - NOT REAL PATIENT DATA")
    return report


def patient(rng: random.Random, number: int) -> tuple[dict, list[Report]]:
    conditions = rng.sample(CONDITIONS, rng.randint(2, 3))
    names = [c[1] for c in conditions]
    conditions = [c for i, c in enumerate(conditions) if c[1] not in names[:i]]  # one mention per condition
    medications = rng.sample(MEDICATIONS, rng.randint(3, 5))
    remaining = [m for m in MEDICATIONS if m[1] not in {x[1] for x in medications}]
    profile = {
        "id": f"icse-p{number:02d}",
        "conditions": conditions,
        "unknown_condition": rng.choice(UNKNOWN_CONDITIONS),
        "allergies": rng.sample(ALLERGIES, rng.randint(1, 2)) if rng.random() < 0.6 else [],
        "medications": medications,
        "stopped": rng.choice(remaining) if rng.random() < 0.7 else None,
        "unknown_prescribed": rng.choice(UNKNOWN_PRESCRIBED),
        "unknown_free_text": rng.choice(UNKNOWN_FREE_TEXT),
    }
    # An allergy must not also be a current medicine.
    allergy_names = {a[1] for a in profile["allergies"]}
    profile["medications"] = [m for m in medications if m[1] not in allergy_names]

    start = date(2026, 1, 5) + timedelta(days=rng.randint(0, 60))
    reports = [
        lab(rng, start, rng.sample(LABS, 6), repeat=False),
        note(rng, profile, start + timedelta(days=rng.randint(3, 20)), "clinic"),
        lab(rng, start + timedelta(days=rng.randint(60, 120)), rng.sample(LABS, 7), repeat=True),
    ]
    if rng.random() < 0.5:
        reports.append(note(rng, profile, start + timedelta(days=rng.randint(130, 200)), "discharge"))
    return profile, reports


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(exist_ok=True)
    (OUT / "README.txt").write_text(
        "Synthetic patients for the clinical-summary benchmark. NOT REAL PATIENT DATA.\n"
        "Generated by scripts/icse_bench/generate_patients.py.\n",
        encoding="utf-8",
    )
    count = 0
    for number in range(1, 13):
        profile, reports = patient(rng, number)
        folder = OUT / profile["id"]
        folder.mkdir(exist_ok=True)
        manifest = []
        for index, report in enumerate(sorted(reports, key=lambda r: r.day), start=1):
            stem = f"r{index}_{report.kind}"
            (folder / f"{stem}.txt").write_text("\n".join(report.lines) + "\n", encoding="utf-8")
            manifest.append(
                {
                    "file": f"{stem}.txt",
                    "kind": report.kind,
                    "date": report.day.isoformat(),
                    "entities": report.truth,
                    "out_of_knowledge_base": report.out_of_kb,
                }
            )
            count += 1
        (folder / "entities.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {count} reports for 12 synthetic patients to {OUT}")


if __name__ == "__main__":
    main()
