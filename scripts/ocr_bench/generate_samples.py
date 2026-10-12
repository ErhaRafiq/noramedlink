"""Generate synthetic lab reports with exact ground truth for the OCR benchmark.

Run with the benchmark virtualenv (reportlab, pypdfium2, pillow, numpy):

    .venv-ocr-bench\\Scripts\\python.exe scripts\\ocr_bench\\generate_samples.py

Writes to ocr_samples/ (git-ignored), for each report <base>:
    <base>.txt             ground-truth text (reading order; table cells joined by " | ";
                           "=== page 2 ===" between pages)
    <base>.values.csv      key values: test,value,unit (value exactly as printed)
    <base>__digital.pdf    PDF with a real text layer
    <base>__scan.pdf       image-only "scan": rasterised, slight rotation, noise, blur, JPEG
    <base>__scan_hard.pdf  harsher scan (lower resolution, more rotation and noise), some reports
Phone photos go next to them as <base>__photo1.jpg, <base>__photo2.jpg, ...

Everything is invented: names, IDs, labs, doctors and values. Every page says
"SYNTHETIC TEST REPORT - NOT REAL PATIENT DATA". The output is deterministic (fixed seed).
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ocr_samples"
MARK = "SYNTHETIC TEST REPORT - NOT REAL PATIENT DATA"


@dataclass
class Row:
    test: str
    value: str  # exactly as printed
    unit: str
    ref: str
    flag: str = ""


@dataclass
class Panel:
    title: str
    rows: list[Row]


@dataclass
class Report:
    base: str
    lab: str
    address: str
    patient: str
    age_sex: str
    mrn: str
    doctor: str
    collected: str
    reported: str
    pages: list[list[Panel]]
    font: str = "Helvetica"
    size: float = 10
    grid: bool = True
    comment: str = "Results flagged H or L are outside the reference range. Correlate clinically."
    hard_scan: bool = False
    extra: dict = field(default_factory=dict)


def flag(value: float, low: float | None, high: float | None) -> str:
    if low is not None and value < low:
        return "L"
    if high is not None and value > high:
        return "H"
    return ""


def row(test: str, value: float, unit: str, low: float | None, high: float | None, decimals: int = 1, fmt=None) -> Row:
    printed = fmt(value) if fmt else f"{value:.{decimals}f}"
    if low is not None and high is not None:
        ref = f"{low:g} - {high:g}"
    elif high is not None:
        ref = f"< {high:g}"
    else:
        ref = f"> {low:g}"
    return Row(test, printed, unit, ref, flag(value, low, high))


def lakh(value: float) -> str:
    """Indian/Pakistani digit grouping: 250000 -> 2,50,000."""
    digits = str(round(value))
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


# --- panels -------------------------------------------------------------------------------


def cbc(r: random.Random, anaemic=False, counts_per_ul=False, hb_g_l=False) -> Panel:
    hb = r.uniform(8.6, 10.9) if anaemic else r.uniform(12.4, 15.8)
    wbc = r.uniform(3.2, 13.8)
    plt = r.uniform(110, 470)
    rows = [
        row("Hemoglobin", hb * 10, "g/L", 120, 175, 0) if hb_g_l else row("Hemoglobin", hb, "g/dL", 12.0, 17.5),
        row("RBC Count", r.uniform(3.6, 5.8), "x10^12/L", 4.0, 5.9, 2),
        row("Hematocrit (HCT)", hb * 3, "%", 36, 52, 1),
        row("MCV", r.uniform(70, 98), "fL", 80, 100, 1),
        row("MCH", r.uniform(22, 33), "pg", 27, 33, 1),
    ]
    if counts_per_ul:
        # Labs round counts: WBC to tens, platelets to thousands.
        rows.append(row("WBC Count", round(wbc * 100) * 10, "/uL", 4000, 11000, fmt=lakh))
        rows.append(row("Platelet Count", round(plt) * 1000, "/uL", 150000, 450000, fmt=lakh))
    else:
        rows.append(row("WBC Count", wbc, "x10^9/L", 4.0, 11.0, 1))
        rows.append(row("Platelet Count", plt, "x10^9/L", 150, 450, 0))
    rows += [
        row("Neutrophils", r.uniform(40, 78), "%", 40, 75, 0),
        row("Lymphocytes", r.uniform(18, 45), "%", 20, 45, 0),
    ]
    return Panel("COMPLETE BLOOD COUNT (CBC)", rows)


def lipid(r: random.Random, si=False) -> Panel:
    chol, ldl, hdl, tg = r.uniform(150, 260), r.uniform(90, 190), r.uniform(32, 62), r.uniform(90, 260)
    if si:
        return Panel(
            "LIPID PROFILE",
            [
                row("Total Cholesterol", chol / 38.67, "mmol/L", None, 5.2, 2),
                row("LDL Cholesterol", ldl / 38.67, "mmol/L", None, 3.4, 2),
                row("HDL Cholesterol", hdl / 38.67, "mmol/L", 1.0, None, 2),
                row("Triglycerides", tg / 88.57, "mmol/L", None, 1.7, 2),
            ],
        )
    return Panel(
        "LIPID PROFILE",
        [
            row("Total Cholesterol", chol, "mg/dL", None, 200, 0),
            row("LDL Cholesterol", ldl, "mg/dL", None, 130, 0),
            row("HDL Cholesterol", hdl, "mg/dL", 40, None, 0),
            row("Triglycerides", tg, "mg/dL", None, 150, 0),
            row("VLDL Cholesterol", tg / 5, "mg/dL", None, 30, 0),
        ],
    )


def glucose(r: random.Random, diabetic=False, si=False) -> Panel:
    fbs = r.uniform(128, 190) if diabetic else r.uniform(72, 104)
    rbs = fbs + r.uniform(25, 80)
    a1c = r.uniform(7.0, 9.4) if diabetic else r.uniform(4.8, 5.9)
    if si:
        return Panel(
            "GLUCOSE",
            [
                row("Fasting Blood Sugar", fbs / 18, "mmol/L", 3.9, 5.6, 1),
                row("Random Blood Sugar", rbs / 18, "mmol/L", None, 7.8, 1),
                row("HbA1c", a1c, "%", None, 5.7, 1),
            ],
        )
    return Panel(
        "GLUCOSE",
        [
            row("Fasting Blood Sugar", fbs, "mg/dL", 70, 100, 0),
            row("Random Blood Sugar", rbs, "mg/dL", None, 140, 0),
            row("HbA1c", a1c, "%", None, 5.7, 1),
        ],
    )


def kidney(r: random.Random, impaired=False, si=False) -> Panel:
    creat = r.uniform(1.5, 2.6) if impaired else r.uniform(0.6, 1.2)
    urea = r.uniform(48, 85) if impaired else r.uniform(18, 40)
    egfr = r.uniform(28, 55) if impaired else r.uniform(75, 115)
    rows = (
        [row("Urea", urea / 6.006, "mmol/L", 2.5, 7.5, 1), row("Creatinine", creat * 88.4, "umol/L", 53, 115, 0)]
        if si
        else [row("Urea", urea, "mg/dL", 15, 45, 0), row("Creatinine", creat, "mg/dL", 0.6, 1.3, 2)]
    )
    rows += [
        row("eGFR", egfr, "mL/min/1.73m2", 60, None, 0),
        row("Uric Acid", r.uniform(3.2, 8.4), "mg/dL", 3.4, 7.0, 1),
        row("Sodium", r.uniform(132, 146), "mmol/L", 135, 145, 0),
        row("Potassium", r.uniform(3.3, 5.6), "mmol/L", 3.5, 5.1, 1),
    ]
    return Panel("KIDNEY FUNCTION TESTS", rows)


def liver(r: random.Random) -> Panel:
    return Panel(
        "LIVER FUNCTION TESTS",
        [
            row("Total Bilirubin", r.uniform(0.4, 2.1), "mg/dL", None, 1.2, 1),
            row("ALT (SGPT)", r.uniform(14, 95), "U/L", None, 56, 0),
            row("AST (SGOT)", r.uniform(12, 70), "U/L", None, 40, 0),
            row("Alkaline Phosphatase", r.uniform(45, 160), "U/L", 44, 147, 0),
            row("Albumin", r.uniform(3.2, 5.0), "g/dL", 3.5, 5.0, 1),
        ],
    )


# --- reports ------------------------------------------------------------------------------

FIRST = [
    ("Ayesha", "F"),
    ("Bilal", "M"),
    ("Fatima", "F"),
    ("Hamza", "M"),
    ("Iqra", "F"),
    ("Junaid", "M"),
    ("Kiran", "F"),
    ("Mahnoor", "F"),
    ("Omer", "M"),
    ("Rabia", "F"),
    ("Saad", "M"),
    ("Zoya", "F"),
]
LAST = ["Testani", "Samplewala", "Fakhri", "Demoji", "Mockari", "Exampli", "Placeholdar", "Synthani"]
LABS = [
    ("Example Diagnostics Laboratory", "12-B Sample Road, Sector Z-9, Islamabad"),
    ("Demo Clinical Lab & Imaging", "45 Test Avenue, Block X, Lahore"),
    ("Placeholder Pathology Centre", "7 Mock Street, Area Q, Karachi"),
]


def make_reports() -> list[Report]:
    r = random.Random(20261012)

    def person(i: int):
        lab, address = LABS[i % len(LABS)]
        first, sex = FIRST[i % len(FIRST)]
        day = r.randint(1, 26)
        return {
            "lab": lab,
            "address": address,
            "patient": f"{first} {r.choice(LAST)}",
            "age_sex": f"{r.randint(19, 78)} Y / {sex}",
            "mrn": f"SYN-{r.randint(10000, 99999)}-{r.randint(10, 99)}",
            "doctor": f"Dr. {r.choice(['Sample', 'Example', 'Demo'])} {r.choice(['Physician', 'Consultant'])}",
            "collected": f"{day:02d}-Sep-2026 {r.randint(7, 11):02d}:{r.choice(['05', '20', '40'])} AM",
            # Reported the same day or up to two days after collection.
            "reported": f"{day + r.randint(0, 2):02d}-Sep-2026 {r.randint(1, 6):02d}:{r.choice(['10', '35', '55'])} PM",
        }

    specs = [
        ("lab01_cbc", [[cbc(r, anaemic=True)]], {}),
        ("lab02_lipid", [[lipid(r)]], {"font": "Times-Roman", "grid": False}),
        ("lab03_glucose", [[glucose(r, diabetic=True)]], {}),
        ("lab04_kidney", [[kidney(r, impaired=True)]], {"font": "Helvetica", "size": 10.5}),
        ("lab05_kidney_si", [[kidney(r, si=True)]], {"font": "Courier", "size": 9.5, "grid": False}),
        ("lab06_cbc_lakh", [[cbc(r, counts_per_ul=True)]], {"hard_scan": True}),
        ("lab07_liver", [[liver(r)]], {"font": "Times-Roman"}),
        ("lab08_combined_2pages", [[cbc(r), lipid(r)], [glucose(r, diabetic=True), kidney(r)]], {"size": 9.5}),
        ("lab09_lipid_si", [[lipid(r, si=True), glucose(r, si=True)]], {"grid": False, "hard_scan": True}),
        ("lab10_small_font", [[cbc(r), kidney(r), liver(r)]], {"size": 7.5, "hard_scan": True}),
        ("lab11_cbc_g_per_l", [[cbc(r, anaemic=True, hb_g_l=True)]], {"font": "Courier", "size": 9.5}),
        ("lab12_glucose_kidney", [[glucose(r), kidney(r, impaired=True)]], {"hard_scan": True}),
    ]
    return [Report(base=base, pages=pages, **person(i), **opts) for i, (base, pages, opts) in enumerate(specs)]


# --- ground truth ---------------------------------------------------------------------------

HEADER = ["Test", "Result", "Unit", "Reference Range", "Flag"]


def cells(rw: Row) -> list[str]:
    return [rw.test, rw.value, rw.unit, rw.ref] + ([rw.flag] if rw.flag else [])


def header_lines(rep: Report, page: int, total: int) -> list[str]:
    return [
        rep.lab,
        rep.address,
        "LABORATORY REPORT",
        f"Patient Name: {rep.patient} | Age/Sex: {rep.age_sex}",
        f"MR No: {rep.mrn} | Referred By: {rep.doctor}",
        f"Collected: {rep.collected} | Reported: {rep.reported}",
    ]


def footer_lines(rep: Report, page: int, total: int, last: bool) -> list[str]:
    lines = [f"Comments: {rep.comment}"] if last else []
    return [*lines, MARK, f"Page {page} of {total}"]


def ground_truth(rep: Report) -> str:
    out: list[str] = []
    total = len(rep.pages)
    for p, panels in enumerate(rep.pages, start=1):
        if p > 1:
            out.append(f"=== page {p} ===")
        out += header_lines(rep, p, total)
        for panel in panels:
            out.append(panel.title)
            out.append(" | ".join(HEADER))
            out += [" | ".join(cells(rw)) for rw in panel.rows]
        out += footer_lines(rep, p, total, p == total)
    return "\n".join(out) + "\n"


# --- PDF rendering ----------------------------------------------------------------------------


def bold(font: str) -> str:
    return {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}[font]


def draw_pdf(rep: Report, path: Path) -> None:
    width, height = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"{rep.base} (synthetic)")
    total = len(rep.pages)
    size = rep.size
    lead = size * 1.65
    cols = [50, 250, 320, 420, 520]  # Test, Result, Unit, Reference Range, Flag
    for p, panels in enumerate(rep.pages, start=1):
        y = height - 55
        hdr = header_lines(rep, p, total)
        c.setFont(bold(rep.font), size + 5)
        c.drawString(50, y, hdr[0])
        y -= size + 8
        c.setFont(rep.font, size)
        c.drawString(50, y, hdr[1])
        y -= lead * 1.4
        c.setFont(bold(rep.font), size + 2)
        c.drawCentredString(width / 2, y, hdr[2])
        y -= lead * 1.3
        c.setFont(rep.font, size)
        for line in hdr[3:]:
            left, right = line.split(" | ")
            c.drawString(50, y, left)
            c.drawString(320, y, right)
            y -= lead
        y -= lead * 0.6
        for panel in panels:
            c.setFont(bold(rep.font), size + 1)
            c.drawString(50, y, panel.title)
            y -= lead * 1.2
            c.setFont(bold(rep.font), size)
            for x, text in zip(cols, HEADER, strict=True):
                c.drawString(x, y, text)
            if rep.grid:
                c.line(45, y - 4, 560, y - 4)
            y -= lead
            c.setFont(rep.font, size)
            for rw in panel.rows:
                values = [rw.test, rw.value, rw.unit, rw.ref, rw.flag]
                for x, text in zip(cols, values, strict=True):
                    if text:
                        if x == cols[1] and rw.flag:
                            c.setFont(bold(rep.font), size)
                        c.drawString(x, y, text)
                        c.setFont(rep.font, size)
                if rep.grid:
                    c.setLineWidth(0.3)
                    c.line(45, y - 4, 560, y - 4)
                    c.setLineWidth(1)
                y -= lead
            y -= lead * 0.8
        footer = footer_lines(rep, p, total, p == total)
        fy = 70
        c.setFont(rep.font, size - 0.5)
        if p == total:
            c.drawString(50, fy + 28, footer[0])
        c.setFont(bold(rep.font), size - 1)
        c.drawCentredString(width / 2, fy, MARK)
        c.setFont(rep.font, size - 1)
        c.drawRightString(width - 50, fy - 18, footer[-1])
        c.showPage()
    c.save()


def scan(digital: Path, path: Path, rng: np.random.Generator, hard: bool) -> None:
    """Rasterise each page and degrade it like a cheap office scan."""
    dpi = 150 if hard else 200
    pages: list[Image.Image] = []
    pdf = pdfium.PdfDocument(str(digital))
    for index in range(len(pdf)):
        image = pdf[index].render(scale=dpi / 72).to_pil().convert("L")
        angle = float(rng.uniform(1.5, 3.0) if hard else rng.uniform(0.3, 1.2)) * float(rng.choice([-1, 1]))
        image = image.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=255)
        image = image.filter(ImageFilter.GaussianBlur(0.9 if hard else 0.5))
        pixels = np.asarray(image, dtype=np.float32)
        pixels = pixels * (0.86 if hard else 0.94) + 12  # greyer paper, weaker ink contrast
        pixels += rng.normal(0, 14 if hard else 7, pixels.shape)
        image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=45 if hard else 70)
        pages.append(Image.open(buffer).convert("L"))
    pdf.close()
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=dpi)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(20261012)
    reports = make_reports()
    for rep in reports:
        (OUT / f"{rep.base}.txt").write_text(ground_truth(rep), encoding="utf-8")
        with (OUT / f"{rep.base}.values.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["test", "value", "unit"])
            for panels in rep.pages:
                for panel in panels:
                    writer.writerows([rw.test, rw.value, rw.unit] for rw in panel.rows)
        digital = OUT / f"{rep.base}__digital.pdf"
        draw_pdf(rep, digital)
        scan(digital, OUT / f"{rep.base}__scan.pdf", rng, hard=False)
        if rep.hard_scan:
            scan(digital, OUT / f"{rep.base}__scan_hard.pdf", rng, hard=True)
    (OUT / "README.txt").write_text(README, encoding="utf-8")
    print(f"{len(reports)} synthetic reports written to {OUT}")


README = """Synthetic OCR benchmark samples (generated by scripts/ocr_bench/generate_samples.py).
Everything here is invented; no real patient data. This folder is git-ignored.

Per report <base>:
  <base>.txt             ground truth text
  <base>.values.csv      key values (test,value,unit)
  <base>__digital.pdf    digital PDF (real text layer)
  <base>__scan.pdf       scanned-style image PDF
  <base>__scan_hard.pdf  harsher scan (some reports only)

Phone photos: save as <base>__photo1.jpg, <base>__photo2.jpg, ... (same base name).
"""


if __name__ == "__main__":
    main()
