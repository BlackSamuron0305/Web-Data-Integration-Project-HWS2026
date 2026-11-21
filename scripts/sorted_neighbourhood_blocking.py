"""Phase II: Sorted Neighbourhood Method (SNM) + rule-based matching, evaluated on validation_data.

SNM (PyDI SortedNeighbourhoodBlocker):
  1. generate a key for every record, made of prefixes of attribute values
     (like 'first 3 letters of the SSN + first 3 letters of the surname'),
  2. sort the records of both datasets together by the key, so that similar records end up
     close to each other,
  3. slide a window of size w over the sorted records: every record is compared with the
     next w-1 records (only pairs across the two datasets become candidates).
PyDI's ``window`` parameter counts the records *after* the current one, so it is set to w-1.

Keys (records with a missing part are left out, they would all sort next to each other):
  name prefix + country    first 3 letters of the normalised name + country code
                           'university of heidelberg', DE  -> 'uni de'
  country + word prefixes  country code + first 3 letters of the first two distinctive name
                           words (generic words such as 'university', 'of' removed; words in
                           alphabetical order, so word order and language of the generic part
                           do not matter)                   -> 'de hei'
  word prefixes            the same without the country, for records whose country is missing
                           or differs between the sources   -> 'hei'
Many records share a short key (e.g. 'uni de'), so the rest of the name is appended as a
tie-breaker: inside one key the records are then sorted by name instead of by dataset.

Experiments: every key with w = 5, 10, 20, 40 (effect of the window size), and multi-pass
SNM = union of the candidates of the three keys (w = 10).
For every run: match with Rule1 (PyDI RuleBasedMatcher, as in standard_blocking.py), choose the
threshold on train_data, report P/R/F1, #Corr and time (blocking + matching) on validation_data.

Output: results/snm_blocking_validation.csv
Run (after gold_standard.py): python scripts/sorted_neighbourhood_blocking.py
"""
import logging
import time

import pandas as pd
from PyDI.entitymatching.blocking import SortedNeighbourhoodBlocker

from blocking import OUTPUT_DIR, add_block_text, tokens
from common import RESULTS, load_target
from standard_blocking import MATCHERS, PAIRS, match
from validation import evaluate, load_labelled, pair_completeness, tune_threshold, write_log

logging.basicConfig(level=logging.WARNING)

PREFIX = 3
KEYS = {
    "name prefix + country": "snm_name_cc",
    "country + word prefixes": "snm_cc_words",
    "word prefixes": "snm_words",
}
WINDOWS = [5, 10, 20, 40]
MULTI_PASS_WINDOW = 10


def add_sort_keys(data):
    """Adds the key columns 'snm_*' (key + tie-breaker); empty if a part of the key is missing."""
    for df in data.values():
        cc = df["country_code"].fillna("").str.lower()
        name = df["name_norm"].fillna("")
        words = [sorted(tokens([n])) for n in name]
        df["snm_name_cc"] = [f"{n[:PREFIX]} {c}|{n}" if n and c else "" for n, c in zip(name, cc)]
        df["snm_cc_words"] = [f"{c} {' '.join(t[:PREFIX] for t in w[:2])}|{' '.join(w)}" if c and w else ""
                              for c, w in zip(cc, words)]
        df["snm_words"] = [f"{' '.join(t[:PREFIX] for t in w[:2])}|{' '.join(w)}" if w else "" for w in words]


def has_key(df, col):
    return df[col].fillna("").astype(str).str.strip() != ""


def snm(col, w):
    """Candidates of one SNM pass with window size w (each record vs. the next w-1 records)."""
    def block(left, right):
        l, r = left[has_key(left, col)], right[has_key(right, col)]
        return SortedNeighbourhoodBlocker(l, r, key=col, id_column="id", window=w - 1,
                                          output_dir=OUTPUT_DIR).materialize()
    return block


def multi_pass(cols, w):
    def block(left, right):
        return pd.concat([snm(c, w)(left, right) for c in cols], ignore_index=True)
    return block


def run_blocker(a, b, left, right, train, valid, bname, block_fn):
    """Block, match, choose the threshold on train_data, evaluate on validation_data."""
    total = len(left) * len(right)
    t0 = time.time()
    cand = block_fn(left, right)[["id1", "id2"]].drop_duplicates().reset_index(drop=True)
    t_block = time.time() - t0
    pc = pair_completeness(cand, valid)
    rows = []
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
                         time_s=round(t_block + t_match, 1)))
        print({k: rows[-1][k] for k in ("pair", "blocker", "candidates", "pair_completeness", "precision",
                                          "recall", "f1", "corr", "time_s")}, flush=True)
    return rows


def main():
    data = load_target()
    add_block_text(data)
    add_sort_keys(data)
    rows = []
    for a, b in PAIRS:
        left, right = data[a], data[b]
        train, valid = load_labelled("train", a, b), load_labelled("validation", a, b)
        for kname, col in KEYS.items():
            for w in WINDOWS:
                rows += run_blocker(a, b, left, right, train, valid, f"SNM: {kname} (w={w})", snm(col, w))
        rows += run_blocker(a, b, left, right, train, valid, f"Multi-pass SNM: 3 keys (w={MULTI_PASS_WINDOW})",
                            multi_pass(list(KEYS.values()), MULTI_PASS_WINDOW))
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "snm_blocking_validation.csv", index=False)
    print("log:", write_log(out, "snm_blocking", "Sorted Neighbourhood Method (PyDI SortedNeighbourhoodBlocker)"))
    show = out[["pair", "matcher", "blocker", "candidates", "pair_completeness", "precision", "recall", "f1",
                "corr", "time_s"]]
    print("\nValidation results (P/R/F1 on validation_data, threshold chosen on train_data)\n")
    print(show.rename(columns={"pair_completeness": "PC", "precision": "P", "recall": "R", "f1": "F1",
                               "corr": "#Corr", "time_s": "Time (s)"}).to_string(index=False))


if __name__ == "__main__":
    main()
