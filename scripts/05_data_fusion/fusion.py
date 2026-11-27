"""Data fusion of the cleaned sources with the final correspondences, built like the PyDI
fusion exercise: compares conflict resolution strategies on the gold standard.  Usage: python fusion.py
"""
import json
import logging
import math
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

import fused_to_xml

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
# scored too, but left out of both means: the gold standard holds no website of its own (its accepted
# domains decide), and its coordinates come from a geocoder (column coordinates_source)
EXTRA = ["website"]
# a fused point is right if it lies this close to the gold point: strict (the campus), tolerant (the same
# part of the city). Fixed before the coordinates were evaluated.
NEAR_KM = {"strict": 1, "tolerant": 5}
# sensitivity: the same shares for stricter and looser limits (only reported, the choice stays at 5 km)
SENSITIVITY_KM = [0.1, 0.5, 1, 5, 10]


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


def host(url):
    """The host of a website without scheme, "www." and path: "https://www.x.edu/en/" is "x.edu"."""
    url = re.sub(r"^[a-z][a-z0-9+.-]*://", "", str(url).strip().lower())
    url = re.split(r"[/?#:]", url, maxsplit=1)[0]
    return re.sub(r"^www\d*\.", "", url).rstrip(".")


def same_website(fused, accepted):
    """The gold standard has no website of its own, so its accepted domains decide: the website is right
    when its host is one of them. A subdomain (eng.x.edu) counts as wrong, as in the domain lists."""
    return host(fused) in {d.lower() for d in accepted}


def km(a, b):
    """Great-circle distance in km between two (latitude, longitude) points."""
    (la1, lo1), (la2, lo2) = [(math.radians(float(x)), math.radians(float(y))) for x, y in (a, b)]
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def near(limit):
    def same_place(fused, expected):
        return km(fused, expected) <= limit
    same_place.__name__ = f"within_{limit}_km"
    return same_place


def point(lat, lon):
    # latitude and longitude as one value, so that a point is evaluated as a whole
    return None if pd.isna(lat) or pd.isna(lon) else (float(lat), float(lon))


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
    s.add_evaluation_function("website", same_website)
    s.add_evaluation_function("coordinates", near(NEAR_KM[comparison]))
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
                              "founding_year": (voting_ties_by_trust, {"key": year}),
                              "website": (voting_ties_by_trust, {"key": host})},
}

# what we compare for lists (lecture: union, intersection, intersection of k sources, favour sources);
# only domains are in the gold standard, so only domains can be scored
LIST_FUNCTIONS = {
    "union": (union, {}),
    "in at least 2 sources": (intersection_k_sources, {"k": 2}),
    "trust: ROR first": (prefer_higher_trust, {}),
    "trust: Wikidata first": (prefer_higher_trust, {"trust_map": TRUST_WIKIDATA}),
}

# what we compare for coordinates (only ROR and Wikidata have them): the median, which with two points is
# their midpoint, against the point of one source, which keeps latitude and longitude together
COORDINATE_FUNCTIONS = {
    "median": (median, {}),
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
    universities, values looked up in external sources (coordinates: a geocoder, then checked by
    hand, see the README). Every accepted value of a name (name and alternativeNames) and of the domains counts as
    correct; city and founding year have one value."""
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
    # no website of its own: a website is right when its host is an accepted domain
    expected["website"] = expected["domains"]
    if "latitude" in gold:
        expected["coordinates"] = [point(a, b) for a, b in zip(gold["latitude"], gold["longitude"])]
    else:
        expected["coordinates"] = None
    return expected


def coordinate_errors(fused, expected):
    """Distance in km from each fused point to its gold point, for the gold universities that have both."""
    gold = {i: p for i, p in zip(expected["eval_id"], expected["coordinates"]) if p}
    out = []
    for sources, lat, lon in zip(fused["_fusion_sources"], fused["latitude"], fused["longitude"]):
        gid = next((s for s in sources if s in gold), None)
        if gid and point(lat, lon):
            out.append(km(point(lat, lon), gold[gid]))
    return pd.Series(out, dtype=float)


def errors_to_csv(log, out):
    """One row per wrong value from PyDI's debug log: the university, the fused and the accepted values
    (several accepted values joined by " | ") and what each source offered. Sorted, because PyDI's order
    changes between runs. Deletes the log."""
    joined = lambda v: " | ".join(map(str, v)) if isinstance(v, list) else v
    rows = []
    for line in open(log, encoding="utf-8"):
        e = json.loads(line) if line.strip() else {}
        if e.get("type") != "evaluation_mismatch":
            continue
        rows.append({"attribute": e["attribute"], "id": e["expected_id"], "fused_value": joined(e["fused_value"]),
                     "expected_value": joined(e["expected_value"]),
                     "source_values": " | ".join(f"{i['dataset']}: {joined(i['value'])}" for i in e["inputs"]),
                     "conflict_rule": e["conflict_rule"], "evaluation_rule": e["evaluation_rule"]})
    pd.DataFrame(rows, columns=["attribute", "id", "fused_value", "expected_value", "source_values",
                                "conflict_rule", "evaluation_rule"]).sort_values(["attribute", "id"]).to_csv(
        out, index=False)
    log.unlink()


def evaluate(strategy, fused, expected, debug_file=None, attributes=EVALUATED + EXTRA):
    fused = fused.copy()
    if "coordinates" in attributes:
        fused["coordinates"] = [point(a, b) for a, b in zip(fused["latitude"], fused["longitude"])]
    ids = set(expected["eval_id"])
    fused["eval_id"] = [next((s for s in sources if s in ids), None) for sources in fused["_fusion_sources"]]
    fused = fused[["eval_id", "_fusion_sources", "_fusion_metadata", *attributes]]
    expected = expected[expected["eval_id"].isin(set(fused["eval_id"]))][["eval_id", *attributes]]
    # PyDI writes its debug log as JSON lines, we keep it as a CSV like the other error files
    log = debug_file.with_suffix(".jsonl") if debug_file else None
    if log:
        log.unlink(missing_ok=True)
        evaluator = DataFusionEvaluator(strategy, debug=True, debug_file=log)
    else:
        evaluator = DataFusionEvaluator(strategy)
    metrics = evaluator.evaluate(fused_df=fused, fused_id_column="eval_id",
                                 expected_df=expected, expected_id_column="eval_id")
    if log:
        errors_to_csv(log, debug_file)
    row = {"universities": len(expected)}
    for attribute in attributes:
        row[attribute] = round(metrics[f"{attribute}_accuracy"], 3)
    if not set(EVALUATED) <= set(attributes):
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
        choose = next(r for r in list_rows if r["function"] == name and r["gold subset"] == "choose")
        print(f"  domains, {name}: accuracy on the choose half {choose['domains']}", flush=True)
    lists = pd.DataFrame(list_rows)
    lists.to_csv(RESULTS / "list_functions.csv", index=False)

    # coordinates: the functions for latitude and longitude, everything else as in "trust: ROR first".
    # Only when the gold standard has coordinates (column coordinates_source of fusion_gold.csv)
    coord_rows = []
    within = {c: f"within {NEAR_KM[c]} km" for c in NEAR_KM}
    if expected["coordinates"].notna().any():
        for name, rule in COORDINATE_FUNCTIONS.items():
            rules = {**STRATEGIES["trust: ROR first"], "latitude": rule, "longitude": rule}
            fused = DataFusionEngine(make_strategy(f"coordinates: {name}", rules)).run(data, corr, id_column="id")
            for subset, part in parts():
                row = {"function": name, "gold subset": subset}
                errors = coordinate_errors(fused, part)
                for limit in SENSITIVITY_KM:
                    row[f"within {limit:g} km"] = round((errors <= limit).mean(), 3)
                for comparison in NEAR_KM:
                    r = evaluate(make_strategy(name, rules, comparison), fused, part, attributes=["coordinates"])
                    # PyDI's evaluation and the distances must agree (every fused university has a point)
                    assert abs(r["coordinates"] - row[within[comparison]]) < 0.001, (name, subset, comparison)
                    row[within[comparison]] = r["coordinates"]
                row["universities"] = len(errors)
                row["median distance km"] = round(errors.median(), 2)
                coord_rows.append(row)
            choose = next(r for r in coord_rows if r["function"] == name and r["gold subset"] == "choose")
            print(f"  coordinates, {name}: {within['tolerant']} on the choose half {choose[within['tolerant']]}",
                  flush=True)
        pd.DataFrame(coord_rows).to_csv(RESULTS / "coordinate_functions.csv", index=False)

    # final strategy: for every evaluated attribute the function that was best on the "choose" half of the
    # gold standard (lecture: choose on a validation part of the ground truth), compared tolerantly as in
    # the exercise, the first listed on a tie. Its accuracy is then measured on the "test" half.
    table = pd.DataFrame(rows)
    overall = table[(table["gold subset"] == "choose") & (table["comparison"] == "tolerant")]
    final = {"other": STRATEGIES["trust: ROR first"]["other"]}
    best = lists[lists["gold subset"] == "choose"].sort_values("domains", ascending=False, kind="stable").iloc[0]
    final["domains"] = LIST_FUNCTIONS[best["function"]]
    print(f"  best for domains: {best['function']}")
    if coord_rows:
        coords = pd.DataFrame(coord_rows)
        best = coords[coords["gold subset"] == "choose"].sort_values(
            within["tolerant"], ascending=False, kind="stable").iloc[0]
        final["latitude"] = final["longitude"] = COORDINATE_FUNCTIONS[best["function"]]
        print(f"  best for coordinates: {best['function']}")
    for attribute in SINGLE + EXTRA:
        best = overall.sort_values(attribute, ascending=False, kind="stable").iloc[0]["strategy"]
        rules = STRATEGIES[best]
        final[attribute] = rules.get(attribute, rules["other"])
        print(f"  best for {attribute}: {best}")
    # the country name is not evaluated; it follows the record that gave the country code
    if final["country_code"][0] is voting_ties_by_trust:
        final["country"] = (country_of_code, {})
    strategy = make_strategy("best per attribute", final)
    fused = DataFusionEngine(strategy).run(data, corr, id_column="id")
    rows += score("best per attribute", final, fused, RESULTS / "fusion_errors.csv")
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "strategies.csv", index=False)
    print(table.to_string(index=False))

    fused = DataFusionEngine(strategy).run(data, corr, id_column="id", include_singletons=True)
    keep = ["_id", "_fusion_sources", "_fusion_source_datasets", *[c for c in COLUMNS.values() if c in fused]]
    fused = fused[[c for c in keep if c in fused]]
    fused["sources"] = fused["_fusion_source_datasets"].map(lambda x: " | ".join(sorted(set(x))))
    fused.to_csv(RESULTS / "universities_fused.csv", index=False)
    # the same universities in the target schema, checked against target.xsd
    fused_to_xml.main()

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
