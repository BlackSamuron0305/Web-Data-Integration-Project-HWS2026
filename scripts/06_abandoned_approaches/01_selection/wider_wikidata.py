"""Quick check (dropped): select Wikidata by "higher education institution" (Q38723) instead of "university" (Q3918).

Usage (from the repo root):
  python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py fetch   # about 20 minutes
  python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py check

fetch  downloads the items of the wider class that are not in data/wikidata/original/ and, for each, the
       few attributes the Wikidata cleaning rules need (name, country, types, students, ROR id)
       -> results/wider_new_records.csv (snapshot of 24 November 2026)
check  runs the current Wikidata cleaning rules 1-4 on them, counts the overlap with ROR and with the
       fused result, and draws the stratified sample of 200 that AI agents judged
       -> results/summary.csv, results/sample_200.csv
The verdicts of the agents are in results/sample_200_ai_checked.csv (AI, not checked by hand).
"""
import ast
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESULTS = HERE / "results"
NEW = RESULTS / "wider_new_records.csv"
sys.path.insert(0, str(REPO / "scripts" / "01_data_collection"))         # fetch_wikidata.py
sys.path.insert(0, str(REPO / "scripts" / "02_filtering"))              # common.py of the filters
sys.path.insert(0, str(REPO / "scripts" / "02_filtering" / "wikidata"))  # filter.py

WIDER_IDS = "SELECT DISTINCT ?u WHERE { ?u wdt:P31/wdt:P279* wd:Q38723 }"

LIGHT = """
SELECT ?u ?k ?v ?x ?y WHERE {
  VALUES ?u { %s }
  { ?u rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("name" AS ?k) }
  UNION { ?u wdt:P17 ?v . BIND("country" AS ?k) }
  UNION { ?u wdt:P31 ?v . BIND("type" AS ?k) }
  UNION { ?u wdt:P6782 ?v . BIND("ror_id" AS ?k) }
  UNION { ?u p:P2196 ?s . ?s ps:P2196 ?v ; wikibase:rank ?x . OPTIONAL { ?s pq:P585 ?y }
          BIND("students" AS ?k) }
}"""


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def fetch():
    import fetch_wikidata as fw

    wider = fw.unique(fw.qid(b["u"]) for b in fw.sparql(WIDER_IDS))
    ours = set(read(REPO / "data/wikidata/original/wikidata_universities.csv")["wikidata_id"])
    ids = [q for q in wider if q not in ours]
    print(f"wider class: {len(wider)} items, {len(wider) - len(ids)} already ours, {len(ids)} new")

    fw.BATCH = 400
    values = defaultdict(lambda: defaultdict(list))
    students = defaultdict(list)
    for b in fw.run_batched(LIGHT, ids, "attributes"):
        u, key, v = fw.qid(b["u"]), b["k"]["value"], b["v"]
        if key == "students":
            students[u].append((v["value"], b["x"]["value"], b.get("y", {}).get("value", "")))
        elif key in ("country", "type"):
            if fw.qid(v):
                values[u][key].append(fw.qid(v))
        else:
            values[u][key].append(v["value"])

    things = fw.fetch_things(ids, values)
    rows = []
    for u in fw.by_number(ids):
        v = values[u]
        countries = fw.unique(v["country"])
        countries = [c for c in countries if not things[c]["dissolved"]] or countries
        rows.append({
            "wikidata_id": u,
            "name": fw.clean(v["name"][0]) if v["name"] else "",
            "country": fw.SEP.join(fw.labels_of(things, countries)),
            "types": fw.SEP.join(sorted(fw.labels_of(things, fw.unique(v["type"])))),
            "students": fw.pick_students(students[u]),
            "ror_id": fw.SEP.join(sorted(fw.unique(v["ror_id"]))),
        })
    RESULTS.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(NEW, index=False)
    print(f"wrote {NEW.relative_to(REPO).as_posix()} ({len(rows)} rows)")


def check():
    import filter as wf

    new = read(NEW)
    labels = new["types"].apply(wf.clean_types)
    res = [wf.rules_1_to_4(lab, n, s, c) for lab, n, s, c in zip(labels, new["name"], new["students"], new["country"])]
    new["rule"] = [r[0] for r in res]
    kept = new[(new["rule"] == "") & (new["name"] != "")]

    # overlap with ROR and with the fused result
    ours = set(read(REPO / "data/wikidata/original/wikidata_universities.csv")["wikidata_id"])
    ror = read(REPO / "data/ror/filtered/ror_education.csv")
    ror_q = ror["wikidata_id"].str.split(" | ", regex=False).str[0]
    outside = ror[(ror_q != "") & ~ror_q.isin(ours)]
    fused = read(REPO / "scripts/05_data_fusion/results/universities_fused.csv")["_fusion_sources"]
    ror_only = {s[0][4:] for s in map(ast.literal_eval, fused) if len(s) == 1 and s[0].startswith("ror_")}
    kept_ror = kept[kept["ror_id"] != ""]["ror_id"].str.split(" | ", regex=False).str[0]

    summary = {
        "new items in the wider class": len(new),
        "  without an English name": int((new["name"] == "").sum()),
        "  removed by Wikidata rules 1-4": int((new["rule"] != "").sum()),
        "  kept by rules 1-4": len(kept),
        "    of those with a ROR id": len(kept_ror),
        "    linked to a cleaned ROR record": int(kept_ror.isin(set(ror["ror_id"])).sum()),
        "    linked to a ROR-only entry of the fused result": int(kept_ror.isin(ror_only).sum()),
        "cleaned ROR records whose Wikidata item is outside our selection": len(outside),
        "  of those in the wider class": int(outside["wikidata_id"].str.split(" | ", regex=False).str[0]
                                             .isin(set(new["wikidata_id"])).sum()),
    }
    pd.Series(summary, name="count").rename_axis("what").to_csv(RESULTS / "summary.csv")
    print(pd.Series(summary).to_string())
    print("\ntop countries of the kept:", kept["country"].value_counts().head(5).to_dict())

    cols = ["wikidata_id", "name", "country", "types", "students", "ror_id"]
    sample = pd.concat([
        kept[kept["ror_id"] != ""].sample(100, random_state=2026)[cols].assign(stratum="with_ror"),
        kept[kept["ror_id"] == ""].sample(100, random_state=2026)[cols].assign(stratum="without_ror"),
    ])
    sample.to_csv(RESULTS / "sample_200.csv", index=False)
    print("wrote results/summary.csv and results/sample_200.csv")


if __name__ == "__main__":
    {"fetch": fetch, "check": check}[sys.argv[1]]()
