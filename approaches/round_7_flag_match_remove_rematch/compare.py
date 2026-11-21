"""Compares run 1 (round 3, all records) with run 2 (round 7, flag-filtered records) on the test pairs
whose records were not removed, and writes results/compare.csv. Run with: python compare.py
(after flag_filter.py and final.py 7)"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import LABELS, PAIRS

FINAL = HERE.parent / "05_final" / "results"


def score(corr, labels):
    pred = set(zip(corr["id1"], corr["id2"]))
    hit = [(a, b) in pred for a, b in zip(labels["id1"], labels["id2"])]
    lab = labels["label"].astype(str).str.lower().isin(["true", "1"]).tolist()
    tp = sum(h and l for h, l in zip(hit, lab))
    fp = sum(h and not l for h, l in zip(hit, lab))
    fn = sum(l and not h for h, l in zip(hit, lab))
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = round(2 * p * r / (p + r), 3) if p + r else 0
    return dict(P=round(p, 3), R=round(r, 3), F1=f1, TP=tp, FP=fp, FN=fn, test_pairs=len(labels))


def main():
    gone = set(pd.read_csv(HERE / "results" / "removed.csv")["id"])
    rows = []
    for a, b in PAIRS:
        test = pd.read_csv(LABELS / "round2" / f"{a}_{b}_test.csv")
        test = test[~test["id1"].isin(gone) & ~test["id2"].isin(gone)]
        run1 = pd.read_csv(FINAL / f"correspondences_{a}_{b}_r3.csv")
        run1_after = run1[~run1["id1"].isin(gone) & ~run1["id2"].isin(gone)]
        run2 = pd.read_csv(FINAL / f"correspondences_{a}_{b}_r7.csv")

        for name, corr in [("run 1, all records", run1),
                           ("run 1, removed records dropped after matching", run1_after),
                           ("run 2, matched again without removed records", run2)]:
            rows.append(dict(pair=f"{a}-{b}", version=name, **score(corr, test), links=len(corr)))

        before = set(zip(run1_after["id1"], run1_after["id2"]))
        after = set(zip(run2["id1"], run2["id2"]))
        print(f"{a}-{b}: links of kept records only in run 1: {len(before - after):,}, "
              f"only in run 2: {len(after - before):,}, in both: {len(before & after):,}")

    out = pd.DataFrame(rows)
    out.to_csv(HERE / "results" / "compare.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
