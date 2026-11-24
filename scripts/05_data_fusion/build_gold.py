"""Picks 50 universities that are in two or more sources for the fusion gold standard
(40 where the sources disagree, 10 random) and writes gold_candidates.csv.  Usage: python build_gold.py

The correct values of these 50 are then looked up in external sources and checked by hand:
data/golden_set/fusion/fusion_gold.csv."""
import random
import re
import unicodedata
from pathlib import Path

import pandas as pd
from PyDI.io import load_xml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = 2026
CLEANED = {
    "wikidata": ROOT / "scripts/03_schema_mapping/wikidata/filtered/Wikidata_Mapping.xml",
    "ror": ROOT / "scripts/03_schema_mapping/ror/filtered/ROR_Mapping.xml",
    "deqar": ROOT / "scripts/03_schema_mapping/deqar/filtered/deqar_Mapping.xml",
}
CORR = ROOT / "scripts/04_identity_resolution/05_final/results"
FIELDS = {"name": "name", "alt_names": "alternativeNames_alternativeName",
          "country_code": "location_countryCode", "city": "location_city",
          "founding_year": "lifecycle_foundingYear", "website": "web_website",
          "domains": "web_domains_domain"}


def norm(text):
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[\W_]+", " ", text).strip()


def flat(value):
    if isinstance(value, (list, tuple)):
        return " | ".join(str(x) for x in value)
    return "" if pd.isna(value) else str(value)


def main():
    data = {s: load_xml(p, name=s).set_index("id") for s, p in CLEANED.items()}
    partner = {}
    for a in ["wikidata", "deqar"]:
        c = pd.read_csv(CORR / f"correspondences_{a}_ror_r8.csv")
        for x, y in zip(c["id1"], c["id2"]):
            partner.setdefault(y, {})[a] = x

    rows = []
    for ror_id, others in partner.items():
        row = {"anchor_id": ror_id, "sources": "ror | " + " | ".join(sorted(others))}
        ids = {"ror": ror_id, **others}
        for s, rid in ids.items():
            rec = data[s].loc[rid]
            row[f"{s}_id"] = rid
            for f, col in FIELDS.items():
                row[f"{s}_{f}"] = flat(rec[col]) if col in rec else ""
        rows.append(row)
    df = pd.DataFrame(rows).fillna("")

    def differ(field, fn=norm):
        cols = [c for c in df if c.endswith(f"_{field}") and c.split("_")[0] in CLEANED]
        return df[cols].apply(lambda r: len({fn(v) for v in r if str(v).strip()}) > 1, axis=1)

    def year(v):
        return str(v)[:4]

    conflicts = {
        "founding_year": differ("founding_year", year),
        "city": differ("city"),
        "name": differ("name"),
        "domain": df.apply(lambda r: len({frozenset(str(r[c]).split(" | ")) for c in r.index
                                          if c.endswith("_domains") and r[c]}) > 1, axis=1),
        "country": differ("country_code", str),
    }
    rng = random.Random(SEED)
    chosen, why = [], {}
    share = {"founding_year": 12, "city": 10, "name": 10, "domain": 5, "country": 3}
    for attribute, n in share.items():
        pool = [i for i in df.index[conflicts[attribute]] if i not in why]
        for i in rng.sample(pool, min(n, len(pool))):
            why[i] = f"conflict: {attribute}"
    short = 40 - len(why)
    pool = [i for i in df.index if i not in why and any(c[i] for c in conflicts.values())]
    for i in rng.sample(pool, min(short, len(pool))):
        why[i] = "conflict: several"
    pool = [i for i in df.index if i not in why]
    for i in rng.sample(pool, 10):
        why[i] = "random"
    out = df.loc[list(why)].assign(selected_because=[why[i] for i in why])
    out = out.sample(frac=1, random_state=SEED)
    out.to_csv(HERE / "gold_candidates.csv", index=False)
    print(len(df), "universities in two or more sources;", len(out), "selected")
    print(out["selected_because"].value_counts().to_string())


if __name__ == "__main__":
    main()
