"""Regression and integrity checks for the identity resolution extensions."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from extract_rule_features import (
    CACHE, PAIRS, CANDIDATES, BLOCKER,
    slug, sha256
)
from common import candidates, labels, evaluate
from tfidf_matching import compute_scores, CONFIGS
from semantic_matching import semantic_scores
from optimized_rules import generate_weights

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUTPUT = RESULTS / "final_evaluation"

IDS = ["id1", "id2"]


def check_functions():

    left = pd.DataFrame({
        "id": ["a"],
        "name_norm": ["heidelberg university"]
    })

    right = pd.DataFrame({
        "id": ["b", "c"],
        "name_norm": [
            "heidelberg university",
            "medical college"
        ]
    })

    pairs = pd.DataFrame({
        "id1": ["a", "a"],
        "id2": ["b", "c"]
    })

    for method, config in CONFIGS.items():

        scores = compute_scores(
            left, right, pairs, config
        )

        assert np.isclose(scores[0], 1)
        assert scores[0] > scores[1]
        assert ((scores >= 0) & (scores <= 1)).all()

        print(f"[PASS] {method}")

    vectors = np.eye(3, dtype=np.float32)

    scores = semantic_scores(
        vectors, vectors,
        np.array([0, 0, 1]),
        np.array([0, 1, 1])
    )

    assert np.allclose(scores, [1, 0, 1])

    print("[PASS] Semantic cosine similarity")

    weights = np.array(generate_weights())

    assert weights.shape == (252, 6)
    assert (weights >= 0).all()
    assert np.allclose(weights.sum(axis=1), 1)
    assert len(np.unique(weights, axis=0)) == 252

    print("[PASS] Weight configuration generation")


def main():

    check_functions()

    manifest = json.loads(
        (RESULTS / "optimized_rules/feature_manifest.json")
        .read_text()
    )

    frozen = json.loads(
        (OUTPUT / "frozen_configurations.json").read_text()
    )

    test_results = pd.read_csv(
        OUTPUT / "test_results.csv"
    )

    assert len(frozen) == len(test_results) == 14

    verified = 0

    for a, b in PAIRS:

        pair = f"{a}-{b}"

        candidate_path = CANDIDATES / (
            f"{a}_{b}_r3_{slug(BLOCKER[3])}.csv"
        )

        feature_path = CACHE / f"{a}_{b}_features.npy"

        info = manifest["pairs"][pair]

        assert sha256(candidate_path) == info["candidate_sha256"]
        assert sha256(feature_path) == info["feature_sha256"]

        blocked = candidates(a, b, 3)

        matrix = np.load(
            feature_path, mmap_mode="r", allow_pickle=False
        )

        assert matrix.shape == (len(blocked), 6)
        assert np.isfinite(matrix).all()

        candidate_index = pd.MultiIndex.from_frame(
            blocked[IDS]
        )

        assert candidate_index.is_unique

        print(f"[PASS] {pair}: candidates and feature cache")

        val = labels(a, b, "validation", 3)
        test = labels(a, b, "test", 3)

        for config in frozen:

            if config["pair"] != pair:
                continue

            path = ROOT / config["prediction_file"]

            assert sha256(path) == config["prediction_sha256"]

            corr = pd.read_csv(path)

            assert len(corr) == config["correspondences"]
            assert not corr["id1"].duplicated().any()
            assert not corr["id2"].duplicated().any()

            predicted = pd.MultiIndex.from_frame(corr[IDS])

            assert predicted.isin(candidate_index).all()

            assert np.allclose(
                evaluate(corr, val),
                [
                    config["validation_precision"],
                    config["validation_recall"],
                    config["validation_f1"]
                ]
            )

            row = test_results[
                (test_results["pair"] == pair)
                & (test_results["method"] == config["method"])
            ]

            assert len(row) == 1

            assert np.allclose(
                evaluate(corr, test),
                row[
                    ["test_precision", "test_recall", "test_f1"]
                ].iloc[0].to_numpy(dtype=float)
            )

            verified += 1

            print(f"[PASS] {pair}: {config['method']}")

    assert verified == 14

    print("\nALL REGRESSION AND INTEGRITY CHECKS PASSED.")


if __name__ == "__main__":
    main()
