"""Freeze selected configurations before test evaluation."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

# her scripts are split over one folder per approach; make the other folders importable
import sys as _sys
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parents[1] / d) for d in ("09_optimized_rules",)]

from extract_rule_features import sha256, PAIRS
from common import labels, evaluate

ROOT = Path(__file__).resolve().parent
IR = ROOT.parent   # prediction files are stored relative to this folder
RESULTS = ROOT / "results"
OUTPUT = RESULTS / "final_evaluation"


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    tfidf = pd.read_csv(
        IR / "07_tfidf/results/refined/matching.csv"
    )

    semantic = pd.read_csv(
        IR / "08_semantic/results/matching.csv"
    )

    rules = pd.read_csv(
        IR / "09_optimized_rules/results/matching.csv"
    )

    baseline = pd.read_csv(
        IR / "10_ml_baseline_reproduction/results/matching.csv"
    )

    frozen = []

    for a, b in PAIRS:

        pair = f"{a}-{b}"
        prefix = f"{a}_{b}"

        val = labels(a, b, "validation", 3)

        def register(method, row, file):

            corr = pd.read_csv(file)

            assert not corr["id1"].duplicated().any()
            assert not corr["id2"].duplicated().any()

            assert len(corr) == int(row["correspondences"])

            p, r, f = evaluate(corr, val)

            assert np.allclose(
                [p, r, f],
                [row["precision"], row["recall"], row["f1"]]
            ), f"Validation mismatch: {pair}, {method}"

            frozen.append({
                "pair": pair,
                "method": method,
                "threshold": float(row["threshold"]),
                "validation_precision": float(p),
                "validation_recall": float(r),
                "validation_f1": float(f),
                "correspondences": len(corr),
                "prediction_file": str(
                    file.relative_to(IR)
                ),
                "prediction_sha256": sha256(file),
                "configuration": row.to_dict()
            })

            print(
                f"{pair}: {method}, "
                f"F1={f:.4f}, "
                f"corr={len(corr):,}"
            )

        # Best refined TF-IDF configuration.
        t = tfidf[
            (tfidf["pair"] == pair)
            & (tfidf["global_matching"] == "greedy")
        ].sort_values(
            ["f1", "precision", "threshold"],
            ascending=False
        ).iloc[0]

        register(
            "tfidf",
            t,
            IR / "07_tfidf/results/refined" /
            f"{prefix}_{t['matcher']}_{t['variant']}.csv"
        )

        # Semantic approaches.
        for method in ["semantic_only", "semantic_hybrid"]:

            s = semantic[
                (semantic["pair"] == pair)
                & (semantic["matcher"] == method)
                & (semantic["global_matching"] == "greedy")
            ].iloc[0]

            register(
                method,
                s,
                IR / "08_semantic/results" /
                f"{prefix}_{method}.csv"
            )

        # Optimized and original rules.
        g = rules[
            (rules["pair"] == pair)
            & (rules["global_matching"] == "greedy")
        ]

        optimized = g[
            g["configuration"] != "original"
        ].sort_values(
            ["f1", "precision", "threshold"],
            ascending=False
        ).iloc[0]

        original = g[
            g["configuration"] == "original"
        ].iloc[0]

        register(
            "optimized_rules",
            optimized,
            IR / "09_optimized_rules/results" /
            f"{prefix}_optimized.csv"
        )

        register(
            "original_rules",
            original,
            IR / "09_optimized_rules/results" /
            f"{prefix}_original.csv"
        )

        # Historical and retuned ML classifiers.
        for config, suffix in [
            ("original_threshold", "historical"),
            ("retuned_threshold", "retuned")
        ]:

            m = baseline[
                (baseline["pair"] == pair)
                & (baseline["configuration"] == config)
            ].iloc[0]

            register(
                f"ml_{config}",
                m,
                IR / "10_ml_baseline_reproduction/results" /
                f"{prefix}_{suffix}.csv"
            )

    assert len(frozen) == 14

    path = OUTPUT / "frozen_configurations.json"

    with path.open("x", encoding="utf-8") as f:
        json.dump(frozen, f, indent=2, default=str)

    summary = pd.DataFrame(frozen).drop(
        columns=["configuration"]
    )

    summary.to_csv(
        OUTPUT / "validation_summary.csv",
        index=False
    )

    print("\nAll 14 configurations frozen successfully.")
    print("No test labels accessed.")


if __name__ == "__main__":
    main()
