"""Abandoned approach: keep a record only if its name contains the word "university".

The simplest possible cleaning rule. It catches every language that spells the word with
"univers" (university, universidad, université, Universität, universitas, universiteit, ...).
The script counts how many records the rule would remove and checks the result against the
AI checks of the final filter (verdict junk / real / unsure per record).

Run from the repo root: python scripts/06_abandoned_approaches/02_filtering/university_word_rule.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    "wikidata": ("wikidata_id", "data/wikidata/original/wikidata_universities.csv"),
    "ror": ("ror_id", "data/ror/original/ror_education.csv"),
    "deqar": ("deqar_id", "data/deqar/original/deqar_institutions.csv"),
}


def keep(name) -> bool:
    return "univers" in str(name).lower()


rows = []
for source, (id_col, path) in SOURCES.items():
    data = pd.read_csv(ROOT / path, dtype=str)
    removed = data[~data["name"].map(keep)]

    checks = pd.read_csv(ROOT / f"scripts/02_filtering/validation/{source}/ai_checks.csv", dtype=str)
    checks = checks.drop_duplicates(id_col, keep="last")  # latest verdict per record
    checked_removed = checks[checks[id_col].isin(removed[id_col])]
    verdicts = checked_removed["verdict"].value_counts()

    rows.append({
        "source": source,
        "records": len(data),
        "removed": len(removed),
        "removed_share": f"{len(removed) / len(data):.0%}",
        "checked_removed": len(checked_removed),
        "of_those_junk": int(verdicts.get("junk", 0)),
        "of_those_real": int(verdicts.get("real", 0)),
        "of_those_unsure": int(verdicts.get("unsure", 0)),
    })

print(pd.DataFrame(rows).to_string(index=False))
