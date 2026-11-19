"""Multilingual semantic and hybrid identity resolution."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from huggingface_hub import HfApi
from sentence_transformers import SentenceTransformer
from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import (
    PAIRS, Timer, candidates, labels, load_all, evaluate
)

from tfidf_refined import optimize, THRESHOLDS

OUTPUT = Path(__file__).resolve().parent / "results" / "semantic"

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

ENCODE_BATCH = 32
MATCH_BATCH = 4096


def encode_names(model, df):
    """Encode each unique primary institution name once."""

    names = df["name"].fillna("").astype(str).str.strip()

    indices, unique_names = pd.factorize(names, sort=True)

    vectors = model.encode(
        unique_names.tolist(),
        batch_size=ENCODE_BATCH,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    vectors = vectors.astype(np.float32)

    # Missing names must not count as semantic evidence.
    vectors[np.asarray(unique_names == "")] = 0

    return vectors[indices]


def candidate_indices(left, right, pairs):

    li = pd.Index(left["id"]).get_indexer(pairs["id1"])
    ri = pd.Index(right["id"]).get_indexer(pairs["id2"])

    if (li < 0).any() or (ri < 0).any():
        raise ValueError("Unknown candidate IDs.")

    return li, ri


def semantic_scores(left_vectors, right_vectors, li, ri):

    scores = np.zeros(len(li), dtype=np.float32)

    for start in range(0, len(li), MATCH_BATCH):
        end = min(start + MATCH_BATCH, len(li))

        x = left_vectors[li[start:end]]
        y = right_vectors[ri[start:end]]

        scores[start:end] = np.einsum("ij,ij->i", x, y)

    return np.clip(scores, 0, 1)


def attribute_scores(left, right, li, ri):

    lc = left["cc"].to_numpy()[li]
    rc = right["cc"].to_numpy()[ri]

    country = np.where(
        (lc == "") | (rc == ""),
        0.5,
        (lc == rc).astype(float)
    )

    ld = [set(x) for x in left["domains"]]
    rd = [set(x) for x in right["domains"]]

    domain = np.fromiter(
        (bool(ld[i] & rd[j]) for i, j in zip(li, ri)),
        dtype=np.float32,
        count=len(li)
    )

    return country, domain


def evaluate_matcher(pairs, scores, gold):

    corr = pairs[["id1", "id2"]].copy()
    corr["score"] = scores

    corr = corr[corr["score"] >= THRESHOLDS[0]]

    corr = corr.sort_values(
        ["score", "id1", "id2"],
        ascending=[False, True, True]
    )

    raw_best = optimize(corr, gold)

    best = None
    final = None
    best_key = None

    for threshold in THRESHOLDS:

        selected = corr[corr["score"] >= threshold].copy()

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
                "threshold": threshold,
                "precision": p,
                "recall": r,
                "f1": f,
            }

            final = predictions.copy()

    assert not final["id1"].duplicated().any()
    assert not final["id2"].duplicated().any()

    raw_best["correspondences"] = int(
        (corr["score"] >= raw_best["threshold"]).sum()
    )

    best["correspondences"] = len(final)

    return raw_best, best, final


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(2026)
    np.random.seed(2026)
    torch.set_num_threads(4)

    revision = HfApi().model_info(MODEL).sha

    print("Loading model:", MODEL, flush=True)
    print("Revision:", revision, flush=True)

    model = SentenceTransformer(
        MODEL,
        revision=revision,
        device="cpu"
    )

    data = load_all(3)
    embeddings = {}
    encoding_times = {}

    # Encode ROR only once because it is the connector.
    for source, df in data.items():

        print(f"\nEncoding {source}: {len(df):,} records")

        with Timer() as timer:
            embeddings[source] = encode_names(model, df)

        encoding_times[source] = timer.seconds

        print(
            f"Shape: {embeddings[source].shape}, "
            f"Time: {timer.seconds}s",
            flush=True
        )

    metadata = {
        "model": MODEL,
        "revision": revision,
        "device": "cpu",
        "seed": 2026,
        "encoding_batch": ENCODE_BATCH,
        "matching_batch": MATCH_BATCH,
        "encoding_times": encoding_times,
        "thresholds": THRESHOLDS.tolist(),
    }

    (OUTPUT / "configuration.json").write_text(
        json.dumps(metadata, indent=2)
    )

    results = []

    for a, b in PAIRS:

        print(f"\nProcessing {a}-{b}", flush=True)

        left, right = data[a], data[b]

        pairs = candidates(a, b, 3)
        gold = labels(a, b, "validation", 3)

        with Timer() as score_timer:

            li, ri = candidate_indices(left, right, pairs)

            semantic = semantic_scores(
                embeddings[a], embeddings[b], li, ri
            )

            country, domain = attribute_scores(
                left, right, li, ri
            )

        configurations = {
            "semantic_only": semantic,
            "semantic_hybrid": (
                0.5 * semantic
                + 0.2 * country
                + 0.3 * domain
            )
        }

        for method, scores in configurations.items():

            print(f"\nRunning {method}", flush=True)

            with Timer() as timer:

                raw, greedy, final = evaluate_matcher(
                    pairs, scores, gold
                )

            for stage, metrics in [
                ("none", raw),
                ("greedy", greedy)
            ]:

                row = {
                    "pair": f"{a}-{b}",
                    "matcher": method,
                    "global_matching": stage,
                    **metrics,
                    "encoding_seconds": (
                        encoding_times[a] + encoding_times[b]
                    ),
                    "scoring_seconds_shared": score_timer.seconds,
                    "threshold_search_seconds": timer.seconds,
                    "split": "validation"
                }

                results.append(row)

                print(
                    f"{stage}: "
                    f"P={row['precision']:.4f} "
                    f"R={row['recall']:.4f} "
                    f"F1={row['f1']:.4f} "
                    f"threshold={row['threshold']:.2f} "
                    f"corr={row['correspondences']:,}",
                    flush=True
                )

            final.to_csv(
                OUTPUT / f"{a}_{b}_{method}.csv",
                index=False
            )

            # Save completed results incrementally.
            pd.DataFrame(results).to_csv(
                OUTPUT / "matching.csv",
                index=False
            )

    print("\nFINAL RESULTS")
    print(pd.DataFrame(results).to_string(index=False))


if __name__ == "__main__":
    main()
