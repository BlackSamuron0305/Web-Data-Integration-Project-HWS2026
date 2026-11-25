"""Matching with a small local language model (Ollama, runs on our own GPU, no paid API).
The model is far too slow for all blocked pairs, so for every Wikidata or DEQAR record it only judges its K
most likely ROR candidates (most similar name, plus a bonus for the same website or city). It reads both
records and answers whether they are the same university. The score is how likely the model finds the
answer "true", rescaled on the training pairs so that the usual thresholds (0.30-0.95) can separate
matches from non-matches; the threshold is then chosen on the validation pairs. Every answer is cached, so a rerun or
an interrupted run picks up where it stopped. Pairs outside the shortlist get no link.
Needs a running Ollama server with the model pulled (ollama pull qwen2.5:3b), best started with
OLLAMA_NUM_PARALLEL=8 so it answers several requests at once.
Usage: python local_llm.py first_pass | final            (full run)
       python local_llm.py first_pass | final --speed    (only time 200 pairs)"""
import json
import math
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from rapidfuzz.distance import JaroWinkler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IR, PAIRS, Timer, as_list, candidates, labels, load_all, run_argument, run_folder, run_matchers

RESULTS = Path(__file__).resolve().parent / "results"
CACHE = IR.parents[1] / "results" / "cache" / "local_llm"   # git-ignored
OLLAMA = "http://127.0.0.1:11434"   # not "localhost": on Windows that tries IPv6 first, 2 s lost per request
MODEL = "qwen2.5:3b"
K = 3            # ROR candidates judged per Wikidata or DEQAR record
THREADS = 8      # requests sent at the same time (as many as the server's OLLAMA_NUM_PARALLEL)
PROMPT_VERSION = "v3"   # part of the cache file name: a changed prompt starts a new cache
SEED = 2026

# the wording was tried out on the training pairs only; a first, stricter version (answer true "only if")
# made the model reject a third of the true DEQAR matches
SYSTEM = (
    "You compare two records of universities and other higher-education institutions taken from two "
    "different databases, and decide whether both records describe the same institution. "
    "Records of the same institution often differ: a name can be translated, abbreviated, renamed or have "
    "a city or honorific added; the city can be a district or the wider region; founding years can differ "
    "by a few years; fields can be missing. A shared website domain is strong evidence for the same "
    "institution. Answer false only when the records clearly describe different institutions: a similar "
    "name in another city or country with a different website, or one is only a campus, branch, faculty "
    "or other part of the other. Reply with JSON only: "
    '{"same": true or false, "confidence": a number from 0 to 100}.'
)

# four fixed examples per dataset pair, all from the TRAINING pairs: two matches whose names differ, a
# campus that is not its university, and the same name in another country
SHOTS = {
    ("wikidata", "ror"): [("wikidata_Q4652198", "ror_04ff49a90"),    # AKS University = Amicable Knowledge Solution Univ.
                          ("wikidata_Q1353248", "ror_01kbvt179"),    # New Mexico State University / its Carlsbad campus
                          ("wikidata_Q5017301", "ror_017tszr07"),    # Cagayan de Oro College - PHINMA
                          ("wikidata_Q3106542", "ror_01e8b7f16")],   # La Salle University US / PH
    ("deqar", "ror"): [("deqar_DEQARINST7275", "ror_01dv2a529"),     # International University of Novi Pazar
                       ("deqar_DEQARINST8005", "ror_03fkbz285"),     # Saint Louis University US / its Madrid campus
                       ("deqar_DEQARINST0685", "ror_05w6fhk97"),     # Cologne Business School
                       ("deqar_DEQARINST7747", "ror_02xe5ns62")],    # Jinan University LB / CN
}


def describe(r):
    # one record as a few short lines
    name = r["name"] if isinstance(r["name"], str) else ""
    others = [n for n in as_list(r.get("alternativeNames_alternativeName")) if n != name][:3]
    others += as_list(r.get("acronyms_acronym"))[:2]
    lines = [f"name: {name or 'unknown'}"]
    if others:
        lines.append("other names: " + "; ".join(others))
    place = ", ".join(x for x in [str(r.get("location_city") or "").strip(), r["cc"]] if x and x != "nan")
    if place:
        lines.append(f"place: {place}")
    if r["domains"]:
        lines.append("website: " + ", ".join(r["domains"][:2]))
    if pd.notna(r["year"]):
        lines.append(f"founded: {int(r['year'])}")
    return "\n".join(lines)


def question(r1, r2):
    return f"Record A\n{describe(r1)}\n\nRecord B\n{describe(r2)}\n\nSame institution?"


def best_jw(n1, n2):
    # best Jaro-Winkler similarity over all name variants (like names_best_jaro_winkler)
    return max((JaroWinkler.normalized_similarity(x, y) for x in n1 for y in n2), default=0.0)


def shortlist(L, R, cand, k):
    # cheap ranking: name similarity + 1 for a shared web domain + 0.2 for the same city (checked on the
    # training pairs: with the name alone 75% of the matches are in the top 3, with this 96%)
    r1, r2 = L.set_index("id"), R.set_index("id")
    n1, n2 = r1["names"].to_dict(), r2["names"].to_dict()
    d1, d2 = r1["domains"].to_dict(), r2["domains"].to_dict()
    c1, c2 = r1["city_norm"].to_dict(), r2["city_norm"].to_dict()
    cand = cand.copy()
    cand["sim"] = [best_jw(n1[i], n2[j]) + float(bool(set(d1[i]) & set(d2[j])))
                   + 0.2 * float(bool(c1[i]) and c1[i] == c2[j]) for i, j in zip(cand["id1"], cand["id2"])]
    cand = cand.sort_values(["id1", "sim", "id2"], ascending=[True, False, True])
    return cand.groupby("id1").head(k).reset_index(drop=True)


def examples(L, R, a, b, run):
    # the fixed examples as earlier turns of the chat
    train = labels(a, b, "train", run)
    label = {(i, j): bool(l) for i, j, l in zip(train["id1"], train["id2"], train["label"])}
    rows1, rows2 = L.set_index("id"), R.set_index("id")
    messages = []
    for i, j in SHOTS[(a, b)]:
        messages.append({"role": "user", "content": question(rows1.loc[i], rows2.loc[j])})
        messages.append({"role": "assistant", "content": json.dumps({"same": label[(i, j)], "confidence": 90})})
    return messages, SHOTS[(a, b)]


def p_true(tokens):
    # how likely the model found "true" against "false" at the place where it wrote its answer
    for t in tokens:
        if t["token"].strip().strip('"') in ("true", "false"):
            p = {"true": 0.0, "false": 0.0}
            for alt in t.get("top_logprobs") or [t]:
                word = alt["token"].strip().strip('"')
                if word in p:
                    p[word] += math.exp(alt["logprob"])
            total = p["true"] + p["false"]
            return round(p["true"] / total, 6) if total > 0 else None
    return None


def ask(messages):
    body = {"model": MODEL, "messages": messages, "stream": False, "format": "json", "logprobs": True,
            "top_logprobs": 10, "options": {"temperature": 0, "num_predict": 32, "num_ctx": 2048, "seed": SEED}}
    for attempt in range(3):
        try:
            r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=300)
            r.raise_for_status()
            reply = r.json()
            answer = json.loads(reply["message"]["content"])
            same = answer.get("same")
            if isinstance(same, str):
                same = same.strip().lower() == "true"
            confidence = float(answer.get("confidence", 50))
            return {"same": bool(same), "confidence": max(0.0, min(100.0, confidence)),
                    "p_true": p_true(reply.get("logprobs") or [])}
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
            time.sleep(2 * (attempt + 1))
    return {"same": None, "confidence": None, "p_true": None}   # no usable answer


def raw(answer):
    # the probability of "true"; if that is missing, 0.5-1 for "same" and 0-0.5 for "not same" by the
    # stated confidence; no answer at all = 0
    if answer["same"] is None:
        return 0.0
    if answer.get("p_true") is not None:
        return answer["p_true"]
    c = answer["confidence"] / 200
    return 0.5 + c if answer["same"] else 0.5 - c


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def calibrate(answers, train):
    """The model is very sure of itself: most true matches get a probability below 0.3, the lowest threshold
    we try. A logistic curve on the log-odds, fitted on the TRAINING pairs, spreads the scores out without
    changing their order (Platt scaling). Returns (slope, intercept)."""
    from sklearn.linear_model import LogisticRegression
    x = [[logit(raw(answers[(i, j)]))] for i, j in zip(train["id1"], train["id2"])]
    fit = LogisticRegression(C=1e6).fit(x, train["label"].astype(int))
    return float(fit.coef_[0][0]), float(fit.intercept_[0])


def score(answer, curve):
    slope, intercept = curve
    return 1 / (1 + math.exp(-(slope * logit(raw(answer)) + intercept)))


def asking_seconds(cache_file):
    # total time the model spent answering the questions in this cache file, kept next to it; a rerun that
    # reads answers from the cache still reports how long they took to get
    f = cache_file.with_suffix(".seconds")
    return float(f.read_text()) if f.exists() else 0.0


def judge(pairs, L, R, few_shot, cache_file, label=""):
    """Asks the model about every (id1, id2) not in the cache; returns ({(id1, id2): answer}, pairs/s)."""
    done = {}
    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    done[(d["id1"], d["id2"])] = d
    todo = [p for p in dict.fromkeys(pairs) if p not in done]
    print(f"  {label}: {len(pairs):,} pairs, {len(pairs) - len(todo):,} cached, {len(todo):,} to ask", flush=True)
    rows1, rows2 = L.set_index("id"), R.set_index("id")
    lock = threading.Lock()
    start = time.time()

    def one(p):
        messages = [{"role": "system", "content": SYSTEM}, *few_shot,
                    {"role": "user", "content": question(rows1.loc[p[0]], rows2.loc[p[1]])}]
        return p, ask(messages)

    with open(cache_file, "a", encoding="utf-8") as f, ThreadPoolExecutor(THREADS) as pool:
        futures = [pool.submit(one, p) for p in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            (i, j), answer = fut.result()
            d = {"id1": i, "id2": j, **answer}
            with lock:
                f.write(json.dumps(d) + "\n")
                f.flush()
            done[(i, j)] = d
            if n % 2000 == 0 or n == len(todo):
                rate = n / (time.time() - start)
                print(f"    {n:,}/{len(todo):,} asked, {rate:.1f} pairs/s, "
                      f"about {(len(todo) - n) / rate / 60:.0f} min left", flush=True)
    rate = len(todo) / (time.time() - start) if todo else None
    if todo:
        cache_file.with_suffix(".seconds").write_text(str(round(asking_seconds(cache_file) + time.time() - start, 1)))
    return done, rate


def model_info():
    details = requests.post(f"{OLLAMA}/api/show", json={"model": MODEL}, timeout=30).json().get("details", {})
    version = requests.get(f"{OLLAMA}/api/version", timeout=30).json()["version"]
    tags = requests.get(f"{OLLAMA}/api/tags", timeout=30).json()["models"]
    digest = next((m["digest"] for m in tags if m["name"] == MODEL), None)
    return {"model": MODEL, "digest": digest, "parameter_size": details.get("parameter_size"),
            "quantization": details.get("quantization_level"), "ollama_version": version}


def main(run, speed_only=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    data = load_all(run)
    config = {"run": run, **model_info(), "k": K, "threads": THREADS, "prompt_version": PROMPT_VERSION,
              "temperature": 0, "shortlist": "top-k ROR candidates per record among the blocked candidate pairs, "
              "ranked by best Jaro-Winkler over all name variants + 1 if a web domain is shared + 0.2 if the "
              "city is the same", "score": "probability of the answer true (from the token log-probabilities), "
              "spread out by a logistic curve on its log-odds fitted on the training pairs (Platt scaling)",
              "pairs": {}}

    if speed_only:
        a, b = PAIRS[0]
        L, R = data[a], data[b]
        short = shortlist(L, R, candidates(a, b, run), K)
        few_shot, _ = examples(L, R, a, b, run)
        sample = list(short.sample(200, random_state=SEED)[["id1", "id2"]].itertuples(index=False, name=None))
        test_file = CACHE / f"speedtest_{int(time.time())}.jsonl"
        with Timer() as t:
            answers, _ = judge(sample, L, R, few_shot, test_file, "speed test")
        test_file.unlink()
        total = sum(len(shortlist(data[x], data[y], candidates(x, y, run), K)) for x, y in PAIRS)
        print(f"200 pairs in {t.seconds}s = {200 / t.seconds:.1f} pairs/s; full shortlist {total:,} pairs "
              f"= about {total / (200 / t.seconds) / 3600:.1f} h; "
              f"'same' answers: {sum(bool(v['same']) for v in answers.values())}, "
              f"no answer: {sum(v['same'] is None for v in answers.values())}, "
              f"no probability: {sum(v['p_true'] is None for v in answers.values())}")
        return

    out = run_folder(RESULTS, run)
    for a, b in PAIRS:
        L, R = data[a], data[b]
        cand = candidates(a, b, run)
        short = shortlist(L, R, cand, K)
        few_shot, shots = examples(L, R, a, b, run)
        cache_file = CACHE / f"{a}_{b}_{run}_{MODEL.replace(':', '_')}_{PROMPT_VERSION}.jsonl"

        # training pairs for the calibration, without the four that are shown in the prompt
        train = labels(a, b, "train", run)
        ids1, ids2 = set(L["id"]), set(R["id"])
        train = train[[i in ids1 and j in ids2 and (i, j) not in set(shots)
                       for i, j in zip(train["id1"], train["id2"])]].reset_index(drop=True)

        def match(_):
            with Timer() as t:
                trained, _ = judge(list(zip(train["id1"], train["id2"])), L, R, few_shot, cache_file,
                                   f"{a}-{b} training pairs")
                curve = calibrate(trained, train)
                pairs = list(zip(short["id1"], short["id2"]))
                answers, rate = judge(pairs, L, R, few_shot, cache_file, f"{a}-{b} shortlist")
                corr = pd.DataFrame([{"id1": i, "id2": j, "score": score(answers[(i, j)], curve)}
                                     for i, j in pairs])
            config["pairs"][f"{a}-{b}"] = {
                "blocked_pairs": len(cand), "left_records": int(short["id1"].nunique()),
                "shortlist_pairs": len(short), "seconds_this_run": t.seconds,
                "seconds_asking_in_total": asking_seconds(cache_file),
                "pairs_per_second_this_run": round(rate, 2) if rate else None,
                "same_answers": sum(bool(answers[p]["same"]) for p in pairs),
                "no_answer": sum(answers[p]["same"] is None for p in pairs),
                "calibration_on_train": {"pairs": len(train), "slope": round(curve[0], 4),
                                         "intercept": round(curve[1], 4)},
                "few_shot_train_pairs": [list(s) for s in shots]}
            return corr, max(t.seconds, asking_seconds(cache_file))

        name = f"{MODEL}, top-{K} candidates, 4-shot"
        run_matchers(out, run, a, b, {name: None}, match, labels(a, b, "validation", run))
        with open(out / "configuration.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)


if __name__ == "__main__":
    main(run_argument(), speed_only="--speed" in sys.argv)
