"""Phase II: standard blocking + rule-based matching, evaluated on validation_data.

For every dataset pair and every standard blocker (PyDI StandardBlocker, equality of a key):
  1. block: candidate pairs of records with the same key (records without a key are left out,
     otherwise they would all share the empty key),
  2. match: PyDI RuleBasedMatcher (weighted average of comparators) on all candidate pairs,
  3. choose the threshold with the best F1 on train_data,
  4. report on validation_data: precision, recall, F1, number of correspondences (#Corr,
     all records, score >= threshold, no post-clustering) and the run time of blocking + matching.

"No blocking" is listed with its number of pairs only: comparing all pairs is infeasible.

Output: results/standard_blocking_validation.csv
Run (after gold_standard.py): python scripts/standard_blocking.py
"""
import logging
import time

import pandas as pd
from PyDI.entitymatching import RuleBasedMatcher
from PyDI.entitymatching.blocking import StandardBlocker

from blocking import OUTPUT_DIR, add_block_text
from common import RESULTS, load_target
from matching import feature_comparators
from validation import evaluate, load_labelled, pair_completeness, tune_threshold, write_log

logging.basicConfig(level=logging.WARNING)

PAIRS = [("wikidata", "ror"), ("deqar", "ror"), ("wikidata", "deqar")]

# blocker name -> key column(s); the columns are made by blocking.add_block_text / common
BLOCKERS = {
    "Standard: normalised name": ["name_norm"],
    "Standard: country + first word": ["cc_first"],
    "Standard: web domain": ["domain"],
}

# matcher name -> {comparator name of matching.feature_comparators: weight}
MATCHERS = {
    "Rule1: names+country+domain": {"names_best_jaro_winkler": 0.5, "domain": 0.3, "country": 0.2},
}


def has_key(df, cols):
    """Records whose blocking key is complete (no empty or missing part)."""
    ok = pd.Series(True, index=df.index)
    for c in cols:
        v = df[c]
        ok &= v.notna() & (v.astype(str).str.strip() != "")
        if c == "cc_first":  # 'country|first word': both parts needed
            ok &= ~v.astype(str).str.startswith("|") & ~v.astype(str).str.endswith("|")
    return ok


def block(left, right, cols):
    l, r = left[has_key(left, cols)], right[has_key(right, cols)]
    blocker = StandardBlocker(l, r, on=cols, id_column="id", output_dir=OUTPUT_DIR)
    return blocker.materialize()[["id1", "id2"]].drop_duplicates().reset_index(drop=True)


def match(left, right, candidates, rule):
    comps, _ = feature_comparators()
    comparators = [{"comparator": comps[n], "weight": w} for n, w in rule.items()]
    batches = [candidates.iloc[i:i + 100_000] for i in range(0, len(candidates), 100_000)]
    return RuleBasedMatcher().match(left, right, batches, "id", comparators=comparators, threshold=0.0)


def main():
    data = load_target()
    add_block_text(data)
    rows = []
    for a, b in PAIRS:
        left, right = data[a], data[b]
        train, valid = load_labelled("train", a, b), load_labelled("validation", a, b)
        total = len(left) * len(right)
        rows.append(dict(pair=f"{a}-{b}", matcher="-", blocker="No blocking", candidates=total,
                         reduction_ratio=0.0, note="not run: too many pairs"))
        for bname, cols in BLOCKERS.items():
            t0 = time.time()
            cand = block(left, right, cols)
            t_block = time.time() - t0
            pc = pair_completeness(cand, valid)
            for mname, rule in MATCHERS.items():
                t1 = time.time()
                corr = match(left, right, cand, rule)
                t_match = time.time() - t1
                best = tune_threshold(corr, train)          # chosen on train_data
                t = best["threshold"]
                final = corr[corr["score"] >= t]
                res = evaluate(final, valid)                # reported on validation_data
                rows.append(dict(pair=f"{a}-{b}", matcher=mname, blocker=bname, candidates=len(cand),
                                 pair_completeness=round(pc, 4), reduction_ratio=round(1 - len(cand) / total, 6),
                                 threshold=t, train_f1=round(best["f1"], 4),
                                 precision=round(res["precision"], 4), recall=round(res["recall"], 4),
                                 f1=round(res["f1"], 4), tp=res["tp"], fp=res["fp"], fn=res["fn"],
                                 corr=len(final), block_s=round(t_block, 1), match_s=round(t_match, 1),
                                 time_s=round(t_block + t_match, 1), note=""))
                print({k: rows[-1][k] for k in ("pair", "blocker", "candidates", "precision", "recall", "f1",
                                                  "corr", "time_s")})
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "standard_blocking_validation.csv", index=False)
    print("log:", write_log(out, "standard_blocking", "Standard blocking (PyDI StandardBlocker)"))
    show = out[out["blocker"] != "No blocking"][["pair", "matcher", "blocker", "precision", "recall", "f1",
                                                  "corr", "time_s"]]
    print("\nValidation results (P/R/F1 on validation_data, threshold chosen on train_data)\n")
    print(show.rename(columns={"precision": "P", "recall": "R", "f1": "F1", "corr": "#Corr",
                               "time_s": "Time (s)"}).to_string(index=False))


if __name__ == "__main__":
    main()
