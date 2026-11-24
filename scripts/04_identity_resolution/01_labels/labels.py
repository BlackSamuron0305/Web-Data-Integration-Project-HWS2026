"""Builds the labelled pairs (train / validation / test) on the original data.
Usage: python labels.py 1 | pool | extra | 2   (careful: pool and extra overwrite the hand-checked pool files)"""
import random
import sys
import zlib
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import LABELS, PAIRS, label_folder, links, load_all

SEED = 2026
SPLITS = ["train", "validation", "test"]


def split_of(id1):
    # the same left record always lands in the same split
    return SPLITS[zlib.crc32(id1.encode()) % 3]


def name_sim(names1, names2):
    return max((fuzz.token_sort_ratio(x, y) for x in names1 for y in names2), default=0)


def write(round_, a, b, df):
    folder = label_folder(round_)
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


def round1(data, link):
    # ID links as matches, random pairs as non-matches
    rng = random.Random(SEED)
    for a, b in PAIRS:
        L, R = data[a].set_index("id"), data[b].set_index("id")
        matches = rng.sample(sorted(link[(a, b)]), 450)
        non = random_pairs(L, R, 450, link[(a, b)], rng)
        rows = [(x, y, True) for x, y in matches] + [(x, y, False) for x, y in non]
        write(1, a, b, pd.DataFrame(rows, columns=["id1", "id2", "label"]))


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
    for x, y in rng.sample(known, min(3000, len(known))):
        tokens = {t for n in L.at[x, "names"] for t in n.split() if len(t) > 3}
        cands = set()
        for t in tokens:
            block = by_token.get((L.at[x, "cc"], t), [])
            if len(block) < 200:
                for z in block:
                    cands.add(z)
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
    pairs = []
    for child, parents in zip(R.index, R["parents"]):
        for p in parents:
            for parent in by_name.get(p, []):
                if parent in left_of:
                    pairs.append((left_of[parent], child))
    return rng.sample(pairs, min(60, len(pairs)))


def same_name_other_country(L, R, rng):
    by_name = {}
    for y, n, cc in zip(R.index, R["name_norm"], R["cc"]):
        by_name.setdefault(n, []).append((y, cc))
    pairs = []
    for x, n, cc in zip(L.index, L["name_norm"], L["cc"]):
        for y, cc2 in by_name.get(n, []):
            if cc and cc2 and cc != cc2:
                pairs.append((x, y))
    return rng.sample(pairs, min(40, len(pairs)))


def describe(D, i):
    r = D.loc[i]
    alt = [n for n in r["names"] if n != r["name_norm"]][:3]
    year = "" if pd.isna(r["year"]) else int(r["year"])
    return f"{r['name']} {alt} | {r['cc']} {r['city_norm']} | {' '.join(r['domains'][:2])} | {year}"


def pool(data, link):
    # pairs to check by hand: about 20% random matches, 50% corner cases, 30% random non-matches
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


# 200 more test pairs per source pair (slide 34 wants > 500 test pairs), same mix as the pool
EXTRA = {"random match": 40, "match, different names": 30, "similar name, other university": 40,
         "part of / parent": 20, "same name, other country": 10, "random non-match": 60}


def extra(data, link):
    rng = random.Random(SEED + 1)
    for a, b in PAIRS:
        L, R = data[a].set_index("id"), data[b].set_index("id")
        old = pd.read_csv(LABELS / f"pool_{a}_{b}.csv")
        taken = set(zip(old["id1"], old["id2"]))

        def fresh(pairs):
            # only test split records and nothing that is already in the pool
            return [p for p in pairs if split_of(p[0]) == "test" and p not in taken]

        known = sorted(link[(a, b)])
        test_known = fresh(known)

        found = {
            "random match": rng.sample(test_known, len(test_known)),
            "match, different names": fresh(different_names(L, R, test_known, rng)),
            "similar name, other university": fresh(similar_names(L, R, test_known, rng)),
            "part of / parent": fresh(part_of(R, known, rng)),
            "same name, other country": fresh(same_name_other_country(L, R, rng)),
        }
        test_left = L[[split_of(x) == "test" for x in L.index]]
        found["random non-match"] = fresh(random_pairs(test_left, R, 200, set(known), rng))

        rows, used = [], set()
        for kind, n in EXTRA.items():
            label = kind in ("random match", "match, different names")
            picked = [p for p in found[kind] if p not in used][:n]
            used |= set(picked)
            rows += [(x, y, label, kind) for x, y in picked]
        # the first pool took almost all "different names" matches, so fill up with the other kinds
        for kind in ["similar name, other university", "part of / parent", "same name, other country",
                     "random non-match"]:
            short = 200 - len(rows)
            picked = [p for p in found[kind] if p not in used][:short]
            used |= set(picked)
            rows += [(x, y, False, kind) for x, y in picked]

        df = pd.DataFrame(rows, columns=["id1", "id2", "label", "kind"])
        df["left"] = [describe(L, x) for x in df["id1"]]
        df["right"] = [describe(R, y) for y in df["id2"]]
        df.to_csv(LABELS / f"pool_extra_{a}_{b}.csv", index=False)
        print(f"  {a}-{b}: {len(df)} extra test pairs to check", df["kind"].value_counts().to_dict())


def checked(pool_file, review_file):
    df = pd.read_csv(LABELS / pool_file)
    review = pd.read_csv(LABELS / review_file)
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
    print(f"  {pool_file}: {len(df)} checked, {flips} changed, {drops} dropped")
    return rows


def round2():
    # the pools with the hand check applied
    for a, b in PAIRS:
        rows = checked(f"pool_{a}_{b}.csv", f"review_{a}_{b}.csv")
        if (LABELS / f"review_extra_{a}_{b}.csv").exists():
            rows += checked(f"pool_extra_{a}_{b}.csv", f"review_extra_{a}_{b}.csv")
        write(2, a, b, pd.DataFrame(rows, columns=["id1", "id2", "label"]))


if __name__ == "__main__":
    step = sys.argv[1]
    if step == "2":
        round2()
    elif step == "extra":
        extra(load_all(1), links())
    elif step == "1":
        round1(load_all(1), links())
    elif step == "pool":
        pool(load_all(1), links())
    else:
        raise SystemExit(__doc__)
