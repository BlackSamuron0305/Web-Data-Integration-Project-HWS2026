"""Evaluate frozen identity resolution configurations on test data."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from extract_rule_features import sha256, PAIRS
from common import labels, evaluate

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "results/final_evaluation"


def main():

    frozen_path = OUTPUT / "frozen_configurations.json"

    frozen = json.loads(frozen_path.read_text())

    assert len(frozen) == 14

    # Verify all predictions before accessing test labels.
    for config in frozen:

        file = ROOT / config["prediction_file"]

        assert sha256(file) == config["prediction_sha256"], (
            f"Prediction file changed: {file}"
        )

    print("All frozen prediction checksums verified.")

    results = []

    for a, b in PAIRS:

        pair = f"{a}-{b}"

        print(f"\nProcessing {pair}", flush=True)

        gold = labels(a, b, "test", 3)

        print(f"Test pairs: {len(gold)}")
        print(f"Positive pairs: {gold['label'].sum()}")
        print(f"Negative pairs: {(~gold['label']).sum()}")

        for config in frozen:

            if config["pair"] != pair:
                continue

            file = ROOT / config["prediction_file"]

            corr = pd.read_csv(file)

            assert len(corr) == config["correspondences"]
            assert not corr["id1"].duplicated().any()
            assert not corr["id2"].duplicated().any()

            p, r, f = evaluate(corr, gold)

            predicted = set(
                map(tuple, corr[["id1", "id2"]].values)
            )

            actual = gold["label"].to_numpy(dtype=bool)

            predictions = np.array([
                (x, y) in predicted
                for x, y in gold[["id1", "id2"]].values
            ], dtype=bool)

            tp = int((predictions & actual).sum())
            fp = int((predictions & ~actual).sum())
            tn = int((~predictions & ~actual).sum())
            fn = int((~predictions & actual).sum())

            assert tp + fp + tn + fn == len(gold)

            manual_p = tp / (tp + fp) if tp + fp else 0
            manual_r = tp / (tp + fn) if tp + fn else 0

            manual_f = (
                2 * tp / (2 * tp + fp + fn)
                if 2 * tp + fp + fn else 0
            )

            assert np.allclose(
                [p, r, f],
                [manual_p, manual_r, manual_f]
            ), "Evaluation metric mismatch"

            result = {
                "pair": pair,
                "method": config["method"],
                "threshold": config["threshold"],
                "validation_f1": config["validation_f1"],
                "test_precision": p,
                "test_recall": r,
                "test_f1": f,
                "f1_difference": (
                    f - config["validation_f1"]
                ),
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "correspondences": len(corr),
                "test_pairs": len(gold)
            }

            results.append(result)

            print(
                f"{config['method']}: "
                f"P={p:.4f} "
                f"R={r:.4f} "
                f"F1={f:.4f} "
                f"TP={tp} FP={fp} TN={tn} FN={fn}",
                flush=True
            )

    assert len(results) == 14

    summary = pd.DataFrame(results)

    summary.to_csv(
        OUTPUT / "test_results.csv",
        index=False
    )

    print("\nFINAL TEST RESULTS")
    print(summary.to_string(index=False))

    print("\nAll configurations evaluated successfully.")


if __name__ == "__main__":
    main()
