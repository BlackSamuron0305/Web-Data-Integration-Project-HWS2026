"""Takes the best matcher of a round, applies global matching (and the round 8 cut-off), evaluates on test.
Usage: python final.py <round>"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import (EntityMatchingEvaluator, GreedyOneToOneMatchingAlgorithm,
                                 MaximumBipartiteMatching, StableMatching)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IR, PAIRS, Timer, evaluate, labels, load_all, log, reset_log, row

RESULTS = Path(__file__).resolve().parent / "results"
# round 8 only: a wrong match is worse for us than a missed one, so we cut harder (see cutoff_check.py)
FINAL_CUTOFF = {"wikidata-ror": 0.7, "deqar-ror": 0.55}
GLOBAL = {
    "greedy one-to-one": GreedyOneToOneMatchingAlgorithm(),
    "stable matching": StableMatching(),
    "maximum bipartite": MaximumBipartiteMatching(),
}


def best_matcher(a, b, round_):
    # the better of 03_rule_based and 04_ml_based by validation F1
    found = []
    for method in ["03_rule_based", "04_ml_based"]:
        folder = IR / method / "results"
        info = folder / f"best_{a}_{b}_r{round_}_info.csv"
        if info.exists():   # round 1 has no learned matcher
            found.append((pd.read_csv(info).iloc[0], folder / f"best_{a}_{b}_r{round_}.csv"))
    info, path = max(found, key=lambda x: x[0]["F1"])
    return info, pd.read_csv(path)


def save_errors(path, corr, val, L, R):
    # every validation pair we get wrong, with both names
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
    data = load_all(round_)
    final = []

    for a, b in PAIRS:
        pair = f"{a}-{b}"
        val = labels(a, b, "validation", round_)
        test = labels(a, b, "test", round_)
        info, corr = best_matcher(a, b, round_)
        matcher, t, seconds = info["matcher"], info["threshold"], info["seconds"]

        # global matching: each record linked to at most one record of the other source
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

        # rounds 1 and 2: the version with the best validation F1; from round 3 on always one-to-one
        if round_ >= 3:
            chosen = "greedy one-to-one"
        else:
            chosen = max(versions, key=lambda k: evaluate(versions[k], val)[2])
        corr = versions[chosen]

        # round 8: log the test result before the cut-off too, for comparison
        if round_ == 8:
            cut = FINAL_CUTOFF[pair]
            p, r, f = evaluate(corr, test)
            log(log_file, row(round_, pair, f"{matcher} + {chosen}", "test", t, p, r, f, len(corr), seconds,
                              note="before the final cut-off, for comparison"))
            print(f"  {pair} TEST before cut-off: P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(corr):,}")
            corr.to_csv(RESULTS / f"correspondences_{a}_{b}_r{round_}_before_cutoff.csv", index=False)
            corr = corr[corr["score"] >= cut].reset_index(drop=True)
            chosen += f" + cut-off {cut}"
            p, r, f = evaluate(corr, val)
            log(log_file, row(round_, pair, f"{matcher} + {chosen}", "validation", t, p, r, f, len(corr), seconds))

        p, r, f = evaluate(corr, test)
        log(log_file, row(round_, pair, f"{matcher} + {chosen}", "test", t, p, r, f, len(corr), seconds,
                          note="final choice of this round"))
        print(f"  {pair} TEST {matcher} + {chosen}: P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(corr):,}")

        corr.to_csv(RESULTS / f"correspondences_{a}_{b}_r{round_}.csv", index=False)
        save_errors(RESULTS / f"errors_{pair}_r{round_}.csv", corr, val, data[a], data[b])
        final.append(corr)

    # group size 3 = one university found in all three sources
    sizes = EntityMatchingEvaluator.create_cluster_size_distribution(pd.concat(final, ignore_index=True))
    sizes.insert(0, "round", round_)
    sizes.to_csv(RESULTS / f"group_sizes_r{round_}.csv", index=False)
    print(sizes.head(10).to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]))
