"""ROR: keep the education records of the data dump v2.13.

Usage: python build_ror_education.py [path/to/ror-data.zip]
"""
import csv
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

import requests

DUMP_URL = "https://zenodo.org/api/records/22902037/files/v2.13-2026-09-22-ror-data.zip/content"
DUMP_NAME = "v2.13-2026-09-22-ror-data.zip"
OUT = Path(__file__).resolve().parents[2] / "data" / "ror" / "ror_education.csv"
SEP = " | "
COLUMNS = ["ror_id", "name", "alt_names", "acronyms", "country", "country_code", "region", "city",
           "website", "domains", "founding_year", "latitude", "longitude", "types", "status",
           "parent_ror_id", "wikidata_id", "wikipedia_en"]


def download():
    path = Path(tempfile.gettempdir()) / DUMP_NAME
    if not path.exists():
        print("downloading", DUMP_URL)
        with requests.get(DUMP_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return path


def clean(text):
    text = re.sub(r"[​-‏­﻿]", "", text)   # invisible characters
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def unique(values):
    out = []
    for v in values:
        if v and v not in out:
            out.append(v)
    return out


def names(record, kind):
    return unique(clean(n["value"]) for n in record["names"] if kind in n["types"])


def links(record, kind):
    return [link["value"] for link in record["links"] if link["type"] == kind]


def wikidata_ids(record):
    for e in record["external_ids"]:
        if e["type"] == "wikidata":
            return unique(([e["preferred"]] if e["preferred"] else []) + e["all"])
    return []


def wikipedia_title(url):
    m = re.match(r"https?://en(?:\.m)?\.wikipedia\.org/wiki/([^#?]+)", url)
    return unquote(m.group(1)).replace(" ", "_") if m else ""


def short_id(ror_url):
    return ror_url.rsplit("/", 1)[-1]


def make_row(r):
    name = names(r, "ror_display")[0]
    place = r["locations"][0]["geonames_details"] if r["locations"] else {}
    alt_names = [n for n in unique(names(r, "label") + names(r, "alias")) if n != name]
    parents = [short_id(x["id"]) for x in r["relationships"] if x["type"] == "parent"]
    return {
        "ror_id": short_id(r["id"]),
        "name": name,
        "alt_names": SEP.join(sorted(alt_names)),
        "acronyms": SEP.join(sorted(names(r, "acronym"))),
        "country": place.get("country_name") or "",
        "country_code": place.get("country_code") or "",
        "region": place.get("country_subdivision_name") or "",
        "city": place.get("name") or "",
        "website": SEP.join(unique(links(r, "website"))),
        "domains": SEP.join(sorted(r["domains"])),
        "founding_year": r["established"] or "",
        "latitude": place.get("lat", ""),
        "longitude": place.get("lng", ""),
        "types": SEP.join(sorted(r["types"])),
        "status": r["status"],
        "parent_ror_id": SEP.join(sorted(parents)),
        "wikidata_id": SEP.join(wikidata_ids(r)),
        "wikipedia_en": SEP.join(unique(map(wikipedia_title, links(r, "wikipedia")))),
    }


def main():
    dump = Path(sys.argv[1]) if len(sys.argv) > 1 else download()
    with zipfile.ZipFile(dump) as z:
        json_file = next(n for n in z.namelist() if n.endswith(".json"))
        records = json.load(z.open(json_file))
    print(f"{len(records)} records in the dump")

    # education records only; withdrawn records are merged duplicates
    keep = [r for r in records if "education" in r["types"] and r["status"] != "withdrawn"]
    keep.sort(key=lambda r: r["id"])

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in keep:
            writer.writerow(make_row(r))
    print(f"done: {len(keep)} rows written to {OUT}")


if __name__ == "__main__":
    main()
