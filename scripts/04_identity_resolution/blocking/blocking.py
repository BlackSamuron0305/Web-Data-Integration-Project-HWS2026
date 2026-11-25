"""Compares the blockers (pair completeness, reduction ratio) and saves their candidate pairs.
Usage: python blocking.py first_pass | final"""
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import EmbeddingBlocker, SortedNeighbourhoodBlocker, StandardBlocker, TokenBlocker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import CANDIDATES, PAIRS, Timer, labels, load_all, log, reset_log, run_argument, slug

RESULTS = Path(__file__).resolve().parent / "results"
LIMIT = 20_000_000   # blockers that would produce more candidate pairs than this are not run

# words too common to group records by (they are in thousands of names)
GENERIC = set("university universitat universite universidad universita college institute school academy "
              "national state technology science sciences of the and de di la der fur und du des".split())


def add_block_keys(left, right, cap=150):
    """Adds the columns the blockers group records by:
    ex_key         first 2 letters of the first 3 words of the name (the key of the exercise)
    name_tokens    every word of 3+ letters of all names of the record
    domain_text    the web domains
    scoped_tokens  country + name word, like DE_heidelberg, without generic words and without keys that
                   more than `cap` records share (those would create too many pairs)"""
    for df in (left, right):
        df["ex_key"] = df["name"].map(lambda n: "".join(t[:2].upper() for t in str(n).split()[:3]) or None)
        df["name_tokens"] = [" ".join({t for n in ns for t in n.split() if len(t) > 2}) for ns in df["names"]]
        df["domain_text"] = df["domains"].map(" ".join)

    def keys(cc, tokens):
        return [f"{cc}_{t}" for t in tokens.split() if t not in GENERIC]

    count = Counter()
    for df in (left, right):
        for cc, tokens in zip(df["cc"], df["name_tokens"]):
            count.update(keys(cc, tokens))
    for df in (left, right):
        df["scoped_tokens"] = [" ".join(k for k in keys(cc, tokens) if count[k] <= cap)
                               for cc, tokens in zip(df["cc"], df["name_tokens"])]


def blockers(L, R):
    # lambdas so a blocker is only built when it is its turn
    kw = dict(id_column="id", output_dir=str(RESULTS / "pydi_output"))
    return {
        "standard: exercise key (2 letters x 3 words)": lambda: StandardBlocker(L, R, on=["ex_key"], **kw),
        "standard: normalised name": lambda: StandardBlocker(L, R, on=["name_norm"], **kw),
        "sorted neighbourhood: name, window 20": lambda: SortedNeighbourhoodBlocker(L, R, key="name_norm", window=20, **kw),
        "token: words of all names": lambda: TokenBlocker(L, R, column="name_tokens", tokenizer=str.split, **kw),
        "token: character 3-grams of the name": lambda: TokenBlocker(L, R, column="name_norm", ngram_size=3, ngram_type="character", **kw),
        "token: country + name word": lambda: TokenBlocker(L, R, column="scoped_tokens", tokenizer=str.split, **kw),
        "token: same web domain": lambda: TokenBlocker(L, R, column="domain_text", tokenizer=str.split, **kw),
        "embedding: name, top 10": lambda: EmbeddingBlocker(L, R, text_cols=["name"], top_k=10, threshold=0.5, **kw),
    }


# a union keeps every pair found by at least one of its blockers
UNIONS = {
    "union: country + name word | same domain":
        ["token: country + name word", "token: same web domain"],
    "union: country + name word | same domain | embedding":
        ["token: country + name word", "token: same web domain", "embedding: name, top 10"],
}


def main(run):
    RESULTS.mkdir(exist_ok=True)
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    log_file = RESULTS / "blocking.csv"
    reset_log(log_file, run)
    data = load_all(run)

    for a, b in PAIRS:
        L, R = data[a], data[b]
        add_block_keys(L, R)
        val = labels(a, b, "validation", run)
        matches = set(map(tuple, val[val["label"]][["id1", "id2"]].values))
        total = len(L) * len(R)

        def report(name, n, seconds, pairs=None):
            # pairs=None means the blocker was skipped as too big
            if pairs is None:
                # n is an estimate that counts a pair once per shared token, so no reduction ratio
                pc, rr, note = "", "", "too many pairs, not run"
                print(f"  {a}-{b} {name}: ~{n:,} pairs, skipped")
            else:
                pc, rr, note = round(len(matches & set(map(tuple, pairs.values))) / len(matches), 4), round(1 - n / total, 6), ""
                print(f"  {a}-{b} {name}: {n:,} pairs, PC {pc:.3f}, RR {rr:.5f}, {seconds}s")
            log(log_file, dict(run=run, pair=f"{a}-{b}", blocker=name, candidates=n,
                               pair_completeness=pc, reduction_ratio=rr, seconds=seconds, note=note))

        report("no blocking (all pairs)", total, "")

        found = {}   # name: (candidate pairs, seconds)
        for name, make in blockers(L, R).items():
            with Timer() as t:
                blocker = make()
                estimate = blocker.estimate_pairs()
                if estimate <= LIMIT:
                    pairs = blocker.materialize()[["id1", "id2"]].drop_duplicates()
            if estimate > LIMIT:
                report(name, estimate, t.seconds)
            else:
                found[name] = (pairs, t.seconds)
                report(name, len(pairs), t.seconds, pairs)

        for name, parts in UNIONS.items():
            if all(p in found for p in parts):
                pairs = pd.concat([found[p][0] for p in parts]).drop_duplicates()
                seconds = round(sum(found[p][1] for p in parts), 1)
                found[name] = (pairs, seconds)
                report(name, len(pairs), seconds, pairs)

        for name, (pairs, _) in found.items():
            pairs.to_csv(CANDIDATES / f"{a}_{b}_{run}_{slug(name)}.csv", index=False)


if __name__ == "__main__":
    main(run_argument())
