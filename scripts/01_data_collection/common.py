"""Helpers used by fetch_wikidata.py, build_ror_education.py and fetch_deqar.py."""
import csv
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
USER_AGENT = "WDI-StudentProject/1.0 (University of Mannheim, Web Data Integration course project)"
SEP = " | "   # separates several values in one CSV field


def clean(text):
    # "|" is our value separator, so it can't be inside a value
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def unique(values):
    """Non-empty values without repeats, in their original order."""
    seen = set()
    out = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"done: {len(rows)} rows written to {path}")
