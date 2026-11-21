"""Regenerate Round 3 blocking candidates using CPU embeddings."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "02_blocking"))

from PyDI.entitymatching import EmbeddingBlocker

from common import (
    PAIRS, CANDIDATES, BLOCKER, Timer,
    load_all, add_block_keys, slug, labels
)

from blocking import blockers, UNIONS


def main():
    round_ = 3
    CANDIDATES.mkdir(parents=True, exist_ok=True)

    data = load_all(round_)
    selected = BLOCKER[round_]

    for a, b in PAIRS:
        print(f"\nProcessing {a} - {b}", flush=True)

        L, R = data[a], data[b]
        add_block_keys(L, R)
        available = blockers(L, R, round_)

        parts = []

        for name in UNIONS[selected]:
            print(f"\nRunning: {name}", flush=True)

            with Timer() as timer:
                if name == "embedding: name, top 10":
                    blocker = EmbeddingBlocker(
                        L,
                        R,
                        text_cols=["name"],
                        id_column="id",
                        model="sentence-transformers/all-MiniLM-L6-v2",
                        top_k=10,
                        threshold=0.5,
                        device="cpu",
                        output_dir=str(
                            ROOT / "02_blocking/results/pydi_output"
                        )
                    )
                else:
                    blocker = available[name]()

                pairs = blocker.materialize()[["id1", "id2"]]
                pairs = pairs.drop_duplicates()

            print(f"Candidate pairs: {len(pairs):,}")
            print(f"Execution time: {timer.seconds}s", flush=True)

            parts.append(pairs)

        candidates = pd.concat(
            parts, ignore_index=True
        ).drop_duplicates()

        path = CANDIDATES / (
            f"{a}_{b}_r{round_}_{slug(selected)}.csv"
        )

        candidates.to_csv(path, index=False)

        gold = labels(a, b, "validation", round_)
        positives = gold.loc[gold["label"], ["id1", "id2"]]

        retained = positives.merge(
            candidates, on=["id1", "id2"]
        )

        pc = len(retained) / len(positives)
        rr = 1 - len(candidates) / (len(L) * len(R))

        print("\nFINAL BLOCKING RESULTS")
        print(f"Candidates: {len(candidates):,}")
        print(f"Pair completeness: {pc:.4f}")
        print(f"Reduction ratio: {rr:.6f}")
        print(f"Saved to: {path}", flush=True)


if __name__ == "__main__":
    main()
