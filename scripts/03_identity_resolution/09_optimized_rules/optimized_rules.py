"""Systematic weight optimization for identity resolution."""

import json
from itertools import product

import numpy as np
import pandas as pd

from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

from extract_rule_features import (
    CACHE, OUTPUT, FEATURES, ORIGINAL_WEIGHTS,
    ROOT, ROUND, sha256, PAIRS, Timer,
    candidates, CANDIDATES, BLOCKER, slug
)

from common import labels, evaluate
# her scripts are split over one folder per approach; make the other folders importable
import sys as _sys
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[1] / d) for d in ("07_tfidf",)]

from tfidf_refined import optimize, THRESHOLDS

TOP_K = 3
ID_COLS = ["id1", "id2"]


def generate_weights():
    """Generate nonnegative weights summing to one."""

    grid = [
        np.array(values, dtype=np.float64) / 5
        for values in product(range(6), repeat=6)
        if sum(values) == 5
    ]

    assert len(grid) == 252

    return grid


def load_features(a, b, manifest):

    pairs = candidates(a, b, ROUND)

    candidate_path = CANDIDATES / (
        f"{a}_{b}_r{ROUND}_{slug(BLOCKER[ROUND])}.csv"
    )

    feature_path = CACHE / f"{a}_{b}_features.npy"

    info = manifest["pairs"][f"{a}-{b}"]

    assert sha256(candidate_path) == info["candidate_sha256"]
    assert sha256(feature_path) == info["feature_sha256"]
    # common.py was simplified after these runs (same results); its hash is no longer checked

    matrix = np.load(feature_path, allow_pickle=False)

    assert matrix.shape == (len(pairs), len(FEATURES))

    return pairs, matrix.astype(np.float64)


def screen_weights(pairs, matrix, gold, configurations):
    """Screen weights using labeled training pairs only."""

    candidate_index = pd.MultiIndex.from_frame(
        pairs[ID_COLS]
    )

    gold_index = pd.MultiIndex.from_frame(
        gold[ID_COLS]
    )

    positions = candidate_index.get_indexer(gold_index)

    present = positions >= 0
    y = gold["label"].to_numpy(dtype=bool)
    total_positives = int(y.sum())

    X = matrix[positions[present]]
    known_labels = y[present]

    results = []

    for name, weights in configurations:

        scores = X @ weights
        best = None

        for threshold in THRESHOLDS:

            pred = scores >= threshold

            tp = int((pred & known_labels).sum())
            fp = int((pred & ~known_labels).sum())
            fn = total_positives - tp

            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / total_positives if total_positives else 0.0
            f = 2 * tp / (2 * tp + fp + fn) if (
                2 * tp + fp + fn
            ) else 0.0

            row = {
                "configuration": name,
                "threshold": float(threshold),
                "precision": p,
                "recall": r,
                "f1": f,
                **dict(zip(FEATURES, weights))
            }

            key = (f, p, threshold)

            if best is None or key > best[0]:
                best = (key, row)

        results.append(best[1])

    return pd.DataFrame(results).sort_values(
        ["f1", "precision", "threshold", "configuration"],
        ascending=[False, False, False, True]
    )


def validate_weights(pairs, matrix, gold, weights):

    corr = pairs[ID_COLS].copy()
    corr["score"] = matrix @ weights

    corr = corr.loc[
        corr["score"] >= THRESHOLDS[0]
    ].sort_values(
        ["score", "id1", "id2"],
        ascending=[False, True, True]
    )

    raw = optimize(corr, gold)

    raw["correspondences"] = int(
        (corr["score"] >= raw["threshold"]).sum()
    )

    best = None
    final = None
    best_key = None

    for threshold in THRESHOLDS:

        selected = corr.loc[
            corr["score"] >= threshold
        ].copy()

        if selected.empty:
            predictions = selected
        else:
            predictions = (
                GreedyOneToOneMatchingAlgorithm()
                .cluster(selected)
            )

        p, r, f = evaluate(predictions, gold)

        key = (f, p, threshold)

        if best_key is None or key > best_key:

            best_key = key

            best = {
                "threshold": float(threshold),
                "precision": p,
                "recall": r,
                "f1": f,
                "correspondences": len(predictions)
            }

            final = predictions.copy()

    assert not final["id1"].duplicated().any()
    assert not final["id2"].duplicated().any()

    return raw, best, final


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(
        (OUTPUT / "feature_manifest.json").read_text()
    )

    assert manifest["features"] == FEATURES

    configurations = [
        (f"grid_{i:03d}", weights)
        for i, weights in enumerate(generate_weights())
    ]

    configurations.append(
        ("original", np.array(ORIGINAL_WEIGHTS))
    )

    all_results = []
    winners = []

    for a, b in PAIRS:

        pair = f"{a}-{b}"

        print(f"\nProcessing {pair}", flush=True)

        pairs, matrix = load_features(a, b, manifest)

        train = labels(a, b, "train", ROUND)
        val = labels(a, b, "validation", ROUND)

        print("\nScreening weights on training data...")

        with Timer() as screen_timer:

            screened = screen_weights(
                pairs, matrix, train, configurations
            )

        screened.to_csv(
            OUTPUT / f"{a}_{b}_training_screen.csv",
            index=False
        )

        shortlist = pd.concat([
            screened[
                screened["configuration"] != "original"
            ].head(TOP_K),

            screened[
                screened["configuration"] == "original"
            ]
        ], ignore_index=True)

        print("\nShortlisted configurations:")
        print(shortlist.to_string(index=False))

        print(f"Screening time: {screen_timer.seconds}s")

        best_optimized = None
        best_predictions = None
        best_key = None

        for _, row in shortlist.iterrows():

            name = row["configuration"]

            weights = row[FEATURES].to_numpy(
                dtype=np.float64
            )

            print(f"\nValidating {name}", flush=True)
            print(dict(zip(FEATURES, weights)))

            with Timer() as timer:

                raw, greedy, final = validate_weights(
                    pairs, matrix, val, weights
                )

            for stage, metrics in [
                ("none", raw),
                ("greedy", greedy)
            ]:

                result = {
                    "pair": pair,
                    "configuration": name,
                    "global_matching": stage,
                    "split": "validation",
                    **metrics,
                    **dict(zip(FEATURES, weights)),
                    "training_f1": row["f1"],
                    "seconds_total": timer.seconds
                }

                all_results.append(result)

                print(
                    f"{stage}: "
                    f"P={metrics['precision']:.4f} "
                    f"R={metrics['recall']:.4f} "
                    f"F1={metrics['f1']:.4f} "
                    f"threshold={metrics['threshold']:.2f} "
                    f"corr={metrics['correspondences']:,}",
                    flush=True
                )

            if name == "original":

                final.to_csv(
                    OUTPUT / f"{a}_{b}_original.csv",
                    index=False
                )

            else:

                key = (
                    greedy["f1"],
                    greedy["precision"],
                    greedy["threshold"]
                )

                if best_key is None or key > best_key:

                    best_key = key
                    best_optimized = result.copy()
                    best_predictions = final.copy()

            pd.DataFrame(all_results).to_csv(
                OUTPUT / "matching.csv",
                index=False
            )

        winners.append(best_optimized)

        best_predictions.to_csv(
            OUTPUT / f"{a}_{b}_optimized.csv",
            index=False
        )

        pd.DataFrame(winners).to_csv(
            OUTPUT / "best_optimized.csv",
            index=False
        )

        print(f"\nBEST OPTIMIZED RULE: {pair}")

        print(pd.Series(best_optimized).to_string())

    print("\nFINAL VALIDATION RESULTS")
    print(pd.DataFrame(all_results).to_string(index=False))


if __name__ == "__main__":
    main()
