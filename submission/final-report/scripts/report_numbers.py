"""Recompute report numbers that no pipeline script writes, from the repository's own files.
Run from the repo root: python submission/final-report/scripts/report_numbers.py  (needs pandas and PyDI)."""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "04_identity_resolution"))
from common import links  # noqa: E402  one-to-one identifier links (Sect. 3)

DATA, FUSED = ROOT / "data", ROOT / "scripts" / "05_data_fusion" / "results"
FINAL = ROOT / "scripts" / "04_identity_resolution" / "05_final" / "results"


def relinked_records():
    """Sect. 4.1: records whose round-3 partner was removed by the cleaning and that got a new final link."""
    removed = {s: set(f"{s}_" + pd.read_csv(DATA / s / "filtered" / "removed.csv", dtype=str)[f"{s}_id"])
               for s in ("wikidata", "deqar", "ror")}
    key, total = links(), {"links": 0, "right": 0, "wrong": 0}
    for a in ("wikidata", "deqar"):
        r3 = pd.read_csv(FINAL / f"correspondences_{a}_ror_r3.csv")
        gone1, gone2 = r3["id1"].isin(removed[a]), r3["id2"].isin(removed["ror"])
        one = r3[gone1 ^ gone2]  # exactly one record of the round-3 link was removed
        kept = set(one.loc[~one["id1"].isin(removed[a]), "id1"]) | set(one.loc[~one["id2"].isin(removed["ror"]), "id2"])
        left = dict(key[(a, "ror")])
        right = {y: x for x, y in key[(a, "ror")]}
        r8 = pd.read_csv(FINAL / f"correspondences_{a}_ror_r8.csv")
        new = r8[r8["id1"].isin(kept) | r8["id2"].isin(kept)]
        ok = sum(left.get(x) == y for x, y in zip(new["id1"], new["id2"]))
        bad = sum(left.get(x) != y and (x in left or y in right) for x, y in zip(new["id1"], new["id2"]))
        print(f"Sect. 4.1 {a}-ror: {len(new)} final links of records whose partner was removed;"
              f" identifier links confirm {ok}, contradict {bad}")
        total["links"] += len(new); total["right"] += ok; total["wrong"] += bad
    print(f"Sect. 4.1 together: {total['links']} links, {total['right']} confirmed, {total['wrong']} contradicted"
          "  (report: 70, 33, 22)")


def fused_checks():
    """Sect. 5 and 6: LLM verdicts on all fused entries (ai_check_fused.csv, column in_scope) by number of sources,
    and what one more name rule would remove."""
    ai = pd.read_csv(FUSED / "ai_check_fused.csv")
    no = ai[ai["in_scope"] == "no"]
    for n in (1, 2, 3):
        print(f"Sect. 5  {n} source(s): {(no['n_sources'] == n).sum():,} of {(ai['n_sources'] == n).sum():,}"
              f" judged not a university = {(no['n_sources'] == n).sum() / (ai['n_sources'] == n).sum():.1%}"
              "  (report: 20.5%, 1.8%, 0.2%)")
    fused = pd.read_csv(FUSED / "universities_fused.csv", usecols=["_fusion_source_datasets"])
    ai = ai.assign(datasets=fused["_fusion_source_datasets"].astype(str).values)  # same row order (fid = n<row>)
    # the higher-education words of the ROR filter (scripts/02_filtering/ror/filter.py)
    words = re.compile(r"universit|college|school|academy|institute of technology|polytechn|hochschule", re.I)
    sel = ai[(ai["datasets"] == "['ror']") & ~ai["name"].astype(str).str.contains(words)]
    v = sel["in_scope"].value_counts()
    print(f"Sect. 6  ROR-only entries without a higher-education word: {len(sel):,}; not a university"
          f" {v.get('no', 0):,}, university {v.get('yes', 0):,}, unsure {v.get('unsure', 0):,}"
          "  (report: 1,461 and 2,729)")


if __name__ == "__main__":
    relinked_records()
    fused_checks()
