"""Build the education subset of the ROR data dump, one row per organisation.

Source:  ROR data dump v2.13 (2026-09-22), https://doi.org/10.5281/zenodo.22902037
Scope:   records whose types contain "education"; withdrawn records (merged duplicates) are skipped.
Output:  data/ror_education.csv  (UTF-8, list values separated by " | ")

The JSON file of the dump is used instead of the CSV file, because the CSV packs several names
into one cell with commas and cannot be split back reliably.

Run:  python scripts/build_ror_education.py [path/to/v2.13-2026-09-22-ror-data.zip]
      Without a path the dump is downloaded to the system temp folder.
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
OUT = Path(__file__).resolve().parent.parent / "data" / "ror_education.csv"
SEP = " | "


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
    return re.sub(r"\s+", " ", re.sub(r"[​-‏­﻿]", "", text).replace("|", "/")).strip()


def unique(values):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def names(record, kind):
    return unique(clean(n["value"]) for n in record["names"] if kind in n["types"])


def links(record, kind):
    return [l["value"] for l in record["links"] if l["type"] == kind]


def external_ids(record, kind):
    for e in record["external_ids"]:
        if e["type"] == kind:
            return unique(([e["preferred"]] if e["preferred"] else []) + e["all"])
    return []


def wikipedia_title(url):
    m = re.match(r"https?://en(?:\.m)?\.wikipedia\.org/wiki/([^#?]+)", url)
    return unquote(m.group(1)).replace(" ", "_") if m else ""


def main():
    dump = Path(sys.argv[1]) if len(sys.argv) > 1 else download()
    with zipfile.ZipFile(dump) as z:
        json_name = next(n for n in z.namelist() if n.endswith(".json"))
        records = json.load(z.open(json_name))
    print(f"{len(records)} records in the dump")

    columns = ["ror_id", "name", "alt_names", "acronyms", "country", "country_code", "region", "city", "website",
               "domains", "founding_year", "latitude", "longitude", "types", "status", "parent_ror_id",
               "wikidata_id", "wikipedia_en"]
    OUT.parent.mkdir(exist_ok=True)
    kept = 0
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in sorted(records, key=lambda r: r["id"]):
            if "education" not in r["types"] or r["status"] == "withdrawn":
                continue
            name = names(r, "ror_display")[0]
            place = r["locations"][0]["geonames_details"] if r["locations"] else {}
            writer.writerow({
                "ror_id": r["id"].rsplit("/", 1)[-1],
                "name": name,
                "alt_names": SEP.join(sorted(n for n in unique(names(r, "label") + names(r, "alias")) if n != name)),
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
                "parent_ror_id": SEP.join(sorted(x["id"].rsplit("/", 1)[-1] for x in r["relationships"]
                                                 if x["type"] == "parent")),
                "wikidata_id": SEP.join(external_ids(r, "wikidata")),
                "wikipedia_en": SEP.join(unique(map(wikipedia_title, links(r, "wikipedia")))),
            })
            kept += 1
    print(f"done: {kept} rows written to {OUT}")


if __name__ == "__main__":
    main()
