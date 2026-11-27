"""Recompute report numbers that no pipeline script writes, from the repository's own files.
Run from the repo root: python submission/final-report/scripts/report_numbers.py  (needs pandas and PyDI)."""
import re
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


def fusion_limitations():
    """Sect. 5 limitations: how often each source's own value is right on the fusion gold standard (head to
    head, where exactly one of two sources is right), how often two wrong sources give the same wrong value,
    how often the sources store each other's IDs, and wrong founding years that are alternative dates."""
    sys.path.insert(0, str(ROOT / "scripts" / "05_data_fusion"))
    import fusion as F  # same loading and evaluation functions as the fusion step
    data = {d.attrs["dataset_name"]: d.set_index("id") for d in (F.load(s) for s in F.CLEANED)}
    partner = {}
    for a in ("wikidata", "deqar"):
        for x, y in pd.read_csv(FINAL / f"correspondences_{a}_ror_final.csv")[["id1", "id2"]].itertuples(index=False):
            partner.setdefault(y, {})[a] = x
    gold = F.load_gold().set_index("eval_id")
    checks = {"name": (F.same_text_tolerant, F.norm), "country_code": (F.same_code, str),
              "city": (F.same_text_tolerant, F.norm), "founding_year": (F.same_year, F.year),
              "website": (F.same_website, F.host)}
    right = {}   # (gold id, attribute, source) -> (is right, comparable value)
    for gid, g in gold.iterrows():
        ids = {"ror": gid, **partner.get(gid, {})}
        if len(ids) < 2:
            continue
        for attr, (check, key) in checks.items():
            if not g[attr]:
                continue
            for s, i in ids.items():
                v = data[s].loc[i].get(attr)
                if isinstance(v, str) and v.strip():
                    right[gid, attr, s] = (bool(check(v, g[attr])), key(v))
    for a, b in (("ror", "deqar"), ("ror", "wikidata"), ("wikidata", "deqar")):
        both = [(right[k[0], k[1], a], right[k[0], k[1], b]) for k in right if k[2] == a and (k[0], k[1], b) in right]
        print(f"Sect. 5 {a} vs {b}: only {a} right {sum(x[0] and not y[0] for x, y in both)}, "
              f"only {b} right {sum(y[0] and not x[0] for x, y in both)}  (fusion README: 18-10, 35-17, 10-12)")
    wrong = [(right[k[0], k[1], a], right[k[0], k[1], b]) for k in right
             for a, b in (("ror", "wikidata"), ("ror", "deqar"), ("wikidata", "deqar"))
             if k[2] == a and (k[0], k[1], b) in right and not right[k][0] and not right[k[0], k[1], b][0]]
    print(f"Sect. 5 two sources both wrong: {len(wrong)}, the same wrong value {sum(x[1] == y[1] for x, y in wrong)}"
          "  (report and fusion README: 15 of 34)")
    ror = pd.read_csv(DATA / "ror" / "filtered" / "ror_education.csv", dtype=str, keep_default_na=False)
    print(f"Sect. 5 ROR records with a Wikidata ID: {(ror['wikidata_id'] != '').mean():.0%}  (fusion README: 75%)")
    # copied facts would be written alike: linked websites written exactly alike, points within 100 m
    for a in ("wikidata", "deqar"):
        c = pd.read_csv(FINAL / f"correspondences_{a}_ror_final.csv")
        w = [(data[a].loc[x].get("website"), data["ror"].loc[y].get("website")) for x, y in zip(c["id1"], c["id2"])]
        w = [(u, v) for u, v in w if isinstance(u, str) and isinstance(v, str)]
        print(f"Sect. 5 {a}-ror websites written exactly alike: {sum(u == v for u, v in w) / len(w):.0%} of {len(w):,}, "
              f"same host {sum(F.host(u) == F.host(v) for u, v in w) / len(w):.0%}  (fusion README)")
        if a == "wikidata":
            pts = [(F.point(data[a].loc[x].get("latitude"), data[a].loc[x].get("longitude")),
                    F.point(data["ror"].loc[y].get("latitude"), data["ror"].loc[y].get("longitude")))
                   for x, y in zip(c["id1"], c["id2"])]
            d = [F.km(u, v) for u, v in pts if u and v]
            print(f"Sect. 5 wikidata-ror points within 100 m: {sum(x <= 0.1 for x in d) / len(d):.1%} of {len(d):,}"
                  "  (fusion README)")
    csv = pd.read_csv(DATA / "golden_set" / "fusion" / "fusion_gold.csv", dtype=str, keep_default_na=False)
    alts = {r.anchor_id: set(r.founding_year_alternatives.replace("|", ",").split(",")) - {""}
            for r in csv.itertuples()}
    errors = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "fusion_errors.csv", dtype=str)
    errors = errors[errors["attribute"] == "founding_year"].to_dict("records")
    print(f"Sect. 5 gold universities with alternative founding dates: {sum(bool(x) for x in alts.values())} of "
          f"{len(alts)}; wrong founding years on the test half: {len(errors)}, of them an alternative date: "
          f"{sum(F.year(e['fused_value']) in alts[e['id']] for e in errors)}  (report: 54 of 80, fusion README: 3 of 9)")
    # parent institutions: ROR parents whose name lookup failed are still a ROR ID
    parents = [p for ps in data["ror"]["parents"].dropna() for p in F.as_list(ps)]
    raw = sum(bool(re.fullmatch(r"0[a-z0-9]{8}", p)) for p in parents)
    print(f"Sect. 5 ROR parent institutions that are still a ROR ID: {raw} of {len(parents):,}  (fusion README)")


if __name__ == "__main__":
    relinked_records()
    fusion_limitations()
