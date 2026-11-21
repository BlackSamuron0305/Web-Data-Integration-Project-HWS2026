"""Builds the two lookup tables the MapForce mappings read: data/ror/ror_names.csv and data/deqar/country_codes.csv.

Both come from the CSVs in data/<source>/original/, nothing is downloaded. Usage: python build_lookup_tables.py
"""
import csv
import unicodedata
from collections import Counter

import pandas as pd

from common import DATA

# DEQAR spellings that ROR and Wikidata don't use
BY_HAND = {
    "Belgium (Flemish Community)": "BE",
    "Belgium (French Community)": "BE",
    "Belgium (German-speaking Community)": "BE",
    "China, People's Republic of": "CN",
    "Cote d'Ivoire (Ivory Coast)": "CI",
    "Holy See": "VA",
    "Korea, South": "KR",
    "Netherlands": "NL",
    "United Kingdom (England)": "GB",
    "United Kingdom (Northern Ireland)": "GB",
    "United Kingdom (Scotland)": "GB",
    "United Kingdom (Wales)": "GB",
}


def plain(text):
    # removes accents, so Türkiye becomes Turkiye
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def read(source, name):
    return pd.read_csv(DATA / source / "original" / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def write(df, path):
    # MapForce wants UTF-8 with BOM, CRLF line ends and every field in quotes
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    print(f"{path.relative_to(DATA.parent)}: {len(df):,} rows")


def country_codes(ror, wiki, deqar):
    """One row (country, code) per DEQAR country name, codes taken from ROR and Wikidata."""
    pairs = Counter(zip(ror["country"], ror["country_code"])) + Counter(zip(wiki["country"], wiki["country_code"]))
    code = {}
    # most frequent code wins if a name has several
    for (country, cc), _ in pairs.most_common():
        if country and cc:
            code.setdefault(country, cc)
    # the one value with several countries gets no code; sorted with accents ignored
    names = sorted({c for c in deqar["country"] if c and "|" not in c}, key=lambda c: (plain(c), c))
    rows = [(c, BY_HAND.get(c) or code.get(c)) for c in names]
    missing = [c for c, cc in rows if not cc]
    if missing:
        raise SystemExit(f"no code for: {missing}")
    return pd.DataFrame(rows, columns=["country", "code"])


def main():
    ror = read("ror", "ror_education.csv")
    wiki = read("wikidata", "wikidata_universities.csv")
    deqar = read("deqar", "deqar_institutions.csv")
    write(ror[["ror_id", "name"]], DATA / "ror" / "ror_names.csv")
    write(country_codes(ror, wiki, deqar), DATA / "deqar" / "country_codes.csv")


if __name__ == "__main__":
    main()
