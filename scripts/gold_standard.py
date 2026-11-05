"""Phase II: builds the gold standard for the three dataset pairs.

Matches (label 1): pairs that the sources themselves link through their identifier
columns (Wikidata <-> ROR, DEQAR <-> ROR, Wikidata <-> DEQAR through the shared ROR
record), restricted to records that take part in exactly one link.

Non-matches (label 0) are never derived from a missing link. They are
  hard / random : candidate pairs in which both records are linked to a *different*
                  record of the other dataset (so neither can be the partner of the other);
                  'hard' are the most similar ones, 'random' a random draw;
  same_name_other_country : equal normalised names, different known countries;
  part_of       : a part of an institution (ROR child with a parent) against the institution
                  or against a part of it;
  predecessor   : a closed DEQAR institution against the successor named in its history.

Run (after phase2_blocking.py): python scripts/gold_standard.py
"""
import re
from collections import defaultdict

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from common import DATA, RESULTS, link_pairs, load_schema, load_target, norm_text, one_to_one, split_list

PAIRS = [("wikidata", "ror"), ("deqar", "ror"), ("wikidata", "deqar")]
GOLD = DATA / "gold_standard"
GOLD.mkdir(exist_ok=True)
SEED = 2026


def records_of_ror(links, raw):
    """ror id -> {dataset: set of schema ids} for the records that describe that ROR record."""
    recs = defaultdict(lambda: defaultdict(set))
    for a, b in links[("wikidata", "ror")]:
        recs[b[4:]]["wikidata"].add(a)
    for a, b in links[("deqar", "ror")]:
        recs[b[4:]]["deqar"].add(a)
    _, r, _ = raw
    for x in r["ror_id"]:
        recs[x]["ror"].add("ror_" + x)
    return recs


def part_of_pairs(raw, recs, a, b):
    _, r, _ = raw
    out = set()
    for child, parent in zip(r["ror_id"], r["parent_ror_id"]):
        for p in split_list(parent):
            for x, y in ((p, child), (child, p)):
                for ra in recs[x][a]:
                    for rb in recs[y][b]:
                        out.add((ra, rb))
    return out


def predecessor_pairs(data, recs, a, b):
    """Closed DEQAR institutions against the successor named in their history."""
    if "deqar" not in (a, b):
        return set()
    ror = data["ror"]
    by_name = defaultdict(list)
    for i, n, cc in zip(ror["id"], ror["name_norm"], ror["country_code"]):
        by_name[(n, cc)].append(i[4:])
    out = set()
    deqar = data["deqar"]
    for did, cc, hist, closed in zip(deqar["id"], deqar["country_code"], deqar["history"], deqar["closure_year"]):
        if pd.isna(closed):
            continue
        for event in hist:
            m = re.search(r"(?:succeeded by|absorbed by)\s+(.+)$", event)
            if not m:
                continue
            for succ in by_name.get((norm_text(m.group(1)), cc), []):
                for rd in ([did] if a == "deqar" else recs_of(recs, succ, a)):
                    for rb in (recs_of(recs, succ, b) if a == "deqar" else [did]):
                        out.add((rd, rb))
    return out


def recs_of(recs, ror_id, dataset):
    return recs[ror_id][dataset]


def build(a, b, data, links, recs, raw, rng):
    left, right = data[a], data[b]
    all_links = links[(a, b)]
    pos = one_to_one(all_links)
    linked_left = {x for x, _ in all_links}
    linked_right = {y for _, y in all_links}
    cand = pd.read_csv(RESULTS / "cache" / f"candidates_{a}_{b}.csv")
    name_l = dict(zip(left["id"], left["name_norm"]))
    name_r = dict(zip(right["id"], right["name_norm"]))
    # candidates in which both records have a partner somewhere else
    ok = cand[cand["id1"].isin(linked_left) & cand["id2"].isin(linked_right)]
    ok = ok[[(x, y) not in all_links for x, y in zip(ok["id1"], ok["id2"])]].copy()
    ok["sim"] = [fuzz.token_set_ratio(name_l[x], name_r[y]) for x, y in zip(ok["id1"], ok["id2"])]
    n_hard = min(len(pos), len(ok) // 2)
    hard = ok.sort_values("sim", ascending=False).head(n_hard)
    rest = ok.drop(hard.index)
    rand = rest.sample(min(len(rest), len(pos) // 2), random_state=SEED)

    # equal name, different country
    cc_l = dict(zip(left["id"], left["country_code"]))
    cc_r = dict(zip(right["id"], right["country_code"]))
    by_name = defaultdict(list)
    for i, n in zip(right["id"], right["name_norm"]):
        if n:
            by_name[n].append(i)
    same = []
    for i, n in zip(left["id"], left["name_norm"]):
        for j in by_name.get(n, []):
            if cc_l[i] and cc_r[j] and cc_l[i] != cc_r[j] and (i, j) not in all_links:
                same.append((i, j))
    same = [same[k] for k in rng.permutation(len(same))[:300]]

    part = sorted(part_of_pairs(raw, recs, a, b) - all_links)
    pred = sorted(predecessor_pairs(data, recs, a, b) - all_links)

    rows = [(x, y, 1, "match") for x, y in sorted(pos)]
    rows += [(x, y, 0, "hard") for x, y in zip(hard["id1"], hard["id2"])]
    rows += [(x, y, 0, "random") for x, y in zip(rand["id1"], rand["id2"])]
    rows += [(x, y, 0, "same_name_other_country") for x, y in same]
    rows += [(x, y, 0, "part_of") for x, y in part]
    rows += [(x, y, 0, "predecessor") for x, y in pred]
    gs = pd.DataFrame(rows, columns=["id1", "id2", "label", "kind"]).drop_duplicates(["id1", "id2"])
    # development / test split by the left record, so that no record is in both parts
    gs["split"] = np.where(gs["id1"].map(lambda s: hash_split(s)) < 0.5, "dev", "test")
    return gs


def hash_split(s):
    import zlib
    return (zlib.crc32((str(SEED) + s).encode()) % 10000) / 10000


def main():
    data = load_target()
    _, raw = load_schema()
    links = link_pairs(raw)
    recs = records_of_ror(links, raw)
    rng = np.random.default_rng(SEED)
    summary = []
    for a, b in PAIRS:
        gs = build(a, b, data, links, recs, raw, rng)
        gs.to_csv(GOLD / f"gold_{a}_{b}.csv", index=False)
        for (split, kind), n in gs.groupby(["split", "kind"]).size().items():
            summary.append(dict(pair=f"{a}-{b}", split=split, kind=kind, pairs=n))
        print(a, b, gs.groupby("kind").size().to_dict())
    pd.DataFrame(summary).to_csv(RESULTS / "gold_standard_summary.csv", index=False)


if __name__ == "__main__":
    main()
