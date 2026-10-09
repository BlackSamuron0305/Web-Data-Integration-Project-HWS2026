"""Fetch all universities from OpenStreetMap, one row per university.

Source:  OpenStreetMap, queried through the Overpass API (https://overpass-api.de/api/interpreter)
Scope:   every node, way and relation tagged amenity=university that has a name.
Output:  data/osm_universities.csv  (UTF-8, list values separated by " | ")

How it works
  1. The world is queried in 30-degree slices of longitude, because one query for the whole world
     times out. Each object comes back with its tags and one coordinate (its centre).
  2. OpenStreetMap has no country tag, so the country of each object is looked up from its
     coordinate in the country borders of Natural Earth (1:10m, public domain).
  3. The campuses of one university are mapped as separate objects; they are merged into one row.

Rules applied while grouping
  one university  objects with the same wikidata tag. Objects without that tag are grouped by name
                  and country and join the tagged university of the same name and country.
  values          taken from the object with the most tags; gaps are filled from the other objects.
  alt_names       name:en, int_name, official_name, alt_name, old_name.
  acronyms        short_name.
  city, street, postcode   the addr:* tags; nothing is derived from the coordinates.
  website         website, contact:website, url; leading http/https and www variants are merged.
  founding_year   year in start_date.
  wikidata_id, wikipedia_en   links to the other sources (gold standard, not used for matching).

Run:  python scripts/fetch_osm.py [path/to/overpass-result.json]
      Without a path the data is downloaded, which takes about 15 minutes.
"""
import csv
import json
import re
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import requests

ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.openstreetmap.fr/api/interpreter"]
HEADERS = {"User-Agent": "WDI-StudentProject/1.0 (University of Mannheim, Web Data Integration course project)"}
QUERY = ('[out:json][timeout:300][maxsize:536870912];'
         'nwr["amenity"="university"]["name"](-90,%d,90,%d);out tags center;')
BORDERS_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
               "ne_10m_admin_0_countries.geojson")
OUT = Path(__file__).resolve().parent.parent / "data" / "osm_universities.csv"
SEP = " | "
ALT_NAME_TAGS = ["name:en", "int_name", "official_name", "official_name:en", "alt_name", "alt_name:en",
                 "old_name", "old_name:en"]
TYPE_RANK = {"relation": 0, "way": 1, "node": 2}


def overpass(query):
    for attempt in range(8):
        try:
            r = requests.post(ENDPOINTS[attempt % len(ENDPOINTS)], data={"data": query}, headers=HEADERS,
                              timeout=400)
            result = r.json() if r.status_code == 200 else {"remark": "failed"}
            if "remark" not in result:  # remark = the server stopped early
                return result["elements"]
        except (requests.RequestException, ValueError):
            pass
        time.sleep(20 * (attempt + 1))
    raise RuntimeError("Overpass query failed after 8 attempts")


def download():
    elements = {}
    for west in range(-180, 180, 30):
        page = overpass(QUERY % (west, west + 30))
        for e in page:  # an object that crosses a slice border is returned twice
            elements[(e["type"], e["id"])] = e
        print(f"  longitude {west} to {west + 30}: {len(page)} objects", flush=True)
        time.sleep(5)
    return list(elements.values())


def load_borders():
    path = Path(tempfile.gettempdir()) / "ne_10m_admin_0_countries.geojson"
    if not path.exists():
        print("downloading", BORDERS_URL)
        r = requests.get(BORDERS_URL, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
    countries = []
    with open(path, encoding="utf-8") as f:
        for feature in json.load(f)["features"]:
            p, geometry = feature["properties"], feature["geometry"]
            polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
            code = p["ISO_A2_EH"] if p["ISO_A2_EH"] != "-99" else ""
            countries.append((p["NAME"], code, [[np.asarray(ring, dtype=float) for ring in poly]
                                                for poly in polygons]))
    return countries


def inside(ring, x, y):
    """Ray casting: True for every point (x, y) that lies inside the ring."""
    x1, y1, x2, y2 = ring[:-1, 0], ring[:-1, 1], ring[1:, 0], ring[1:, 1]
    hit = np.zeros(len(x), dtype=bool)
    step = max(1, 4_000_000 // len(ring))
    for start in range(0, len(x), step):
        px, py = x[start:start + step, None], y[start:start + step, None]
        crosses = (y1 > py) != (y2 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            at = (x2 - x1) * (py - y1) / (y2 - y1) + x1
        hit[start:start + step] = (crosses & (px < at)).sum(axis=1) % 2 == 1
    return hit


def lookup_countries(lon, lat):
    """Country name and ISO code for every coordinate; empty where the coordinate is missing."""
    borders = load_borders()
    names = np.full(len(lon), "", dtype=object)
    codes = np.full(len(lon), "", dtype=object)
    todo = ~np.isnan(lon)
    for name, code, polygons in borders:
        for outer, *holes in polygons:
            box = np.flatnonzero(todo & (lon >= outer[:, 0].min()) & (lon <= outer[:, 0].max())
                                 & (lat >= outer[:, 1].min()) & (lat <= outer[:, 1].max()))
            if not len(box):
                continue
            hit = inside(outer, lon[box], lat[box])
            for hole in holes:
                hit[hit] &= ~inside(hole, lon[box][hit], lat[box][hit])
            names[box[hit]], codes[box[hit]], todo[box[hit]] = name, code, False
    # coordinates just off the coast: country of the nearest border point, if closer than about 30 km
    vertices = np.concatenate([poly[0] for _, _, polygons in borders for poly in polygons])
    owner = np.concatenate([np.full(len(poly[0]), i) for i, (_, _, polygons) in enumerate(borders)
                            for poly in polygons])
    for i in np.flatnonzero(todo):
        distance = (vertices[:, 0] - lon[i]) ** 2 + (vertices[:, 1] - lat[i]) ** 2
        nearest = distance.argmin()
        if distance[nearest] < 0.3 ** 2:
            names[i], codes[i] = borders[owner[nearest]][:2]
    return names, codes


def clean(text):
    invisible = "[​-‏­﻿]"  # zero-width characters, soft hyphen, byte order mark
    return re.sub(r"\s+", " ", re.sub(invisible, "", text).replace("|", "/")).strip()


def norm(name):
    return re.sub(r"[\W_]+", " ", name.casefold()).strip()


def unique(values):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def wikidata_ids(obj):
    return [q for q in re.split(r"\s*;\s*", obj["tags"].get("wikidata", "")) if re.fullmatch(r"Q\d+", q)]


def values(obj, tags):
    return unique(clean(v) for t in tags for v in obj["tags"].get(t, "").split(";"))


def first(members, tags):
    """Values of the first object (the one with the most tags comes first) that has any of the tags."""
    for obj in members:
        found = values(obj, tags)
        if found:
            return found
    return []


def website_key(url):
    return re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")


def unique_websites(urls):
    best = {}
    for url in sorted(u if re.match(r"https?://", u, re.I) else "http://" + u for u in urls):
        key = website_key(url)
        if key not in best or url.startswith("https://"):
            best[key] = url
    return sorted(best.values())


def year(values_):
    for v in values_:
        m = re.match(r"~?(\d{4})\b", v)
        if m and 800 <= int(m.group(1)) <= 2026:
            return int(m.group(1))
    return ""


def street(members):
    for obj in members:
        if values(obj, ["addr:street"]):
            return " ".join(values(obj, ["addr:street"])[:1] + values(obj, ["addr:housenumber"])[:1])
    return ""


def wikipedia_en(obj):
    title = obj["tags"].get("wikipedia:en", "")
    if obj["tags"].get("wikipedia", "").startswith("en:"):
        title = obj["tags"]["wikipedia"][3:]
    return clean(title).replace(" ", "_")


def group(objects):
    """Lists of objects that describe the same university."""
    tagged, untagged, owners = defaultdict(list), defaultdict(list), defaultdict(set)
    for obj in objects:
        key = (norm(obj["tags"]["name"]), obj["country_code"])
        ids = wikidata_ids(obj)
        if ids:
            tagged[ids[0]].append(obj)
            owners[key].add(ids[0])
        else:
            untagged[key].append(obj)
    groups = []
    for key, members in untagged.items():
        if len(owners[key]) == 1:
            tagged[next(iter(owners[key]))] += members
        else:
            groups.append(members)
    return groups + list(tagged.values())


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            objects = json.load(f)["elements"]
    else:
        print("querying", ENDPOINTS[0])
        objects = download()
    print(f"{len(objects)} objects")

    for obj in objects:
        point = obj.get("center", obj)
        obj["lat"], obj["lon"] = point.get("lat"), point.get("lon")
    lon = np.array([o["lon"] if o["lon"] is not None else np.nan for o in objects], dtype=float)
    lat = np.array([o["lat"] if o["lat"] is not None else np.nan for o in objects], dtype=float)
    countries, codes = lookup_countries(lon, lat)
    for obj, country, code in zip(objects, countries, codes):
        obj["country"], obj["country_code"] = country, code
    print(f"{sum(1 for o in objects if not o['country'])} objects without a country")

    rows = []
    for members in group(objects):
        members.sort(key=lambda o: (-len(o["tags"]), TYPE_RANK[o["type"]], o["id"]))
        main_obj = members[0]
        name = clean(main_obj["tags"]["name"])
        rows.append({
            "osm_id": f"{main_obj['type']}/{main_obj['id']}",
            "name": name,
            "alt_names": SEP.join(sorted(n for n in unique(v for o in members for v in values(o, ALT_NAME_TAGS))
                                         if n != name)),
            "acronyms": SEP.join(sorted(unique(v for o in members for v in values(o, ["short_name", "short_name:en"])))),
            "country": main_obj["country"],
            "country_code": main_obj["country_code"],
            "city": SEP.join(first(members, ["addr:city"])[:1]),
            "street": street(members),
            "postcode": SEP.join(first(members, ["addr:postcode"])[:1]),
            "website": SEP.join(unique_websites(first(members, ["website", "contact:website", "url"]))),
            "phone": SEP.join(first(members, ["phone", "contact:phone"])),
            "founding_year": year(first(members, ["start_date"])),
            "latitude": main_obj["lat"] if main_obj["lat"] is not None else "",
            "longitude": main_obj["lon"] if main_obj["lon"] is not None else "",
            "operator_type": SEP.join(first(members, ["operator:type"])),
            "wikidata_id": SEP.join(unique(q for o in members for q in wikidata_ids(o))),
            "wikipedia_en": SEP.join(unique(wikipedia_en(o) for o in members)),
        })

    print("writing", OUT)
    OUT.parent.mkdir(exist_ok=True)
    rows.sort(key=lambda r: (TYPE_RANK[r["osm_id"].split("/")[0]], int(r["osm_id"].split("/")[1])))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"done: {len(rows)} rows")


if __name__ == "__main__":
    main()
