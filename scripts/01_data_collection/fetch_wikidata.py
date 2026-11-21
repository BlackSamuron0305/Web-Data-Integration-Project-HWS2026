"""Wikidata: download all universities (instances of Q3918 or a subclass) to data/wikidata/original/.

Usage: python fetch_wikidata.py
"""
import re
import time
from collections import defaultdict

import requests

from common import DATA, SEP, USER_AGENT, clean, unique, write_csv

ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"}
OUT = DATA / "wikidata" / "original" / "wikidata_universities.csv"
BATCH = 250   # universities per query
ENTITY = "http://www.wikidata.org/entity/"
COLUMNS = ["wikidata_id", "name", "alt_names", "acronyms", "country", "country_code", "city", "website",
           "founding_year", "latitude", "longitude", "students", "types", "member_of", "ror_id", "wikipedia_en"]

IDS_QUERY = "SELECT DISTINCT ?u WHERE { ?u wdt:P31/wdt:P279* wd:Q3918 }"

# one row per (university, attribute, value)
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

# labels in any language, for universities without an English label
ANY_LABEL_QUERY = """
SELECT ?u ?v (LANG(?v) AS ?x) WHERE { VALUES ?u { %s } ?u rdfs:label ?v }"""

# countries, types and organisations
LOOKUP_QUERY = """
SELECT ?u ?k ?v WHERE {
  VALUES ?u { %s }
  { ?u rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("label" AS ?k) }
  UNION { ?u wdt:P297 ?v . BIND("iso" AS ?k) }
  UNION { ?u wdt:P576 ?v . BIND("dissolved" AS ?k) }
}"""

# places: label, the place they are in, and whether they are a settlement (city, town ...)
PLACE_QUERY = """
SELECT ?u ?k ?v WHERE {
  VALUES ?u { %s }
  { ?u rdfs:label ?v . FILTER(LANG(?v) = "en") BIND("label" AS ?k) }
  UNION { ?u wdt:P131 ?v . BIND("parent" AS ?k) }
  UNION { ?u wdt:P31/wdt:P279* wd:Q486972 . BIND("yes" AS ?v) BIND("settlement" AS ?k) }
}"""

LABEL_LANGUAGES = ["mul", "en-gb", "en-ca", "en-us", "de", "fr", "es", "it", "pt", "nl", "sv", "pl", "id", "tr"]


def sparql(query):
    # on an error wait and try again, at most 6 times
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


def by_number(ids):
    # Q2 before Q10
    return sorted(ids, key=lambda q: int(q[1:]))


def run_batched(query, ids, what):
    # the ids go in at %s, BATCH at a time
    ids = by_number(ids)
    rows = []
    for n, start in enumerate(range(0, len(ids), BATCH), 1):
        batch = ids[start:start + BATCH]
        rows += sparql(query % " ".join("wd:" + q for q in batch))
        print(f"  {what}: batch {n} ({len(rows)} rows)", flush=True)
        time.sleep(0.5)
    return rows


def qid(binding):
    # None for literals
    if binding["type"] == "uri" and binding["value"].startswith(ENTITY):
        return binding["value"][len(ENTITY):]
    return None


def lookup(query, ids, what):
    # info[id][key] is the list of values
    info = defaultdict(lambda: defaultdict(list))
    for b in run_batched(query, ids, what):
        info[qid(b["u"])][b["k"]["value"]].append(qid(b["v"]) or b["v"]["value"])
    return info


def pick_label(labels):
    # labels are (language, text); first a preferred language, then any latin label, then any
    by_lang = dict(sorted(labels))
    for lang in LABEL_LANGUAGES:
        if lang in by_lang:
            return by_lang[lang]
    latin = [t for _, t in sorted(labels) if re.search(r"[A-Za-z]", t)]
    if latin:
        return latin[0]
    return sorted(labels)[0][1] if labels else ""


def unique_websites(urls):
    # one url per site, https preferred
    best = {}
    for url in sorted(urls):
        key = re.sub(r"^https?://(www\.)?", "", url.strip().lower()).rstrip("/")
        if key not in best or url.startswith("https://"):
            best[key] = url
    return sorted(best.values())


def year_of(value):
    # "-0300-01-01..." gives -300
    m = re.match(r"(-?)(\d{4})-", value)
    return int(m.group(1) + m.group(2)) if m else None


def pick_students(statements):
    # statements are (value, rank, date); preferred rank wins, then the newest, then the largest
    usable = [s for s in statements
              if not s[1].endswith("DeprecatedRank") and re.fullmatch(r"\d+(\.\d+)?", s[0])]
    if not usable:
        return ""
    best = max(usable, key=lambda s: (s[1].endswith("PreferredRank"), s[2], float(s[0])))
    return str(int(float(best[0])))


def fetch_attributes(ids):
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
    return values, students


def fetch_other_labels(ids, values):
    other = defaultdict(list)
    no_name = [u for u in ids if not values[u]["name"]]
    for b in run_batched(ANY_LABEL_QUERY, no_name, "labels in other languages"):
        other[qid(b["u"])].append((b["x"]["value"], b["v"]["value"]))
    return other


def fetch_places(ids, values):
    # the places the universities are in, and the places those are in
    place_ids = {q for u in ids for key in ("located_in", "headquarters") for q in values[u][key]}
    places = lookup(PLACE_QUERY, place_ids, "places")
    parent_ids = {p for q in place_ids for p in places[q]["parent"] if p not in place_ids}
    places.update(lookup(PLACE_QUERY, parent_ids, "parent places"))
    return places


def fetch_things(ids, values):
    thing_ids = {q for u in ids for key in ("country", "type", "member_of") for q in values[u][key]}
    return lookup(LOOKUP_QUERY, thing_ids, "countries/types/organisations")


def labels_of(info, qids):
    return unique(clean(info[q]["label"][0]) for q in qids if info[q]["label"])


def city_of(v, places):
    # headquarters if it is a city, else the place it is located in, else that place's parent
    in_parent = []
    for q in v["located_in"]:
        for p in places[q]["parent"]:
            if places[p]["settlement"]:
                in_parent.append(p)
    for candidates in (
        [q for q in v["headquarters"] if places[q]["settlement"]],
        [q for q in v["located_in"] if places[q]["settlement"]],
        in_parent,
        v["headquarters"] or v["located_in"],
    ):
        found = labels_of(places, candidates)
        if found:
            return found
    return []


def make_row(u, v, students, other_labels, places, things):
    name = clean(v["name"][0]) if v["name"] else clean(pick_label(other_labels))

    countries = unique(v["country"])
    current = [c for c in countries if not things[c]["dissolved"]]   # e.g. not the Soviet Union
    countries = current or countries

    years = [y for y in map(year_of, v["founded"]) if y is not None]
    point = re.match(r"Point\((-?[\d.]+) (-?[\d.]+)\)", min(v["coordinates"], default=""))

    return {
        "wikidata_id": u,
        "name": name,
        "alt_names": SEP.join(sorted(n for n in unique(map(clean, v["alt_name"])) if n != name)),
        "acronyms": SEP.join(sorted(unique(map(clean, v["acronym"])))),
        "country": SEP.join(labels_of(things, countries)),
        "country_code": SEP.join(unique(things[c]["iso"][0] for c in countries if things[c]["iso"])),
        "city": SEP.join(city_of(v, places)),
        "website": SEP.join(unique_websites(v["website"])),
        "founding_year": min(years) if years else "",
        "latitude": point.group(2) if point else "",
        "longitude": point.group(1) if point else "",
        "students": pick_students(students),
        "types": SEP.join(sorted(labels_of(things, unique(v["type"])))),
        "member_of": SEP.join(sorted(labels_of(things, unique(v["member_of"])))),
        "ror_id": SEP.join(sorted(unique(v["ror_id"]))),
        "wikipedia_en": SEP.join(sorted(unique(t.replace(" ", "_") for t in v["wikipedia_en"]))),
    }


def main():
    print("1/4 university ids")
    ids = unique(qid(b["u"]) for b in sparql(IDS_QUERY))
    print(f"  {len(ids)} universities")

    print("2/4 attributes")
    values, students = fetch_attributes(ids)
    other_labels = fetch_other_labels(ids, values)

    print("3/4 countries, places, types, organisations")
    places = fetch_places(ids, values)
    things = fetch_things(ids, values)

    print("4/4 writing")
    rows = [make_row(u, values[u], students[u], other_labels[u], places, things) for u in by_number(ids)]
    write_csv(OUT, COLUMNS, rows)


if __name__ == "__main__":
    main()
