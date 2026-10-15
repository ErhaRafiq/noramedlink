"""Rebuild table rows from OCR text boxes, keeping each cell's OCR score.

RapidOCR returns one box per text cell, roughly top to bottom. Joining them one per line breaks
table rows apart, and on a tilted page a row's value comes out before its name. Here the boxes are
put back into rows (benchmarked in scripts/ocr_bench: 0 wrong numbers on the synthetic scans):

1. Estimate the page tilt from the top edges of wide boxes (weighted median).
2. Straighten the box centres by that angle.
3. Group boxes whose straightened centres are within half a text height into one row, and order
   each row left to right.

The text is never changed: a number OCR is unsure of stays as read, and its score is kept, so the
reader can mark that value "check against the original report" instead of trusting it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import median

NUMBER = re.compile(r"\d")
# A printed reference range ("12 - 17.5", "< 200"): the rules never read it as a value.
RANGE_CELL = re.compile(r"^\s*(?:[<>]\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?)\s*$")
UNCERTAIN_BELOW = 0.90  # a cell with a number scored below this is "check against the original report"
MIN_TEXT_SCORE = 0.5  # boxes without a digit scored below this are logos and stamps: dropped

# The detector also "reads" logos and stamps; keep only characters a report in English uses.
_UNEXPECTED_CHARS = re.compile(r"[^\x20-\x7E°±µ×μ–—‘’“”]")


@dataclass
class Box:
    text: str
    score: float
    cx: float
    cy: float
    width: float
    height: float
    angle: float  # radians, of the top edge


def to_boxes(result) -> list[Box]:
    """Boxes from [(4 corner points, text, score), ...]. Text is cleaned; a box with a digit is
    always kept (dropping it would let the reader take the next number, e.g. a reference range)."""
    boxes = []
    for points, text, score in result or []:
        cleaned = " ".join(_UNEXPECTED_CHARS.sub("", str(text)).split())
        if not cleaned or (float(score) < MIN_TEXT_SCORE and not NUMBER.search(cleaned)):
            continue
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = [tuple(p) for p in points[:4]]
        width = math.hypot(x1 - x0, y1 - y0)
        height = (math.hypot(x3 - x0, y3 - y0) + math.hypot(x2 - x1, y2 - y1)) / 2
        boxes.append(
            Box(
                text=cleaned,
                score=float(score),
                cx=(x0 + x1 + x2 + x3) / 4,
                cy=(y0 + y1 + y2 + y3) / 4,
                width=width,
                height=max(height, 1.0),
                angle=math.atan2(y1 - y0, x1 - x0),
            )
        )
    return boxes


def page_skew(boxes: list[Box]) -> float:
    """Weighted median of the top-edge angles of wide boxes (short boxes give noisy angles)."""
    weighted = sorted((b.angle, b.width) for b in boxes if b.width > 2 * b.height)
    if not weighted:
        return 0.0
    half = sum(w for _, w in weighted) / 2
    running = 0.0
    for angle, w in weighted:
        running += w
        if running >= half:
            return angle
    return weighted[-1][0]


def group_rows(boxes: list[Box]) -> list[list[Box]]:
    if not boxes:
        return []
    skew = page_skew(boxes)
    sin, cos = math.sin(-skew), math.cos(-skew)
    straight = sorted(((b.cx * sin + b.cy * cos, b.cx * cos - b.cy * sin, b) for b in boxes), key=lambda t: t[0])
    tolerance = 0.5 * median(b.height for b in boxes)
    grouped: list[list[tuple[float, float, Box]]] = []
    for item in straight:
        if grouped and abs(item[0] - sum(y for y, _, _ in grouped[-1]) / len(grouped[-1])) <= tolerance:
            grouped[-1].append(item)
        else:
            grouped.append([item])
    return [[b for _, _, b in sorted(group, key=lambda t: t[1])] for group in grouped]


def rebuild(result, page: int = 1) -> list[dict]:
    """Rows as {"page", "text", "cells": [{"text", "score"}]}; the row text is its cells joined."""
    return [
        {
            "page": page,
            "text": " ".join(b.text for b in row),
            "cells": [{"text": b.text, "score": round(b.score, 4)} for b in row],
        }
        for row in group_rows(to_boxes(result))
    ]


def uncertain_values(text: str, rows: list[dict], below: float = UNCERTAIN_BELOW) -> list[dict]:
    """Numbers OCR was unsure of that are still in the text as OCR read them.

    A row the patient has since edited no longer appears in the text, so its numbers count as
    entered by the patient and are not listed.
    """
    from services.report_text import clean_ocr_text  # the cleaning the stored text went through

    lines = set(clean_ocr_text(text).splitlines())
    found = []
    for row in rows or []:
        if clean_ocr_text(row["text"]) not in lines:
            continue
        for cell in row["cells"]:
            if cell["score"] < below and NUMBER.search(cell["text"]) and not RANGE_CELL.match(cell["text"]):
                found.append(
                    {"page": row.get("page"), "line": row["text"], "text": cell["text"], "score": cell["score"]}
                )
    return found
