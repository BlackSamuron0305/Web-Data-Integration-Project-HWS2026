"""DEQAR: download the list of higher education institutions to data/deqar/original/.

Usage: python fetch_deqar.py [path/to/deqar-institutions.csv]
"""
import csv
import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests

from common import DATA, SEP, USER_AGENT, clean, unique, write_csv

SOURCE_URL = "https://backend.deqar.eu/static/daily-csv/deqar-institutions.csv"
OUT = DATA / "deqar" / "original" / "deqar_institutions.csv"
COLUMNS = ["deqar_id", "name", "alt_names", "country", "city", "website", "founding_year", "closure_year",
           "parent_institutions", "history", "qa_reports", "last_qa_report", "ror_id"]


def read_source():
    # from the given path, or downloaded
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    else:
        print("downloading", SOURCE_URL)
        r = requests.get(SOURCE_URL, headers={"User-Agent": USER_AGENT}, timeout=300)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def eter_code(eter_id):
    # FR0123 gives FR
    m = re.match(r"([A-Z]{2})\d", eter_id)
    return m.group(1) if m else ""


def referenced(text):
    # "DEQARINST0015 Name A, DEQARINST0016 Name B" gives [Name A, Name B]
    parts = re.split(r",\s*(?=(?:\d{4}-\d\d-\d\d: [a-z ]+)?DEQARINST\d+ )", text)
    return unique(clean(re.sub(r"DEQARINST\d+ ", "", p)) for p in parts)


def year(date):
    return date[:4] if re.match(r"\d{4}-", date) else ""


def country_by_code(source):
    # most common country name per ETER code, for rows without a country
    seen = defaultdict(Counter)
    for r in source:
        code = eter_code(r["eter_id"])
        if r["country"].strip() and code:
            seen[code][re.sub(r"\s*\(.*\)", "", r["country"].strip())] += 1
    return {code: names.most_common(1)[0][0] for code, names in seen.items()}


def make_row(deqar_id, rows, countries_by_code):
    # the file has one row per location, rows are all rows of this institution
    r = rows[0]
    name = clean(re.sub(r"^\(\d+\)\s*", "", r["name_primary"]))   # drop "(00207) " in front
    alt_names = [n for n in unique([clean(r["name_official"]), clean(r["name_versions"])]) if n != name]
    country = SEP.join(unique(clean(x["country"]) for x in rows))
    website = clean(r["website_link"])
    ror_ids = re.findall(r"ROR:\s*(?:https?://ror\.org/)?(\w+)", r["identifiers_all"])
    return {
        "deqar_id": deqar_id,
        "name": name,
        "alt_names": SEP.join(alt_names),
        "country": country or countries_by_code.get(eter_code(r["eter_id"]), ""),
        "city": SEP.join(unique(clean(x["city"]) for x in rows)),
        "website": "" if website == "N/A" else website,
        "founding_year": year(r["founding_date"]),
        "closure_year": year(r["closure_date"]),
        "parent_institutions": SEP.join(referenced(r["parent_institution"])),
        "history": SEP.join(referenced(r["historic_relationships"])),
        "qa_reports": r["report_count"].strip(),
        "last_qa_report": r["report_last"].strip(),
        "ror_id": SEP.join(unique(ror_ids)),
    }


def main():
    source = read_source()
    print(f"{len(source)} rows in the file")
    countries_by_code = country_by_code(source)

    grouped = defaultdict(list)
    for r in source:
        grouped[r["deqar_id"]].append(r)
    write_csv(OUT, COLUMNS, [make_row(i, grouped[i], countries_by_code) for i in sorted(grouped)])


if __name__ == "__main__":
    main()
