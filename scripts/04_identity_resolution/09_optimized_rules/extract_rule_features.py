"""Extract and cache similarity features for rule optimization."""

import sys
import json
import hashlib
from pathlib import Path
from importlib.metadata import version

import numpy as np
import pandas as pd

from PyDI.entitymatching import FeatureExtractor

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]

sys.path.insert(0, str(ROOT))

from common import (
    PAIRS, Timer, load_all, candidates, comparators,
    CANDIDATES, BLOCKER, slug
)

CACHE = REPO / "results/cache/identity_resolution_extensions"

OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
)

FEATURES = [
    "names_best_jaro_winkler",
    "country",
    "domain",
    "city",
    "year",
    "geo"
]

ORIGINAL_WEIGHTS = [
    0.35, 0.15, 0.25, 0.10, 0.10, 0.05
]

ROUND = 3
BATCH_SIZE = 25000


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def extract_features(left, right, pairs, extractor):

    columns = extractor.get_feature_names()

    matrix = np.empty(
        (len(pairs), len(FEATURES)),
        dtype=np.float32
    )

    for start in range(0, len(pairs), BATCH_SIZE):

        end = min(start + BATCH_SIZE, len(pairs))

        batch = pairs.iloc[start:end][
            ["id1", "id2"]
        ].copy()

        X = extractor.create_features(
            left, right, batch, "id"
        )

        # Preserve the original candidate ordering.
        aligned = batch.merge(
            X,
            on=["id1", "id2"],
            how="left",
            validate="one_to_one",
            sort=False
        )

        values = aligned[columns].to_numpy(
            dtype=np.float32
        )

        if not np.isfinite(values).all():
            raise ValueError(
                "Missing or non-finite similarity values."
            )

        if values.min() < -1e-6 or values.max() > 1 + 1e-6:
            raise ValueError(
                "Similarity features outside [0, 1]."
            )

        matrix[start:end] = values

        print(
            f"Processed {end:,}/{len(pairs):,} "
            f"({end / len(pairs):.1%})",
            flush=True
        )

    return matrix


def main():

    CACHE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    data = load_all(ROUND)
    comps = comparators()

    extractor = FeatureExtractor(
        [comps[f] for f in FEATURES]
    )

    manifest = {
        "round": ROUND,
        "features": FEATURES,
        "pydi_feature_names": extractor.get_feature_names(),
        "original_weights": ORIGINAL_WEIGHTS,
        "batch_size": BATCH_SIZE,
        "dtype": "float32",
        "pydi_version": version("uma-pydi"),
        "common_sha256": sha256(ROOT / "common.py"),
        "pairs": {}
    }

    for a, b in PAIRS:

        print(f"\nProcessing {a}-{b}", flush=True)

        left = data[a]
        right = data[b]

        pairs = candidates(a, b, ROUND)

        candidate_path = CANDIDATES / (
            f"{a}_{b}_r{ROUND}_{slug(BLOCKER[ROUND])}.csv"
        )

        assert not pairs[["id1", "id2"]].duplicated().any()

        with Timer() as timer:

            matrix = extract_features(
                left, right, pairs, extractor
            )

        path = CACHE / f"{a}_{b}_features.npy"

        np.save(path, matrix, allow_pickle=False)

        stats = pd.DataFrame({
            "feature": FEATURES,
            "min": matrix.min(axis=0),
            "max": matrix.max(axis=0),
            "mean": matrix.mean(axis=0),
            "std": matrix.std(axis=0),
            "zero_fraction": (matrix == 0).mean(axis=0)
        })

        stats.to_csv(
            OUTPUT / f"{a}_{b}_feature_stats.csv",
            index=False
        )

        manifest["pairs"][f"{a}-{b}"] = {
            "candidate_sha256": sha256(candidate_path),
            "feature_sha256": sha256(path),
            "rows": len(matrix),
            "columns": len(FEATURES),
            "seconds": timer.seconds
        }

        print("\nFeature statistics:")
        print(stats.to_string(index=False))

        print(f"\nMatrix shape: {matrix.shape}")
        print(f"Memory: {matrix.nbytes / 1024**2:.2f} MiB")
        print(f"Extraction time: {timer.seconds}s")
        print(f"Saved to: {path}", flush=True)

        (OUTPUT / "feature_manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )

    print("\nFeature extraction completed successfully.")


if __name__ == "__main__":
    main()
