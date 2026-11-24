"""Checks the round 8 cut-off against the ID links and the labelled pairs, writes results/cutoff_check.csv.
Usage: python cutoff_check.py  (after final.py 8)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import labels, links

RESULTS = Path(__file__).resolve().parent / "results"
# the first cut-off is the matcher threshold, so no extra cut
CUTOFFS = {"wikidata": [0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9],
           "deqar": [0.35, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9]}


def main():
    key = links()
    rows = []
    for a, cutoffs in CUTOFFS.items():
        corr = pd.read_csv(RESULTS / f"correspondences_{a}_ror_r8_before_cutoff.csv")

        # right = it is the ID link, wrong = one of the records has an ID link to another record
        left = dict(key[(a, "ror")])
        right = {y: x for x, y in key[(a, "ror")]}
        corr["key"] = ["right" if left.get(x) == y else "wrong" if x in left or y in right else None
                       for x, y in zip(corr["id1"], corr["id2"])]

        # -1 if the labelled pair is not linked at all
        score = {(x, y): s for x, y, s in zip(corr["id1"], corr["id2"], corr["score"])}
        lab = pd.concat([labels(a, "ror", s, 8) for s in ["validation", "test"]], ignore_index=True)
        lab_score = [score.get((x, y), -1) for x, y in zip(lab["id1"], lab["id2"])]
        lab_match = lab["label"].values

        base = corr[corr["score"] >= cutoffs[0]]
        base_right, base_wrong = (base["key"] == "right").sum(), (base["key"] == "wrong").sum()
        for t in cutoffs:
            c = corr[corr["score"] >= t]
            r, w = int((c["key"] == "right").sum()), int((c["key"] == "wrong").sum())
            kept = [s >= t for s in lab_score]
            rows.append({
                "pair": f"{a}-ror", "cut-off": t, "links": len(c),
                "ID key: right": r, "ID key: wrong": w, "ID key: share wrong": round(w / (r + w), 4),
                "ID key: wrong removed": int(base_wrong - w), "ID key: right removed": int(base_right - r),
                "labels: wrong matches": sum(k and not m for k, m in zip(kept, lab_match)),
                "labels: missed matches": sum(m and not k for k, m in zip(kept, lab_match)),
            })
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "cutoff_check.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
