"""Phase II, step 4: sets the final similarity threshold and writes the final correspondences.

The threshold of the learned matcher was tuned on the gold standard, whose non-matches are
mostly easy (records that are linked to something else). The correspondences that are not
in the gold standard were therefore checked by hand on a sample (data/gold_standard/
manual_check_*.csv, 60 pairs per dataset pair). This script shows, for a range of thresholds,
the precision and recall on the gold standard (test part, after greedy one-to-one matching)
and the share of correct pairs in the hand-checked sample, and then applies the chosen
threshold to all correspondences.

Run (after phase2_final.py): python scripts/phase2_threshold.py
"""
import pandas as pd
from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

from common import DATA, RESULTS
from phase2_final import metrics
from phase2_matching import CACHE, PAIRS

FINAL_THRESHOLD = 0.8
GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


def main():
    rows = []
    for a, b in PAIRS:
        key = f"{a}-{b}"
        feats = pd.read_csv(CACHE / f"features_{a}_{b}.csv", keep_default_na=False)
        test = feats[feats["split"] == "test"]
        allc = pd.read_csv(DATA / "correspondences" / f"all_{a}_{b}.csv")
        manual = pd.read_csv(DATA / "gold_standard" / f"manual_check_{a}_{b}.csv", keep_default_na=False)
        labelled = set(zip(feats["id1"], feats["id2"]))
        for t in GRID:
            result = GreedyOneToOneMatchingAlgorithm(threshold=t).cluster(allc)
            p, r, f = metrics(result, test)
            sample = manual[manual["score"] >= t]
            unl = sum((x, y) not in labelled for x, y in zip(result["id1"], result["id2"]))
            rows.append(dict(pair=key, threshold=t, correspondences=len(result), not_in_gold_standard=unl,
                             test_precision=round(p, 4), test_recall=round(r, 4), test_f1=round(f, 4),
                             manual_sample_pairs=len(sample),
                             manual_sample_precision=round(sample["label"].astype(int).mean(), 3) if len(sample) else None))
            if t == FINAL_THRESHOLD:
                result.to_csv(DATA / "correspondences" / f"corr_{a}_{b}.csv", index=False)
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "threshold_analysis.csv", index=False)
    print(out.to_string())


if __name__ == "__main__":
    main()
