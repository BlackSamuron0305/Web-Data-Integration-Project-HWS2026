"""Checks the hand-labelled gold set (500 pairs, Chellapuram Keerthan Reddy) and uses it to evaluate the links.

Usage: python gold_check.py   (from this folder; reads only files in the repository)

Inputs (this folder):
  annotation_sample_completed.xlsx  the hand labels (sheet "annotate"), exported to gold_hand_labelled.csv
  blind_ai_labels.csv               750 blind labels by Claude Haiku agents (500 gold pairs + 250 round-2 test pairs)
  results/blind_batches/*.jsonl     what the agents saw (no labels, no ID links); only used for names
Writes to results/:
  label_agreement.csv, disagreements.csv            a. gold labels vs blind labels (and ours vs blind)
  gold_membership.csv, sampling_design.csv,
  sampling_strata.csv                               b. how the 500 pairs were drawn
  evaluation.csv                                    c. P/R/F1 of round 3, round 8 before cut-off, round 8 final
  population_estimate.csv, ai_check_coverage.csv    d./e. stratified precision of all final links, wrong links
  figures/                                          precision by stratum (png)
"""
import json
import re
import unicodedata
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
IR = HERE.parent
DATA = IR.parents[1] / "data"
FINAL = IR / "05_final" / "results"
LABELS = IR / "01_labels" / "results"
CANDIDATES = IR / "02_blocking" / "results" / "candidates"
RESULTS = HERE / "results"
FIGURES = RESULTS / "figures"

PAIRS = {"wikidata": "Wikidata-ROR", "deqar": "DEQAR-ROR"}
DOWNLOAD = {"wikidata": "wikidata_universities.csv", "ror": "ror_education.csv", "deqar": "deqar_institutions.csv"}
ID_COLUMN = {"wikidata": "wikidata_id", "ror": "ror_id", "deqar": "deqar_id"}
CORR = {"r3": "round 3", "r8_before_cutoff": "round 8 before cut-off", "r8": "round 8 final"}
STRATA = ["ID link", "ID conflict", "no ID info"]
Z = 1.959964
SEED = 0
DRAWS = 200_000

# same words as common.GENERIC: the "country + name word" blocking key ignores them
GENERIC = set("university universitat universite universidad universita college institute school academy "
              "national state technology science sciences of the and de di la der fur und du des".split())


# ---------------------------------------------------------------- helpers

def wilson(k, n):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if p + r else np.nan
    return p, r, f


def last_part(value):
    # ROR ids may be URLs: keep the last path part
    return value.strip().rstrip("/").split("/")[-1]


def split_ids(value):
    return [last_part(x) for x in str(value).split(" | ") if x.strip()]


def norm(value):
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace("&", " and ")
    return re.sub(r"[\W_]+", " ", s).strip()


def host(url):
    url = str(url).strip().lower()
    if not url:
        return ""
    url = re.sub(r"^[a-z]+://", "", url).split("/")[0].split(":")[0]
    return url[4:] if url.startswith("www.") else url


def read_source(name, folder="original"):
    return pd.read_csv(DATA / name / folder / DOWNLOAD[name], dtype=str, keep_default_na=False)


def save_csv(df, name):
    df.to_csv(RESULTS / name, index=False, encoding="utf-8")
    print(f"wrote results/{name} ({len(df)} rows)")


# ---------------------------------------------------------------- inputs

def load_gold():
    gold = pd.read_excel(HERE / "annotation_sample_completed.xlsx", sheet_name="annotate",
                         dtype=str, keep_default_na=False)
    gold.to_csv(HERE / "gold_hand_labelled.csv", index=False, encoding="utf-8")
    print(f"wrote gold_hand_labelled.csv ({len(gold)} rows, exported from the xlsx)")
    gold["a"] = gold["A_record_id"].str.split("_").str[0]
    assert set(gold["a"]) == set(PAIRS) and gold["B_record_id"].str.startswith("ror_").all()
    assert (gold["a"].map(PAIRS) == gold["pair_type"]).all()
    gold["pair"] = gold["pair_type"]
    return gold


def id_keys():
    """ID links from the downloaded files. 'any': every listed link (like the gold sample was drawn, see README);
    'one_to_one': only links whose two ids occur once (= common.links(), used by 05_final/cutoff_check.py)."""
    w, r, d = read_source("wikidata"), read_source("ror"), read_source("deqar")
    ror_ids, wiki_ids = set(r["ror_id"].map(last_part)), set(w["wikidata_id"])
    wr = {(a, x) for a, b in zip(w["wikidata_id"], w["ror_id"]) for x in split_ids(b) if x in ror_ids}
    wr |= {(x, last_part(b)) for a, b in zip(r["wikidata_id"], r["ror_id"]) for x in split_ids(a) if x in wiki_ids}
    dr = {(a, x) for a, b in zip(d["deqar_id"], d["ror_id"]) for x in split_ids(b) if x in ror_ids}

    def prefix(pairs, p1):
        return {(p1 + a, "ror_" + b) for a, b in pairs}

    def one_to_one(pairs):
        c1 = pd.Series([a for a, _ in pairs]).value_counts()
        c2 = pd.Series([b for _, b in pairs]).value_counts()
        return {(a, b) for a, b in pairs if c1[a] == 1 and c2[b] == 1}

    keys = {"any": {"wikidata": prefix(wr, "wikidata_"), "deqar": prefix(dr, "deqar_")}}
    keys["one_to_one"] = {a: one_to_one(p) for a, p in keys["any"].items()}
    return keys


def stratum(key):
    """function (id1, id2) -> 'ID link' | 'ID conflict' (a record has an ID link to another record) | 'no ID info'"""
    left, right = set(), set()
    for x, y in key:
        left.add(x)
        right.add(y)

    def f(x, y):
        if (x, y) in key:
            return "ID link"
        return "ID conflict" if x in left or y in right else "no ID info"
    return f


def load_corr(a, name):
    c = pd.read_csv(FINAL / f"correspondences_{a}_ror_{name}.csv", dtype={"id1": str, "id2": str})
    return c


def candidate_file(a):
    # same name as common.candidates(a, "ror", 8); the folder is git-ignored and may be missing
    blocker = "union: country + name word | same domain | embedding"
    slug = "".join(c if c.isalnum() else "_" for c in blocker)[:60]
    path = CANDIDATES / f"{a}_ror_r8_{slug}.csv"
    if path.exists():
        return path
    found = sorted(CANDIDATES.glob(f"{a}_ror_r8_*.csv")) if CANDIDATES.exists() else []
    return found[0] if found else None


def removed_ids():
    return {f"{name}_{i}" for name, col in ID_COLUMN.items()
            for i in pd.read_csv(DATA / name / "filtered" / "removed.csv", dtype=str)[col]}


def record_features():
    """country code, name tokens (without generic words), web hosts per record id (approximate blocking keys)"""
    codes = pd.read_csv(DATA / "deqar" / "country_codes.csv", dtype=str, encoding="utf-8-sig", keep_default_na=False)
    code = dict(zip(codes["country"], codes["code"]))
    feats = {}
    for name in DOWNLOAD:
        df = read_source(name)
        col = lambda c: df[c] if c in df.columns else pd.Series([""] * len(df))
        ccs = df["country_code"] if "country_code" in df.columns else df["country"].map(lambda c: code.get(c, ""))
        for i, cc, n, alt, acr, web, dom in zip(df[ID_COLUMN[name]], ccs, df["name"], col("alt_names"),
                                                col("acronyms"), col("website"), col("domains")):
            names = [n] + alt.split(" | ") + acr.split(" | ")
            toks = {t for x in names for t in norm(x).split() if len(t) > 2} - GENERIC
            hosts = {host(web)} | {host(x) for x in dom.split(" | ")}
            feats[f"{name}_{last_part(i)}"] = (cc, toks, hosts - {""})
    return feats


# ---------------------------------------------------------------- a. label agreement

def agreement_row(comparison, subset, df, orig, other):
    dec = df[(df[orig] != "UNCERTAIN") & (df[other] != "UNCERTAIN")]
    agree = int((dec[orig] == dec[other]).sum())
    lo, hi = wilson(agree, len(dec))
    return dict(comparison=comparison, subset=subset, pairs=len(df), both_decided=len(dec), agree=agree,
                agreement=agree / len(dec) if len(dec) else np.nan, ci_low=lo, ci_high=hi,
                match_vs_non_match=int(((dec[orig] == "MATCH") & (dec[other] == "NON_MATCH")).sum()),
                non_match_vs_match=int(((dec[orig] == "NON_MATCH") & (dec[other] == "MATCH")).sum()),
                uncertain_first=int((df[orig] == "UNCERTAIN").sum()),
                uncertain_second=int((df[other] == "UNCERTAIN").sum()))


def label_agreement(gold, blind, ai_links):
    # the blind labels of the gold pairs must point to the same records and carry the same labels
    theirs = blind[blind["set"] == "theirs"].merge(
        gold[["pair_id", "A_record_id", "B_record_id", "gold_label", "confidence"]],
        left_on="orig_id", right_on="pair_id", validate="one_to_one")
    assert len(theirs) == len(gold) == 500
    assert (theirs["id1"] == theirs["A_record_id"]).all() and (theirs["id2"] == theirs["B_record_id"]).all()
    assert (theirs["original_label"] == theirs["gold_label"]).all()
    ours = blind[blind["set"] == "ours"].copy()
    for a in PAIRS:  # orig_id = <pair>:<row in the round-2 test file>
        test = pd.read_csv(LABELS / "round2" / f"{a}_ror_test.csv", dtype=str)
        sub = ours[ours["orig_id"].str.startswith(f"{a}_ror:")]
        rows = test.loc[sub["orig_id"].str.split(":").str[1].astype(int)]
        assert (rows["id1"].values == sub["id1"].values).all() and (rows["id2"].values == sub["id2"].values).all()
        lab = np.where(rows["label"].str.lower().isin(["true", "1"]), "MATCH", "NON_MATCH")
        assert (lab == sub["original_label"].values).all()
    gone = removed_ids()
    assert not (ours["id1"].isin(gone) | ours["id2"].isin(gone)).any()

    rows = []
    for name, df in [("hand labels vs blind AI", theirs), ("round-2 test labels vs blind AI", ours)]:
        rows.append(agreement_row(name, "all", df, "original_label", "ai_label"))
        for p in PAIRS.values():
            rows.append(agreement_row(name, f"pair={p}", df[df["dataset_pair"] == p], "original_label", "ai_label"))
        if name.startswith("hand"):
            for c in ["HIGH", "MEDIUM", "LOW"]:
                rows.append(agreement_row(name, f"hand confidence={c}", df[df["confidence"] == c],
                                          "original_label", "ai_label"))
        rows.append(agreement_row(name, "AI confidence=HIGH", df[df["ai_confidence"] == "HIGH"],
                                  "original_label", "ai_label"))

    # third opinion: the AI check of the round-8 links (05_final) on the gold pairs it also judged
    v = ai_links.set_index(["id1", "id2"])["verdict"].map({"correct": "MATCH", "wrong": "NON_MATCH",
                                                          "unsure": "UNCERTAIN"})
    both = gold.assign(ai_link=[v.get((x, y)) for x, y in zip(gold["A_record_id"], gold["B_record_id"])])
    both = both[both["ai_link"].notna()]
    rows.append(agreement_row("hand labels vs AI link check (ai_check_links_r8)", "all", both,
                              "gold_label", "ai_link"))
    for p in PAIRS.values():
        rows.append(agreement_row("hand labels vs AI link check (ai_check_links_r8)", f"pair={p}",
                                  both[both["pair"] == p], "gold_label", "ai_link"))
    save_csv(pd.DataFrame(rows), "label_agreement.csv")

    # disagreements (labels differ; both_decided = neither side said UNCERTAIN)
    names = {}
    for f in sorted((RESULTS / "blind_batches").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                names[r["pair"]] = (r["record_A"].get("name", ""), r["record_B"].get("name", ""))
    dis = pd.concat([theirs, ours])
    dis = dis[dis["original_label"] != dis["ai_label"]].copy()
    dis["both_decided"] = (dis["original_label"] != "UNCERTAIN") & (dis["ai_label"] != "UNCERTAIN")
    dis["name_A"] = dis["blind_id"].map(lambda b: names.get(b, ("", ""))[0])
    dis["name_B"] = dis["blind_id"].map(lambda b: names.get(b, ("", ""))[1])
    dis = dis[["set", "orig_id", "blind_id", "dataset_pair", "id1", "id2", "name_A", "name_B", "both_decided",
               "original_label", "original_confidence", "original_evidence", "ai_label", "ai_confidence",
               "ai_reason"]].sort_values(["both_decided", "set", "orig_id"], ascending=[False, False, True])
    save_csv(dis, "disagreements.csv")
    return theirs


# ---------------------------------------------------------------- b. sampling design

def membership(gold, keys):
    feats = record_features()
    gone = removed_ids()
    corr = {a: {n: load_corr(a, n) for n in CORR} for a in PAIRS}
    rows = []
    for a in PAIRS:
        g = gold[gold["a"] == a]
        sets = {n: set(zip(c["id1"], c["id2"])) for n, c in corr[a].items()}
        score = dict(zip(zip(corr[a]["r8_before_cutoff"]["id1"], corr[a]["r8_before_cutoff"]["id2"]),
                         corr[a]["r8_before_cutoff"]["score"]))
        cand_path = candidate_file(a)
        cand = None
        if cand_path is not None:
            c = pd.read_csv(cand_path, dtype=str)
            cand = set(zip(c.iloc[:, 0], c.iloc[:, 1]))
        st = {k: stratum(keys[k][a]) for k in keys}
        r8 = corr[a]["r8"]
        linked_l, linked_r = dict(zip(r8["id1"], r8["id2"])), dict(zip(r8["id2"], r8["id1"]))
        for _, r in g.iterrows():
            x, y = r["A_record_id"], r["B_record_id"]
            fa, fb = feats.get(x, ("", set(), set())), feats.get(y, ("", set(), set()))
            s_any = st["any"](x, y)
            rows.append(dict(
                pair_id=r["pair_id"], pair=r["pair"], id1=x, id2=y, gold_label=r["gold_label"],
                confidence=r["confidence"],
                in_r8=(x, y) in sets["r8"], in_r8_before_cutoff=(x, y) in sets["r8_before_cutoff"],
                in_r3=(x, y) in sets["r3"], in_r8_candidates=None if cand is None else (x, y) in cand,
                score_r8_before_cutoff=score.get((x, y), np.nan),
                id_link=s_any == "ID link", id_conflict=s_any == "ID conflict", stratum=s_any,
                stratum_one_to_one=st["one_to_one"](x, y),
                id1_linked_elsewhere_r8=x in linked_l and linked_l[x] != y,
                id2_linked_elsewhere_r8=y in linked_r and linked_r[y] != x,
                both_unlinked_r8=x not in linked_l and y not in linked_r,
                same_country=bool(fa[0]) and fa[0] == fb[0],
                shared_name_word=bool(fa[1] & fb[1]),
                same_web_host=bool(fa[2] & fb[2]),
                record_removed=x in gone or y in gone))
    m = pd.DataFrame(rows)
    m["design_group"] = np.select(
        [m["in_r8"] & m["id_link"], m["in_r8"] & m["id_conflict"], m["in_r8"],
         ~m["in_r8"] & m["id_link"]],
        ["final link: ID link", "final link: ID conflict", "final link: no ID info", "not linked: ID link"],
        "not linked: no ID link")
    m["approx_block_key"] = m["same_country"] & m["shared_name_word"] | m["same_web_host"]
    save_csv(m, "gold_membership.csv")

    flags = ["in_r8", "in_r8_before_cutoff", "in_r3", "id_link", "id_conflict"]
    design = (m.assign(in_r8_candidates=m["in_r8_candidates"].map(lambda v: "n/a (no file)" if v is None else v))
              .groupby(["pair"] + flags + ["in_r8_candidates"])
              .agg(pairs=("pair_id", "size"),
                   MATCH=("gold_label", lambda s: int((s == "MATCH").sum())),
                   NON_MATCH=("gold_label", lambda s: int((s == "NON_MATCH").sum())),
                   UNCERTAIN=("gold_label", lambda s: int((s == "UNCERTAIN").sum())))
              .reset_index().sort_values(["pair", "in_r8", "id_link", "id_conflict"], ascending=False))
    save_csv(design, "sampling_design.csv")

    # design groups with their population (where one exists) and how the sample compares to it
    rows = []
    for a, p in PAIRS.items():
        mm = m[m["pair"] == p]
        r8 = corr[a]["r8"].copy()
        f_any = stratum(keys["any"][a])
        r8["stratum"] = [f_any(x, y) for x, y in zip(r8["id1"], r8["id2"])]
        r8_set = set(zip(r8["id1"], r8["id2"]))
        missed = [(x, y) for x, y in keys["any"][a] if x not in gone and y not in gone and (x, y) not in r8_set]
        bc = set(zip(corr[a]["r8_before_cutoff"]["id1"], corr[a]["r8_before_cutoff"]["id2"]))
        pop = {f"final link: {s}": r8[r8["stratum"] == s] for s in STRATA}
        for grp in ["final link: ID link", "final link: ID conflict", "final link: no ID info",
                    "not linked: ID link", "not linked: no ID link"]:
            s = mm[mm["design_group"] == grp]
            row = dict(pair=p, design_group=grp, sample=len(s),
                       MATCH=int((s["gold_label"] == "MATCH").sum()),
                       NON_MATCH=int((s["gold_label"] == "NON_MATCH").sum()),
                       UNCERTAIN=int((s["gold_label"] == "UNCERTAIN").sum()),
                       in_r8_before_cutoff=int(s["in_r8_before_cutoff"].sum()), in_r3=int(s["in_r3"].sum()),
                       same_country=int(s["same_country"].sum()), shared_name_word=int(s["shared_name_word"].sum()),
                       approx_block_key=int(s["approx_block_key"].sum()),
                       linked_elsewhere_r8=int((s["id1_linked_elsewhere_r8"] | s["id2_linked_elsewhere_r8"]).sum()),
                       both_unlinked_r8=int(s["both_unlinked_r8"].sum()))
            if grp in pop:
                sc = pop[grp]["score"]
                ss = s["score_r8_before_cutoff"]
                row.update(population=len(pop[grp]), sampling_fraction=len(s) / len(pop[grp]),
                           score_q25_sample=ss.quantile(.25), score_median_sample=ss.median(),
                           score_q25_population=sc.quantile(.25), score_median_population=sc.median())
            elif grp == "not linked: ID link":
                row.update(population=len(missed), sampling_fraction=len(s) / len(missed),
                           population_note="ID links (both records kept by the cleaning) not in the final links")
                missed_set = set(missed)
                row["in_population"] = int(sum((x, y) in missed_set for x, y in zip(s["id1"], s["id2"])))
                row["missed_in_r8_before_cutoff"] = int(sum(q in bc for q in missed))
            else:
                row.update(population_note="no defined population (hard non-links, see README)")
            rows.append(row)
    save_csv(pd.DataFrame(rows), "sampling_strata.csv")
    return m, corr


# ---------------------------------------------------------------- c. evaluation

def evaluation(m, corr):
    rows = []
    variants = {"hand labels, UNCERTAIN excluded": m[m["gold_label"] != "UNCERTAIN"],
                "hand labels, HIGH confidence only": m[(m["gold_label"] != "UNCERTAIN") & (m["confidence"] == "HIGH")]}
    gone = removed_ids()
    for a, p in PAIRS.items():
        test = pd.read_csv(LABELS / "round2" / f"{a}_ror_test.csv", dtype=str)
        test = test[~test["id1"].isin(gone) & ~test["id2"].isin(gone)]
        test_lab = pd.DataFrame({"id1": test["id1"], "id2": test["id2"],
                                 "match": test["label"].str.lower().isin(["true", "1"])})
        sets = {}
        for name, lab in variants.items():
            sets[name] = lab[lab["pair"] == p].assign(match=lambda d: d["gold_label"] == "MATCH")[
                ["id1", "id2", "match"]]
        sets["round-2 test labels (records kept by cleaning)"] = test_lab
        for lname, lab in sets.items():
            for cname, ctitle in CORR.items():
                c = corr[a][cname]
                linked = set(zip(c["id1"], c["id2"]))
                pred = np.array([(x, y) in linked for x, y in zip(lab["id1"], lab["id2"])])
                y = lab["match"].values
                tp, fp, fn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum())
                P, R, F = prf(tp, fp, fn)
                plo, phi = wilson(tp, tp + fp)
                rows.append(dict(labels=lname, pair=p, correspondences=ctitle, labelled_pairs=len(lab),
                                 matches=int(y.sum()), non_matches=int((~y).sum()), links_in_labels=int(pred.sum()),
                                 tp=tp, fp=fp, fn=fn, precision=P, recall=R, f1=F, precision_ci_low=plo,
                                 precision_ci_high=phi, links_total=len(c)))
    save_csv(pd.DataFrame(rows), "evaluation.csv")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- d./e. population estimate

def combine(parts, rng):
    """parts: list of (N_h, correct_h, wrong_h). Weighted precision, normal CI (from Wilson half-widths),
    Monte Carlo CI (p_h ~ Beta(correct + 0.5, wrong + 0.5), Jeffreys)."""
    N = np.array([q[0] for q in parts], float)
    W = N / N.sum()
    c = np.array([q[1] for q in parts], float)
    w = np.array([q[2] for q in parts], float)
    p = c / (c + w)
    est = float((W * p).sum())
    se = [(wilson(ci, ci + wi)[1] - wilson(ci, ci + wi)[0]) / (2 * Z) for ci, wi in zip(c, w)]
    tot = float(np.sqrt(((W * np.array(se)) ** 2).sum()))
    draws = sum(Wh * rng.beta(ch + 0.5, wh + 0.5, DRAWS) for Wh, ch, wh in zip(W, c, w))
    return est, max(0.0, est - Z * tot), min(1.0, est + Z * tot), *np.percentile(draws, [2.5, 97.5])


def population_estimate(m, corr, keys, ai_links):
    rng = np.random.default_rng(SEED)
    rows = []
    for kname in keys:
        for a, p in PAIRS.items():
            r8 = corr[a]["r8"].copy()
            f = stratum(keys[kname][a])
            r8["stratum"] = [f(x, y) for x, y in zip(r8["id1"], r8["id2"])]
            N = r8["stratum"].value_counts()
            r8_set = set(zip(r8["id1"], r8["id2"]))
            col = "stratum" if kname == "any" else "stratum_one_to_one"

            hand = m[(m["pair"] == p) & m["in_r8"] & (m["gold_label"] != "UNCERTAIN")]
            ai = ai_links[[(x, y) in r8_set for x, y in zip(ai_links["id1"], ai_links["id2"])]].copy()
            ai["stratum"] = [f(x, y) for x, y in zip(ai["id1"], ai["id2"])]
            sources = {
                "hand labels": (hand, lambda d: d[col], lambda d: d["gold_label"] == "MATCH",
                                lambda d: d["gold_label"] == "NON_MATCH", None),
                "hand labels, HIGH only": (hand[hand["confidence"] == "HIGH"], lambda d: d[col],
                                           lambda d: d["gold_label"] == "MATCH",
                                           lambda d: d["gold_label"] == "NON_MATCH", None),
                "AI link check": (ai, lambda d: d["stratum"], lambda d: d["verdict"] == "correct",
                                  lambda d: d["verdict"] == "wrong", lambda d: d["verdict"] == "unsure"),
            }
            sources["hand labels, ID-link stratum from AI check"] = None
            for sname, src in sources.items():
                parts = []
                for s in STRATA:
                    if src is None:  # hybrid: AI check where the hand sample is thin (55 ID links), hand labels elsewhere
                        df, stf, okf, badf, unsf = sources["AI link check" if s == "ID link" else "hand labels"]
                    else:
                        df, stf, okf, badf, unsf = src
                    d = df[stf(df) == s]
                    c, w = int(okf(d).sum()), int(badf(d).sum())
                    u = int(unsf(d).sum()) if unsf else int(len(m[(m["pair"] == p) & m["in_r8"] &
                                                                   (m[col] == s) & (m["gold_label"] == "UNCERTAIN")]))
                    lo, hi = wilson(c, c + w)
                    Nh = int(N.get(s, 0))
                    parts.append((Nh, c, w))
                    rows.append(dict(key=kname, estimate=sname, pair=p, stratum=s, links=Nh, weight=Nh / len(r8),
                                     labelled=c + w, correct=c, wrong=w, uncertain_excluded=u,
                                     precision=c / (c + w) if c + w else np.nan, ci_low=lo, ci_high=hi,
                                     ci_method="Wilson",
                                     wrong_links=Nh * (1 - c / (c + w)) if c + w else np.nan,
                                     wrong_links_low=Nh * (1 - hi), wrong_links_high=Nh * (1 - lo)))
                est, nlo, nhi, mlo, mhi = combine(parts, rng)
                labelled = sum(q[1] + q[2] for q in parts)
                for method, lo, hi in [("Monte Carlo (Jeffreys per stratum)", mlo, mhi),
                                       ("normal approx. (Wilson half-widths)", nlo, nhi)]:
                    rows.append(dict(key=kname, estimate=sname, pair=p, stratum="all final links (weighted)",
                                     links=len(r8), weight=1.0, labelled=labelled,
                                     correct=sum(q[1] for q in parts), wrong=sum(q[2] for q in parts),
                                     precision=est, ci_low=lo, ci_high=hi, ci_method=method,
                                     wrong_links=len(r8) * (1 - est), wrong_links_low=len(r8) * (1 - hi),
                                     wrong_links_high=len(r8) * (1 - lo)))
                if sname == "AI link check":  # the AI sample is a uniform random sample: plain proportion too
                    c, w = int((df["verdict"] == "correct").sum()), int((df["verdict"] == "wrong").sum())
                    lo, hi = wilson(c, c + w)
                    rows.append(dict(key=kname, estimate=sname, pair=p, stratum="all final links (unweighted)",
                                     links=len(r8), weight=1.0, labelled=c + w, correct=c, wrong=w,
                                     uncertain_excluded=int((df["verdict"] == "unsure").sum()),
                                     precision=c / (c + w), ci_low=lo, ci_high=hi, ci_method="Wilson",
                                     wrong_links=len(r8) * w / (c + w), wrong_links_low=len(r8) * (1 - hi),
                                     wrong_links_high=len(r8) * (1 - lo)))
    out = pd.DataFrame(rows)
    save_csv(out, "population_estimate.csv")

    # how the AI link check covers the links: a uniform sample of the links before the cut-off?
    cov = []
    checked = set(zip(ai_links["id1"], ai_links["id2"]))
    for a, p in PAIRS.items():
        f = stratum(keys["any"][a])
        for cname in ["r8_before_cutoff", "r8"]:
            c = corr[a][cname]
            st = pd.Series([f(x, y) for x, y in zip(c["id1"], c["id2"])])
            hit = pd.Series([(x, y) in checked for x, y in zip(c["id1"], c["id2"])])
            for s in ["all"] + STRATA:
                sel = st == s if s != "all" else pd.Series(True, index=st.index)
                cov.append(dict(pair=p, correspondences=CORR[cname], stratum=s, links=int(sel.sum()),
                                ai_checked=int(hit[sel].sum()), share_checked=hit[sel].mean()))
        before = set(zip(corr[a]["r8_before_cutoff"]["id1"], corr[a]["r8_before_cutoff"]["id2"]))
        outside = sum(1 for x, y in checked if x.startswith(a + "_") and (x, y) not in before)
        cov.append(dict(pair=p, correspondences="not in round 8 before cut-off", stratum="all", links=np.nan,
                        ai_checked=outside, share_checked=np.nan))
    save_csv(pd.DataFrame(cov), "ai_check_coverage.csv")
    return out


# ---------------------------------------------------------------- figures (look of 11_comparison/plot_results.py)

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150,
                     "pdf.fonttype": 42, "svg.fonttype": "none"})
TEAL, ORANGE, BLUE, LIGHT = "#287271", "#DB8A6C", "#527DA3", "#8CA9C7"


def save(fig, name, pdf=False):
    for ext in ["png"]:
        fig.savefig(FIGURES / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote results/figures/{name}.png/.svg" + ("/.pdf" if pdf else ""))


def errbar(ax, x, y, lo, hi, **kw):
    ax.errorbar(x, y, yerr=[[y - lo], [hi - y]], fmt="o", capsize=3, **kw)


# ---------------------------------------------------------------- main

def main():
    RESULTS.mkdir(exist_ok=True)
    gold = load_gold()
    blind = pd.read_csv(HERE / "blind_ai_labels.csv", dtype=str, keep_default_na=False)
    ai_links = pd.read_csv(FINAL / "ai_check_links_r8.csv", dtype=str, keep_default_na=False)
    keys = id_keys()

    label_agreement(gold, blind, ai_links)
    m, corr = membership(gold, keys)
    assert not m["record_removed"].any(), "a gold record was removed by the cleaning"
    ev = evaluation(m, corr)
    pop = population_estimate(m, corr, keys, ai_links)

    # short console summary
    pd.set_option("display.width", 200)
    print("\nsampling design (design groups):")
    print(pd.read_csv(RESULTS / "sampling_strata.csv")[["pair", "design_group", "sample", "population"]]
          .to_string(index=False))
    print("\nprecision of all final links (key = any ID link):")
    s = pop[(pop["key"] == "any") & (pop["stratum"] == "all final links (weighted)") &
            (pop["ci_method"].str.startswith("Monte"))]
    print(s[["estimate", "pair", "precision", "ci_low", "ci_high", "wrong_links"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
