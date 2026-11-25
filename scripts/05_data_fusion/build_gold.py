"""Picks the universities of the fusion gold standard and writes gold_candidates.csv.
Usage: python build_gold.py

All are in two or more sources; four in five are drawn because their sources disagree on a value, one in
five at random. The first 50 (40 + 10) were drawn first; 30 more (24 + 6) were added later so that the
gold standard can be split into two halves of 40: one to choose the conflict resolution function per
attribute, one to measure the accuracy of that choice (column `half`). Universities already in
gold_candidates.csv are kept as they are and never drawn again.

The correct values are then looked up in external sources and checked by hand:
data/golden_set/fusion/fusion_gold.csv."""
import random
import re
import unicodedata
from pathlib import Path

import pandas as pd
from PyDI.io import load_xml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "gold_candidates.csv"
SEED = 2026
CLEANED = {
    "wikidata": ROOT / "scripts/03_schema_mapping/wikidata/filtered/Wikidata_Mapping.xml",
    "ror": ROOT / "scripts/03_schema_mapping/ror/filtered/ROR_Mapping.xml",
    "deqar": ROOT / "scripts/03_schema_mapping/deqar/filtered/deqar_Mapping.xml",
}
CORR = ROOT / "scripts/04_identity_resolution/global_matching_and_test/results"
FIELDS = {"name": "name", "alt_names": "alternativeNames_alternativeName",
          "country_code": "location_countryCode", "city": "location_city",
          "founding_year": "lifecycle_foundingYear", "website": "web_website",
          "domains": "web_domains_domain"}
# how many are drawn per conflicting attribute, then how many with any conflict, then at random
DRAWS = [
    {"conflict": {"founding_year": 12, "city": 10, "name": 10, "domain": 5, "country": 3},
     "any conflict": 40, "random": 10},                                    # the first 50
    {"conflict": {"founding_year": 7, "city": 6, "name": 6, "domain": 3, "country": 2},
     "any conflict": 24, "random": 6},                                     # 30 added later
]


def norm(text):
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[\W_]+", " ", text).strip()


def flat(value):
    if isinstance(value, (list, tuple)):
        return " | ".join(str(x) for x in value)
    return "" if pd.isna(value) else str(value)


def candidates():
    """Every ROR record with a partner, with the values of each source, and which attributes conflict."""
    data = {s: load_xml(p, name=s).set_index("id") for s, p in CLEANED.items()}
    partner = {}
    for a in ["wikidata", "deqar"]:
        c = pd.read_csv(CORR / f"correspondences_{a}_ror_final.csv")
        for x, y in zip(c["id1"], c["id2"]):
            partner.setdefault(y, {})[a] = x

    rows = []
    for ror_id, others in partner.items():
        row = {"anchor_id": ror_id, "sources": "ror | " + " | ".join(sorted(others))}
        for s, rid in {"ror": ror_id, **others}.items():
            rec = data[s].loc[rid]
            row[f"{s}_id"] = rid
            for f, col in FIELDS.items():
                row[f"{s}_{f}"] = flat(rec[col]) if col in rec else ""
        rows.append(row)
    df = pd.DataFrame(rows).fillna("").set_index("anchor_id", drop=False)

    def differ(field, fn=norm):
        cols = [c for c in df if c.endswith(f"_{field}") and c.split("_")[0] in CLEANED]
        return df[cols].apply(lambda r: len({fn(v) for v in r if str(v).strip()}) > 1, axis=1)

    conflicts = {
        "founding_year": differ("founding_year", lambda v: str(v)[:4]),
        "city": differ("city"),
        "name": differ("name"),
        "domain": df.apply(lambda r: len({frozenset(str(r[c]).split(" | ")) for c in r.index
                                          if c.endswith("_domains") and r[c]}) > 1, axis=1),
        "country": differ("country_code", str),
    }
    return df, conflicts


def draw(df, conflicts, taken, plan, rng):
    """Draws plan["conflict"] per attribute, fills up to plan["any conflict"], then plan["random"]."""
    why = {}
    for attribute, n in plan["conflict"].items():
        pool = [i for i in df.index[conflicts[attribute]] if i not in why and i not in taken]
        for i in rng.sample(pool, min(n, len(pool))):
            why[i] = f"conflict: {attribute}"
    pool = [i for i in df.index if i not in why and i not in taken and any(c[i] for c in conflicts.values())]
    for i in rng.sample(pool, min(plan["any conflict"] - len(why), len(pool))):
        why[i] = "conflict: several"
    pool = [i for i in df.index if i not in why and i not in taken]
    for i in rng.sample(pool, plan["random"]):
        why[i] = "random"
    return why


def main():
    df, conflicts = candidates()
    print(len(df), "universities in two or more sources")
    # universities drawn before stay as they were (with the source values seen when they were drawn)
    old = pd.read_csv(OUT, dtype=str, keep_default_na=False) if OUT.exists() else pd.DataFrame()
    batches = [old.drop(columns=["half"], errors="ignore")] if len(old) else []
    taken = set(old["anchor_id"]) if len(old) else set()
    total = 0
    for k, plan in enumerate(DRAWS):
        total += plan["any conflict"] + plan["random"]
        if len(taken) >= total:
            continue   # this draw was done before
        rng = random.Random(SEED + k)
        why = draw(df, conflicts, taken, plan, rng)
        new = df.loc[list(why)].assign(selected_because=[why[i] for i in why])
        batches.append(new.sample(frac=1, random_state=SEED))
        taken |= set(why)
        print(f"draw {k + 1}: {len(why)} added")
    out = pd.concat(batches, ignore_index=True).fillna("")

    # two halves with the same mix of conflict and random: one to choose the functions, one to test them
    rng = random.Random(SEED)
    half = {}
    for _, group in out.groupby(out["selected_because"] == "random"):
        ids = sorted(group["anchor_id"])
        rng.shuffle(ids)
        for j, i in enumerate(ids):
            half[i] = "choose" if j % 2 == 0 else "test"
    out["half"] = out["anchor_id"].map(half)
    out.to_csv(OUT, index=False)
    print(len(out), "in", OUT.name)
    print(pd.crosstab(out["selected_because"], out["half"]).to_string())


if __name__ == "__main__":
    main()
