"""Final run: how the blocker changes P/R/F1 with the final matcher held fixed, writes results/blocking_effect.csv.
The learner scores each pair on its own, so on a smaller candidate set it returns the pairs of best_*_final.csv in
that set; these get the same greedy one-to-one and cut-off as in final.py. The embedding blocker is not re-run (2 hours).
Usage: python blocking_effect.py  (after final.py final)"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import GreedyOneToOneMatchingAlgorithm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blocking"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "global_matching_and_test"))
from blocking import UNIONS, add_block_keys, blockers
from common import BLOCKER, IR, PAIRS, evaluate, labels, load_all
from final import best_matcher

RESULTS = Path(__file__).resolve().parent / "results"
FINAL = Path(__file__).resolve().parents[1] / "global_matching_and_test" / "results"
KEYS = "union: country + name word | same domain"   # the union without the embedding


def main():
    data = load_all("final")
    logged = pd.read_csv(IR / "blocking" / "results" / "blocking.csv").query("run == 'final'")
    cutoff = pd.read_csv(FINAL / "cutoff_final.csv").set_index("pair")["cutoff"]   # chosen by final.py
    rows = []
    for a, b in PAIRS:
        pair = f"{a}-{b}"
        L, R = data[a], data[b]
        add_block_keys(L, R)
        make = blockers(L, R)
        found = {name: set(map(tuple, make[name]().materialize()[["id1", "id2"]].values)) for name in UNIONS[KEYS]}
        found[KEYS] = set.union(*found.values())
        found[BLOCKER] = None   # the full union: all scored pairs

        # pairs the final matcher scored above its threshold on the full union
        _, scored = best_matcher(a, b, "final")
        log = logged[logged["pair"] == pair].set_index("blocker")
        splits = {s: labels(a, b, s, "final") for s in ["validation", "test"]}
        for blocker, cand in found.items():
            assert cand is None or len(cand) == log.at[blocker, "candidates"], "candidates differ from blocking.csv"
            keep = [cand is None or p in cand for p in zip(scored["id1"], scored["id2"])]
            corr = GreedyOneToOneMatchingAlgorithm().cluster(scored[keep].reset_index(drop=True))
            corr = corr[corr["score"] >= cutoff[pair]]
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
