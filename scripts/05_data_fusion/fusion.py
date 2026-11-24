"""Data fusion of the cleaned sources with the round 8 correspondences, built like the PyDI
fusion exercise: compares conflict resolution strategies on the gold standard.  Usage: python fusion.py
"""
import logging
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd
from PyDI.fusion import (DataFusionEngine, DataFusionEvaluator, DataFusionStrategy,
                         build_record_groups_from_correspondences, longest_string, median,
                         minimum, prefer_higher_trust, union, voting)
from PyDI.io import load_xml

logging.disable(logging.WARNING)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
GOLD = ROOT / "data" / "golden_set" / "fusion"
CLEANED = {
    "wikidata": ROOT / "scripts/03_schema_mapping/wikidata/filtered/Wikidata_Mapping.xml",
    "ror": ROOT / "scripts/03_schema_mapping/ror/filtered/ROR_Mapping.xml",
    "deqar": ROOT / "scripts/03_schema_mapping/deqar/filtered/deqar_Mapping.xml",
}
CORRESPONDENCES = ROOT / "scripts/04_identity_resolution/05_final/results"

# ROR is curated by its own team, Wikidata by volunteers,
# DEQAR only has what the quality agencies report
TRUST = {"ror": 3, "wikidata": 2, "deqar": 1}
TRUST_WIKIDATA = {"wikidata": 3, "ror": 2, "deqar": 1}

COLUMNS = {
    "name": "name", "alternativeNames_alternativeName": "alt_names", "acronyms_acronym": "acronyms",
    "location_country": "country", "location_countryCode": "country_code", "location_region": "region",
    "location_city": "city", "location_latitude": "latitude", "location_longitude": "longitude",
    "web_website": "website", "web_domains_domain": "domains", "lifecycle_foundingYear": "founding_year",
    "lifecycle_closureYear": "closure_year", "lifecycle_history_event": "history",
    "institutionTypes_institutionType": "types", "numberOfStudents": "students",
    "memberships_membership": "memberships", "parentInstitutions_parentInstitution": "parents",
    "status": "status", "qualityAssurance_numberOfQAReports": "qa_reports",
    "qualityAssurance_lastQAReportDate": "qa_last_report",
}
LISTS = ["alt_names", "acronyms", "domains", "types", "memberships", "parents", "history"]
SCALARS = ["name", "country", "country_code", "region", "city", "website", "founding_year",
           "closure_year", "students", "status", "qa_reports", "qa_last_report"]
EVALUATED = ["name", "country_code", "city", "founding_year", "domains"]
SINGLE = ["name", "country_code", "city", "founding_year"]


def norm(text):
    # same cleaning as in identity resolution: no case, accents, punctuation or leading "the"
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower().replace("&", " and ")
    text = re.sub(r"[\W_]+", " ", text).strip()
    return re.sub(r"^the ", "", text)


def year(value):
    # years as whole numbers, so "1386" and "1386.0" are the same year
    return str(int(float(value)))


def accepted(main, alternatives):
    """The expected value plus its alternatives, empty if there is no expected value."""
    if not split(main):
        return []
    return split(main) + split(alternatives)


def split(value):
    if pd.isna(value) or not str(value).strip():
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def as_list(value):
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    if pd.isna(value) or not str(value).strip():
        return []
    return [str(value)]


# evaluation functions: the gold standard lists every accepted value, e.g. other spellings

def same_text(fused, accepted):
    return norm(fused) in {norm(x) for x in accepted}


def same_year(fused, accepted):
    return year(fused) in {year(x) for x in accepted}


def same_domain(fused, accepted):
    return len({d.lower() for d in as_list(fused)} & set(accepted)) > 0


def same_code(fused, expected):
    return str(fused) == expected


# our own conflict resolution function: voting cannot choose between two sources that disagree,
# trust ignores two sources that agree against the most trusted one

def voting_ties_by_trust(values, sources, source_datasets, trust_map, key=norm, **kwargs):
    """The value most sources agree on (compared with key, as in the evaluation), as the most trusted of
    them writes it; on a tie the value of the most trusted source. PyDI passes the same arguments as to
    prefer_higher_trust."""
    votes = Counter(key(v) for v in values)
    trust = [trust_map.get(source_datasets.get(s), 0) for s in sources]
    best = max(range(len(values)), key=lambda i: (votes[key(values[i])], trust[i]))
    winner = votes[key(values[best])]
    return values[best], winner / len(values), {"rule": "voting_ties_by_trust", "winner_votes": winner,
                                                "selected_dataset": source_datasets.get(sources[best])}


CODES = {}   # record id -> country code, filled in main()


def country_of_code(values, sources, source_datasets, trust_map, **kwargs):
    """The country name of the record whose country code wins voting_ties_by_trust, so that the fused
    country and country code always belong together."""
    codes = [str(CODES.get(s)) for s in sources]
    votes = Counter(codes)
    trust = [trust_map.get(source_datasets.get(s), 0) for s in sources]
    best = max(range(len(values)), key=lambda i: (votes[codes[i]], trust[i]))
    return values[best], votes[codes[best]] / len(values), {"rule": "country_of_code",
                                                             "selected_dataset": source_datasets.get(sources[best])}


def make_strategy(name, rules):
    """rules: attribute -> (function, extra arguments). Lists get union, coordinates the median."""
    s = DataFusionStrategy(name)
    for attribute in LISTS:
        s.add_attribute_fuser(attribute, union)
    for attribute in ["latitude", "longitude"]:
        s.add_attribute_fuser(attribute, median)
    for attribute in SCALARS:
        function, kwargs = rules.get(attribute, rules["other"])
        s.add_attribute_fuser(attribute, function, **kwargs)
    s.add_evaluation_function("name", same_text)
    s.add_evaluation_function("city", same_text)
    s.add_evaluation_function("country_code", same_code)
    s.add_evaluation_function("founding_year", same_year)
    s.add_evaluation_function("domains", same_domain)
    return s


# what we compare (lecture: content-based vs metadata-based conflict resolution)
STRATEGIES = {
    "content-based": {"other": (voting, {}), "name": (longest_string, {}), "website": (longest_string, {}),
                      "founding_year": (minimum, {})},
    "voting": {"other": (voting, {})},
    "trust: ROR first": {"other": (prefer_higher_trust, {})},
    "trust: Wikidata first": {"other": (prefer_higher_trust, {"trust_map": TRUST_WIKIDATA})},
    # ours: the content decides (votes), the metadata (trust) only on a tie
    "voting: ties by trust": {"other": (voting_ties_by_trust, {}),
                              "country_code": (voting_ties_by_trust, {"key": str}),
                              "founding_year": (voting_ties_by_trust, {"key": year})},
}


def load(source):
    df = load_xml(CLEANED[source], name=source).rename(columns=COLUMNS)
    df.attrs["dataset_name"] = source
    df.attrs["trust"] = TRUST[source]
    return df


def load_gold():
    old = pd.read_csv(GOLD / "fusion_gold.csv", dtype=str).assign(subset="first")
    new = pd.read_csv(GOLD / "fusion_gold_new.csv", dtype=str)
    new = new[new["confidence"].str.lower() != "low"]
    new["subset"] = new["selected_because"].map(lambda x: "random" if x == "random" else "conflict")
    gold = pd.concat([old, new], ignore_index=True)

    expected = pd.DataFrame({"eval_id": gold["anchor_id"], "subset": gold["subset"],
                             "country_code": gold["country_code"]})
    expected["name"] = [accepted(a, b) for a, b in zip(gold["name"], gold["name_alternatives"])]
    expected["city"] = [accepted(a, b) for a, b in zip(gold["city"], gold["city_alternatives"])]
    expected["domains"] = [accepted(a, b) for a, b in zip(gold["domain"], gold["domain_alternatives"])]
    expected["founding_year"] = [accepted(a, b) for a, b in
                                 zip(gold["founding_year"], gold["founding_year_alternatives"])]
    return expected


def evaluate(strategy, fused, expected, debug_file=None):
    fused = fused.copy()
    ids = set(expected["eval_id"])
    fused["eval_id"] = [next((s for s in sources if s in ids), None) for sources in fused["_fusion_sources"]]
    fused = fused[["eval_id", "_fusion_sources", "_fusion_metadata", *EVALUATED]]
    expected = expected[expected["eval_id"].isin(set(fused["eval_id"]))]
    if debug_file:
        evaluator = DataFusionEvaluator(strategy, debug=True, debug_file=debug_file)
    else:
        evaluator = DataFusionEvaluator(strategy)
    metrics = evaluator.evaluate(fused_df=fused, fused_id_column="eval_id",
                                 expected_df=expected.drop(columns="subset"), expected_id_column="eval_id")
    row = {"universities": len(expected)}
    for attribute in EVALUATED:
        row[attribute] = round(metrics[f"{attribute}_accuracy"], 3)
    # mean of the unrounded accuracies (averaging the rounded ones can be off by 0.001)
    row["mean"] = round(sum(metrics[f"{a}_accuracy"] for a in EVALUATED) / len(EVALUATED), 3)
    # domains are united in every strategy, so only the single-valued attributes tell them apart
    row["mean single-valued"] = round(sum(metrics[f"{a}_accuracy"] for a in SINGLE) / len(SINGLE), 3)
    return row


def consistency(data, corr):
    """Share of groups where all sources give the same value, counted over the groups in which at
    least two records have a value (a single value cannot disagree with anything)."""
    groups = build_record_groups_from_correspondences(data, corr, id_column="id")
    same, total = {}, {}
    for group in groups:
        if len(group.records) < 2:
            continue
        for attribute in ["name", "country_code", "city", "website", "founding_year"]:
            values = []
            for record in group.records:
                value = record.get(attribute)
                if not isinstance(value, list) and pd.notna(value) and str(value).strip():
                    values.append(str(int(float(value))) if attribute == "founding_year" else norm(value))
            if len(values) < 2:
                continue
            total[attribute] = total.get(attribute, 0) + 1
            if len(set(values)) == 1:
                same[attribute] = same.get(attribute, 0) + 1
    return {a: round(same.get(a, 0) / total[a], 3) for a in total}


def main():
    RESULTS.mkdir(exist_ok=True)
    data = [load(s) for s in CLEANED]
    CODES.update({i: c for d in data for i, c in zip(d["id"], d["country_code"])})
    corr = pd.concat([pd.read_csv(CORRESPONDENCES / f"correspondences_{a}_ror_r8.csv")
                      for a in ["wikidata", "deqar"]], ignore_index=True)
    expected = load_gold()
    print(f"gold standard: {len(expected)} universities ({expected['subset'].value_counts().to_dict()})")

    cons = consistency(data, corr)
    pd.Series(cons, name="consistency").to_csv(RESULTS / "consistency.csv")
    print("consistency before fusion:", cons)

    rows = []
    for name, rules in STRATEGIES.items():
        strategy = make_strategy(name, rules)
        fused = DataFusionEngine(strategy).run(data, corr, id_column="id")
        for subset in ["all", "conflict", "random", "first"]:
            part = expected if subset == "all" else expected[expected["subset"] == subset]
            rows.append({"strategy": name, "gold subset": subset, **evaluate(strategy, fused, part)})
        print(f"  {name}: mean accuracy {rows[-4]['mean']} on {rows[-4]['universities']} universities", flush=True)

    # final strategy: for every evaluated attribute the function that was best on the gold standard
    # (on a tie the one listed first)
    table = pd.DataFrame(rows)
    overall = table[table["gold subset"] == "all"]
    final = {"other": STRATEGIES["trust: ROR first"]["other"]}
    for attribute in SINGLE:
        best = overall.sort_values(attribute, ascending=False, kind="stable").iloc[0]["strategy"]
        rules = STRATEGIES[best]
        final[attribute] = rules.get(attribute, rules["other"])
        print(f"  best for {attribute}: {best}")
    # the country name is not evaluated; it follows the record that gave the country code
    if final["country_code"][0] is voting_ties_by_trust:
        final["country"] = (country_of_code, {})
    strategy = make_strategy("best per attribute", final)
    fused = DataFusionEngine(strategy).run(data, corr, id_column="id")
    for subset in ["all", "conflict", "random", "first"]:
        part = expected if subset == "all" else expected[expected["subset"] == subset]
        debug = RESULTS / "fusion_errors.jsonl" if subset == "all" else None
        rows.append({"strategy": "best per attribute", "gold subset": subset,
                     **evaluate(strategy, fused, part, debug)})
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "strategies.csv", index=False)
    print(table.to_string(index=False))

    fused = DataFusionEngine(strategy).run(data, corr, id_column="id", include_singletons=True)
    keep = ["_id", "_fusion_sources", "_fusion_source_datasets", *[c for c in COLUMNS.values() if c in fused]]
    fused = fused[[c for c in keep if c in fused]]
    fused["sources"] = fused["_fusion_source_datasets"].map(lambda x: " | ".join(sorted(set(x))))
    fused.to_csv(RESULTS / "universities_fused.csv", index=False)

    sizes = fused["_fusion_source_datasets"].map(len).value_counts().sort_index()
    sizes.rename_axis("sources per university").rename("universities").to_csv(RESULTS / "group_sizes.csv")
    print(f"fused universities: {len(fused):,}")
    print(sizes.to_string())

    density = {s.attrs["dataset_name"]: s.drop(columns=["id"]).notna().mean() for s in data}
    density["fused"] = fused.drop(columns=[c for c in fused if c.startswith("_") or c == "sources"]).notna().mean()
    pd.DataFrame(density).round(3).to_csv(RESULTS / "density.csv")
    print(pd.DataFrame(density).round(2).loc[["name", "country_code", "city", "website", "founding_year",
                                               "latitude", "students", "alt_names"]].to_string())


if __name__ == "__main__":
    sys.exit(main())
