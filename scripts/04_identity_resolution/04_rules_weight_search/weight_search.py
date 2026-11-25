"""Weight search: instead of setting the weights of the "all attributes" rule by hand, try every
combination in steps of 0.2 (252 of them) on the training pairs and keep the one with the best F1. The rules
with the 3 best combinations are then run like the hand-made ones, threshold picked on validation.
Usage: python weight_search.py first_pass | final"""
import sys
from itertools import product
from pathlib import Path

import numpy as np
from PyDI.entitymatching import FeatureExtractor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import THRESHOLDS, labels, run_argument, run_rules

RESULTS = Path(__file__).resolve().parent / "results"
ATTRIBUTES = ["names_best_jaro_winkler", "country", "domain", "city", "year", "geo"]
SHORT = {"names_best_jaro_winkler": "names"}
TOP = 3


def search(a, b, L, R, comps, run):
    train = labels(a, b, "train", run)
    extractor = FeatureExtractor([comps[c] for c in ATTRIBUTES])
    X = extractor.create_features(L, R, train[["id1", "id2"]], "id", labels=train["label"].astype(int))
    S = X[extractor.get_feature_names()].fillna(0).to_numpy(dtype=float)
    y = X["label"].to_numpy().astype(bool)

    found = []   # (training F1, weights), best threshold per combination
    for steps in product(range(6), repeat=len(ATTRIBUTES)):
        if sum(steps) != 5:
            continue
        w = np.array(steps) / 5
        scores = S @ w
        best = 0
        for t in THRESHOLDS:
            pred = scores >= t
            tp, fp, fn = (pred & y).sum(), (pred & ~y).sum(), (~pred & y).sum()
            best = max(best, 2 * tp / (2 * tp + fp + fn))
        found.append((best, steps, w))
    found.sort(key=lambda x: x[:2], reverse=True)

    rules = {}
    for _, _, w in found[:TOP]:
        cols = [c for c, x in zip(ATTRIBUTES, w) if x > 0]
        weights = [round(float(x), 1) for x in w if x > 0]
        name = "searched weights: " + " + ".join(f"{SHORT.get(c, c)} {x}" for c, x in zip(cols, weights))
        rules[name] = (cols, weights)
    return rules


if __name__ == "__main__":
    run = run_argument()
    run_rules(RESULTS, run, lambda a, b, L, R, comps: search(a, b, L, R, comps, run))
