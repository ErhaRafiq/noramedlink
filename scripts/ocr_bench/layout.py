"""Rebuild table rows from OCR text boxes (candidate for services/local_ocr.py).

RapidOCR returns one box per text cell, roughly top to bottom. Joining them one per line
breaks table rows apart, and on a tilted page a row's value cells come out before its name
("Hemoglobin" then the next row's number). Here the boxes are put back into rows:

1. Estimate the page tilt from the top edges of wide boxes (weighted median).
2. Straighten the box centres by that angle.
3. Group boxes whose straightened centres are within half a text height into one row, and
   order each row left to right.

Optionally, numbers in a box OCR is unsure of are replaced by "[?]" so they read as
unreadable instead of being passed on (a missing value is safer than a wrong one).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import median

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
UNREADABLE = "[?]"


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
    boxes = []
    for points, text, score in result or []:
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = points[:4]
        width = math.hypot(x1 - x0, y1 - y0)
        height = (math.hypot(x3 - x0, y3 - y0) + math.hypot(x2 - x1, y2 - y1)) / 2
        boxes.append(
            Box(
                text=text,
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


def rows(boxes: list[Box]) -> list[list[Box]]:
    if not boxes:
        return []
    skew = page_skew(boxes)
    sin, cos = math.sin(-skew), math.cos(-skew)
    straight = sorted(((b.cx * sin + b.cy * cos, b.cx * cos - b.cy * sin, b) for b in boxes), key=lambda t: t[0])
    tolerance = 0.5 * median(b.height for b in boxes)
    grouped: list[list[tuple[float, float, Box]]] = []
    for item in straight:
        if grouped and abs(item[0] - mean_y(grouped[-1])) <= tolerance:
            grouped[-1].append(item)
        else:
            grouped.append([item])
    return [[b for _, _, b in sorted(group, key=lambda t: t[1])] for group in grouped]


def mean_y(group: list[tuple[float, float, Box]]) -> float:
    return sum(y for y, _, _ in group) / len(group)


def cell_text(box: Box, flag_below: float | None) -> str:
    if flag_below is not None and box.score < flag_below and NUMBER.search(box.text):
        return NUMBER.sub(UNREADABLE, box.text)
    return box.text


def rebuild(result, flag_below: float | None = None) -> tuple[list[str], list[float]]:
    """Text lines (one per table row) and the box scores, from a RapidOCR result."""
    boxes = to_boxes(result)
    lines = [" ".join(cell_text(b, flag_below) for b in row) for row in rows(boxes)]
    return lines, [b.score for b in boxes]
