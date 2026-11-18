"""DEQAR: download the list of higher education institutions.

Usage: python fetch_deqar.py [path/to/deqar-institutions.csv]
"""
import csv
import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests

SOURCE_URL = "https://backend.deqar.eu/static/daily-csv/deqar-institutions.csv"
HEADERS = {"User-Agent": "WDI-StudentProject/1.0 (University of Mannheim, Web Data Integration course project)"}
OUT = Path(__file__).resolve().parents[2] / "data" / "deqar" / "deqar_institutions.csv"
SEP = " | "
COLUMNS = ["deqar_id", "name", "alt_names", "country", "city", "website", "founding_year", "closure_year",
           "parent_institutions", "history", "qa_reports", "last_qa_report", "ror_id"]


def read_source():
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    else:
        print("downloading", SOURCE_URL)
        r = requests.get(SOURCE_URL, headers=HEADERS, timeout=300)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def clean(text):
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def unique(values):
    out = []
    for v in values:
        if v and v not in out:
            out.append(v)
    return out


def eter_code(eter_id):
    # FR0123 -> FR
    m = re.match(r"([A-Z]{2})\d", eter_id)
    return m.group(1) if m else ""


def referenced(text):
    # "DEQARINST0015 Name A, DEQARINST0016 Name B" -> ["Name A", "Name B"]
    parts = re.split(r",\s*(?=(?:\d{4}-\d\d-\d\d: [a-z ]+)?DEQARINST\d+ )", text)
    return unique(clean(re.sub(r"DEQARINST\d+ ", "", p)) for p in parts)


def year(date):
    return date[:4] if re.match(r"\d{4}-", date) else ""


def country_by_code(source):
    # the most common country name for each ETER country code
    seen = defaultdict(Counter)
    for r in source:
        code = eter_code(r["eter_id"])
        if r["country"].strip() and code:
            seen[code][re.sub(r"\s*\(.*\)", "", r["country"].strip())] += 1
    return {code: names.most_common(1)[0][0] for code, names in seen.items()}


def make_row(deqar_id, rows, countries_by_code):
    r = rows[0]
    name = clean(re.sub(r"^\(\d+\)\s*", "", r["name_primary"]))   # drop "(00207) " in front
    alt_names = [n for n in unique([clean(r["name_official"]), clean(r["name_versions"])]) if n != name]
    countries = unique(clean(x["country"]) for x in rows)
    if not countries:
        countries = [countries_by_code.get(eter_code(r["eter_id"]), "")]
    website = clean(r["website_link"])
    ror_ids = re.findall(r"ROR:\s*(?:https?://ror\.org/)?(\w+)", r["identifiers_all"])
    return {
        "deqar_id": deqar_id,
        "name": name,
        "alt_names": SEP.join(alt_names),
        "country": SEP.join(filter(None, countries)),
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

    # the file has one row per institution and location
    grouped = defaultdict(list)
    for r in source:
        grouped[r["deqar_id"]].append(r)

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for deqar_id in sorted(grouped):
            writer.writerow(make_row(deqar_id, grouped[deqar_id], countries_by_code))
    print(f"done: {len(grouped)} rows written to {OUT}")


if __name__ == "__main__":
    main()
