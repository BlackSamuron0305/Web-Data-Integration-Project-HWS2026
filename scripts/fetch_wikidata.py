"""Fetch all universities from Wikidata, one row per university.

Source:  https://query.wikidata.org/sparql
Scope:   every item that is an instance of "university" (Q3918) or of one of its subclasses.
Output:  data/wikidata_universities.csv  (UTF-8, list values separated by " | ")

How it works
  1. One query returns the ids of all universities.
  2. The ids are sent in batches; each batch query returns one row per (university, attribute, value).
  3. Countries, places, types and organisations come back as ids and are looked up once.
  4. The values are grouped per university and written as one row.

Rules applied while grouping
  name          English label; if there is none, a label in another language.
  alt_names     English aliases, native label (P1705), official name (P1448).
  country       current countries are preferred over dissolved states (e.g. Soviet Union).
  city          headquarters location (P159) if it is a settlement, otherwise the place the
                university is located in (P131); if that place is a district, the settlement
                it belongs to. Falls back to the raw P131 value.
  founding_year earliest year of inception (P571).
  students      student count (P2196): preferred value, otherwise the most recent one.

Run:  python scripts/fetch_wikidata.py
"""
import csv
import re
import time
from collections import defaultdict
from pathlib import Path

import requests

ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "WDI-StudentProject/1.0 (University of Mannheim, Web Data Integration course project)",
    "Accept": "application/sparql-results+json",
}
OUT = Path(__file__).resolve().parent.parent / "data" / "wikidata_universities.csv"
SEP = " | "
BATCH = 250
ENTITY = "http://www.wikidata.org/entity/"

IDS_QUERY = "SELECT DISTINCT ?u WHERE { ?u wdt:P31/wdt:P279* wd:Q3918 }"

ATTRIBUTE_QUERY = """
SELECT ?u ?k ?v ?x ?y WHERE {
  VALUES ?u { %s }
  { ?u rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("name" AS ?k) }
  UNION { ?u skos:altLabel ?v . FILTER(LANG(?v) = "en") BIND("alt_name" AS ?k) }
  UNION { ?u wdt:P1705 ?v . BIND("alt_name" AS ?k) }
  UNION { ?u wdt:P1448 ?v . BIND("alt_name" AS ?k) }
  UNION { ?u wdt:P1813 ?v . BIND("acronym" AS ?k) }
  UNION { ?u wdt:P17 ?v . BIND("country" AS ?k) }
  UNION { ?u wdt:P131 ?v . BIND("located_in" AS ?k) }
  UNION { ?u wdt:P159 ?v . BIND("headquarters" AS ?k) }
  UNION { ?u wdt:P856 ?v . BIND("website" AS ?k) }
  UNION { ?u wdt:P625 ?v . BIND("coordinates" AS ?k) }
  UNION { ?u wdt:P571 ?v . BIND("founded" AS ?k) }
  UNION { ?u wdt:P31 ?v . BIND("type" AS ?k) }
  UNION { ?u wdt:P463 ?v . BIND("member_of" AS ?k) }
  UNION { ?u wdt:P6782 ?v . BIND("ror_id" AS ?k) }
  UNION { ?a schema:about ?u ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?v .
          BIND("wikipedia_en" AS ?k) }
  UNION { ?u p:P2196 ?s . ?s ps:P2196 ?v ; wikibase:rank ?x . OPTIONAL { ?s pq:P585 ?y }
          BIND("students" AS ?k) }
}"""

ANY_LABEL_QUERY = """
SELECT ?u ?v (LANG(?v) AS ?x) WHERE { VALUES ?u { %s } ?u rdfs:label ?v }"""

LOOKUP_QUERY = """
SELECT ?u ?k ?v WHERE {
  VALUES ?u { %s }
  { ?u rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("label" AS ?k) }
  UNION { ?u wdt:P297 ?v . BIND("iso" AS ?k) }
  UNION { ?u wdt:P576 ?v . BIND("dissolved" AS ?k) }
}"""

PLACE_QUERY = """
SELECT ?u ?k ?v WHERE {
  VALUES ?u { %s }
  { ?u rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("label" AS ?k) }
  UNION { ?u wdt:P131 ?v . BIND("parent" AS ?k) }
  UNION { ?u wdt:P31/wdt:P279* wd:Q486972 . BIND("yes" AS ?v) BIND("settlement" AS ?k) }
}"""

LABEL_LANGUAGES = ["mul", "en-gb", "en-ca", "en-us", "de", "fr", "es", "it", "pt", "nl", "sv", "pl", "id", "tr"]


def sparql(query):
    for attempt in range(6):
        wait = 10 * (attempt + 1)
        try:
            r = requests.post(ENDPOINT, data={"query": query}, headers=HEADERS, timeout=180)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            wait = int(r.headers.get("Retry-After", wait))
        except (requests.RequestException, ValueError):
            pass
        time.sleep(wait)
    raise RuntimeError("Wikidata query failed after 6 attempts")


def batches(ids):
    ids = sorted(ids, key=lambda q: int(q[1:]))
    for i in range(0, len(ids), BATCH):
        yield ids[i:i + BATCH]


def run_batched(query, ids, what):
    rows = []
    for n, batch in enumerate(batches(ids), 1):
        rows += sparql(query % " ".join("wd:" + q for q in batch))
        print(f"  {what}: batch {n} ({len(rows)} rows)", flush=True)
        time.sleep(0.5)
    return rows


def qid(binding):
    """Return the Q-id of an entity binding, or None for literals and unknown values."""
    if binding["type"] == "uri" and binding["value"].startswith(ENTITY):
        return binding["value"][len(ENTITY):]
    return None


def lookup(query, ids, what):
    info = defaultdict(lambda: defaultdict(list))
    for b in run_batched(query, ids, what):
        info[qid(b["u"])][b["k"]["value"]].append(qid(b["v"]) or b["v"]["value"])
    return info


def clean(text):
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def unique(values):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def pick_label(labels):
    """labels: list of (language, text). Used only when there is no English label."""
    by_lang = {lang: text for lang, text in sorted(labels)}
    for lang in LABEL_LANGUAGES:
        if lang in by_lang:
            return by_lang[lang]
    latin = [t for _, t in sorted(labels) if re.search(r"[A-Za-z]", t)]
    return latin[0] if latin else (sorted(labels)[0][1] if labels else "")


def website_key(url):
    return re.sub(r"^https?://(www\.)?", "", url.strip().lower()).rstrip("/")


def unique_websites(urls):
    best = {}
    for url in sorted(urls):
        key = website_key(url)
        if key not in best or url.startswith("https://"):
            best[key] = url
    return sorted(best.values())


def year_of(value):
    m = re.match(r"(-?)(\d{4})-", value)
    return int(m.group(1) + m.group(2)) if m else None


def pick_students(statements):
    """statements: list of (value, rank, date). Preferred rank first, then newest, then largest."""
    usable = [s for s in statements if not s[1].endswith("DeprecatedRank") and re.fullmatch(r"\d+(\.\d+)?", s[0])]
    if not usable:
        return ""
    best = max(usable, key=lambda s: (s[1].endswith("PreferredRank"), s[2], float(s[0])))
    return str(int(float(best[0])))


def main():
    print("1/4 university ids")
    ids = unique(qid(b["u"]) for b in sparql(IDS_QUERY))
    print(f"  {len(ids)} universities")

    print("2/4 attributes")
    values = defaultdict(lambda: defaultdict(list))
    students = defaultdict(list)
    for b in run_batched(ATTRIBUTE_QUERY, ids, "attributes"):
        u, key, v = qid(b["u"]), b["k"]["value"], b["v"]
        if key == "students":
            students[u].append((v["value"], b["x"]["value"], b.get("y", {}).get("value", "")))
        elif key in ("country", "located_in", "headquarters", "type", "member_of"):
            if qid(v):
                values[u][key].append(qid(v))
        elif v["type"] != "bnode" and not v["value"].startswith("http://www.wikidata.org/.well-known/"):
            values[u][key].append(v["value"])

    no_name = [u for u in ids if not values[u]["name"]]
    other_labels = defaultdict(list)
    if no_name:
        for b in run_batched(ANY_LABEL_QUERY, no_name, "labels in other languages"):
            other_labels[qid(b["u"])].append((b["x"]["value"], b["v"]["value"]))

    print("3/4 countries, places, types, organisations")
    place_ids = {q for u in ids for key in ("located_in", "headquarters") for q in values[u][key]}
    other_ids = {q for u in ids for key in ("country", "type", "member_of") for q in values[u][key]}
    places = lookup(PLACE_QUERY, place_ids, "places")
    parent_ids = {p for q in place_ids for p in places[q]["parent"] if p not in place_ids}
    places.update(lookup(PLACE_QUERY, parent_ids, "parent places"))
    things = lookup(LOOKUP_QUERY, other_ids, "countries/types/organisations")

    def labels(info, qids):
        return unique(clean(info[q]["label"][0]) for q in qids if info[q]["label"])

    def is_settlement(q):
        return bool(places[q]["settlement"])

    def city_of(v):
        for candidates in (
            [q for q in v["headquarters"] if is_settlement(q)],
            [q for q in v["located_in"] if is_settlement(q)],
            [p for q in v["located_in"] for p in places[q]["parent"] if is_settlement(p)],
            v["headquarters"] or v["located_in"],
        ):
            found = labels(places, candidates)
            if found:
                return found
        return []

    print("4/4 writing", OUT)
    OUT.parent.mkdir(exist_ok=True)
    columns = ["wikidata_id", "name", "alt_names", "acronyms", "country", "country_code", "city", "website",
               "founding_year", "latitude", "longitude", "students", "types", "member_of", "ror_id", "wikipedia_en"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for u in sorted(ids, key=lambda q: int(q[1:])):
            v = values[u]
            name = clean(v["name"][0]) if v["name"] else clean(pick_label(other_labels[u]))
            countries = unique(v["country"])
            current = [c for c in countries if not things[c]["dissolved"]]
            countries = current or countries
            years = [y for y in map(year_of, v["founded"]) if y is not None]
            point = re.match(r"Point\((-?[\d.]+) (-?[\d.]+)\)", min(v["coordinates"], default=""))
            writer.writerow({
                "wikidata_id": u,
                "name": name,
                "alt_names": SEP.join(sorted(n for n in unique(map(clean, v["alt_name"])) if n != name)),
                "acronyms": SEP.join(sorted(unique(map(clean, v["acronym"])))),
                "country": SEP.join(labels(things, countries)),
                "country_code": SEP.join(unique(things[c]["iso"][0] for c in countries if things[c]["iso"])),
                "city": SEP.join(city_of(v)),
                "website": SEP.join(unique_websites(v["website"])),
                "founding_year": min(years) if years else "",
                "latitude": point.group(2) if point else "",
                "longitude": point.group(1) if point else "",
                "students": pick_students(students[u]),
                "types": SEP.join(sorted(labels(things, unique(v["type"])))),
                "member_of": SEP.join(sorted(labels(things, unique(v["member_of"])))),
                "ror_id": SEP.join(sorted(unique(v["ror_id"]))),
                "wikipedia_en": SEP.join(sorted(unique(t.replace(" ", "_") for t in v["wikipedia_en"]))),
            })
    print(f"done: {len(ids)} rows")


if __name__ == "__main__":
    main()
