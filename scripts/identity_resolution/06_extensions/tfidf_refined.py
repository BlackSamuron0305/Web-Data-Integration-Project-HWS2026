"""Extended TF-IDF matching with aliases and threshold optimization."""

import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

from tfidf_matching import (
    compute_scores, CONFIGS, PAIRS, RESULTS,
    candidates, labels, load_all, evaluate, Timer
)

OUTPUT = RESULTS / "refined"

THRESHOLDS = np.round(
    np.arange(0.05, 1.01, 0.05), 2
)


def include_aliases(df):
    result = df.copy()

    result["name_norm"] = result["names"].map(
        lambda names: "\n".join(names)
    )

    return result


def alias_config(config):
    analyzer = TfidfVectorizer(
        **config
    ).build_analyzer()

    # Generate n-grams within each name separately.
    # Avoid artificial n-grams across name boundaries.
    def analyze(text):
        return [
            token
            for name in text.splitlines()
            for token in analyzer(name)
        ]

    return {"analyzer": analyze}


def optimize(corr, gold):
    known = corr.merge(
        gold[["id1", "id2"]],
        on=["id1", "id2"],
        how="inner"
    )

    rows = []

    for threshold in THRESHOLDS:
        selected = known[
            known["score"] >= threshold
        ]

        p, r, f = evaluate(selected, gold)

        rows.append({
            "threshold": threshold,
            "precision": p,
            "recall": r,
            "f1": f
        })

    return max(
        rows,
        key=lambda x: (
            x["f1"],
            x["precision"],
            x["threshold"]
        )
    )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    data = load_all(3)
    results = []

    for a, b in PAIRS:
        pairs = candidates(a, b, 3)
        gold = labels(a, b, "validation", 3)

        for method, config in CONFIGS.items():
            for use_aliases in [False, True]:

                variant = (
                    "all_names" if use_aliases
                    else "primary_name"
                )

                print(
                    f"\n{a}-{b}: {method}, {variant}",
                    flush=True
                )

                left, right = data[a], data[b]

                if use_aliases:
                    left = include_aliases(left)
                    right = include_aliases(right)
                    cfg = alias_config(config)
                else:
                    cfg = config

                with Timer() as timer:
                    scores = compute_scores(
                        left, right, pairs, cfg
                    )

                    corr = pairs[["id1", "id2"]].copy()
                    corr["score"] = scores

                    corr = corr[
                        corr["score"] >= THRESHOLDS[0]
                    ]

                    corr = corr.sort_values(
                        ["score", "id1", "id2"],
                        ascending=[False, True, True]
                    )

                    raw_best = optimize(corr, gold)

                    greedy = (
                        GreedyOneToOneMatchingAlgorithm()
                        .cluster(corr.copy())
                    )

                    greedy_best = optimize(greedy, gold)

                    threshold = greedy_best["threshold"]

                    final = greedy[
                        greedy["score"] >= threshold
                    ]

                    # Verify that thresholding after greedy
                    # gives the same pairs as thresholding first.
                    check = (
                        GreedyOneToOneMatchingAlgorithm()
                        .cluster(
                            corr[
                                corr["score"] >= threshold
                            ].copy()
                        )
                    )

                    cols = ["id1", "id2"]

                    assert set(map(tuple, final[cols].values)) == (
                        set(map(tuple, check[cols].values))
                    ), "Greedy threshold equivalence failed"

                for stage, metrics, predictions in [
                    ("none", raw_best, corr),
                    ("greedy", greedy_best, greedy)
                ]:
                    row = {
                        "pair": f"{a}-{b}",
                        "matcher": method,
                        "variant": variant,
                        "global_matching": stage,
                        **metrics,
                        "correspondences": int(
                            (
                                predictions["score"]
                                >= metrics["threshold"]
                            ).sum()
                        ),
                        "seconds_total": timer.seconds
                    }

                    results.append(row)

                    print(
                        f"{stage}: "
                        f"P={row['precision']:.4f} "
                        f"R={row['recall']:.4f} "
                        f"F1={row['f1']:.4f} "
                        f"threshold={row['threshold']:.2f}",
                        flush=True
                    )

                final.to_csv(
                    OUTPUT / f"{a}_{b}_{method}_{variant}.csv",
                    index=False
                )

    summary = pd.DataFrame(results)

    summary.to_csv(
        OUTPUT / "matching.csv",
        index=False
    )

    print("\nFINAL RESULTS")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
