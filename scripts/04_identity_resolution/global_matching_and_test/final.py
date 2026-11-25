"""Takes the best matcher of a run, applies one-to-one matching (and in the final run the cut-off), evaluates
on test. The other global matching algorithms are logged on validation for comparison.
Usage: python final.py first_pass | final"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import (EntityMatchingEvaluator, GreedyOneToOneMatchingAlgorithm,
                                 MaximumBipartiteMatching, StableMatching)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IR, PAIRS, Timer, evaluate, labels, load_all, log, reset_log, row, run_argument

RESULTS = Path(__file__).resolve().parent / "results"
MATCHERS = ["01_rules_string_similarity", "02_rules_tfidf", "03_rules_embeddings", "04_rules_weight_search",
            "05_machine_learning", "06_rules_more_similarity", "07_more_learners", "08_fine_tuned_language_model",
            "09_local_llm"]
# final run only (its links go into the fusion): a wrong link merges two universities, which is worse for us
# than a missed one, so after one-to-one matching we keep only links with a score at or above a final cut-off: the lowest
# cut-off at which the links reach this precision on the validation pairs (chosen on validation only)
PRECISION_TARGET = 0.99
GLOBAL = {
    "greedy one-to-one": GreedyOneToOneMatchingAlgorithm(),
    "stable matching": StableMatching(),
    "maximum bipartite": MaximumBipartiteMatching(),
}


def best_matcher(a, b, run):
    # the best of all matcher folders by validation F1
    found = []
    for method in MATCHERS:
        folder = IR / method / "results" / run
        info = folder / f"best_{a}_{b}_info.csv"
        if info.exists():
            found.append((pd.read_csv(info).iloc[0], folder / f"best_{a}_{b}.csv"))
    info, path = max(found, key=lambda x: x[0]["F1"])
    return info, pd.read_csv(path)


def choose_cutoff(corr, val, threshold):
    """Lowest cut-off (the matcher threshold or above, in steps of 0.05) whose links reach PRECISION_TARGET on
    the validation pairs; if none does, the one with the highest validation precision (the lowest on a tie)."""
    grid = [threshold] + [c / 100 for c in range(5, 100, 5) if c / 100 > threshold + 1e-9]
    scores = []
    for c in grid:
        p, r, f = evaluate(corr[corr["score"] >= c], val)
        if p >= PRECISION_TARGET:
            return round(c, 2), p, r, f
        scores.append((p, -c, r, f))
    p, c, r, f = max(scores)
    return round(-c, 2), p, r, f


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


def group_sizes(corr, run, path):
    # group size 3 = one university found in all three sources
    sizes = EntityMatchingEvaluator.create_cluster_size_distribution(pd.concat(corr, ignore_index=True))
    sizes.insert(0, "run", run)
    sizes.to_csv(path, index=False)
    return sizes


def main(run):
    RESULTS.mkdir(exist_ok=True)
    log_file = RESULTS / "final.csv"
    reset_log(log_file, run)
    data = load_all(run)
    final, without, cutoffs = [], [], []

    for a, b in PAIRS:
        pair = f"{a}-{b}"
        val = labels(a, b, "validation", run)
        test = labels(a, b, "test", run)
        info, corr = best_matcher(a, b, run)
        matcher, t, seconds = info["matcher"], info["threshold"], info["seconds"]

        # global matching: each record linked to at most one record of the other source
        versions = {"none": corr}
        p, r, f = evaluate(corr, val)
        log(log_file, row(run, pair, f"{matcher} + no global matching", "validation", t, p, r, f, len(corr), seconds))
        for name, algorithm in GLOBAL.items():
            with Timer() as tt:
                versions[name] = algorithm.cluster(corr)
            p, r, f = evaluate(versions[name], val)
            n = len(versions[name])
            log(log_file, row(run, pair, f"{matcher} + {name}", "validation", t, p, r, f, n, round(seconds + tt.seconds, 1)))
            print(f"  {pair} {matcher} + {name}: P={p:.3f} R={r:.3f} F1={f:.3f} corr={n:,}")

        # always one-to-one: each university exists once per source
        chosen = "greedy one-to-one"
        without.append(corr)
        corr = versions[chosen]

        # final run: log the test result before the cut-off too, for comparison
        if run == "final":
            cut, vp, vr, vf = choose_cutoff(corr, val, t)
            print(f"  {pair} cut-off chosen on validation: {cut} (P={vp:.3f} R={vr:.3f} F1={vf:.3f}, "
                  f"target precision {PRECISION_TARGET})")
            cutoffs.append({"pair": pair, "matcher_threshold": t, "cutoff": cut,
                            "precision_target": PRECISION_TARGET, "validation_P": round(vp, 3),
                            "validation_R": round(vr, 3), "validation_F1": round(vf, 3)})
            p, r, f = evaluate(corr, test)
            log(log_file, row(run, pair, f"{matcher} + {chosen}", "test", t, p, r, f, len(corr), seconds,
                              note="before the final cut-off, for comparison"))
            print(f"  {pair} TEST before cut-off: P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(corr):,}")
            corr.to_csv(RESULTS / f"correspondences_{a}_{b}_{run}_before_cutoff.csv", index=False)
            corr = corr[corr["score"] >= cut].reset_index(drop=True)
            chosen += f" + cut-off {cut}"
            p, r, f = evaluate(corr, val)
            log(log_file, row(run, pair, f"{matcher} + {chosen}", "validation", t, p, r, f, len(corr), seconds))

        p, r, f = evaluate(corr, test)
        log(log_file, row(run, pair, f"{matcher} + {chosen}", "test", t, p, r, f, len(corr), seconds,
                          note="final choice of this run"))
        print(f"  {pair} TEST {matcher} + {chosen}: P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(corr):,}")

        corr.to_csv(RESULTS / f"correspondences_{a}_{b}_{run}.csv", index=False)
        save_errors(RESULTS / f"errors_{pair}_{run}.csv", corr, val, data[a], data[b])
        final.append(corr)

    # group sizes of the final links, and of the matcher's links without one-to-one matching for comparison
    sizes = group_sizes(final, run, RESULTS / f"group_sizes_{run}.csv")
    group_sizes(without, run, RESULTS / f"group_sizes_{run}_without_one_to_one.csv")
    print(sizes.head(10).to_string(index=False))
    if cutoffs:
        pd.DataFrame(cutoffs).to_csv(RESULTS / f"cutoff_{run}.csv", index=False)


if __name__ == "__main__":
    main(run_argument())
