"""Shared code of the additional filtering (rounds 4-6): flag rows that are not a university of their
own, find duplicates inside a source and write filtered copies of the data.
Used by <source>/filter.py, duplicates.py and apply.py. Archived, paths are from the old layout."""
import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PER_SAFE_GROUP = 10

# csv, id column, id prefix, MapForce output
SOURCES = {
    "wikidata": ("wikidata/wikidata_universities.csv", "wikidata_id", "wikidata_", "wikidata/Wikidata_Mapping.xml"),
    "ror": ("ror/ror_education.csv", "ror_id", "ror_", "ror/ROR_Mapping.xml"),
    "deqar": ("deqar/deqar_institutions.csv", "deqar_id", "deqar_", "deqar/deqar_Mapping.xml"),
}
COLUMNS = ["id", "name", "alt_names", "country", "city", "part_of", "why_flagged", "group", "check_by_hand",
           "ai_suggestion", "ai_note", "university", "checked_by", "comment"]
DECISIONS = ["ai_suggestion", "ai_note", "university", "checked_by", "comment"]   # kept when run again

HE_WORDS = (r"college|university|universitat|universite|universidad|universita|universidade|universiteit|"
            r"uniwersytet|academy|hochschule|polytechnic|politecnica|politecnico")


def norm_text(value):
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[\W_]+", " ", s.replace("&", " and ")).strip()
    return re.sub(r"^the ", "", s)


def has(text, words):
    """True if the normalised text contains one of the words (regex alternatives)."""
    return re.search(rf" (?:{words}) ", f" {norm_text(text)} ") is not None


def read(source):
    csv = SOURCES[source][0]
    return pd.read_csv(DATA / csv, dtype=str, keep_default_na=False)


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def write_hand_check(source_dir, flagged):
    f = flagged.copy()
    path = source_dir / "hand_check.csv"
    for c in DECISIONS:
        f[c] = ""
    f["university"] = "n"
    if path.exists():   # keep the decisions that were already made
        old = pd.read_csv(path, dtype=str, keep_default_na=False).set_index("id")
        known = f["id"].isin(old.index)
        for c in DECISIONS:
            f.loc[known, c] = f.loc[known, "id"].map(old[c])
        gone = old[~old.index.isin(f["id"]) & (old["checked_by"] != "")]
        if len(gone):
            print(f"note: {len(gone)} hand-checked rows are no longer flagged:", "; ".join(gone["name"]))
    # sample of each safe group = rows with the smallest hash of their id, so it stays the same between runs
    f["_h"] = f["id"].map(md5)
    sample = set(f[f["group"] != "risky"].sort_values("_h").groupby("group").head(PER_SAFE_GROUP)["id"])
    f["check_by_hand"] = ["yes" if g == "risky" or i in sample or a in ("y", "unclear") else "no"
                          for g, i, a in zip(f["group"], f["id"], f["ai_suggestion"])]
    f = f.sort_values(["check_by_hand", "group", "why_flagged", "country", "name"],
                      ascending=[False, True, True, True, True])[COLUMNS]
    f.to_csv(path, index=False, encoding="utf-8-sig")   # utf-8-sig so Excel shows the accents right
    print(f"hand_check.csv: {len(f)} flagged | to check by hand {(f['check_by_hand'] == 'yes').sum()} | "
          f"marked y {(f['university'] == 'y').sum()}, n {(f['university'] == 'n').sum()} | "
          f"checked by a person {(f['checked_by'] != '').sum()}")
    print(f.groupby(["group", "why_flagged"]).size().to_string())


DUP_COLUMNS = ["id1", "name1", "info1", "id2", "name2", "info2", "why_flagged", "group", "check_by_hand",
               "ai_suggestion", "ai_note", "same", "keep", "checked_by", "comment"]
DUP_DECISIONS = ["ai_suggestion", "ai_note", "same", "keep", "checked_by", "comment"]
LINKS = {"wikidata": ["ror_id", "wikipedia_en"], "ror": ["wikidata_id", "wikipedia_en"], "deqar": ["ror_id"]}
INFO = ["country_code", "country", "city", "website", "founding_year", "closure_year", "status", "alt_names"]


def find_duplicates(source, source_dir):
    """Pairs in one source that point to the same record of another source or have the same name and country."""
    _, id_col, prefix, _ = SOURCES[source]
    d = read(source)
    d["id"] = prefix + d[id_col]
    # rows already marked as non-universities are removed anyway
    check = pd.read_csv(source_dir / "hand_check.csv", dtype=str, keep_default_na=False)
    d = d[~d["id"].isin(set(check.loc[check["university"] == "n", "id"]))]
    country = "country_code" if "country_code" in d else "country"

    keys = {}
    for c in LINKS[source]:
        pairs = []
        for values, i in zip(d[c], d["id"]):
            for v in values.split(" | "):
                if v.strip():
                    pairs.append((v.strip(), i))
        keys[f"same {c}"] = pairs
    keys["same name + country"] = [((norm_text(n), c), i) for n, c, i in zip(d["name"], d[country], d["id"])]

    why = {}
    for reason, pairs in keys.items():
        groups = pd.DataFrame(pairs, columns=["key", "id"]).groupby("key")["id"].apply(lambda s: sorted(set(s)))
        for ids in groups[groups.map(len) > 1]:
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    why.setdefault((a, b), []).append(reason)

    rows = d.set_index("id")

    def info(i):
        return " | ".join(f"{c}: {rows.at[i, c]}" for c in INFO if c in rows and rows.at[i, c])

    def filled(i):
        return (rows.loc[i] != "").sum()

    def host(i):
        return re.sub(r"^(https?://)?(www\.)?", "", rows.at[i, "website"].lower()).split("/")[0]

    out = []
    for (a, b), reasons in why.items():
        out.append(dict(id1=a, name1=rows.at[a, "name"], info1=info(a), id2=b, name2=rows.at[b, "name"],
                        info2=info(b), why_flagged=" & ".join(reasons), keep=a if filled(a) >= filled(b) else b))
    out = pd.DataFrame(out)

    group = []
    for reason, a, b in zip(out["why_flagged"], out["id1"], out["id2"]):
        city_a, city_b = rows.at[a, "city"], rows.at[b, "city"]
        # two cities and two websites ("Government Medical College" Surat / Nagpur). An empty or
        # differently written city alone proves nothing, Wikidata has some universities twice
        apart = (all([city_a, city_b, host(a), host(b)])
                 and norm_text(city_a) != norm_text(city_b) and host(a) != host(b))
        # same entry twice: same name, website and city (ROR campuses share name and website)
        twin = (host(a) and host(a) == host(b) and norm_text(rows.at[a, "name"]) == norm_text(rows.at[b, "name"])
                and norm_text(city_a) == norm_text(city_b))
        if reason == "same name + country" and apart:
            group.append("same name, other city and website")
        elif twin:
            group.append("same name and website")
        else:
            group.append("risky")
    out["group"] = group
    return out


# what the AI should say in a safe group, if it says something else the pair is checked by hand
EXPECTED = {"same name, other city and website": "n", "same name and website": "y"}


def write_duplicate_check(source_dir, pairs):
    """same = y: one institution (apply.py drops the row not in keep), n: two institutions."""
    f = pairs.copy()
    path = source_dir / "duplicate_check.csv"
    for c in ["ai_suggestion", "ai_note", "checked_by", "comment"]:
        f[c] = ""
    f["same"] = "n"
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False).set_index(["id1", "id2"])
        idx = pd.MultiIndex.from_arrays([f["id1"], f["id2"]])
        known = idx.isin(old.index)
        for c in DUP_DECISIONS:
            f.loc[known, c] = old.loc[idx[known], c].values
    # by hand: every unclear pair and every pair where the AI disagrees with the group,
    # plus 10 pairs of each group out of the rest
    must = []
    for g, a in zip(f["group"], f["ai_suggestion"]):
        if a == "unclear":
            must.append(True)
        elif g == "risky":
            must.append(a == "y")
        else:
            must.append(a != "" and a != EXPECTED[g])
    f["_h"] = (f["id1"] + f["id2"]).map(md5)
    rest = f[[not m for m in must]]
    sample = set(rest.sort_values("_h").groupby("group").head(PER_SAFE_GROUP).index)
    f["check_by_hand"] = ["yes" if m or i in sample else "no" for i, m in zip(f.index, must)]
    f = f.sort_values(["check_by_hand", "group", "name1"], ascending=[False, True, True])[DUP_COLUMNS]
    f.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"duplicate_check.csv: {len(f)} pairs | to check by hand {(f['check_by_hand'] == 'yes').sum()} | "
          f"same y {(f['same'] == 'y').sum()}, n {(f['same'] == 'n').sum()} | checked by a person "
          f"{(f['checked_by'] != '').sum()}")
    print(f.groupby(["group", "why_flagged"]).size().to_string())


def is_location(name):
    return has(name, "campus|branch") and not has(name, r"institut|institute|centre|center|laboratory|faculty")


def campuses(source, source_dir):
    """campuses.csv: every removed campus or branch with the university it belongs to.
    The university is the parent link, the name after "branch of" / "campus of", or the longest
    start of the name that is a kept record of the same country."""
    _, id_col, prefix, _ = SOURCES[source]
    d = read(source)
    d["id"] = prefix + d[id_col]
    check = pd.read_csv(source_dir / "hand_check.csv", dtype=str, keep_default_na=False)
    gone = set(check.loc[check["university"] == "n", "id"])
    places = check[(check["university"] == "n") & check["name"].map(is_location)]
    kept = d[~d["id"].isin(gone)]
    kept_ids = set(kept["id"])
    country = "country_code" if "country_code" in d else "country"
    by_name = {(norm_text(n), c): i for n, c, i in zip(kept["name"], kept[country], kept["id"])}
    rows = d.set_index("id")
    out = []
    for cid in places["id"]:
        r = rows.loc[cid]
        c = r[country]
        parents = []
        if source == "ror":
            for p in r.get("parent_ror_id", "").split(" | "):
                if prefix + p in kept_ids:
                    parents.append(prefix + p)
        else:
            for p in r.get("parent_institutions", "").split(" | "):
                if p and (norm_text(p), c) in by_name:
                    parents.append(by_name[(norm_text(p), c)])
        after_of = re.split(r"\b(?:branch|campus) of\b", r["name"], flags=re.I)
        if len(after_of) > 1 and (norm_text(after_of[1]), c) in by_name:
            parents.append(by_name[(norm_text(after_of[1]), c)])
        # "Shandong University of Science and Technology Taian Campus" -> "... Science and Technology"
        words = norm_text(r["name"]).split()
        for k in range(len(words) - 1, 1, -1):
            start = " ".join(words[:k])
            if (start, c) in by_name and has(start, HE_WORDS):
                parents.append(by_name[(start, c)])
                break
        if parents:
            out.append(dict(university_id=parents[0], university=rows.at[parents[0], "name"], campus_id=cid,
                            campus=r["name"], city=r["city"], country=c))
    out = pd.DataFrame(out, columns=["university_id", "university", "campus_id", "campus", "city", "country"])
    out.sort_values(["university", "campus"]).to_csv(source_dir / "campuses.csv", index=False, encoding="utf-8-sig")
    print(f"{source}: {len(out)} of {len(places)} removed campuses / branches attached to {out['university_id'].nunique()} "
          f"universities -> campuses.csv")


def decisions(path, column, label):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df[column] = df[column].str.strip().str.lower()
    bad = df[~df[column].isin(["y", "n"])]
    if len(bad):
        raise SystemExit(f"{path.name}: {len(bad)} rows have no y / n in '{column}', e.g. "
                         + "; ".join(bad[label].head(5)))
    return df


def write_version(source, source_dir, remove, suffix):
    """Writes the source without the ids in remove, as CSV and as MapForce XML."""
    csv_file, id_col, prefix, xml_file = SOURCES[source]
    src = read(source)
    keep = ~(prefix + src[id_col]).isin(remove)
    out_csv = source_dir / Path(csv_file).name.replace(".csv", f"_{suffix}.csv")
    src[keep].to_csv(out_csv, index=False)
    # MapForce writes one <institution> per CSV row, so dropping the blocks is the same as mapping again
    xml = (DATA / xml_file).read_text(encoding="utf-8")
    blocks = list(re.finditer(r"[ \t]*<institution>.*?</institution>\r?\n", xml, flags=re.S))
    kept = []
    for b in blocks:
        if re.search(r"<id>(.*?)</id>", b.group(0)).group(1) not in remove:
            kept.append(b.group(0))
    out_xml = source_dir / Path(xml_file).name.replace(".xml", f"_{suffix}.xml")
    out_xml.write_text(xml[:blocks[0].start()] + "".join(kept) + xml[blocks[-1].end():], encoding="utf-8")
    assert keep.sum() == len(kept), "CSV and XML do not lose the same rows"
    valid = etree.XMLSchema(etree.parse(str(DATA / "target.xsd"))).validate(etree.parse(str(out_xml)))
    print(f"  {out_xml.name}: {len(src)} -> {keep.sum()} rows, valid against target.xsd: {valid}")


def apply(source, source_dir):
    """Writes *_filtered (round 4), campuses.csv and *_deduplicated (round 6) next to the checks."""
    check = decisions(source_dir / "hand_check.csv", "university", "name")
    non_uni = set(check.loc[check["university"] == "n", "id"])
    print(f"{source}: {len(non_uni)} non-universities ({len(check) - len(non_uni)} flagged rows kept); "
          f"checked by a person {(check['checked_by'] != '').sum()} of {(check['check_by_hand'] == 'yes').sum()}")
    write_version(source, source_dir, non_uni, "filtered")
    campuses(source, source_dir)
    path = source_dir / "duplicate_check.csv"
    if path.exists():
        dup = decisions(path, "same", "name1")
        drop = set()
        for a, b, keep, same in zip(dup["id1"], dup["id2"], dup["keep"], dup["same"]):
            if same == "y":
                drop.add(b if keep == a else a)
        print(f"{source}: {len(drop)} duplicates; checked by a person {(dup['checked_by'] != '').sum()}")
        write_version(source, source_dir, drop, "deduplicated")
