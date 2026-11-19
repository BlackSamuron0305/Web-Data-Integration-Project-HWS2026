"""Final step of a round.  Usage: python final.py <round>
From round 5 on, the links that touch a non-university (scripts/additional_filtering/) are removed
after the global matching ("filter after matching"). Round 5 reuses the matcher output of round 3."""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import (EntityMatchingEvaluator, GreedyOneToOneMatchingAlgorithm,
                                 MaximumBipartiteMatching, StableMatching)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IR, PAIRS, Timer, evaluate, labels, load_all, log, non_universities, reset_log, row

RESULTS = Path(__file__).resolve().parent / "results"
MATCHER_ROUND = {5: 3}   # round 5 = the matching of round 3, filtered afterwards
GLOBAL = {
    "greedy one-to-one": GreedyOneToOneMatchingAlgorithm(),
    "stable matching": StableMatching(),
    "maximum bipartite": MaximumBipartiteMatching(),
}


def best_matcher(a, b, round_):
    # the better of 03_rule_based and 04_ml_based (by validation F1)
    found = []
    for method in ["03_rule_based", "04_ml_based"]:
        folder = IR / method / "results"
        info = folder / f"best_{a}_{b}_r{round_}_info.csv"
        if info.exists():
            found.append((pd.read_csv(info).iloc[0], folder / f"best_{a}_{b}_r{round_}.csv"))
    info, path = max(found, key=lambda x: x[0]["F1"])
    return info, pd.read_csv(path)


def save_errors(path, corr, val, L, R):
    predicted = set(map(tuple, corr[["id1", "id2"]].values))
    name = dict(zip(L["id"], L["name"])) | dict(zip(R["id"], R["name"]))
    rows = []
    for x, y, label in val[["id1", "id2", "label"]].values:
        if label and (x, y) not in predicted:
            rows.append(("missed match", x, y, name.get(x), name.get(y)))
        if not label and (x, y) in predicted:
            rows.append(("wrong match", x, y, name.get(x), name.get(y)))
    pd.DataFrame(rows, columns=["error", "id1", "id2", "name1", "name2"]).to_csv(path, index=False)


def main(round_):
    RESULTS.mkdir(exist_ok=True)
    log_file = RESULTS / "final.csv"
    reset_log(log_file, round_)
    data = load_all()
    final = []

    for a, b in PAIRS:
        pair = f"{a}-{b}"
        val = labels(a, b, "validation", round_)
        test = labels(a, b, "test", round_)
        info, corr = best_matcher(a, b, MATCHER_ROUND.get(round_, round_))
        matcher, t, seconds = info["matcher"], info["threshold"], info["seconds"]

        # global matching
        versions = {"none": corr}
        p, r, f = evaluate(corr, val)
        log(log_file, row(round_, pair, f"{matcher} + no global matching", "validation", t, p, r, f, len(corr), seconds))
        for name, algorithm in GLOBAL.items():
            with Timer() as tt:
                versions[name] = algorithm.cluster(corr)
            p, r, f = evaluate(versions[name], val)
            n = len(versions[name])
            log(log_file, row(round_, pair, f"{matcher} + {name}", "validation", t, p, r, f, n, round(seconds + tt.seconds, 1)))
            print(f"  {pair} {matcher} + {name}: P={p:.3f} R={r:.3f} F1={f:.3f} corr={n:,}")

        # round 1 and 2: best validation F1; from round 3 always one-to-one
        if round_ >= 3:
            chosen = "greedy one-to-one"
        else:
            chosen = max(versions, key=lambda k: evaluate(versions[k], val)[2])
        corr = versions[chosen]

        # from round 5: remove every link that touches a non-university (filter after matching)
        if round_ >= 5:
            gone = non_universities()
            n_before = len(corr)
            corr = corr[~corr["id1"].isin(gone) & ~corr["id2"].isin(gone)]
            chosen += " + filter after matching"
            p, r, f = evaluate(corr, val)
            log(log_file, row(round_, pair, f"{matcher} + {chosen}", "validation", t, p, r, f, len(corr), seconds,
                              note=f"{n_before - len(corr)} links to non-universities removed"))
            print(f"  {pair} {matcher} + {chosen}: P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(corr):,} "
                  f"({n_before - len(corr)} removed)")

        # the only evaluation on the test labels
        p, r, f = evaluate(corr, test)
        log(log_file, row(round_, pair, f"{matcher} + {chosen}", "test", t, p, r, f, len(corr), seconds,
                          note="final choice of this round"))
        print(f"  {pair} TEST {matcher} + {chosen}: P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(corr):,}")

        corr.to_csv(RESULTS / f"correspondences_{a}_{b}_r{round_}.csv", index=False)
        save_errors(RESULTS / f"errors_{pair}_r{round_}.csv", corr, val, data[a], data[b])
        final.append(corr)

    sizes = EntityMatchingEvaluator.create_cluster_size_distribution(pd.concat(final, ignore_index=True))
    sizes.insert(0, "round", round_)
    sizes.to_csv(RESULTS / f"group_sizes_r{round_}.csv", index=False)
    print(sizes.head(10).to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]))
