"""Shared code for the identity resolution scripts (loading, blocking keys, comparators, labels, evaluation).
Rounds: 1 = ID links as labels, 2 = hand-checked labels, 3 = translated names, 8 = final run on the cleaned data."""
import csv
import logging
import math
import re
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

IR = Path(__file__).resolve().parent
DATA = IR.parents[1] / "data"
LABELS = IR / "01_labels" / "results"
CANDIDATES = IR / "02_blocking" / "results" / "candidates"

MAPPING = {"wikidata": "Wikidata_Mapping.xml", "ror": "ROR_Mapping.xml", "deqar": "deqar_Mapping.xml"}
DOWNLOAD = {"wikidata": "wikidata_universities.csv", "ror": "ror_education.csv", "deqar": "deqar_institutions.csv"}
ID_COLUMN = {"wikidata": "wikidata_id", "ror": "ror_id", "deqar": "deqar_id"}
PAIRS = [("wikidata", "ror"), ("deqar", "ror")]   # ROR links the other two

UNION = "union: country + name word | same domain | embedding"
BLOCKER = {1: "sorted neighbourhood: name, window 20", 2: UNION, 3: UNION, 8: UNION}


def norm_text(value):
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


# from round 3 on these words get replaced by the English word
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


def load(name, round_):
    folder = "filtered" if round_ == 8 else "original"
    df = load_xml(DATA / name / folder / MAPPING[name], name=name)

    def column(c):
        # not every source has every attribute
        return df[c] if c in df.columns else pd.Series([None] * len(df), index=df.index)

    names = []
    for n, alt, acr in zip(df["name"], column("alternativeNames_alternativeName"), column("acronyms_acronym")):
        s = {norm_text(x) for x in [n, *as_list(alt), *as_list(acr)]} - {""}
        if round_ >= 3:
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
    df["parents"] = column("parentInstitutions_parentInstitution").map(lambda v: [norm_text(x) for x in as_list(v)])
    df.attrs["dataset_name"] = name
    return df


def load_all(round_):
    return {name: load(name, round_) for name in MAPPING}


def links():
    """One-to-one ID links between the sources in the downloaded files."""
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


GENERIC = set("university universitat universite universidad universita college institute school academy "
              "national state technology science sciences of the and de di la der fur und du des".split())


def add_block_keys(left, right, cap=150):
    # scoped_tokens like DE_heidelberg, without generic words and keys shared by more than cap records
    for df in (left, right):
        df["ex_key"] = df["name"].map(lambda n: "".join(t[:2].upper() for t in str(n).split()[:3]) or None)
        df["name_tokens"] = [" ".join({t for n in ns for t in n.split() if len(t) > 2}) for ns in df["names"]]
        df["domain_text"] = df["domains"].map(" ".join)

    def keys(cc, tokens):
        return [f"{cc}_{t}" for t in tokens.split() if t not in GENERIC]

    count = Counter()
    for df in (left, right):
        for cc, tokens in zip(df["cc"], df["name_tokens"]):
            count.update(keys(cc, tokens))
    for df in (left, right):
        df["scoped_tokens"] = [" ".join(k for k in keys(cc, tokens) if count[k] <= cap)
                               for cc, tokens in zip(df["cc"], df["name_tokens"])]


def missing(v):
    return v is None or v == "" or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, list) and not v)


def country(r1, r2):
    # 0.5 if a country is missing
    if missing(r1["cc"]) or missing(r2["cc"]):
        return 0.5
    return float(r1["cc"] == r2["cc"])


def domain(r1, r2):
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


# features of the learned matchers (part_word only in an extra round 3 test)
ALL = ["name_levenshtein", "name_jaro_winkler", "name_jaccard", "names_best_jaro_winkler",
       "names_best_jaccard", "country", "domain", "city", "year", "geo",
       "has_domain", "has_city", "has_year", "has_geo"]


def removed_ids():
    # ids like wikidata_Q1 of the records the cleaning removed
    return {f"{name}_{i}" for name, col in ID_COLUMN.items()
            for i in pd.read_csv(DATA / name / "filtered" / "removed.csv", dtype=str)[col]}


def labels(a, b, split, round_):
    # rounds 3 and 8 use the round 2 labels; round 8 drops pairs with a removed record (out of scope)
    df = pd.read_csv(LABELS / f"round{min(round_, 2)}" / f"{a}_{b}_{split}.csv")
    df["label"] = df["label"].astype(str).str.lower().isin(["true", "1"])
    if round_ == 8:
        gone = removed_ids()
        df = df[~df["id1"].isin(gone) & ~df["id2"].isin(gone)].reset_index(drop=True)
    return df


def slug(name):
    # blocker name -> file name
    return "".join(c if c.isalnum() else "_" for c in name)[:60]


def candidates(a, b, round_):
    return pd.read_csv(CANDIDATES / f"{a}_{b}_r{round_}_{slug(BLOCKER[round_])}.csv")


THRESHOLDS = np.round(np.arange(0.30, 0.96, 0.05), 2)   # 0.30, 0.35, ..., 0.95


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


def row(round_, pair, matcher, split, t, p, r, f, n, seconds, note=""):
    return dict(round=round_, pair=pair, matcher=matcher, blocker=BLOCKER[round_], split=split,
                threshold=t, P=round(p, 3), R=round(r, 3), F1=round(f, 3), corr=n,
                seconds=seconds, note=note)


def run_matchers(results, round_, a, b, matchers, run, val):
    # run(config) returns (correspondences, seconds); the best matcher by validation F1 is saved for 05_final
    pair = f"{a}-{b}"
    best = None
    for name, config in matchers.items():
        corr, seconds = run(config)
        t, p, r, f = best_threshold(corr, val)
        kept = corr[corr["score"] >= t]
        log(results / "matching.csv", row(round_, pair, name, "validation", t, p, r, f, len(kept), seconds))
        print(f"  {pair} {name}: t={t} P={p:.3f} R={r:.3f} F1={f:.3f} corr={len(kept):,} {seconds}s", flush=True)
        if best is None or f > best["F1"]:
            best = dict(round=round_, pair=pair, matcher=name, threshold=t, F1=f, seconds=seconds)
            best_corr = kept

    best_corr.to_csv(results / f"best_{a}_{b}_r{round_}.csv", index=False)
    pd.DataFrame([best]).to_csv(results / f"best_{a}_{b}_r{round_}_info.csv", index=False)


def reset_log(path, round_):
    # drop the rows of this round so a rerun replaces them
    if path.exists():
        df = pd.read_csv(path)
        df[df["round"] != round_].to_csv(path, index=False)


def log(path, row):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new:
            writer.writeheader()
        writer.writerow(row)


class Timer:
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.seconds = round(time.time() - self.start, 1)
