"""Build the DEQAR dataset of higher education institutions, one row per institution.

Source:  Database of External Quality Assurance Results (DEQAR) of EQAR, list of higher education
         institutions, https://backend.deqar.eu/static/daily-csv/deqar-institutions.csv
         (linked from https://www.eqar.eu/qa-results/download-data-sets/, refreshed every night)
Scope:   every institution in the file.
Output:  data/deqar_institutions.csv  (UTF-8, list values separated by " | ")

Rules applied
  one institution  the file repeats an institution once per location; these rows are merged.
  name             name_primary; a register number in front of it ("(00207) ...") is cut off.
  alt_names        name_official and name_versions.
  country          the country column; if it is empty, the country of the code that starts the
                   ETER identifier (FR0123 -> France). International alliances have no country.
  website          website_link; "N/A" counts as empty.
  founding_year, closure_year   year of founding_date and closure_date.
  parent_institutions, history  names of the institutions DEQAR refers to, without their DEQAR ids.
  qa_reports, last_qa_report    number of quality assurance reports and date of the latest one.
  ror_id           ROR identifier in identifiers_all (gold standard, not used for matching).

Run:  python scripts/fetch_deqar.py [path/to/deqar-institutions.csv]
      Without a path the file is downloaded.
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
OUT = Path(__file__).resolve().parent.parent / "data" / "deqar_institutions.csv"
SEP = " | "


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
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def eter_country_code(eter_id):
    m = re.match(r"([A-Z]{2})\d", eter_id)
    return m.group(1) if m else ""


def referenced(text):
    """Entries of a field such as "DEQARINST0015 Name A, DEQARINST0016 Name B", without the ids."""
    parts = re.split(r",\s*(?=(?:\d{4}-\d\d-\d\d: [a-z ]+)?DEQARINST\d+ )", text)
    return unique(clean(re.sub(r"DEQARINST\d+ ", "", p)) for p in parts)


def year(date):
    return date[:4] if re.match(r"\d{4}-", date) else ""


def main():
    source = read_source()
    print(f"{len(source)} rows in the file")

    # country of each ETER country code, learned from the rows that have both
    seen = defaultdict(Counter)
    for r in source:
        if r["country"].strip() and eter_country_code(r["eter_id"]):
            seen[eter_country_code(r["eter_id"])][re.sub(r"\s*\(.*\)", "", r["country"].strip())] += 1
    country_of_code = {code: names.most_common(1)[0][0] for code, names in seen.items()}

    grouped = defaultdict(list)
    for r in source:
        grouped[r["deqar_id"]].append(r)

    columns = ["deqar_id", "name", "alt_names", "country", "city", "website", "founding_year", "closure_year",
               "parent_institutions", "history", "qa_reports", "last_qa_report", "ror_id"]
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for deqar_id in sorted(grouped):
            rows = grouped[deqar_id]
            r = rows[0]
            name = clean(re.sub(r"^\(\d+\)\s*", "", r["name_primary"]))
            countries = unique(clean(x["country"]) for x in rows)
            if not countries:
                countries = [country_of_code.get(eter_country_code(r["eter_id"]), "")]
            website = clean(r["website_link"])
            writer.writerow({
                "deqar_id": deqar_id,
                "name": name,
                "alt_names": SEP.join(n for n in unique([clean(r["name_official"]), clean(r["name_versions"])])
                                      if n != name),
                "country": SEP.join(filter(None, countries)),
                "city": SEP.join(unique(clean(x["city"]) for x in rows)),
                "website": "" if website == "N/A" else website,
                "founding_year": year(r["founding_date"]),
                "closure_year": year(r["closure_date"]),
                "parent_institutions": SEP.join(referenced(r["parent_institution"])),
                "history": SEP.join(referenced(r["historic_relationships"])),
                "qa_reports": r["report_count"].strip(),
                "last_qa_report": r["report_last"].strip(),
                "ror_id": SEP.join(unique(re.findall(r"ROR:\s*(?:https?://ror\.org/)?(\w+)", r["identifiers_all"]))),
            })
    print(f"done: {len(grouped)} rows written to {OUT}")


if __name__ == "__main__":
    main()
