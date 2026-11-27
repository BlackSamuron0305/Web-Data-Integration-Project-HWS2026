"""A small local language model (Ollama) decides for each record whether it is a university.

test    300 records with a known answer:
        - the 150 records removed by the cleaning that we checked by hand
          (scripts/02_filtering/validation/<source>/hand_check_removed.csv, truth: hand_verdict)
        - 50 kept records per source from the agents' random sample of the final kept records
          (ai_checks.csv, round 3a, truth: the agents' verdict)
        Each record is asked twice: with the record only ("plain"), and with text from the internet
        ("web"): title, description and start of the record's homepage, or the English Wikidata
        description if there is no website.
rescue  all 9,519 removed records, record only. Counts how many the model would bring back and compares
        them with the verdicts the AI agents gave the removed records (ai_checks.csv).

Needs a running Ollama server with the model pulled (ollama pull qwen2.5:3b).
Usage: python local_llm_cleaning.py test|rescue [model]      (default model qwen2.5:3b)
Writes results/llm_<mode>_<model>.csv (per record) and results/evaluation_<mode>_<model>.csv (the counts).
The model's answers and the fetched web text are cached in results/cache/local_llm_cleaning/ at the
repository root (not in git, like approach 9), so a rerun only asks what is missing.
"""
import csv, html, json, random, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[3]
VAL = REPO / "scripts" / "02_filtering" / "validation"
RESULTS = Path(__file__).resolve().parent / "results"
CACHE = REPO / "results" / "cache" / "local_llm_cleaning"   # git-ignored, like approach 9
OLLAMA = "http://127.0.0.1:11434"   # not "localhost": on Windows that tries IPv6 first
SOURCES = {"wikidata": ("wikidata_universities.csv", "wikidata_id"), "ror": ("ror_education.csv", "ror_id"),
           "deqar": ("deqar_institutions.csv", "deqar_id")}

# the cleaning rules (scripts/02_filtering/rules.md) in short
RULES = """You decide whether a record from a university database is a university in our sense.
KEEP it only if ALL hold:
1. It awards degrees at bachelor's level or higher: universities, universities of applied sciences,
   polytechnics, art and music academies, conservatories, specialised universities.
   DROP community colleges, junior colleges, seminaries and theological schools, vocational and technical
   schools below bachelor's level, high schools, primary schools, language schools.
2. It is a recognised higher education institution.
3. It is an organisation of its own. DROP faculties, schools and departments inside a university,
   campuses and branches of a university, institutes, centres and labs that belong to a university.
4. Its main purpose is education. DROP research institutes without degrees, hospitals (also university
   hospitals), libraries, museums, archives, associations and networks of universities, companies,
   publishers, government agencies.
Answer only with JSON: {"keep": true} or {"keep": false}."""


def read(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def record(source, r, **more):
    extra = " | ".join(x for x in [
        f"types={r['types']}" if r.get("types") else "",
        f"parent={r['parent_ror_id']}" if r.get("parent_ror_id") else "",
        f"parent_institutions={r['parent_institutions']}" if r.get("parent_institutions") else ""] if x)
    return {"source": source, "id": r[SOURCES[source][1]], "name": r["name"], "alt": r["alt_names"],
            "country": r["country"], "city": r["city"], "website": r["website"],
            "year": r["founding_year"], "extra": extra, **more}


def test_records():
    out = []
    for s, (f, key) in SOURCES.items():
        orig = {r[key]: r for r in read(REPO / "data" / s / "original" / f)}
        for h in read(VAL / s / "hand_check_removed.csv"):
            out.append(record(s, orig[h["id"]], set="hand", truth=h["hand_verdict"] == "real_university"))
        kept = {r[key]: r for r in read(REPO / "data" / s / "filtered" / f)}
        checks = [c for c in read(VAL / s / "ai_checks.csv")
                  if c["round"].startswith("3a") and c["verdict"] in ("real", "junk") and c[key] in kept]
        random.Random(0).shuffle(checks)
        out += [record(s, kept[c[key]], set="kept", truth=c["verdict"] == "real") for c in checks[:50]]
    return out


def removed_records():
    out = []
    for s, (f, key) in SOURCES.items():
        orig = {r[key]: r for r in read(REPO / "data" / s / "original" / f)}
        agent = {}
        for c in read(VAL / s / "ai_checks.csv"):   # later rounds overwrite earlier ones
            agent[c[key]] = c["verdict"]
        hand = {h["id"]: h["hand_verdict"] for h in read(VAL / s / "hand_check_removed.csv")}
        for r in read(REPO / "data" / s / "filtered" / "removed.csv"):
            out.append(record(s, orig[r[key]], rule=r["rule"], agent=agent.get(r[key], ""),
                              hand=hand.get(r[key], "")))
    return out


def page_text(url):
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (compatible; uni-classifier-test)"})
        t = r.text[:300_000]
    except Exception as e:
        return f"(website not reachable: {type(e).__name__})"
    title = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', t, re.I)
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    body = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
    parts = [f"title: {html.unescape(title.group(1)).strip()}" if title else "",
             f"description: {html.unescape(desc.group(1)).strip()}" if desc else "", f"text: {body[:500]}"]
    return " | ".join(p for p in parts if p)[:900]


def wikidata_desc(qid):
    try:
        j = requests.get("https://www.wikidata.org/w/api.php", timeout=8, params={
            "action": "wbgetentities", "ids": qid, "props": "descriptions", "languages": "en", "format": "json"},
            headers={"User-Agent": "uni-classifier-test/0.1"}).json()
        return "Wikidata description: " + j["entities"][qid]["descriptions"]["en"]["value"]
    except Exception:
        return ""


def web_texts(recs):
    path = CACHE / "web_text.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def one(r):
        if r["website"]:
            return r["id"], page_text(r["website"] if r["website"].startswith("http") else "http://" + r["website"])
        return r["id"], wikidata_desc(r["id"]) if r["source"] == "wikidata" else ""
    with ThreadPoolExecutor(16) as ex:
        for k, v in ex.map(one, [r for r in recs if r["id"] not in cache]):
            cache[k] = v
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    return cache


def describe(r, web=None):
    lines = [f"name: {r['name']}", f"other names: {r['alt'][:200]}" if r["alt"] else "",
             f"country: {r['country']}", f"city: {r['city']}" if r["city"] else "",
             f"website: {r['website']}" if r["website"] else "", f"founded: {r['year']}" if r["year"] else "",
             f"source info: {r['extra'][:200]}" if r["extra"] else "",
             f"from the internet: {web}" if web else ""]
    return "\n".join(x for x in lines if x)


def ask_all(recs, model, key, web=None):
    """Asks the model about every record; answers are cached per model and variant."""
    path = CACHE / f"{model.replace(':', '_')}_{key}.jsonl"
    cache = {}
    if path.exists():
        for line in open(path, encoding="utf-8"):
            d = json.loads(line); cache[d["id"]] = d["keep"]
    todo = [r for r in recs if r["id"] not in cache]
    t = time.time()
    with open(path, "a", encoding="utf-8") as f:
        for r in todo:
            body = {"model": model, "stream": False, "format": "json",
                    "messages": [{"role": "system", "content": RULES},
                                 {"role": "user", "content": describe(r, web.get(r["id"]) if web else None)}],
                    "options": {"temperature": 0, "num_predict": 16, "num_ctx": 2048, "seed": 0}}
            reply = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=300).json()
            try:
                keep = bool(json.loads(reply["message"]["content"])["keep"])
            except Exception:
                keep = None
            cache[r["id"]] = keep
            f.write(json.dumps({"id": r["id"], "keep": keep}) + "\n")
    if todo:
        print(f"  {key}: {len(todo)} records asked, {len(todo) / (time.time() - t):.1f} records/s")
    for r in recs:
        r[key] = cache[r["id"]]


def test(model):
    recs = test_records()
    web = web_texts(recs)
    ask_all(recs, model, "plain")
    ask_all(recs, model, "web", web)
    rows = []
    for key in ["plain", "web"]:
        for s in ["hand", "kept"]:
            part = [r for r in recs if r["set"] == s]
            real = [r for r in part if r["truth"]]
            junk = [r for r in part if not r["truth"]]
            rows.append({"model": model, "variant": "record only" if key == "plain" else "with homepage",
                         "set": s, "records": len(part), "universities": len(real), "others": len(junk),
                         "model right": sum(r[key] == r["truth"] for r in part),
                         "rules right": sum((s == "kept") == r["truth"] for r in part),  # rules removed "hand", kept "kept"
                         "universities kept": sum(r[key] is True for r in real),
                         "others dropped": sum(r[key] is False for r in junk),
                         "no answer": sum(r[key] is None for r in part)})
    write(recs, f"llm_test_{model.replace(':', '_')}.csv", ["set", "source", "id", "name", "truth", "plain", "web"])
    evaluation(rows, f"evaluation_test_{model.replace(':', '_')}.csv")


def rescue(model):
    recs = removed_records()
    ask_all(recs, model, "plain")
    groups = [("all removed records", recs)]
    groups += [(f"source: {s}", [r for r in recs if r["source"] == s]) for s in SOURCES]
    groups += [(f"agents: {v or 'no verdict'}", [r for r in recs if r["agent"] == v])
               for v in ["real", "unsure", "junk", ""]]
    groups += [(f"hand check: {v}", [r for r in recs if r["hand"] == v])
               for v in ["real_university", "removal_correct"]]
    rows = [{"model": model, "group": g, "records": len(part),
             "brought back": sum(r["plain"] is True for r in part),
             "no answer": sum(r["plain"] is None for r in part)} for g, part in groups]
    write(recs, f"llm_rescue_{model.replace(':', '_')}.csv",
          ["source", "id", "name", "rule", "agent", "hand", "plain"])
    evaluation(rows, f"evaluation_rescue_{model.replace(':', '_')}.csv")


def write(recs, name, cols):
    with open(RESULTS / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(recs)
    print(f"per record: results/{name}")


def evaluation(rows, name):
    with open(RESULTS / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    width = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in rows[0]}
    print("  ".join(k.ljust(width[k]) for k in rows[0]))
    for r in rows:
        print("  ".join(str(r[k]).ljust(width[k]) for k in r))
    print(f"evaluation: results/{name}")


if __name__ == "__main__":
    RESULTS.mkdir(exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    mode, model = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:3b")
    {"test": test, "rescue": rescue}[mode](model)
