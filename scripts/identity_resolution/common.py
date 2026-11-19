"""Shared code for all identity resolution steps."""
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

FILES = {
    "wikidata": "wikidata/Wikidata_Mapping.xml",
    "ror": "ror/ROR_Mapping.xml",
    "deqar": "deqar/deqar_Mapping.xml",
}
# input of later rounds, written by scripts/additional_filtering/<source>/apply.py
#   round 4: without the rows that are not a university of their own (filter BEFORE matching; rejected)
#   round 5: like round 3; the non-universities are removed AFTER matching (final.py)
#   round 6: without duplicates within a source; non-universities removed after matching
FILTERING = IR.parent / "additional_filtering"
MAPPING = {"wikidata": "Wikidata_Mapping", "ror": "ROR_Mapping", "deqar": "deqar_Mapping"}
INPUT = {4: "filtered", 6: "deduplicated"}
PAIRS = [("wikidata", "ror"), ("deqar", "ror")]   # ROR connects the other two

BLOCKER = {
    1: "sorted neighbourhood: name, window 20",
    2: "union: country + name word | same domain | embedding",
    3: "union: country + name word | same domain | embedding",
    4: "union: country + name word | same domain | embedding",
    5: "union: country + name word | same domain | embedding",
    6: "union: country + name word | same domain | embedding",
}


# ---------- loading ----------

def norm_text(value):
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[\W_]+", " ", s).strip()
    return re.sub(r"^the ", "", s)


def as_list(value):
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if value is None or (isinstance(value, float) and math.isnan(value)) or not str(value).strip():
        return []
    return [str(value)]


# round 3: the same word in other languages
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


def load(name, translated=False, path=None):
    df = load_xml(DATA / (path or FILES[name]), name=name)
    col = lambda c: df[c] if c in df.columns else pd.Series([None] * len(df), index=df.index)

    names = []
    for n, alt, acr in zip(df["name"], col("alternativeNames_alternativeName"), col("acronyms_acronym")):
        s = {norm_text(x) for x in [n, *as_list(alt), *as_list(acr)]} - {""}
        if translated:
            s |= {translate(x) for x in s} - {""}
        names.append(sorted(s))

    df["name_norm"] = df["name"].map(norm_text)
    df["names"] = names
    df["cc"] = col("location_countryCode").fillna("").astype(str)
    df["city_norm"] = col("location_city").map(norm_text)
    df["domains"] = col("web_domains_domain").map(lambda v: [d.lower() for d in as_list(v)])
    df["year"] = pd.to_numeric(col("lifecycle_foundingYear"), errors="coerce")
    df["lat"] = pd.to_numeric(col("location_latitude"), errors="coerce")
    df["lon"] = pd.to_numeric(col("location_longitude"), errors="coerce")
    df["parents"] = col("parentInstitutions_parentInstitution").map(lambda v: [norm_text(x) for x in as_list(v)])
    df.attrs["dataset_name"] = name
    return df


def load_all(round_=1):
    """Rounds 4 and 6 read the XML written by scripts/additional_filtering/<source>/apply.py."""
    data = {}
    for name in FILES:
        path = FILTERING / name / f"{MAPPING[name]}_{INPUT[round_]}.xml" if round_ in INPUT else None
        if path and not path.exists():
            raise SystemExit(f"{path.name} is missing: run scripts/additional_filtering/{name}/apply.py first")
        data[name] = load(name, translated=round_ >= 3, path=path)
    return data


def non_universities():
    """Ids of every record marked university = n in scripts/additional_filtering/<source>/hand_check.csv."""
    out = set()
    for name in FILES:
        h = pd.read_csv(FILTERING / name / "hand_check.csv", dtype=str, keep_default_na=False)
        out |= set(h.loc[h["university"] == "n", "id"])
    return out


def links():
    """ID links between the sources (one-to-one only). Only used to build the labels."""
    read = lambda f: pd.read_csv(DATA / f, dtype=str, keep_default_na=False)
    w = read("wikidata/wikidata_universities.csv")
    r = read("ror/ror_education.csv")
    d = read("deqar/deqar_institutions.csv")
    ror_ids, wiki_ids = set(r["ror_id"]), set(w["wikidata_id"])

    wr = {(a, x) for a, b in zip(w["wikidata_id"], w["ror_id"]) for x in b.split(" | ") if x in ror_ids}
    wr |= {(x, b) for a, b in zip(r["wikidata_id"], r["ror_id"]) for x in a.split(" | ") if x in wiki_ids}
    dr = {(a, b) for a, b in zip(d["deqar_id"], d["ror_id"]) if b in ror_ids}

    def one_to_one(pairs, p1, p2):
        c1 = Counter(a for a, _ in pairs)
        c2 = Counter(b for _, b in pairs)
        return {(p1 + a, p2 + b) for a, b in pairs if c1[a] == 1 and c2[b] == 1}

    return {("wikidata", "ror"): one_to_one(wr, "wikidata_", "ror_"),
            ("deqar", "ror"): one_to_one(dr, "deqar_", "ror_")}


# ---------- blocking keys ----------

GENERIC = set("university universitat universite universidad universita college institute school academy "
              "national state technology science sciences of the and de di la der fur und du des".split())


def add_block_keys(left, right, cap=150):
    for df in (left, right):
        df["ex_key"] = df["name"].map(lambda n: "".join(t[:2].upper() for t in str(n).split()[:3]) or None)
        df["name_tokens"] = [" ".join({t for n in ns for t in n.split() if len(t) > 2}) for ns in df["names"]]
        df["domain_text"] = df["domains"].map(" ".join)

    # tokens with the country in front, e.g. DE_heidelberg; very common ones are dropped
    count = Counter()
    for df in (left, right):
        for cc, tokens in zip(df["cc"], df["name_tokens"]):
            count.update(f"{cc}_{t}" for t in tokens.split() if t not in GENERIC)
    for df in (left, right):
        df["scoped_tokens"] = [
            " ".join(k for k in (f"{cc}_{t}" for t in tokens.split() if t not in GENERIC) if count[k] <= cap)
            for cc, tokens in zip(df["cc"], df["name_tokens"])
        ]


# ---------- comparators ----------

def missing(v):
    return v is None or v == "" or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, list) and not v)


def country(r1, r2):
    if missing(r1["cc"]) or missing(r2["cc"]):
        return 0.5
    return float(r1["cc"] == r2["cc"])


def domain(r1, r2):
    return float(bool(set(r1["domains"]) & set(r2["domains"])))


def geo(r1, r2):
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
    p1 = bool(PART & set(r1["name_norm"].split()))
    p2 = bool(PART & set(r2["name_norm"].split()))
    return float(p1 == p2)


def has(col):
    return lambda r1, r2: float(not missing(r1[col]) and not missing(r2[col]))


class Own(BaseComparator):
    def __init__(self, name, function):
        super().__init__(name)
        self.function = function

    def compare(self, r1, r2):
        return self.function(r1, r2)


def comparators():
    best = lambda sim, **kw: StringComparator("names", sim, list_strategy="best_match", **kw)
    return {
        "name_levenshtein": StringComparator("name_norm", "levenshtein"),
        "name_jaro_winkler": StringComparator("name_norm", "jaro_winkler"),
        "name_jaccard": StringComparator("name_norm", "jaccard", tokenization="word"),
        "names_best_jaro_winkler": best("jaro_winkler"),
        "names_best_jaccard": best("jaccard", tokenization="word"),
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


ALL = ["name_levenshtein", "name_jaro_winkler", "name_jaccard", "names_best_jaro_winkler",
       "names_best_jaccard", "country", "domain", "city", "year", "geo",
       "has_domain", "has_city", "has_year", "has_geo"]


# ---------- labels and candidates ----------

def labels(a, b, split, round_):
    folder = LABELS / f"round{min(round_, 2)}"
    df = pd.read_csv(folder / f"{a}_{b}_{split}.csv")
    df["label"] = df["label"].astype(str).str.lower().isin(["true", "1"])
    return df


def slug(name):
    return "".join(c if c.isalnum() else "_" for c in name)[:60]


def candidates(a, b, round_):
    return pd.read_csv(CANDIDATES / f"{a}_{b}_r{round_}_{slug(BLOCKER[round_])}.csv")


# ---------- evaluation ----------

THRESHOLDS = np.round(np.arange(0.30, 0.96, 0.05), 2)


def evaluate(corr, pairs, threshold=None):
    r = EntityMatchingEvaluator.evaluate_matching(corr, pairs, threshold=threshold)
    return r["precision"], r["recall"], r["f1"]


def best_threshold(corr, val):
    results = [(evaluate(corr, val, t), t) for t in THRESHOLDS]
    (p, r, f), t = max(results, key=lambda x: x[0][2])
    return t, p, r, f


def row(round_, pair, matcher, split, t, p, r, f, n, seconds, note=""):
    return dict(round=round_, pair=pair, matcher=matcher, blocker=BLOCKER[round_], split=split,
                threshold=t, P=round(p, 3), R=round(r, 3), F1=round(f, 3), corr=n,
                seconds=seconds, note=note)


def run_matchers(results, round_, a, b, matchers, run, val):
    """Runs all matchers, logs one row each and saves the best one for 05_final."""
    pair = f"{a}-{b}"
    best = None

    for name, cfg in matchers.items():
        corr, seconds = run(cfg)
        t, p, r, f = best_threshold(corr, val)
        n = int((corr["score"] >= t).sum())
        log(results / "matching.csv", row(round_, pair, name, "validation", t, p, r, f, n, seconds))
        print(f"  {pair} {name}: t={t} P={p:.3f} R={r:.3f} F1={f:.3f} corr={n:,} {seconds}s", flush=True)
        if best is None or f > best["F1"]:
            best = dict(round=round_, pair=pair, matcher=name, threshold=t, F1=f, seconds=seconds)
            best_corr = corr[corr["score"] >= t]

    best_corr.to_csv(results / f"best_{a}_{b}_r{round_}.csv", index=False)
    pd.DataFrame([best]).to_csv(results / f"best_{a}_{b}_r{round_}_info.csv", index=False)


# ---------- logging ----------

def reset_log(path, round_):
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
