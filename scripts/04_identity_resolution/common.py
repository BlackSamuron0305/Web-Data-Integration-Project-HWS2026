"""Shared code for the identity resolution scripts. In this order:
- where things are, the two runs
- loading the sources and preparing the names
- the identifier links (our answer key, only used to build and check labels)
- the attribute comparators every approach can use
- labelled pairs and candidate pairs
- threshold search, logging and running a set of rules
The comparators of one approach only (TF-IDF, embeddings, ...) live in that approach's folder."""
import csv
import logging
import math
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from PyDI.entitymatching import EntityMatchingEvaluator, NumericComparator, StringComparator
from PyDI.entitymatching.base import BaseComparator
from PyDI.io import load_xml

logging.disable(logging.WARNING)

# ---------------------------------------------------------------- where things are, the two runs

IR = Path(__file__).resolve().parent
DATA = IR.parents[1] / "data"
SCHEMA_MAPPING = IR.parent / "03_schema_mapping"   # MapForce XML output
GOLD = DATA / "golden_set"
LABELS = GOLD / "labelled_pairs"   # the 1,800 labelled pairs, split by gold_standard/split_labelled_pairs.py
CANDIDATES = IR / "blocking" / "results" / "candidates"

MAPPING = {"wikidata": "Wikidata_Mapping.xml", "ror": "ROR_Mapping.xml", "deqar": "deqar_Mapping.xml"}
DOWNLOAD = {"wikidata": "wikidata_universities.csv", "ror": "ror_education.csv", "deqar": "deqar_institutions.csv"}
ID_COLUMN = {"wikidata": "wikidata_id", "ror": "ror_id", "deqar": "deqar_id"}
PAIRS = [("wikidata", "ror"), ("deqar", "ror")]   # ROR links the other two

BLOCKER = "union: country + name word | same domain | embedding"   # the candidate pairs every matcher scores

# run name: data folder it matches (first_pass = the sources as downloaded, final = the cleaned sources)
RUNS = {"first_pass": "original", "final": "filtered"}


def run_argument():
    # the run named on the command line
    if len(sys.argv) < 2 or sys.argv[1] not in RUNS:
        raise SystemExit(f"usage: python {Path(sys.argv[0]).name} {' | '.join(RUNS)}")
    return sys.argv[1]


# ---------------------------------------------------------------- loading the sources

def norm_text(value):
    # lower case, no accents, no punctuation, "&" -> "and", without a leading "the"
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[\W_]+", " ", s).strip()
    return re.sub(r"^the ", "", s)


def as_list(value):
    # a cell holds either one value or a list
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if value is None or (isinstance(value, float) and math.isnan(value)) or not str(value).strip():
        return []
    return [str(value)]


# these words get replaced by the English word
TRANSLATE = {
    "university": "universitat universite universidad universita universidade universiteit universitet "
                  "uniwersytet univerzita univerzitet universitatea yliopisto universiti universitas egyetem",
    "academy": "academia accademia akademie akademia academie akademija akademiya",
    "institute": "instituto institut istituto instytut institutt",
    "polytechnic": "politecnico politechnika polytechnique politecnica polytechnika",
    "technical": "technische tecnica tecnico technicka teknik tehnicka",
    "college": "colegio collegio kolegium hogeschool hochschule hogskole hogskolan",
    "national": "nacional nazionale nationale narodowy",
    "applied": "angewandte aplicadas applicate toegepaste",
    "sciences": "wissenschaften ciencias scienze nauk tieteiden",
    "arts": "arti artes kunste kunsten sztuk",
    "fine": "belle bellas beaux bildenden pieknych",
    "music": "musica musik musique muzyczna muziek",
    "medical": "medizinische medica medicina medyczny medicale",
    "economics": "wirtschaft economia ekonomiczny economie economicas",
}
WORD = {w: english for english, words in TRANSLATE.items() for w in words.split()}
STOP = set("of the de del della di da do der des die fur und y e et i la le les el en and for w im am".split())


def translate(name):
    return " ".join(WORD.get(t, t) for t in name.split() if t not in STOP)


def load(name, run):
    """Reads one source (MapForce XML of this run) and adds the prepared columns the comparators use."""
    df = load_xml(SCHEMA_MAPPING / name / RUNS[run] / MAPPING[name], name=name)

    def column(c):
        # not every source has every attribute
        return df[c] if c in df.columns else pd.Series([None] * len(df), index=df.index)

    # all names of a record: main name, alternative names, acronyms, each also with common words translated
    names = []
    for n, alt, acr in zip(df["name"], column("alternativeNames_alternativeName"), column("acronyms_acronym")):
        s = {norm_text(x) for x in [n, *as_list(alt), *as_list(acr)]} - {""}
        s |= {translate(x) for x in s} - {""}
        names.append(sorted(s))

    df["name_norm"] = df["name"].map(norm_text)
    df["names"] = names
    df["cc"] = column("location_countryCode").fillna("").astype(str)
    df["city_norm"] = column("location_city").map(norm_text)
    df["domains"] = column("web_domains_domain").map(lambda v: [d.lower() for d in as_list(v)])
    df["year"] = pd.to_numeric(column("lifecycle_foundingYear"), errors="coerce")
    df["lat"] = pd.to_numeric(column("location_latitude"), errors="coerce")
    df["lon"] = pd.to_numeric(column("location_longitude"), errors="coerce")
    df.attrs["dataset_name"] = name
    return df


def load_all(run):
    return {name: load(name, run) for name in MAPPING}


# ---------------------------------------------------------------- the answer key

def links():
    """One-to-one ID links between the sources in the downloaded files (a record naming its partner's ID).
    They are our answer key: used to build and check labels, never inside blocking or matching."""
    def read(name):
        return pd.read_csv(DATA / name / "original" / DOWNLOAD[name], dtype=str, keep_default_na=False)

    w, r, d = read("wikidata"), read("ror"), read("deqar")
    ror_ids, wiki_ids = set(r["ror_id"]), set(w["wikidata_id"])

    # Wikidata-ROR links can be on either side
    wr = {(a, x) for a, b in zip(w["wikidata_id"], w["ror_id"]) for x in b.split(" | ") if x in ror_ids}
    wr |= {(x, b) for a, b in zip(r["wikidata_id"], r["ror_id"]) for x in a.split(" | ") if x in wiki_ids}
    dr = {(a, b) for a, b in zip(d["deqar_id"], d["ror_id"]) if b in ror_ids}

    def one_to_one(pairs, p1, p2):
        c1 = Counter(a for a, _ in pairs)
        c2 = Counter(b for _, b in pairs)
        return {(p1 + a, p2 + b) for a, b in pairs if c1[a] == 1 and c2[b] == 1}

    return {("wikidata", "ror"): one_to_one(wr, "wikidata_", "ror_"),
            ("deqar", "ror"): one_to_one(dr, "deqar_", "ror_")}


# ---------------------------------------------------------------- comparators (each returns a score from 0 to 1)

def missing(v):
    return v is None or v == "" or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, list) and not v)


def country(r1, r2):
    # 0.5 if a country is missing
    if missing(r1["cc"]) or missing(r2["cc"]):
        return 0.5
    return float(r1["cc"] == r2["cc"])


def domain(r1, r2):
    # 1 if the two records share a web domain
    return float(bool(set(r1["domains"]) & set(r2["domains"])))


def geo(r1, r2):
    # 1 up to 2 km apart, going down to 0 at 50 km
    if any(missing(v) for v in (r1["lat"], r1["lon"], r2["lat"], r2["lon"])):
        return 0.0
    p1, p2 = math.radians(r1["lat"]), math.radians(r2["lat"])
    dlon = math.radians(r2["lon"] - r1["lon"])
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    km = 12742 * math.asin(math.sqrt(a))
    return 1.0 if km <= 2 else max(0.0, 1 - (km - 2) / 48)


PART = set("campus branch centre center faculty department laboratory laboratoire unite "
           "observatory observatoire filiale filial standort".split())


def part_word(r1, r2):
    # 1 if both or neither name has a word like campus or faculty in it
    p1 = bool(PART & set(r1["name_norm"].split()))
    p2 = bool(PART & set(r2["name_norm"].split()))
    return float(p1 == p2)


def has(col):
    # tells the learned models if a feature can be trusted
    def both(r1, r2):
        return float(not missing(r1[col]) and not missing(r2[col]))
    return both


class Own(BaseComparator):
    # wraps one of the functions above as a PyDI comparator
    def __init__(self, name, function):
        super().__init__(name)
        self.function = function

    def compare(self, r1, r2):
        return self.function(r1, r2)


def comparators():
    return {
        "name_levenshtein": StringComparator("name_norm", "levenshtein"),
        "name_jaro_winkler": StringComparator("name_norm", "jaro_winkler"),
        "name_jaccard": StringComparator("name_norm", "jaccard", tokenization="word"),
        "names_best_jaro_winkler": StringComparator("names", "jaro_winkler", list_strategy="best_match"),
        "names_best_jaccard": StringComparator("names", "jaccard", tokenization="word", list_strategy="best_match"),
        "country": Own("country", country),
        "domain": Own("domain", domain),
        "city": StringComparator("city_norm", "jaro_winkler"),
        "year": NumericComparator("year", "absolute_difference", max_difference=10),
        "geo": Own("geo", geo),
        "has_domain": Own("has_domain", has("domains")),
        "has_city": Own("has_city", has("city_norm")),
        "has_year": Own("has_year", has("year")),
        "has_geo": Own("has_geo", has("lat")),
        "part_word": Own("part_word", part_word),
    }


# features of the learned matchers
ALL = ["name_levenshtein", "name_jaro_winkler", "name_jaccard", "names_best_jaro_winkler",
       "names_best_jaccard", "country", "domain", "city", "year", "geo",
       "has_domain", "has_city", "has_year", "has_geo"]


# ---------------------------------------------------------------- labelled pairs and candidate pairs

def removed_ids():
    # ids like wikidata_Q1 of the records the cleaning removed
    return {f"{name}_{i}" for name, col in ID_COLUMN.items()
            for i in pd.read_csv(DATA / name / "filtered" / "removed.csv", dtype=str)[col]}


def labels(a, b, split, run):
    # on the cleaned data, pairs with a record the cleaning removed are out of scope and dropped
    df = pd.read_csv(LABELS / f"{a}_{b}_{split}.csv")
    df["label"] = df["label"].astype(str).str.lower().isin(["true", "1"])
    if RUNS[run] == "filtered":
        gone = removed_ids()
        df = df[~df["id1"].isin(gone) & ~df["id2"].isin(gone)].reset_index(drop=True)
    return df


def slug(name):
    # blocker name -> file name
    return "".join(c if c.isalnum() else "_" for c in name)[:60]


def candidates(a, b, run):
    return pd.read_csv(CANDIDATES / f"{a}_{b}_{run}_{slug(BLOCKER)}.csv")


# ---------------------------------------------------------------- threshold search, logging, running rules

# 0.30, 0.35, ..., 0.95, then 0.96 to 0.99: the fine-tuned model puts most of its scores near 0 or 1
THRESHOLDS = np.round(np.concatenate([np.arange(0.30, 0.96, 0.05), np.arange(0.96, 0.995, 0.01)]), 2)


def evaluate(corr, pairs, threshold=None):
    r = EntityMatchingEvaluator.evaluate_matching(corr, pairs, threshold=threshold)
    return r["precision"], r["recall"], r["f1"]


def best_threshold(corr, val):
    # threshold with the best F1, the lowest one on a tie
    best = None
    for t in THRESHOLDS:
        p, r, f = evaluate(corr, val, t)
        if best is None or f > best[3]:
            best = (t, p, r, f)
    return best


def row(run, pair, matcher, split, t, p, r, f, n, seconds, note=""):
    return dict(run=run, pair=pair, matcher=matcher, blocker=BLOCKER, split=split,
                threshold=t, P=round(p, 3), R=round(r, 3), F1=round(f, 3), corr=n,
                seconds=seconds, note=note)


def run_folder(results, run):
    """results/<run>/ of an approach (first_pass or final). Its old matching.csv is removed, so a rerun
    replaces it instead of adding to it."""
    folder = results / run
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "matching.csv").unlink(missing_ok=True)
    return folder


def run_matchers(folder, run, a, b, matchers, match, val):
    """Tries every matcher in matchers ({name: config}) on one dataset pair. match(config) returns
    (correspondences, seconds). Each gets its best threshold on the validation pairs and a row in
    matching.csv of the run folder; the best one by validation F1 is saved for global_matching_and_test."""
    pair = f"{a}-{b}"
    best = None
    for name, config in matchers.items():
        corr, seconds = match(config)
        t, p, r, f = best_threshold(corr, val)
        kept = corr[corr["score"] >= t]
        log(folder / "matching.csv", row(run, pair, name, "validation", t, p, r, f, len(kept), seconds))
        print(f"  {pair} {name}: t={t} P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(kept):,} {seconds}s", flush=True)
        if best is None or f > best["F1"]:
            best = dict(run=run, pair=pair, matcher=name, threshold=t, F1=f, seconds=seconds)
            best_corr = kept

    best_corr.to_csv(folder / f"best_{a}_{b}.csv", index=False)
    pd.DataFrame([best]).to_csv(folder / f"best_{a}_{b}_info.csv", index=False)


def run_rules(results, run, rules, prepare=None, extra=None):
    """Runs the rules of one matcher folder (01-04). rules is {rule name: (comparators, weights)}, or a
    function rules(a, b, L, R, comps) that returns it. prepare(data) adds columns the extra comparators
    need (e.g. the TF-IDF vectors); extra is {name: comparator} on top of comparators()."""
    from PyDI.entitymatching import RuleBasedMatcher
    folder = run_folder(results, run)
    data = load_all(run)
    if prepare:
        prepare(data)
    comps = comparators() | (extra or {})

    for a, b in PAIRS:
        L, R, cand = data[a], data[b], candidates(a, b, run)

        def match(rule):
            cols, weights = rule
            with Timer() as t:
                corr = RuleBasedMatcher().match(L, R, cand, "id", [comps[c] for c in cols],
                                                weights=weights, threshold=THRESHOLDS[0])
            return corr, t.seconds

        rules_here = rules(a, b, L, R, comps) if callable(rules) else rules
        run_matchers(folder, run, a, b, rules_here, match, labels(a, b, "validation", run))


def reset_log(path, run):
    # drop the rows of this run so a rerun replaces them
    if path.exists():
        df = pd.read_csv(path)
        df[df["run"] != run].to_csv(path, index=False)


def log(path, row):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new:
            writer.writeheader()
        writer.writerow(row)


class Timer:
    # with Timer() as t: ...   afterwards t.seconds holds the time it took
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.seconds = round(time.time() - self.start, 1)
