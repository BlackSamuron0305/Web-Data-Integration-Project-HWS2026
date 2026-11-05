"""Phase II, step 1: compares blocking strategies for the three dataset pairs.

Measures pair completeness (share of the linked pairs that survive blocking), reduction
ratio (share of all possible pairs that is not compared) and the number of candidate pairs.
Saves the candidates of the chosen strategy for the next steps.

Run: python scripts/phase2_blocking.py
"""
import time

import pandas as pd

from blocking import add_block_text, strategies
from common import RESULTS, link_pairs, load_schema, load_target, one_to_one

PAIRS = [("wikidata", "ror"), ("deqar", "ror"), ("wikidata", "deqar")]
CHOSEN = "token (scoped) + same web domain"
CACHE = RESULTS / "cache"
CACHE.mkdir(exist_ok=True)


def main():
    data = load_target()
    _, raw = load_schema()
    links = link_pairs(raw)
    add_block_text(data)
    rows = []
    for a, b in PAIRS:
        left, right = data[a], data[b]
        gold = one_to_one(links[(a, b)])
        total = len(left) * len(right)
        for name, run in strategies(left, right).items():
            t = time.time()
            cand, est = run()
            took = time.time() - t
            if cand is None:
                rows.append(dict(pair=f"{a}-{b}", strategy=name, candidates=est, pair_completeness=None,
                                 reduction_ratio=1 - est / total, seconds=None, note="too many pairs, not run"))
                print(rows[-1])
                continue
            found = len(gold & set(zip(cand["id1"], cand["id2"])))
            rows.append(dict(pair=f"{a}-{b}", strategy=name, candidates=len(cand),
                             pair_completeness=found / len(gold), reduction_ratio=1 - len(cand) / total,
                             seconds=round(took, 1), note=""))
            print(rows[-1])
            if name == CHOSEN:
                cand.to_csv(CACHE / f"candidates_{a}_{b}.csv", index=False)
    pd.DataFrame(rows).to_csv(RESULTS / "blocking.csv", index=False)


if __name__ == "__main__":
    main()
