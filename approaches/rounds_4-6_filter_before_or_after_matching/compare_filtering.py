"""Scores rounds 3-6 on the same test labels, once on all test pairs and once only on pairs whose records
were not removed, and writes results/filtering_effect.csv. Run with: python compare_filtering.py
(after final.py of these rounds, missing rounds are skipped)"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import LABELS, PAIRS, non_universities


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
    return dict(P=round(p, 3), R=round(r, 3), F1=f1, TP=tp, FP=fp, FN=fn, pairs=len(labels))


def main():
    gone = non_universities()
    rows = []
    for a, b in PAIRS:
        test = pd.read_csv(LABELS / "round2" / f"{a}_{b}_test.csv")
        kept = test[~test["id1"].isin(gone) & ~test["id2"].isin(gone)]
        for round_ in [3, 4, 5, 6]:
            path = HERE / "results" / f"correspondences_{a}_{b}_r{round_}.csv"
            if not path.exists():
                continue
            corr = pd.read_csv(path)
            # how many links of this round touch a record the filter removes
            with_removed = int((corr["id1"].isin(gone) | corr["id2"].isin(gone)).sum())
            for name, labels in [("all test pairs", test), ("without removed records", kept)]:
                rows.append(dict(pair=f"{a}-{b}", round=round_, labels=name, **score(corr, labels),
                                 correspondences=len(corr), with_removed_record=with_removed))
    out = pd.DataFrame(rows)
    out.to_csv(HERE / "results" / "filtering_effect.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
