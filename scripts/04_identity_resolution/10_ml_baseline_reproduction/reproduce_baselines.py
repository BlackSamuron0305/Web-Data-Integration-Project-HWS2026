"""Reproduce the selected ML baselines on fixed blocking candidates."""

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.base import clone
from PyDI.entitymatching import (
    FeatureExtractor,
    MLBasedMatcher,
    GreedyOneToOneMatchingAlgorithm
)

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "04_ml_based"))

from ml_based import models

from common import (
    PAIRS, Timer, candidates, labels,
    load_all, comparators, evaluate,
    CANDIDATES, BLOCKER, slug
)

# her scripts are split over one folder per approach; make the other folders importable
import sys as _sys
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[1] / d) for d in ("07_tfidf", "09_optimized_rules",)]

from extract_rule_features import sha256
from tfidf_refined import THRESHOLDS

RESULTS = Path(__file__).resolve().parent / "results"
OUTPUT = RESULTS

ROUND = 3
BATCH_SIZE = 25000


def greedy_match(corr, threshold):

    selected = corr.loc[
        corr["score"] >= threshold
    ].copy()

    if selected.empty:
        return selected

    return GreedyOneToOneMatchingAlgorithm().cluster(
        selected
    )


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(
        (ROOT / "09_optimized_rules" / "results" /
         "feature_manifest.json").read_text()
    )

    # common.py was simplified after these runs (same results); its hash is no longer checked

    data = load_all(ROUND)
    comps = comparators()

    results = []
    configurations = {}

    for a, b in PAIRS:

        pair = f"{a}-{b}"

        print(f"\nProcessing {pair}", flush=True)

        info = pd.read_csv(
            ROOT / "04_ml_based" / "results" /
            f"best_{a}_{b}_r3_info.csv"
        ).iloc[0]

        matcher = info["matcher"]
        original_threshold = float(info["threshold"])

        original_model, features = models(ROUND)[matcher]
        model = clone(original_model)

        print("Matcher:", matcher)
        print("Features:", features)
        print("Original threshold:", original_threshold)

        L, R = data[a], data[b]

        pairs = candidates(a, b, ROUND)
        train = labels(a, b, "train", ROUND)
        val = labels(a, b, "validation", ROUND)

        candidate_path = CANDIDATES / (
            f"{a}_{b}_r{ROUND}_{slug(BLOCKER[ROUND])}.csv"
        )

        assert sha256(candidate_path) == (
            manifest["pairs"][pair]["candidate_sha256"]
        )

        extractor = FeatureExtractor(
            [comps[f] for f in features]
        )

        print("\nTraining original classifier...", flush=True)

        with Timer() as training_timer:

            X = extractor.create_features(
                L, R,
                train[["id1", "id2"]],
                "id",
                labels=train["label"].astype(int)
            )

            model.fit(
                X[extractor.get_feature_names()].fillna(0),
                X["label"]
            )

        print("\nScoring candidates...", flush=True)

        parts = []

        with Timer() as scoring_timer:

            for start in range(0, len(pairs), BATCH_SIZE):

                end = min(start + BATCH_SIZE, len(pairs))

                batch = pairs.iloc[start:end].copy()

                corr = MLBasedMatcher(extractor).match(
                    L, R, batch, "id",
                    trained_classifier=model,
                    threshold=0.01,
                    use_probabilities=True
                )

                parts.append(corr[["id1", "id2", "score"]])

                print(
                    f"Processed {end:,}/{len(pairs):,}",
                    flush=True
                )

            corr = pd.concat(parts, ignore_index=True)

        assert not corr[["id1", "id2"]].duplicated().any()
        assert np.isfinite(corr["score"]).all()

        # Reproduce the historical matching threshold.
        with Timer() as historical_timer:

            historical = greedy_match(
                corr, original_threshold
            )

            p, r, f = evaluate(historical, val)

        historical_result = {
            "pair": pair,
            "matcher": matcher,
            "configuration": "original_threshold",
            "split": "validation",
            "threshold": original_threshold,
            "precision": p,
            "recall": r,
            "f1": f,
            "correspondences": len(historical),
            "training_seconds": training_timer.seconds,
            "scoring_seconds": scoring_timer.seconds,
            "matching_seconds": historical_timer.seconds
        }

        results.append(historical_result)

        historical.to_csv(
            OUTPUT / f"{a}_{b}_historical.csv",
            index=False
        )

        # Apply the same threshold optimization procedure
        # used for the extension matchers.
        print("\nOptimizing greedy matching threshold...")

        corr = corr.sort_values(
            ["score", "id1", "id2"],
            ascending=[False, True, True]
        )

        best = None
        final = None
        best_key = None

        with Timer() as search_timer:

            for threshold in THRESHOLDS:

                predictions = greedy_match(
                    corr, threshold
                )

                p, r, f = evaluate(predictions, val)

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

        results.append({
            "pair": pair,
            "matcher": matcher,
            "configuration": "retuned_threshold",
            "split": "validation",
            **best,
            "training_seconds": training_timer.seconds,
            "scoring_seconds": scoring_timer.seconds,
            "matching_seconds": search_timer.seconds
        })

        final.to_csv(
            OUTPUT / f"{a}_{b}_retuned.csv",
            index=False
        )

        configurations[pair] = {
            "matcher": matcher,
            "features": features,
            "model_parameters": model.get_params(),
            "original_threshold": original_threshold,
            "retuned_threshold": best["threshold"],
            "candidate_sha256": sha256(candidate_path)
        }

        pd.DataFrame(results).to_csv(
            OUTPUT / "matching.csv",
            index=False
        )

        (OUTPUT / "configuration.json").write_text(
            json.dumps(configurations, indent=2, default=str)
        )

        print("\nVALIDATION RESULTS")
        print(pd.DataFrame(results).to_string(index=False))

    print("\nBaseline reproduction completed.")


if __name__ == "__main__":
    main()
