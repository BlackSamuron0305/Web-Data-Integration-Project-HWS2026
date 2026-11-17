"""Shared code of the pipeline: reads the three CSV files into the integrated schema
and normalises values.

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


def load_schema():
    """The three datasets in the integrated schema, with their raw frames."""
    w, r, d = load_raw()
    lookup = build_country_lookup(r)
    out = {
        "wikidata": to_schema_wikidata(w, lookup),
        "ror": to_schema_ror(r, lookup),
        "deqar": to_schema_deqar(d, lookup),
    }
    for name, df in out.items():
        df.attrs["dataset_name"] = name
    return out, (w, r, d)


# ------------------------------------------------------ output files
FILES = {"wikidata": "Wikidata_Mapping.xml", "ror": "ROR_Mapping.xml", "deqar": "deqar_Mapping.xml"}

