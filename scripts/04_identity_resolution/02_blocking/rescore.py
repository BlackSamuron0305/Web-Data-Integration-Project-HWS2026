"""Recomputes the pair completeness in results/blocking.csv for new validation labels, from the saved
candidate pairs (results/candidates/), without building the candidates again.

The candidates do not depend on the labels, only the pair completeness does. Building them again would
take hours for the embedding blocker, so after the labelled pairs changed we score the saved candidates.
Number of pairs, reduction ratio and time stay as logged by blocking.py.

Usage: python rescore.py 2 3 8   (the rounds to rescore)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import CANDIDATES, labels, slug  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def main(rounds):
    log = pd.read_csv(RESULTS / "blocking.csv")
    for round_ in rounds:
        for pair in log.loc[log["round"] == round_, "pair"].unique():
            a, b = pair.split("-")
            val = labels(a, b, "validation", round_)
            matches = set(map(tuple, val[val["label"]][["id1", "id2"]].values))
            rows = log.index[(log["round"] == round_) & (log["pair"] == pair)]
            for i in rows:
                file = CANDIDATES / f"{a}_{b}_r{round_}_{slug(log.at[i, 'blocker'])}.csv"
                if not file.exists():
                    continue   # no blocking, or skipped as too big
                pairs = pd.read_csv(file)
                pc = round(len(matches & set(map(tuple, pairs[["id1", "id2"]].values))) / len(matches), 4)
                print(f"  round {round_} {pair} {log.at[i, 'blocker']}: PC {log.at[i, 'pair_completeness']} -> {pc}")
                log.at[i, "pair_completeness"] = pc
    log.to_csv(RESULTS / "blocking.csv", index=False)


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]])
