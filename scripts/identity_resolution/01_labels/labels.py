"""Labelled pairs.  Usage: python labels.py 1 | pool | 2"""
import random
import sys
import zlib
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import LABELS, PAIRS, links, load_all

SEED = 2026
SPLITS = ["train", "validation", "test"]


def split_of(id1):
    # the same left record always lands in the same split
    return SPLITS[zlib.crc32(id1.encode()) % 3]


def name_sim(names1, names2):
    return max((fuzz.token_sort_ratio(x, y) for x in names1 for y in names2), default=0)


def write(round_, a, b, df):
    folder = LABELS / f"round{round_}"
    folder.mkdir(parents=True, exist_ok=True)
    df = df.assign(split=df["id1"].map(split_of))
    for s in SPLITS:
        part = df[df["split"] == s][["id1", "id2", "label"]]
        part.to_csv(folder / f"{a}_{b}_{s}.csv", index=False)
        print(f"  {a}-{b} {s}: {len(part)} pairs, {int(part['label'].sum())} matches")


def random_pairs(L, R, n, exclude, rng):
    pairs = set()
    ids1, ids2 = list(L.index), list(R.index)
    while len(pairs) < n:
        p = (rng.choice(ids1), rng.choice(ids2))
        if p not in exclude:
            pairs.add(p)
    return sorted(pairs)


# ---------- round 1: ID links as matches, random pairs as non-matches ----------

def round1(data, link):
    rng = random.Random(SEED)
    for a, b in PAIRS:
        L, R = data[a].set_index("id"), data[b].set_index("id")
        matches = rng.sample(sorted(link[(a, b)]), 450)
        non = random_pairs(L, R, 450, link[(a, b)], rng)
        rows = [(x, y, True) for x, y in matches] + [(x, y, False) for x, y in non]
        write(1, a, b, pd.DataFrame(rows, columns=["id1", "id2", "label"]))


# ---------- round 2: pool to check by hand (20% / 50% / 30%) ----------

def different_names(L, R, known, rng):
    # linked pairs whose names look different (other language, renamed)
    low = [(x, y) for x, y in known if name_sim(L.at[x, "names"], R.at[y, "names"]) < 80]
    return rng.sample(low, min(250, len(low)))


def similar_names(L, R, known, rng):
    # very similar names, but the right record is linked to another university
    by_token = {}
    for y, cc, names in zip(R.index, R["cc"], R["names"]):
        for t in {t for n in names for t in n.split() if len(t) > 3}:
            by_token.setdefault((cc, t), []).append(y)

    linked = {y for _, y in known}
    found = []
    for x, y in rng.sample(known, 3000):
        tokens = {t for n in L.at[x, "names"] for t in n.split() if len(t) > 3}
        blocks = [by_token.get((L.at[x, "cc"], t), []) for t in tokens]
        cands = {z for block in blocks if len(block) < 200 for z in block}
        cands = [z for z in cands if z != y and z in linked]
        if cands:
            z = max(cands, key=lambda z: name_sim(L.at[x, "names"], R.at[z, "names"]))
            found.append((name_sim(L.at[x, "names"], R.at[z, "names"]), x, z))
    found.sort(reverse=True)
    return [(x, z) for _, x, z in found[:160]]


def part_of(R, known, rng):
    # a ROR child unit against the record linked to its parent
    by_name = {}
    for y, n in zip(R.index, R["name_norm"]):
        by_name.setdefault(n, []).append(y)
    left_of = {y: x for x, y in known}
    pairs = [(left_of[parent], child)
             for child, parents in zip(R.index, R["parents"])
             for p in parents
             for parent in by_name.get(p, [])
             if parent in left_of]
    return rng.sample(pairs, min(60, len(pairs)))


def same_name_other_country(L, R, rng):
    by_name = {}
    for y, n, cc in zip(R.index, R["name_norm"], R["cc"]):
        by_name.setdefault(n, []).append((y, cc))
    pairs = [(x, y)
             for x, n, cc in zip(L.index, L["name_norm"], L["cc"])
             for y, cc2 in by_name.get(n, [])
             if cc and cc2 and cc != cc2]
    return rng.sample(pairs, min(40, len(pairs)))


def describe(D, i):
    r = D.loc[i]
    alt = [n for n in r["names"] if n != r["name_norm"]][:3]
    year = "" if pd.isna(r["year"]) else int(r["year"])
    return f"{r['name']} {alt} | {r['cc']} {r['city_norm']} | {' '.join(r['domains'][:2])} | {year}"


def pool(data, link):
    rng = random.Random(SEED)
    for a, b in PAIRS:
        L, R = data[a].set_index("id"), data[b].set_index("id")
        known = sorted(link[(a, b)])

        rows = [(x, y, True, "random match") for x, y in rng.sample(known, 200)]
        rows += [(x, y, True, "match, different names") for x, y in different_names(L, R, known, rng)]
        rows += [(x, y, False, "similar name, other university") for x, y in similar_names(L, R, known, rng)]
        rows += [(x, y, False, "part of / parent") for x, y in part_of(R, known, rng)]
        rows += [(x, y, False, "same name, other country") for x, y in same_name_other_country(L, R, rng)]
        rows += [(x, y, False, "random non-match") for x, y in random_pairs(L, R, 300, set(known), rng)]

        df = pd.DataFrame(rows, columns=["id1", "id2", "label", "kind"]).drop_duplicates(["id1", "id2"])
        df["left"] = [describe(L, x) for x in df["id1"]]
        df["right"] = [describe(R, y) for y in df["id2"]]
        LABELS.mkdir(parents=True, exist_ok=True)
        df.to_csv(LABELS / f"pool_{a}_{b}.csv", index=False)
        print(f"  {a}-{b}: {len(df)} pairs to check", df["kind"].value_counts().to_dict())


# ---------- round 2: apply the hand check ----------

def round2():
    for a, b in PAIRS:
        df = pd.read_csv(LABELS / f"pool_{a}_{b}.csv")
        review = pd.read_csv(LABELS / f"review_{a}_{b}.csv")
        decision = dict(zip(zip(review["id1"], review["id2"]), review["decision"]))

        rows = []
        for x, y, label in zip(df["id1"], df["id2"], df["label"]):
            d = decision.get((x, y), "ok")
            if d == "flip":
                label = not label
            if d != "drop":
                rows.append((x, y, label))

        flips = sum(d == "flip" for d in decision.values())
        drops = sum(d == "drop" for d in decision.values())
        print(f"  {a}-{b}: {len(df)} checked, {flips} changed, {drops} dropped")
        write(2, a, b, pd.DataFrame(rows, columns=["id1", "id2", "label"]))


if __name__ == "__main__":
    step = sys.argv[1]
    if step == "2":
        round2()
    elif step == "1":
        round1(load_all(), links())
    else:
        pool(load_all(), links())
