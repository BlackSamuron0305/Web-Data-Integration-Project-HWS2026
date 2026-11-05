"""Shared code of the pipeline: reads the three CSV files into the integrated schema,
normalises values and derives the gold-standard links from the identifier columns.

The integrated schema (Table 2 of the project abstract) is the same for all datasets;
a dataset that does not have an attribute leaves the column empty. Attributes that
hold several values are Python lists.
"""
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

SEP = " | "

# columns of the integrated schema (id first); the lists are marked in LIST_COLUMNS
SCHEMA = [
    "id", "name", "alt_names", "acronyms", "country", "country_code", "city", "region",
    "website", "domains", "founding_year", "closure_year", "latitude", "longitude",
    "parent", "types", "students", "memberships", "history", "qa_reports",
    "last_qa_report", "status",
]
LIST_COLUMNS = ["alt_names", "acronyms", "domains", "parent", "types", "memberships", "history"]


def split_list(value):
    if not isinstance(value, str) or not value.strip():
        return []
    return [v.strip() for v in value.split(SEP) if v.strip()]


def to_number(value, kind=float):
    try:
        return kind(value)
    except (TypeError, ValueError):
        return None


def norm_text(value):
    """Lower case, no accents, no punctuation, single spaces, no leading 'the'."""
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[\W_]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"^the ", "", s)


def domain_of(url):
    """Host of a web address without 'www.'; empty if there is none."""
    if not isinstance(url, str) or not url.strip():
        return ""
    u = url.strip()
    if "://" not in u:
        u = "http://" + u
    host = (urlparse(u).hostname or "").lower()
    return re.sub(r"^www\d*\.", "", host)


# ---------------------------------------------------------------- countries
_ALIASES = {
    "czech republic": "CZ", "korea south": "KR", "china people s republic of": "CN",
    "cote d ivoire ivory coast": "CI", "cote d ivoire": "CI", "holy see": "VA", "netherlands": "NL",
    "the netherlands": "NL", "cape verde": "CV", "turkey": "TR", "vatican city": "VA",
    "north macedonia": "MK", "macedonia": "MK", "russian federation": "RU",
    "united kingdom": "GB", "united states": "US", "usa": "US",
}


def build_country_lookup(ror: pd.DataFrame):
    lookup = dict(_ALIASES)
    for name, code in zip(ror["country"], ror["country_code"]):
        if name and code:
            lookup.setdefault(norm_text(name), code)
    return lookup


def country_code_of_name(name, lookup):
    """Country code for a (possibly decorated) country name; '' if unknown or several."""
    if not isinstance(name, str) or not name.strip() or "|" in name:
        return ""
    base = re.sub(r"\s*\(.*?\)", "", name)
    return lookup.get(norm_text(base)) or lookup.get(norm_text(name), "")


# ------------------------------------------------------------------ loading
def _read(name):
    return pd.read_csv(DATA / name, dtype=str, keep_default_na=False, encoding="utf-8")


def _frame(rows):
    df = pd.DataFrame(rows, columns=SCHEMA)
    for c in LIST_COLUMNS:
        df[c] = df[c].apply(lambda v: v if isinstance(v, list) else [])
    return df


def load_raw():
    return _read("wikidata_universities.csv"), _read("ror_education.csv"), _read("deqar_institutions.csv")


def to_schema_wikidata(w, lookup):
    rows = []
    for r in w.itertuples(index=False):
        website = split_list(r.website)
        rows.append(dict(
            id="wikidata_" + r.wikidata_id, name=r.name, alt_names=split_list(r.alt_names),
            acronyms=split_list(r.acronyms), country=r.country,
            country_code=r.country_code if "|" not in r.country_code else "",
            city=r.city, region="", website=website[0] if website else "",
            domains=sorted({domain_of(u) for u in website} - {""}),
            founding_year=to_number(r.founding_year, int), closure_year=None,
            latitude=to_number(r.latitude), longitude=to_number(r.longitude),
            parent=[], types=split_list(r.types), students=to_number(r.students, int),
            memberships=split_list(r.member_of), history=[], qa_reports=None,
            last_qa_report="", status=""))
    return _frame(rows)


def to_schema_ror(r, lookup):
    names = dict(zip(r["ror_id"], r["name"]))
    rows = []
    for x in r.itertuples(index=False):
        website = split_list(x.website)
        rows.append(dict(
            id="ror_" + x.ror_id, name=x.name, alt_names=split_list(x.alt_names),
            acronyms=split_list(x.acronyms), country=x.country, country_code=x.country_code,
            city=x.city, region=x.region, website=website[0] if website else "",
            domains=split_list(x.domains) or sorted({domain_of(u) for u in website} - {""}),
            founding_year=to_number(x.founding_year, int), closure_year=None,
            latitude=to_number(x.latitude), longitude=to_number(x.longitude),
            parent=[names.get(p, p) for p in split_list(x.parent_ror_id)],
            types=[], students=None, memberships=[], history=[],  # ROR types are registry categories
            qa_reports=None, last_qa_report="", status=x.status))
    return _frame(rows)


def to_schema_deqar(d, lookup):
    rows = []
    for x in d.itertuples(index=False):
        website = split_list(x.website)
        rows.append(dict(
            id="deqar_" + x.deqar_id, name=x.name, alt_names=split_list(x.alt_names),
            acronyms=[], country=x.country, country_code=country_code_of_name(x.country, lookup),
            city=x.city, region="", website=website[0] if website else "",
            domains=sorted({domain_of(u) for u in website} - {""}),
            founding_year=to_number(x.founding_year, int), closure_year=to_number(x.closure_year, int),
            latitude=None, longitude=None,
            parent=split_list(x.parent_institutions), types=[], students=None,
            memberships=[], history=split_list(x.history),
            qa_reports=to_number(x.qa_reports, int), last_qa_report=x.last_qa_report, status=""))
    return _frame(rows)


def add_match_columns(df):
    """Helper columns used by blocking and comparison (not part of the schema)."""
    df = df.copy()
    df["name_norm"] = df["name"].map(norm_text)
    df["alt_norm"] = df["alt_names"].map(lambda L: sorted({norm_text(a) for a in L} - {""}))
    df["names_all"] = [sorted(({n} | set(a) | {norm_text(x) for x in ac}) - {""})
                       for n, a, ac in zip(df["name_norm"], df["alt_norm"], df["acronyms"])]
    df["city_norm"] = df["city"].map(norm_text)
    df["domain"] = df["domains"].map(lambda L: L[0] if L else "")
    return df


def load_schema():
    """The three datasets in the integrated schema, with their raw frames."""
    w, r, d = load_raw()
    lookup = build_country_lookup(r)
    out = {
        "wikidata": add_match_columns(to_schema_wikidata(w, lookup)),
        "ror": add_match_columns(to_schema_ror(r, lookup)),
        "deqar": add_match_columns(to_schema_deqar(d, lookup)),
    }
    for name, df in out.items():
        df.attrs["dataset_name"] = name
    return out, (w, r, d)


# ----------------------------------------------------------- gold-standard links
def link_pairs(raw):
    """Pairs of records that the sources themselves declare to be the same institution.

    Returns a dict with the pairs for wikidata-ror, deqar-ror and wikidata-deqar
    (the last one through the shared ROR record), as sets of (id1, id2) with the
    schema ids. These identifier links are only used as gold standard, never for matching.
    """
    w, r, d = raw
    wset, rset = set(w["wikidata_id"]), set(r["ror_id"])
    wr = set()
    for a, b in zip(w["wikidata_id"], w["ror_id"]):
        for x in split_list(b):
            if x in rset:
                wr.add((a, x))
    for a, b in zip(r["wikidata_id"], r["ror_id"]):
        for x in split_list(a):
            if x in wset:
                wr.add((x, b))
    dr = {(a, b) for a, b in zip(d["deqar_id"], d["ror_id"]) if b in rset}
    by_ror = {}
    for a, b in wr:
        by_ror.setdefault(b, set()).add(a)
    wd = {(x, a) for a, b in dr for x in by_ror.get(b, ())}

    def prefix(pairs, p1, p2):
        return {(p1 + a, p2 + b) for a, b in pairs}

    return {
        ("wikidata", "ror"): prefix(wr, "wikidata_", "ror_"),
        ("deqar", "ror"): prefix(dr, "deqar_", "ror_"),
        ("wikidata", "deqar"): prefix(wd, "wikidata_", "deqar_"),
    }


def one_to_one(pairs):
    """Keep only the pairs in which neither record is linked to another record."""
    from collections import Counter
    c1 = Counter(a for a, _ in pairs)
    c2 = Counter(b for _, b in pairs)
    return {(a, b) for a, b in pairs if c1[a] == 1 and c2[b] == 1}


# ------------------------------------------------------ reading the translated XML
FILES = {"wikidata": "Wikidata_Mapping.xml", "ror": "ROR_Mapping.xml", "deqar": "deqar_Mapping.xml"}


def _text(el, path):
    t = el.findtext(path)
    return t.strip() if t and t.strip() else ""


def _items(el, path):
    return [x.text.strip() for x in el.findall(path) if x.text and x.text.strip()]


def read_target_xml(path):
    """Reads one translated XML file (data/*_Mapping.xml) back into the integrated schema."""
    import xml.etree.ElementTree as ET
    rows = []
    for _, e in ET.iterparse(path):
        if e.tag != "institution":
            continue
        rows.append(dict(
            id=_text(e, "id"), name=_text(e, "name"),
            alt_names=_items(e, "alternativeNames/alternativeName"),
            acronyms=_items(e, "acronyms/acronym"),
            country=_text(e, "location/country"), country_code=_text(e, "location/countryCode"),
            city=_text(e, "location/city"), region=_text(e, "location/region"),
            website=_text(e, "web/website"), domains=_items(e, "web/domains/domain"),
            founding_year=to_number(_text(e, "lifecycle/foundingYear"), int),
            closure_year=to_number(_text(e, "lifecycle/closureYear"), int),
            latitude=to_number(_text(e, "location/latitude")),
            longitude=to_number(_text(e, "location/longitude")),
            parent=_items(e, "parentInstitutions/parentInstitution"),
            types=_items(e, "institutionTypes/institutionType"),
            students=to_number(_text(e, "numberOfStudents"), int),
            memberships=_items(e, "memberships/membership"),
            history=_items(e, "lifecycle/history/event"),
            qa_reports=to_number(_text(e, "qualityAssurance/numberOfQAReports"), int),
            last_qa_report=_text(e, "qualityAssurance/lastQAReportDate"),
            status=_text(e, "status")))
        e.clear()
    return _frame(rows)


def load_target():
    """The three datasets as produced by Phase I (read from data/*_Mapping.xml)."""
    out = {}
    for name, file in FILES.items():
        df = add_match_columns(read_target_xml(DATA / file))
        df.attrs["dataset_name"] = name
        out[name] = df
    return out
