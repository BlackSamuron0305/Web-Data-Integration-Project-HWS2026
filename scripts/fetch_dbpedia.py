"""Fetch all universities from DBpedia, one row per university.

Source:  https://dbpedia.org/sparql
Scope:   every resource of class dbo:University (sub-resources with "__" in the URI are skipped).
Output:  data/dbpedia_universities.csv  (UTF-8, list values separated by " | ")

How it works
  The endpoint returns at most 10,000 rows per request. So each attribute is fetched with its own
  query, page by page (ORDER BY inside a subquery, then LIMIT/OFFSET), and the values are grouped
  per university afterwards.

Rules applied while grouping
  name          English rdfs:label; if there is none, the name is taken from the URI.
  alt_names     foaf:name and dbo:formerName.
  country       dbo:country; if empty, the raw infobox value dbp:country.
  website       foaf:homepage; leftover wiki markup ("%7C...") is cut off, archive.org links unwrapped.
  founding_year earliest year in dbo:foundingDate, otherwise in dbp:established.
  coordinates   first georss:point.
  students      largest dbo:numberOfStudents value.

Run:  python scripts/fetch_dbpedia.py
"""
import csv
import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

import requests

ENDPOINT = "https://dbpedia.org/sparql"
HEADERS = {"User-Agent": "WDI-StudentProject/1.0 (University of Mannheim, Web Data Integration course project)"}
OUT = Path(__file__).resolve().parent.parent / "data" / "dbpedia_universities.csv"
SEP = " | "
PAGE = 10000
RESOURCE = "http://dbpedia.org/resource/"
WIKIDATA = "http://www.wikidata.org/entity/"

PAGED_QUERY = """
SELECT ?u ?v WHERE {
  { SELECT DISTINCT ?u ?v WHERE {
      ?u a dbo:University .
      %s
      FILTER(!CONTAINS(STR(?u), "__"))
    } ORDER BY ?u ?v }
} LIMIT %d OFFSET %d"""

PATTERNS = {
    "id": "BIND(?u AS ?v)",
    "name": '?u rdfs:label ?v . FILTER(LANG(?v) = "en")',
    "alt_name": "{ ?u foaf:name ?v } UNION { ?u dbo:formerName ?v } FILTER(isLiteral(?v))",
    "country": "?u dbo:country ?v .",
    "country_raw": "?u dbp:country ?v .",
    "city": "?u dbo:city ?v .",
    "state": "?u dbo:state ?v .",
    "website": "?u foaf:homepage ?v .",
    "founding_date": "?u dbo:foundingDate ?v .",
    "established_raw": "?u dbp:established ?v . FILTER(DATATYPE(?v) IN (xsd:integer, xsd:date))",
    "point": "?u georss:point ?v .",
    "students": "?u dbo:numberOfStudents ?v .",
    "type": "?u dbo:type ?v .",
    "affiliation": "?u dbo:affiliation ?v .",
    "wikidata_id": '?u owl:sameAs ?v . FILTER(STRSTARTS(STR(?v), "%s"))' % WIKIDATA,
}


def sparql(query):
    for attempt in range(6):
        try:
            r = requests.get(ENDPOINT, params={"query": query, "format": "application/sparql-results+json"},
                             headers=HEADERS, timeout=180)
            if r.status_code == 200 and "X-SQL-State" not in r.headers:  # header = incomplete result
                return r.json()["results"]["bindings"]
        except (requests.RequestException, ValueError):
            pass
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("DBpedia query failed after 6 attempts")


def fetch(key):
    rows, offset = [], 0
    while True:
        page = sparql(PAGED_QUERY % (PATTERNS[key], PAGE, offset))
        rows += page
        offset += PAGE
        time.sleep(0.5)
        if len(page) < PAGE:
            break
    print(f"  {key}: {len(rows)} values", flush=True)
    return rows


def clean(text):
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def label(value):
    """Readable text for a value: resource URIs become their page title."""
    if value.startswith(RESOURCE):
        value = unquote(value[len(RESOURCE):]).replace("_", " ")
    return clean(value)


def unique(values):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def clean_website(url):
    url = url.split("%7C")[0]
    archived = re.match(r"https?://web\.archive\.org/(?:web/)?[\d*]+[a-z_]*/(.+)", url)
    if archived:
        url = re.sub(r"^(https?:)/+", r"\1//", archived.group(1))
        if not url.startswith("http"):
            url = "http://" + url
    return url.strip()


def website_key(url):
    return re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")


def unique_websites(urls):
    best = {}
    for url in sorted(filter(None, map(clean_website, urls))):
        key = website_key(url)
        if key not in best or url.startswith("https://"):
            best[key] = url
    return sorted(best.values())


def years(values):
    found = []
    for v in values:
        m = re.match(r"(\d{3,4})(-\d\d-\d\d)?$", v)
        if m and 800 <= int(m.group(1)) <= 2026:
            found.append(int(m.group(1)))
    return found


def main():
    values = defaultdict(lambda: defaultdict(list))
    for key in PATTERNS:
        for b in fetch(key):
            values[b["u"]["value"]][key].append(b["v"]["value"])

    print("writing", OUT)
    OUT.parent.mkdir(exist_ok=True)
    columns = ["dbpedia_id", "name", "alt_names", "country", "state", "city", "website", "founding_year",
               "latitude", "longitude", "students", "types", "affiliations", "wikidata_id"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for uri in sorted(values):
            v = values[uri]
            name = clean(v["name"][0]) if v["name"] else label(uri)
            founded = years(v["founding_date"]) or years(v["established_raw"])
            point = re.match(r"(-?[\d.]+) (-?[\d.]+)$", min(v["point"], default=""))
            students = [int(s) for s in v["students"] if s.isdigit()]
            writer.writerow({
                "dbpedia_id": unquote(uri[len(RESOURCE):]),
                "name": name,
                "alt_names": SEP.join(sorted(n for n in unique(map(clean, v["alt_name"])) if n != name)),
                "country": SEP.join(unique(map(label, v["country"] or v["country_raw"]))),
                "state": SEP.join(unique(map(label, v["state"]))),
                "city": SEP.join(unique(map(label, v["city"]))),
                "website": SEP.join(unique_websites(v["website"])),
                "founding_year": min(founded) if founded else "",
                "latitude": point.group(1) if point else "",
                "longitude": point.group(2) if point else "",
                "students": max(students) if students else "",
                "types": SEP.join(sorted(unique(map(label, v["type"])))),
                "affiliations": SEP.join(sorted(unique(map(label, v["affiliation"])))),
                "wikidata_id": SEP.join(sorted(unique(w[len(WIKIDATA):] for w in v["wikidata_id"]))),
            })
    print(f"done: {len(values)} rows")


if __name__ == "__main__":
    main()
