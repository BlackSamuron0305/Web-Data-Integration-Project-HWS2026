"""Phase II, step 3: runs the best matcher of each dataset pair on all candidate pairs.

Uses PyDI's MLBasedMatcher (or RuleBasedMatcher if a rule won) with the model chosen in
phase2_matching.py, then compares PyDI's post-clustering algorithms that enforce a
one-to-one mapping. Writes the correspondences used for data fusion, the evaluation of
the post-clustering and a sample of unlabelled correspondences for manual checking.

Run (after phase2_matching.py): python scripts/phase2_final.py
"""
import json
import time

import pandas as pd
from PyDI.entitymatching import (
    FeatureExtractor,
    GreedyOneToOneMatchingAlgorithm,
    MaximumBipartiteMatching,
    MLBasedMatcher,
    RuleBasedMatcher,
    StableMatching,
)

from blocking import add_block_text
from common import DATA, RESULTS, load_target
from matching import feature_comparators, named
from phase2_matching import CACHE, PAIRS, SEED, gold_features, models, prf

OUT = DATA / "correspondences"
OUT.mkdir(exist_ok=True)


def metrics(corr, test):
    """Precision/recall/F1 on the test part of the gold standard (PyDI's definition)."""
    label = test.set_index(["id1", "id2"])["label"]
    pred = set(zip(corr["id1"], corr["id2"]))
    keys = list(zip(test["id1"], test["id2"]))
    flags = pd.Series([k in pred for k in keys], index=test.index)
    return prf(flags.to_numpy(), test["label"].to_numpy(), int(test["label"].sum()))


def main():
    data = load_target()
    add_block_text(data)
    best = json.loads((RESULTS / "matching_best.json").read_text(encoding="utf-8"))
    comps, flags = feature_comparators()
    ml_cols = list(comps) + list(flags)
    rows, summary = [], []
    for a, b in PAIRS:
        key = f"{a}-{b}"
        cfg = best[key]
        feats = gold_features(a, b, data)
        dev, test = feats[feats["split"] == "dev"], feats[feats["split"] == "test"]
        cand = pd.read_csv(CACHE / f"candidates_{a}_{b}.csv")
        batches = [cand.iloc[i:i + 100_000] for i in range(0, len(cand), 100_000)]
        start = time.time()
        if cfg["kind"] == "learned":
            model = models()[cfg["name"]]
            model.fit(dev[ml_cols], dev["label"])
            matcher = MLBasedMatcher(FeatureExtractor(named({**comps, **flags})))
            corr = matcher.match(data[a], data[b], batches, "id", trained_classifier=model,
                                 threshold=cfg["threshold"], use_probabilities=True)
        else:
            w = cfg["weights"]
            used = {n: comps[n] for n in w}
            corr = RuleBasedMatcher().match(
                data[a], data[b], batches, "id",
                comparators=[{"comparator": c, "weight": max(w[n], 1e-9)} for n, c in used.items()],
                threshold=cfg["threshold"])
        took = time.time() - start
        p, r, f = metrics(corr, test)
        rows.append(dict(pair=key, post_clustering="none (all pairs above threshold)", correspondences=len(corr),
                         test_precision=p, test_recall=r, test_f1=f, seconds=round(took)))
        print(key, cfg["name"], "correspondences", len(corr), "test P/R/F1", round(p, 4), round(r, 4), round(f, 4))
        keep = None
        for name, clusterer in {
            "greedy one-to-one": GreedyOneToOneMatchingAlgorithm(),
            "maximum bipartite matching": MaximumBipartiteMatching(),
            "stable matching": StableMatching(),
        }.items():
            result = clusterer.cluster(corr)
            p, r, f = metrics(result, test)
            rows.append(dict(pair=key, post_clustering=name, correspondences=len(result),
                             test_precision=p, test_recall=r, test_f1=f, seconds=None))
            print("  ", name, len(result), round(p, 4), round(r, 4), round(f, 4))
            if name == "greedy one-to-one":
                keep = result
        corr.to_csv(OUT / f"all_{a}_{b}.csv", index=False)
        keep.to_csv(OUT / f"corr_{a}_{b}.csv", index=False)
        # unlabelled correspondences for the manual check
        labelled = set(zip(feats["id1"], feats["id2"]))
        unl = keep[[(x, y) not in labelled for x, y in zip(keep["id1"], keep["id2"])]]
        summary.append(dict(pair=key, correspondences=len(keep), in_gold_standard=len(keep) - len(unl),
                            not_in_gold_standard=len(unl)))
        sample = unl.sample(min(60, len(unl)), random_state=SEED)
        da, db = data[a].set_index("id"), data[b].set_index("id")
        cols = ["name", "country", "city", "website", "founding_year"]
        out = pd.concat([sample[["id1", "id2", "score"]].reset_index(drop=True),
                         da.loc[sample["id1"], cols].add_prefix("a_").reset_index(drop=True),
                         db.loc[sample["id2"], cols].add_prefix("b_").reset_index(drop=True)], axis=1)
        out["label"] = ""
        out.to_csv(DATA / "gold_standard" / f"manual_check_{a}_{b}.csv", index=False)
    pd.DataFrame(rows).to_csv(RESULTS / "matching_final.csv", index=False)
    pd.DataFrame(summary).to_csv(RESULTS / "correspondences_summary.csv", index=False)
    print(pd.DataFrame(summary))


if __name__ == "__main__":
    main()
