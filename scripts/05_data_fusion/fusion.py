"""Data fusion of the cleaned sources with the final correspondences, built like the PyDI
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
                         build_record_groups_from_correspondences, intersection_k_sources,
                         longest_string, median, minimum, prefer_higher_trust, tokenized_match, union,
                         voting)
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
CORRESPONDENCES = ROOT / "scripts/04_identity_resolution/global_matching_and_test/results"

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


def filled(value):
    # a value counts as filled unless it is missing, blank or an empty list
    return len(as_list(value)) > 0


def as_list(value):
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    if pd.isna(value) or not str(value).strip():
        return []
    return [str(value)]


# evaluation functions: compare the fused value with the list of accepted values. Like the exercise we
# compare texts twice: strictly (exactly as written) and tolerantly (case, accents, punctuation and word
# order are ignored, and up to a fifth of the words may differ: PyDI's tokenized_match, threshold 0.8)

def same_text_strict(fused, accepted):
    return str(fused) in set(accepted)


# letters that NFKD does not split into a base letter and an accent
LETTERS = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ı": "i",
                         "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"})


def same_text_tolerant(fused, accepted):
    fused = norm(str(fused).translate(LETTERS))
    return any(tokenized_match(fused, norm(x.translate(LETTERS)), threshold=0.8) for x in accepted)


def same_year(fused, accepted):
    return year(fused) in {year(x) for x in accepted}


def same_domain(fused, accepted):
    """Strict for lists: at least one fused domain is accepted and every fused domain is accepted (or a
    subdomain of an accepted one), so a function that keeps a wrong domain counts as wrong."""
    fused = {d.lower() for d in as_list(fused)}
    ok = {d.lower() for d in accepted}
    return bool(fused & ok) and all(any(d == a or d.endswith("." + a) for a in ok) for d in fused)


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


def make_strategy(name, rules, comparison="tolerant"):
    """rules: attribute -> (function, extra arguments). Lists get union and coordinates the median,
    unless rules says otherwise. comparison: how names and cities are compared with the gold standard."""
    s = DataFusionStrategy(name)
    for attribute in LISTS:
        function, kwargs = rules.get(attribute, (union, {}))
        s.add_attribute_fuser(attribute, function, **kwargs)
    for attribute in ["latitude", "longitude"]:
        function, kwargs = rules.get(attribute, (median, {}))
        s.add_attribute_fuser(attribute, function, **kwargs)
    for attribute in SCALARS:
        function, kwargs = rules.get(attribute, rules["other"])
        s.add_attribute_fuser(attribute, function, **kwargs)
    same_text = same_text_tolerant if comparison == "tolerant" else same_text_strict
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

# what we compare for lists (lecture: union, intersection, intersection of k sources, favour sources);
# only domains are in the gold standard, so only domains can be scored
LIST_FUNCTIONS = {
    "union": (union, {}),
    "in at least 2 sources": (intersection_k_sources, {"k": 2}),
    "trust: ROR first": (prefer_higher_trust, {}),
    "trust: Wikidata first": (prefer_higher_trust, {"trust_map": TRUST_WIKIDATA}),
}


def load(source):
    df = load_xml(CLEANED[source], name=source).rename(columns=COLUMNS)
    df.attrs["dataset_name"] = source
    df.attrs["trust"] = TRUST[source]
    return df


def load_gold():
    """The fusion gold standard in the target schema (gold_to_xml.py writes it from fusion_gold.csv): 80
    universities, values looked up in external sources. Every accepted value of a name (name and
    alternativeNames) and of the domains counts as correct; city and founding year have one value."""
    gold = load_xml(GOLD / "fusion_gold.xml", name="gold").rename(columns=COLUMNS)
    # from build_gold.py: why each university was drawn (conflicting sources or random) and its half
    # ("choose": to choose the function per attribute, "test": to measure the accuracy of that choice)
    drawn = pd.read_csv(HERE / "gold_candidates.csv", dtype=str).set_index("anchor_id")
    expected = pd.DataFrame({"eval_id": gold["id"], "country_code": gold["country_code"]})
    expected["subset"] = gold["id"].map(drawn["selected_because"]).map(lambda x: "random" if x == "random"
                                                                         else "conflict")
    expected["half"] = gold["id"].map(drawn["half"])
    expected["name"] = [as_list(n) + as_list(a) for n, a in zip(gold["name"], gold["alt_names"])]
    expected["city"] = gold["city"].map(as_list)
    expected["domains"] = gold["domains"].map(as_list)
    expected["founding_year"] = gold["founding_year"].map(as_list)
    return expected


def evaluate(strategy, fused, expected, debug_file=None, attributes=EVALUATED):
    fused = fused.copy()
    ids = set(expected["eval_id"])
    fused["eval_id"] = [next((s for s in sources if s in ids), None) for sources in fused["_fusion_sources"]]
    fused = fused[["eval_id", "_fusion_sources", "_fusion_metadata", *attributes]]
    expected = expected[expected["eval_id"].isin(set(fused["eval_id"]))][["eval_id", *attributes]]
    if debug_file:
        evaluator = DataFusionEvaluator(strategy, debug=True, debug_file=debug_file)
    else:
        evaluator = DataFusionEvaluator(strategy)
    metrics = evaluator.evaluate(fused_df=fused, fused_id_column="eval_id",
                                 expected_df=expected, expected_id_column="eval_id")
    row = {"universities": len(expected)}
    for attribute in attributes:
        row[attribute] = round(metrics[f"{attribute}_accuracy"], 3)
    if attributes != EVALUATED:
        return row
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
    corr = pd.concat([pd.read_csv(CORRESPONDENCES / f"correspondences_{a}_ror_final.csv")
                      for a in ["wikidata", "deqar"]], ignore_index=True)
    expected = load_gold()
    print(f"gold standard: {len(expected)} universities ({expected['subset'].value_counts().to_dict()}, "
          f"{expected['half'].value_counts().to_dict()})")

    def parts():
        # the whole gold standard, its two halves, and the universities drawn for a conflict or at random
        yield "all", expected
        for half in ["choose", "test"]:
            yield half, expected[expected["half"] == half]
        for subset in ["conflict", "random"]:
            yield subset, expected[expected["subset"] == subset]

    cons = consistency(data, corr)
    pd.Series(cons, name="consistency").to_csv(RESULTS / "consistency.csv")
    print("consistency before fusion:", cons)

    def score(name, rules, fused, debug_file=None):
        """Accuracy of one fused result, compared strictly and tolerantly, on all, conflict and random."""
        out = []
        for comparison in ["strict", "tolerant"]:
            strategy = make_strategy(name, rules, comparison)
            for subset, part in parts():
                debug = debug_file if comparison == "tolerant" and subset == "test" else None
                out.append({"strategy": name, "comparison": comparison, "gold subset": subset,
                            **evaluate(strategy, fused, part, debug)})
        return out

    rows = []
    for name, rules in STRATEGIES.items():
        fused = DataFusionEngine(make_strategy(name, rules)).run(data, corr, id_column="id")
        rows += score(name, rules, fused)
        acc = {(r["comparison"], r["gold subset"]): r["mean"] for r in rows if r["strategy"] == name}
        print(f"  {name}: mean accuracy on the choose half {acc['tolerant', 'choose']} (tolerant), "
              f"{acc['strict', 'choose']} (strict)", flush=True)

    # lists: the functions for domains, everything else as in "trust: ROR first"
    list_rows = []
    for name, rule in LIST_FUNCTIONS.items():
        strategy = make_strategy(f"domains: {name}", {**STRATEGIES["trust: ROR first"], "domains": rule})
        fused = DataFusionEngine(strategy).run(data, corr, id_column="id")
        kept = fused["domains"].map(lambda v: len(as_list(v)))
        for subset, part in parts():
            list_rows.append({"function": name, "gold subset": subset,
                              **evaluate(strategy, fused, part, attributes=["domains"]),
                              "domains per university": round(kept.mean(), 2),
                              "universities without domain": int((kept == 0).sum())})
        print(f"  domains, {name}: accuracy on the choose half {list_rows[-4]['domains']}", flush=True)
    lists = pd.DataFrame(list_rows)
    lists.to_csv(RESULTS / "list_functions.csv", index=False)

    # final strategy: for every evaluated attribute the function that was best on the "choose" half of the
    # gold standard (lecture: choose on a validation part of the ground truth), compared tolerantly as in
    # the exercise, the first listed on a tie. Its accuracy is then measured on the "test" half.
    table = pd.DataFrame(rows)
    overall = table[(table["gold subset"] == "choose") & (table["comparison"] == "tolerant")]
    final = {"other": STRATEGIES["trust: ROR first"]["other"]}
    best = lists[lists["gold subset"] == "choose"].sort_values("domains", ascending=False, kind="stable").iloc[0]
    final["domains"] = LIST_FUNCTIONS[best["function"]]
    print(f"  best for domains: {best['function']}")
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
    rows += score("best per attribute", final, fused, RESULTS / "fusion_errors.jsonl")
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

    # density (lecture): share of filled values per attribute of the target schema, in each source, in the
    # fused table, and in the fused universities that contain a ROR record (ROR is the largest source, so
    # these are ROR's universities after fusion). Per attribute, a source without that attribute is left
    # blank; in the row "all attributes" (the mean over all of them, to compare whole tables) it counts as 0.
    attributes = list(COLUMNS.values())
    with_ror = fused["_fusion_source_datasets"].map(lambda x: "ror" in x)
    tables = {s.attrs["dataset_name"]: s for s in data}
    tables["fused"] = fused
    tables["fused, with ROR record"] = fused[with_ror]
    density = pd.DataFrame({name: [t[a].map(filled).mean() if a in t else None for a in attributes]
                            for name, t in tables.items()}, index=attributes, dtype=float)
    density.loc["all attributes"] = density.fillna(0).mean()
    density.loc["universities"] = [len(t) for t in tables.values()]
    density.round(3).to_csv(RESULTS / "density.csv")
    print(density.round(3).loc[["name", "city", "founding_year", "students", "all attributes",
                                "universities"]].to_string())


if __name__ == "__main__":
    sys.exit(main())
