"""Multi-pass sorted neighbourhood (lecture, slide 31): sorted neighbourhood run several times with simple
keys and window 20, the pairs of all passes merged. Measures pair completeness on the validation pairs,
alone and added to the union the matchers use, and writes results/multi_pass_snm.csv.
It only tests the method; the candidate pairs of the matchers stay those of blocking.py.
Usage: python multi_pass_snm.py first_pass | final"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import SortedNeighbourhoodBlocker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blocking import GENERIC, RESULTS
from common import BLOCKER, PAIRS, Timer, candidates, labels, load_all, run_argument, translate

WINDOW = 20


def add_keys(df):
    # the keys of the passes; an empty key becomes None
    def words(names):
        # the words of the translated main name in alphabetical order: "heidelberg university" for both
        # "Universitat Heidelberg" and "Heidelberg University"
        return " ".join(sorted(set(translate(names).split()) - GENERIC)) or None

    df["snm_name"] = df["name_norm"].replace("", None)
    df["snm_words"] = df["name_norm"].map(words)
    df["snm_domain"] = df["domains"].map(lambda d: d[0].removeprefix("www.") if d else None)
    df["snm_place"] = [f"{cc} {city} {name}" if cc and city else None
                       for cc, city, name in zip(df["cc"], df["city_norm"], df["name_norm"])]


PASSES = {
    "name": "snm_name",
    "name words, sorted": "snm_words",
    "web domain": "snm_domain",
    "country + city + name": "snm_place",
}


def main(run):
    data = load_all(run)
    rows = []
    for a, b in PAIRS:
        L, R = data[a], data[b]
        for df in (L, R):
            add_keys(df)
        val = labels(a, b, "validation", run)
        matches = set(map(tuple, val[val["label"]][["id1", "id2"]].values))
        total = len(L) * len(R)
        union = set(map(tuple, candidates(a, b, run)[["id1", "id2"]].values))

        def report(name, pairs, seconds):
            pc = len(matches & pairs) / len(matches)
            extra = len((matches & pairs) - union)
            rows.append(dict(run=run, pair=f"{a}-{b}", blocker=name, candidates=len(pairs),
                             pair_completeness=round(pc, 4), reduction_ratio=round(1 - len(pairs) / total, 6),
                             seconds=seconds, matches_not_in_union=extra))
            print(f"  {a}-{b} {name}: {len(pairs):,} pairs, PC {pc:.3f}, {extra} matches the union misses, "
                  f"{seconds}s", flush=True)

        merged, seconds = set(), 0.0
        for name, key in PASSES.items():
            with Timer() as t:
                left, right = L[L[key].notna()], R[R[key].notna()]
                blocker = SortedNeighbourhoodBlocker(left, right, key=key, window=WINDOW, id_column="id",
                                                     output_dir=str(RESULTS / "pydi_output"))
                pairs = set(map(tuple, blocker.materialize()[["id1", "id2"]].values))
            merged |= pairs
            seconds += t.seconds
            report(f"sorted neighbourhood pass: {name}", pairs, t.seconds)
        report("sorted neighbourhood, multi-pass (all 4 merged)", merged, round(seconds, 1))
        report(f"{BLOCKER} + multi-pass", union | merged, round(seconds, 1))
        missed = matches - union - merged
        print(f"  {a}-{b}: {len(matches)} validation matches, {len(matches - union)} missed by the union, "
              f"{len(missed)} missed by both", flush=True)

    out = RESULTS / "multi_pass_snm.csv"
    old = pd.read_csv(out) if out.exists() else pd.DataFrame()
    if len(old):
        old = old[old["run"] != run]
    pd.concat([old, pd.DataFrame(rows)]).to_csv(out, index=False)


if __name__ == "__main__":
    main(run_argument())
