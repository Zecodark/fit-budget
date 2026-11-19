"""AI guardrails: pre-LLM safety keywords, post-LLM banned content, number whitelist (PRD §6.6)."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

SAFETY_KEYWORDS = (
    "hamil",
    "menyusui",
    "diabetes",
    "ginjal",
    "jantung",
    "nyeri dada",
    "pingsan",
    "cedera",
    "patah",
    "anoreksia",
    "bulimia",
    "obat",
    "resep",
    "diagnosis",
)

BANNED_OUTPUT_RE = re.compile(
    r"\b(diagnosis|didiagnosis|meresepkan|resep\s+obat|dosis\s+mg|suplemen\s+wajib|500\s*kkal|puasa\s+ekstrem|"
    r"harga\s+real[- ]?time\s+saat\s+ini\s+adalah)\b",
    re.IGNORECASE,
)

# Strip ISO dates YYYY-MM-DD before scanning numbers so year 2026 isn't flagged unless needed
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Numbers with optional Indonesian thousand dots and/or decimal comma/dot
_NUM_RE = re.compile(r"(?<![A-Za-z_])\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


def matches_safety_keyword(message: str) -> bool:
    text = (message or "").lower()
    return any(kw in text for kw in SAFETY_KEYWORDS)


def has_banned_output(explanation: str) -> bool:
    return bool(BANNED_OUTPUT_RE.search(explanation or ""))


def extract_numbers(text: str) -> list[float]:
    cleaned = _ISO_DATE_RE.sub(" ", text or "")
    out: list[float] = []
    for m in _NUM_RE.finditer(cleaned):
        tok = m.group(0)
        # Indonesian thousands format like 45.000 or 161.700,5
        if re.match(r"^\d{1,3}(\.\d{3})+(,\d+)?$", tok):
            norm = tok.replace(".", "").replace(",", ".")
        elif "," in tok:
            norm = tok.replace(",", ".")
        else:
            norm = tok
        try:
            out.append(float(norm))
        except ValueError:
            continue
    return out


def check_number_whitelist(explanation: str, facts_numbers: list[float | int]) -> bool:
    allowed: set[float] = set()
    for n in facts_numbers:
        f = float(n)
        allowed.add(round(f, 2))
        allowed.add(round(f, 1))
        allowed.add(float(Decimal(str(f)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    for val in extract_numbers(explanation):
        # Integers 0..31 (dates, counts) are exempt per PRD §6.6 #1
        if val == int(val) and 0 <= int(val) <= 31:
            continue
        if (
            round(val, 2) not in allowed
            and round(val, 1) not in allowed
            and any(abs(val - a) <= 0.15 for a in allowed) is False
        ):
            return False
    return True

