"""Blocking.  Usage: python blocking.py <round>"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import EmbeddingBlocker, SortedNeighbourhoodBlocker, StandardBlocker, TokenBlocker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import CANDIDATES, PAIRS, Timer, add_block_keys, labels, load_all, log, reset_log, slug

RESULTS = Path(__file__).resolve().parent / "results"
LIMIT = 20_000_000   # skip blockers with more candidate pairs than this


def blockers(L, R, round_):
    kw = dict(id_column="id", output_dir=str(RESULTS / "pydi_output"))
    words = str.split
    b = {
        "standard: exercise key (2 letters x 3 words)": lambda: StandardBlocker(L, R, on=["ex_key"], **kw),
        "standard: normalised name": lambda: StandardBlocker(L, R, on=["name_norm"], **kw),
        "sorted neighbourhood: name, window 20": lambda: SortedNeighbourhoodBlocker(L, R, key="name_norm", window=20, **kw),
        "token: words of all names": lambda: TokenBlocker(L, R, column="name_tokens", tokenizer=words, **kw),
    }
    if round_ >= 2:
        b["token: character 3-grams of the name"] = lambda: TokenBlocker(L, R, column="name_norm", ngram_size=3, ngram_type="character", **kw)
        b["token: country + name word"] = lambda: TokenBlocker(L, R, column="scoped_tokens", tokenizer=words, **kw)
        b["token: same web domain"] = lambda: TokenBlocker(L, R, column="domain_text", tokenizer=words, **kw)
        b["embedding: name, top 10"] = lambda: EmbeddingBlocker(L, R, text_cols=["name"], top_k=10, threshold=0.5, **kw)
    return b


UNIONS = {
    "union: country + name word | same domain":
        ["token: country + name word", "token: same web domain"],
    "union: country + name word | same domain | embedding":
        ["token: country + name word", "token: same web domain", "embedding: name, top 10"],
}


def main(round_):
    RESULTS.mkdir(exist_ok=True)
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    log_file = RESULTS / "blocking.csv"
    reset_log(log_file, round_)
    data = load_all(round_)

    for a, b in PAIRS:
        L, R = data[a], data[b]
        add_block_keys(L, R)
        val = labels(a, b, "validation", round_)
        matches = set(map(tuple, val[val["label"]][["id1", "id2"]].values))
        total = len(L) * len(R)

        def report(name, n, seconds, pairs=None):
            if pairs is None:
                pc, note = "", "too many pairs, not run"
                print(f"  {a}-{b} {name}: ~{n:,} pairs, skipped")
            else:
                pc, note = round(len(matches & set(map(tuple, pairs.values))) / len(matches), 4), ""
                print(f"  {a}-{b} {name}: {n:,} pairs, PC {pc:.3f}, RR {1 - n / total:.5f}, {seconds}s")
            log(log_file, dict(round=round_, pair=f"{a}-{b}", blocker=name, candidates=n,
                               pair_completeness=pc, reduction_ratio=round(1 - n / total, 6),
                               seconds=seconds, note=note))

        report("no blocking (all pairs)", total, "")

        found = {}
        for name, make in blockers(L, R, round_).items():
            with Timer() as t:
                blocker = make()
                estimate = blocker.estimate_pairs() if hasattr(blocker, "estimate_pairs") else None
                too_big = estimate is not None and estimate > LIMIT
                if not too_big:
                    pairs = blocker.materialize()[["id1", "id2"]].drop_duplicates()
            if too_big:
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
            pairs.to_csv(CANDIDATES / f"{a}_{b}_r{round_}_{slug(name)}.csv", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]))
