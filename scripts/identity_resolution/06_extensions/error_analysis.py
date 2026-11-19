"""Analyze errors and disagreements between frozen matchers."""

import json
from pathlib import Path

import pandas as pd

from extract_rule_features import sha256, PAIRS
from common import load_all, labels, candidates

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results/final_evaluation"
OUTPUT = RESULTS / "error_analysis"

ID_COLS = ["id1", "id2"]
SEED = 2026


def pair_set(df):
    return set(map(tuple, df[ID_COLS].values))


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    frozen = json.loads(
        (RESULTS / "frozen_configurations.json").read_text()
    )

    data = load_all(3)

    errors = []
    summaries = []
    audit_samples = []
    overlaps = []

    for a, b in PAIRS:

        pair = f"{a}-{b}"

        print(f"\nAnalyzing {pair}", flush=True)

        left = data[a].set_index("id")
        right = data[b].set_index("id")

        gold = labels(a, b, "test", 3)
        blocked = candidates(a, b, 3)

        coverage = gold[ID_COLS].merge(
            blocked[ID_COLS],
            on=ID_COLS,
            how="left",
            indicator=True
        )

        blocked_gold = pair_set(
            coverage[coverage["_merge"] == "both"]
        )

        saved = {}

        for config in frozen:

            if config["pair"] != pair:
                continue

            method = config["method"]
            path = ROOT / config["prediction_file"]

            assert sha256(path) == config["prediction_sha256"]

            corr = pd.read_csv(path)

            saved[method] = corr

            predicted = pair_set(corr)

            assigned_right = dict(
                zip(corr["id1"], corr["id2"])
            )

            assigned_left = dict(
                zip(corr["id2"], corr["id1"])
            )

            method_errors = []

            for row in gold.itertuples():

                key = (row.id1, row.id2)
                prediction = key in predicted

                if prediction == bool(row.label):
                    continue

                error = (
                    "false_negative"
                    if row.label else "false_positive"
                )

                alternative = assigned_right.get(
                    row.id1, ""
                )

                competing_left = assigned_left.get(
                    row.id2, ""
                )

                l = left.loc[row.id1]
                r = right.loc[row.id2]

                if error == "false_negative":

                    if key not in blocked_gold:
                        reason = "not_generated_by_blocking"

                    elif alternative or competing_left:
                        reason = "competing_assignment_present"

                    else:
                        reason = "blocked_but_not_selected"

                else:
                    reason = "incorrect_labeled_match"

                item = {
                    "pair": pair,
                    "method": method,
                    "error": error,
                    "diagnostic": reason,
                    "id1": row.id1,
                    "id2": row.id2,
                    "name1": l["name"],
                    "name2": r["name"],
                    "country1": l["cc"],
                    "country2": r["cc"],
                    "city1": l["city_norm"],
                    "city2": r["city_norm"],
                    "domains1": l["domains"],
                    "domains2": r["domains"],
                    "assigned_right_id": alternative,
                    "assigned_right_name": (
                        right.loc[alternative, "name"]
                        if alternative in right.index else ""
                    ),
                    "assigned_left_id": competing_left,
                    "assigned_left_name": (
                        left.loc[competing_left, "name"]
                        if competing_left in left.index else ""
                    )
                }

                method_errors.append(item)

            errors.extend(method_errors)

            counts = pd.DataFrame(
                method_errors,
                columns=[
                    "pair", "method", "error", "diagnostic"
                ]
            )

            if not counts.empty:

                summary = (
                    counts.groupby(
                        ["pair", "method", "error", "diagnostic"]
                    ).size()
                    .reset_index(name="count")
                )

                summaries.append(summary)

            print(
                f"{method}: {len(method_errors)} errors",
                flush=True
            )

        # Compare the reproduced historical ML predictions
        # with Laith's original saved predictions.

        historical = pd.read_csv(
            ROOT.parent / "05_final/results" /
            f"correspondences_{a}_{b}_r3.csv"
        )

        old_pairs = pair_set(historical)
        reproduced = pair_set(
            saved["ml_original_threshold"]
        )

        union = old_pairs | reproduced

        overlaps.append({
            "pair": pair,
            "original_count": len(old_pairs),
            "reproduced_count": len(reproduced),
            "intersection": len(old_pairs & reproduced),
            "original_only": len(old_pairs - reproduced),
            "reproduced_only": len(reproduced - old_pairs),
            "jaccard": (
                len(old_pairs & reproduced) / len(union)
                if union else 1.0
            ),
            "identical": old_pairs == reproduced
        })

        # Sample additional predictions for human review.
        # Exclude existing test-labeled pairs.
        # Unlabeled disagreements are not assumed to be errors.

        baseline = reproduced
        known = pair_set(gold)

        for method in ["original_rules", "semantic_hybrid"]:

            corr = saved[method]

            additional = sorted(
                pair_set(corr) - baseline - known
            )

            samples = pd.DataFrame(
                additional, columns=ID_COLS
            )

            samples = samples.sample(
                n=min(20, len(samples)),
                random_state=SEED
            )

            for row in samples.itertuples():

                audit_samples.append({
                    "pair": pair,
                    "method": method,
                    "id1": row.id1,
                    "id2": row.id2,
                    "name1": left.loc[row.id1, "name"],
                    "name2": right.loc[row.id2, "name"],
                    "country1": left.loc[row.id1, "cc"],
                    "country2": right.loc[row.id2, "cc"],
                    "domains1": left.loc[row.id1, "domains"],
                    "domains2": right.loc[row.id2, "domains"],
                    "human_label": "",
                    "evidence_url": "",
                    "review_notes": ""
                })

    pd.DataFrame(errors).to_csv(
        OUTPUT / "test_errors.csv", index=False
    )

    summary = pd.concat(summaries, ignore_index=True)

    summary.to_csv(
        OUTPUT / "error_summary.csv", index=False
    )

    pd.DataFrame(audit_samples).to_csv(
        OUTPUT / "manual_review_sample.csv", index=False
    )

    overlap = pd.DataFrame(overlaps)

    overlap.to_csv(
        OUTPUT / "baseline_overlap.csv", index=False
    )

    print("\nERROR SUMMARY")
    print(summary.to_string(index=False))

    print("\nBASELINE OVERLAP")
    print(overlap.to_string(index=False))

    print(f"\nTotal error observations: {len(errors)}")
    print(f"Manual review sample: {len(audit_samples)}")

    print("\nError analysis files generated successfully.")


if __name__ == "__main__":
    main()
