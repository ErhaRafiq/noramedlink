"""Checks on AI-written text before a patient sees it.

An AI summary may only use values that appear in the report text (AGENTS.md section 6): a
number the model made up, or copied wrongly, must never reach the patient. Any number in the
summary that is not in the source text rejects the summary, and the rule-based one is used.
"""

import re

_NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{2,3})*(?:\.\d+)?")


def _numbers(text: str) -> set[float]:
    return {float(token.replace(",", "")) for token in _NUMBER.findall(text or "")}


def numbers_not_in_source(summary: str, source: str) -> list[str]:
    """Numbers in `summary` that do not appear in `source`.

    Whole numbers up to 10 are ignored: they are list numbering, counts ("2 values") or
    durations in plain-language text, not lab values. Every decimal and every larger number
    must come from the report.
    """
    known = _numbers(source)
    missing = []
    for token in _NUMBER.findall(summary or ""):
        value = float(token.replace(",", ""))
        if "." not in token and value <= 10:
            continue
        if value not in known:
            missing.append(token)
    return missing
