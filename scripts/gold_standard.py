"""Phase II: builds the labelled sets (train / validation / test) for the three dataset pairs.

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

Split. Every record belongs to an institution *family*: the records that describe one ROR
record, joined with the ROR records of its parents/children and with closed DEQAR
institutions and their successors. Whole families are assigned to train (60 %), validation
(20 %) or test (20 %) by a hash, so that no record appears in two sets; the
non-matches are drawn inside each set. The sets are used as
  train_data      : fitting the learned matchers,
  validation_data : choosing matcher, weights, threshold, blocker, post-clustering,
  test_data       : the final evaluation, used once.

Output: data/gold_standard/{train,validation,test}_data_<a>_<b>.csv
        (columns id1, id2, label, kind, split) and results/gold_standard_summary.csv.

Run (after phase2_blocking.py): python scripts/gold_standard.py
"""
import re
import zlib
from collections import defaultdict

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from common import DATA, RESULTS, link_pairs, load_schema, load_target, norm_text, one_to_one, split_list

PAIRS = [("wikidata", "ror"), ("deqar", "ror"), ("wikidata", "deqar")]
GOLD = DATA / "gold_standard"
GOLD.mkdir(exist_ok=True)
CACHE = RESULTS / "cache"
SEED = 2026
SPLITS = [("train", 0.6), ("validation", 0.2), ("test", 0.2)]
FILE_PREFIX = {"train": "train_data", "validation": "validation_data", "test": "test_data"}


def split_path(split, a, b):
    """Path of one labelled set, e.g. data/gold_standard/train_data_wikidata_ror.csv."""
    return GOLD / f"{FILE_PREFIX[split]}_{a}_{b}.csv"


def load_split(split, a, b):
    return pd.read_csv(split_path(split, a, b))


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


def successors(data):
    """(closed DEQAR record, ROR id of its successor) from the 'succeeded/absorbed by' history."""
    ror = data["ror"]
    by_name = defaultdict(list)
    for i, n, cc in zip(ror["id"], ror["name_norm"], ror["country_code"]):
        by_name[(n, cc)].append(i[4:])
    out = []
    deqar = data["deqar"]
    for did, cc, hist, closed in zip(deqar["id"], deqar["country_code"], deqar["history"], deqar["closure_year"]):
        if pd.isna(closed):
            continue
        for event in hist:
            m = re.search(r"(?:succeeded by|absorbed by)\s+(.+)$", event)
            if m:
                out += [(did, succ) for succ in by_name.get((norm_text(m.group(1)), cc), [])]
    return out


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


def predecessor_pairs(succ, recs, a, b):
    """Closed DEQAR institutions against the successor named in their history."""
    if "deqar" not in (a, b):
        return set()
    out = set()
    for did, s in succ:
        if a == "deqar":
            out |= {(did, rb) for rb in recs[s][b]}
        else:
            out |= {(ra, did) for ra in recs[s][a]}
    return out


def same_name_pairs(left, right, all_links):
    """Records with equal normalised names in different known countries."""
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
    return same


def split_of_records(data, raw, recs, succ, extra_pairs=()):
    """record id -> 'train' / 'validation' / 'test', assigned per institution family.
    ``extra_pairs`` are further pairs of records kept in one split (the same-name corner cases)."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for df in data.values():
        for i in df["id"]:
            find(i)
    for ror_id, by_ds in list(recs.items()):
        for ids in by_ds.values():
            for i in ids:
                union("ror_" + ror_id, i)
    _, r, _ = raw
    for child, par in zip(r["ror_id"], r["parent_ror_id"]):
        for p in split_list(par):
            union("ror_" + child, "ror_" + p)
    for did, s in succ:
        union(did, "ror_" + s)
    for x, y in extra_pairs:
        union(x, y)

    # a stable name per family (its smallest id), so the split does not depend on union order
    members = defaultdict(list)
    for x in list(parent):
        members[find(x)].append(x)
    split = {}
    for group in members.values():
        u = (zlib.crc32((str(SEED) + min(group)).encode()) % 10000) / 10000
        s = next(name for name, cum in zip([n for n, _ in SPLITS], np.cumsum([p for _, p in SPLITS])) if u < cum)
        for x in group:
            split[x] = s
    return split


def build(a, b, data, links, recs, raw, succ, split_of, rng):
    left, right = data[a], data[b]
    all_links = links[(a, b)]
    pos = sorted(one_to_one(all_links))
    linked_left = {x for x, _ in all_links}
    linked_right = {y for _, y in all_links}
    for x, y in pos:
        assert split_of[x] == split_of[y], (x, y)

    def same_split(pairs):
        return [(x, y) for x, y in pairs if split_of[x] == split_of[y]]

    # candidates in which both records have a partner somewhere else, inside one split
    cand = pd.read_csv(CACHE / f"candidates_{a}_{b}.csv")
    name_l = dict(zip(left["id"], left["name_norm"]))
    name_r = dict(zip(right["id"], right["name_norm"]))
    ok = cand[cand["id1"].isin(linked_left) & cand["id2"].isin(linked_right)]
    ok = ok[[(x, y) not in all_links and split_of[x] == split_of[y] for x, y in zip(ok["id1"], ok["id2"])]].copy()
    ok["split"] = ok["id1"].map(split_of)
    ok["sim"] = [fuzz.token_set_ratio(name_l[x], name_r[y]) for x, y in zip(ok["id1"], ok["id2"])]
    n_pos = pd.Series([split_of[x] for x, _ in pos]).value_counts()
    hard, rand = [], []
    for s, _ in SPLITS:  # as many hard and half as many random non-matches as matches, per split
        part = ok[ok["split"] == s]
        n = int(n_pos.get(s, 0))
        h = part.sort_values(["sim", "id1", "id2"], ascending=[False, True, True]).head(min(n, len(part) // 2))
        rest = part.drop(h.index)
        hard.append(h)
        rand.append(rest.sample(min(len(rest), n // 2), random_state=SEED))
    hard, rand = pd.concat(hard), pd.concat(rand)

    same = same_split(same_name_pairs(left, right, all_links))
    same = [same[k] for k in rng.permutation(len(same))[:300]]

    part = sorted(same_split(part_of_pairs(raw, recs, a, b) - all_links))
    pred = sorted(same_split(predecessor_pairs(succ, recs, a, b) - all_links))

    rows = [(x, y, 1, "match") for x, y in pos]
    rows += [(x, y, 0, "hard") for x, y in zip(hard["id1"], hard["id2"])]
    rows += [(x, y, 0, "random") for x, y in zip(rand["id1"], rand["id2"])]
    rows += [(x, y, 0, "same_name_other_country") for x, y in same]
    rows += [(x, y, 0, "part_of") for x, y in part]
    rows += [(x, y, 0, "predecessor") for x, y in pred]
    gs = pd.DataFrame(rows, columns=["id1", "id2", "label", "kind"]).drop_duplicates(["id1", "id2"])
    gs["split"] = gs["id1"].map(split_of)
    assert (gs["split"] == gs["id2"].map(split_of)).all()
    return gs


def check_disjoint(gs):
    """Number of records that appear in more than one split (must be 0)."""
    seen = defaultdict(set)
    for col in ("id1", "id2"):
        for i, s in zip(gs[col], gs["split"]):
            seen[i].add(s)
    return sum(len(v) > 1 for v in seen.values())


def main():
    data = load_target()
    _, raw = load_schema()
    links = link_pairs(raw)
    recs = records_of_ror(links, raw)
    succ = successors(data)
    same = [p for a, b in PAIRS for p in same_name_pairs(data[a], data[b], links[(a, b)])]
    split_of = split_of_records(data, raw, recs, succ, same)
    sizes = pd.Series(split_of).value_counts()
    print("records per split:", sizes.to_dict())
    rng = np.random.default_rng(SEED)
    summary = []
    for a, b in PAIRS:
        gs = build(a, b, data, links, recs, raw, succ, split_of, rng)
        assert check_disjoint(gs) == 0
        for s, _ in SPLITS:
            gs[gs["split"] == s].to_csv(split_path(s, a, b), index=False)
        old = GOLD / f"gold_{a}_{b}.csv"  # the former two-way split; remove so nothing reads it
        if old.exists():
            old.unlink()
        stale = CACHE / f"features_{a}_{b}.csv"  # features of the previous labelled sets
        if stale.exists():
            stale.unlink()
        for (s, kind), n in gs.groupby(["split", "kind"]).size().items():
            summary.append(dict(pair=f"{a}-{b}", split=s, kind=kind, pairs=n))
        print(f"\n{a}-{b}: {len(gs)} pairs")
        print(gs.pivot_table(index="kind", columns="split", values="label", aggfunc="size", fill_value=0)
              [[s for s, _ in SPLITS]].to_string())
    pd.DataFrame(summary).to_csv(RESULTS / "gold_standard_summary.csv", index=False)


if __name__ == "__main__":
    main()
