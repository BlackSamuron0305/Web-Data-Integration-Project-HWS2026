"""Summary of the hand check of removed records (data/<source>/filtered/hand_check_removed.csv).

50 removed records per source, drawn at random (random_state 2026) from
data/<source>/filtered/removed.csv. Each row has a pre-check (precheck: removal_correct,
real_university or unsure, with a note) and the verdict of the person who checked it
(hand_verdict, same values, plus hand_note and checked_by). The summary uses the hand verdict
where it is filled in and says how many rows are still unchecked.

Run from this folder: python hand_check_summary.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[3] / "data"
df = pd.concat([pd.read_csv(DATA / s / "filtered" / "hand_check_removed.csv", dtype=str)
                for s in ("wikidata", "ror", "deqar")]).fillna("")
df["verdict"] = df["hand_verdict"].where(df["hand_verdict"] != "", df["precheck"])
rows = []
for source, g in df.groupby("source", sort=False):
    rows.append({
        "source": source,
        "checked": len(g),
        "checked_by_hand": int((g["hand_verdict"] != "").sum()),
        "real_university": int((g["verdict"] == "real_university").sum()),
        "unsure": int((g["verdict"] == "unsure").sum()),
        "removal_correct": int((g["verdict"] == "removal_correct").sum()),
        "hand_disagrees_with_precheck": int(((g["hand_verdict"] != "") & (g["hand_verdict"] != g["precheck"])).sum()),
    })
out = pd.DataFrame(rows)
out["share_real"] = (out["real_university"] / out["checked"]).round(3)
out.to_csv("results/hand_check_summary.csv", index=False)
print(out.to_string(index=False))
print("\nReal universities that were removed:")
print(df[df["verdict"] == "real_university"][["source", "id", "name", "rule", "reason", "precheck_note"]].to_string(index=False))
