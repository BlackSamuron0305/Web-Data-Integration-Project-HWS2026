"""Identity resolution using TF-IDF and cosine similarity."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import (
    PAIRS,
    Timer,
    candidates,
    labels,
    load_all,
    evaluate,
    best_threshold,
)

RESULTS = Path(__file__).resolve().parent / "results" / "tfidf"

ROUND = 3
BATCH_SIZE = 4096

CONFIGS = {
    "word_tfidf": {
        "analyzer": "word",
        "ngram_range": (1, 2),
        "token_pattern": r"(?u)\b\w+\b",
    },
    "char_tfidf": {
        "analyzer": "char_wb",
        "ngram_range": (3, 5),
    },
}


def compute_scores(left, right, pairs, config):
    """Compute cosine similarity for blocked candidate pairs."""

    texts = (
        left["name_norm"].fillna("").tolist()
        + right["name_norm"].fillna("").tolist()
    )

    vectorizer = TfidfVectorizer(
        **config,
        dtype=np.float32,
        norm="l2",
        sublinear_tf=True,
    )

    matrix = vectorizer.fit_transform(texts)

    left_matrix = matrix[:len(left)]
    right_matrix = matrix[len(left):]

    left_indices = pd.Index(left["id"]).get_indexer(
        pairs["id1"]
    )

    right_indices = pd.Index(right["id"]).get_indexer(
        pairs["id2"]
    )

    if (left_indices < 0).any() or (right_indices < 0).any():
        raise ValueError("Unknown candidate record IDs.")

    scores = np.zeros(len(pairs), dtype=np.float32)

    for start in range(0, len(pairs), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(pairs))

        x = left_matrix[left_indices[start:end]]
        y = right_matrix[right_indices[start:end]]

        scores[start:end] = np.asarray(
            x.multiply(y).sum(axis=1)
        ).ravel()

    return np.clip(scores, 0, 1)


def run_experiment(left, right, pairs, gold, method, config):

    with Timer() as timer:
        scores = compute_scores(
            left, right, pairs, config
        )

        corr = pairs[["id1", "id2"]].copy()
        corr["score"] = scores

        # Threshold selection uses validation labels only.
        known = corr.merge(
            gold[["id1", "id2"]],
            on=["id1", "id2"],
            how="inner",
        )

        threshold, _, _, _ = best_threshold(known, gold)

        selected = corr.loc[
            corr["score"] >= threshold
        ].copy()

        p, r, f = evaluate(selected, gold)

    rows = [{
        "matcher": method,
        "global_matching": "none",
        "threshold": threshold,
        "precision": p,
        "recall": r,
        "f1": f,
        "correspondences": len(selected),
        "seconds": timer.seconds,
    }]

    # Resolve conflicting correspondences.
    selected = selected.sort_values(
        ["score", "id1", "id2"],
        ascending=[False, True, True],
    )

    with Timer() as global_timer:
        final = GreedyOneToOneMatchingAlgorithm().cluster(
            selected
        )

        p, r, f = evaluate(final, gold)

    rows.append({
        "matcher": method,
        "global_matching": "greedy one-to-one",
        "threshold": threshold,
        "precision": p,
        "recall": r,
        "f1": f,
        "correspondences": len(final),
        "seconds": timer.seconds + global_timer.seconds,
    })

    return rows, final


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)

    data = load_all(ROUND)
    results = []

    for a, b in PAIRS:
        print(f"\nProcessing {a} - {b}", flush=True)

        left = data[a]
        right = data[b]
        pairs = candidates(a, b, ROUND)
        gold = labels(a, b, "validation", ROUND)

        for method, config in CONFIGS.items():
            print(f"\nRunning {method}...", flush=True)

            rows, final = run_experiment(
                left, right, pairs, gold, method, config
            )

            for row in rows:
                row["pair"] = f"{a}-{b}"
                row["split"] = "validation"
                results.append(row)

                print(
                    f"{row['global_matching']}: "
                    f"P={row['precision']:.4f} "
                    f"R={row['recall']:.4f} "
                    f"F1={row['f1']:.4f} "
                    f"threshold={row['threshold']:.2f} "
                    f"corr={row['correspondences']:,} "
                    f"time={row['seconds']:.1f}s",
                    flush=True,
                )

            final.to_csv(
                RESULTS / f"{a}_{b}_{method}.csv",
                index=False,
            )

    summary = pd.DataFrame(results)

    summary.to_csv(
        RESULTS / "matching.csv",
        index=False,
    )

    print("\nFINAL RESULTS")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
