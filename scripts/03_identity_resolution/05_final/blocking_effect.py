"""Round 8: how the blocker changes P/R/F1 with the final matcher held fixed, writes results/blocking_effect.csv.
The learner scores each pair on its own, so on a smaller candidate set it returns the pairs of best_*_r8.csv in that
set; these get the same greedy one-to-one and cut-off as in final.py. The embedding blocker is not re-run (2 hours).
Usage: python blocking_effect.py  (after final.py 8)"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_blocking"))
from blocking import UNIONS, blockers
from common import BLOCKER, IR, PAIRS, add_block_keys, evaluate, labels, load_all
from final import FINAL_CUTOFF

RESULTS = Path(__file__).resolve().parent / "results"
KEYS = "union: country + name word | same domain"   # the union without the embedding


def main():
    data = load_all(8)
    logged = pd.read_csv(IR / "02_blocking" / "results" / "blocking.csv").query("round == 8")
    rows = []
    for a, b in PAIRS:
        pair = f"{a}-{b}"
        L, R = data[a], data[b]
        add_block_keys(L, R)
        make = blockers(L, R, 8)
        found = {name: set(map(tuple, make[name]().materialize()[["id1", "id2"]].values)) for name in UNIONS[KEYS]}
        found[KEYS] = set.union(*found.values())
        found[BLOCKER[8]] = None   # the full union: all scored pairs

        # pairs the final learner scored above its threshold on the full union
        scored = pd.read_csv(IR / "04_ml_based" / "results" / f"best_{a}_{b}_r8.csv")
        log = logged[logged["pair"] == pair].set_index("blocker")
        splits = {s: labels(a, b, s, 8) for s in ["validation", "test"]}
        for blocker, cand in found.items():
            assert cand is None or len(cand) == log.at[blocker, "candidates"], "candidates differ from blocking.csv"
            keep = [cand is None or p in cand for p in zip(scored["id1"], scored["id2"])]
            corr = GreedyOneToOneMatchingAlgorithm().cluster(scored[keep].reset_index(drop=True))
            corr = corr[corr["score"] >= FINAL_CUTOFF[pair]]
            for split, lab in splits.items():
                p, r, f = evaluate(corr, lab)
                rows.append(dict(pair=pair, blocker=blocker, candidates=log.at[blocker, "candidates"],
                                 pair_completeness=log.at[blocker, "pair_completeness"], split=split,
                                 P=round(p, 3), R=round(r, 3), F1=round(f, 3), corr=len(corr)))
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "blocking_effect.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
