"""Describes the cut-off of the final run after it was chosen, writes results/cutoff_check.csv.

The cut-off itself is chosen in final.py on the validation pairs only (lowest cut-off reaching the target
precision). This script does not choose anything: for every cut-off from the matcher threshold up, it shows
how many links the identifier links (the answer key, never used inside the pipeline) confirm or contradict,
and how many validation pairs are wrongly linked or missed, so the report can describe the trade-off.
Usage: python cutoff_check.py  (after final.py final)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import labels, links  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
FINAL = Path(__file__).resolve().parents[1] / "global_matching_and_test" / "results"


def main():
    key = links()
    chosen = pd.read_csv(FINAL / "cutoff_final.csv").set_index("pair")
    rows = []
    for a in ["wikidata", "deqar"]:
        pair = f"{a}-ror"
        start, cut = float(chosen.at[pair, "matcher_threshold"]), float(chosen.at[pair, "cutoff"])
        cutoffs = [start] + [c / 100 for c in range(5, 100, 5) if c / 100 > start + 1e-9]
        corr = pd.read_csv(FINAL / f"correspondences_{a}_ror_final_before_cutoff.csv")

        # right = it is the ID link, wrong = one of the records has an ID link to another record
        left = dict(key[(a, "ror")])
        right = {y: x for x, y in key[(a, "ror")]}
        corr["key"] = ["right" if left.get(x) == y else "wrong" if x in left or y in right else None
                       for x, y in zip(corr["id1"], corr["id2"])]

        # validation pairs only; -1 if the labelled pair is not linked at all
        score = {(x, y): s for x, y, s in zip(corr["id1"], corr["id2"], corr["score"])}
        val = labels(a, "ror", "validation", "final")
        val_score = [score.get((x, y), -1) for x, y in zip(val["id1"], val["id2"])]
        val_match = val["label"].values

        base = corr[corr["score"] >= start]
        base_right, base_wrong = (base["key"] == "right").sum(), (base["key"] == "wrong").sum()
        for t in cutoffs:
            c = corr[corr["score"] >= t]
            r, w = int((c["key"] == "right").sum()), int((c["key"] == "wrong").sum())
            kept = [s >= t for s in val_score]
            rows.append({
                "pair": pair, "cut-off": round(t, 2), "chosen": abs(t - cut) < 1e-9, "links": len(c),
                "ID key: right": r, "ID key: wrong": w, "ID key: share wrong": round(w / (r + w), 4) if r + w else None,
                "ID key: wrong removed": int(base_wrong - w), "ID key: right removed": int(base_right - r),
                "validation: wrong matches": sum(k and not m for k, m in zip(kept, val_match)),
                "validation: missed matches": sum(m and not k for k, m in zip(kept, val_match)),
            })
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "cutoff_check.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
