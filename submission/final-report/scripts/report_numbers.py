"""Recompute report numbers that no pipeline script writes, from the repository's own files.
Run from the repo root: python submission/final-report/scripts/report_numbers.py  (needs pandas and PyDI)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "04_identity_resolution"))
from common import links  # noqa: E402  one-to-one identifier links (Sect. 3)

DATA = ROOT / "data"
FINAL = ROOT / "scripts" / "04_identity_resolution" / "global_matching_and_test" / "results"


def relinked_records():
    """Sect. 4.1: records whose first-pass partner was removed by the cleaning and that got a new final link."""
    removed = {s: set(f"{s}_" + pd.read_csv(DATA / s / "filtered" / "removed.csv", dtype=str)[f"{s}_id"])
               for s in ("wikidata", "deqar", "ror")}
    key, total = links(), {"links": 0, "right": 0, "wrong": 0}
    for a in ("wikidata", "deqar"):
        r3 = pd.read_csv(FINAL / f"correspondences_{a}_ror_first_pass.csv")
        gone1, gone2 = r3["id1"].isin(removed[a]), r3["id2"].isin(removed["ror"])
        print(f"Sect. 4.1 {a}-ror: {(gone1 | gone2).sum()} first-pass links to removed records")
        one = r3[gone1 ^ gone2]  # exactly one record of the first-pass link was removed
        kept = set(one.loc[~one["id1"].isin(removed[a]), "id1"]) | set(one.loc[~one["id2"].isin(removed["ror"]), "id2"])
        left = dict(key[(a, "ror")])
        right = {y: x for x, y in key[(a, "ror")]}
        r8 = pd.read_csv(FINAL / f"correspondences_{a}_ror_final.csv")
        new = r8[r8["id1"].isin(kept) | r8["id2"].isin(kept)]
        ok = sum(left.get(x) == y for x, y in zip(new["id1"], new["id2"]))
        bad = sum(left.get(x) != y and (x in left or y in right) for x, y in zip(new["id1"], new["id2"]))
        print(f"Sect. 4.1 {a}-ror: {len(new)} final links of records whose partner was removed;"
              f" identifier links confirm {ok}, contradict {bad}")
        total["links"] += len(new); total["right"] += ok; total["wrong"] += bad
    print(f"Sect. 4.1 together: {total['links']} links, {total['right']} confirmed, {total['wrong']} contradicted"
          "  (report: 44, 24, 12)")


if __name__ == "__main__":
    relinked_records()
