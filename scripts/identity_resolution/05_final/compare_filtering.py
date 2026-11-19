"""Effect of the additional filtering: round 3 (all records), round 4 (non-universities removed before
matching), round 5 (removed after matching), round 6 (duplicates removed before matching, non-universities
after). Usage: python compare_filtering.py      (after final.py of these rounds; missing rounds are skipped)

Both rounds are scored on the same test labels, twice:
  all test pairs          - pairs with a removed record count against round 4 (it cannot find them)
  without removed records - only pairs whose two records are still in the filtered data
Also counts how many final correspondences of each round contain a record the filter removes.
Writes results/filtering_effect.csv.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))
from common import LABELS, PAIRS, non_universities


def score(corr, labels):
    pred = set(zip(corr["id1"], corr["id2"]))
    hit = [(a, b) in pred for a, b in zip(labels["id1"], labels["id2"])]
    lab = labels["label"].astype(str).str.lower().isin(["true", "1"]).tolist()
    tp = sum(h and l for h, l in zip(hit, lab))
    fp = sum(h and not l for h, l in zip(hit, lab))
    fn = sum(l and not h for h, l in zip(hit, lab))
    p, r = tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
    return dict(P=round(p, 3), R=round(r, 3), F1=round(2 * p * r / (p + r), 3) if p + r else 0,
                TP=tp, FP=fp, FN=fn, pairs=len(labels))


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
            with_removed = int((corr["id1"].isin(gone) | corr["id2"].isin(gone)).sum())
            for name, labels in [("all test pairs", test), ("without removed records", kept)]:
                rows.append(dict(pair=f"{a}-{b}", round=round_, labels=name, **score(corr, labels),
                                 correspondences=len(corr), with_removed_record=with_removed))
    out = pd.DataFrame(rows)
    out.to_csv(HERE / "results" / "filtering_effect.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
