"""Shared code of the additional filtering: rows of a source that are not a university of their own.

The proposal defines a university as a degree-awarding higher education institution that is an
organisation of its own (no branches, campuses, faculties, schools below higher education). Per source:
  <source>/filter.py   flags candidate rows with word rules -> <source>/hand_check.csv
  <source>/apply.py    removes every row marked university = n -> <source>/*_filtered.csv and .xml
hand_check.csv, column "university": n = not a university (removed), y = a university (stays).
New rows start with n. Column "group": "risky" if a rule word could mean something else in that
name ("University of Texas Medical BRANCH"), otherwise a safe group where that cannot happen.
check_by_hand = yes for every risky row, 10 rows of each safe group and every row the AI doubted.
The filtered files stay here, next to the check; data/ keeps the original sources.
"""
import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PER_SAFE_GROUP = 10

SOURCES = {   # csv, id column, id prefix, MapForce output
    "wikidata": ("wikidata/wikidata_universities.csv", "wikidata_id", "wikidata_", "wikidata/Wikidata_Mapping.xml"),
    "ror": ("ror/ror_education.csv", "ror_id", "ror_", "ror/ROR_Mapping.xml"),
    "deqar": ("deqar/deqar_institutions.csv", "deqar_id", "deqar_", "deqar/deqar_Mapping.xml"),
}
COLUMNS = ["id", "name", "alt_names", "country", "city", "part_of", "why_flagged", "group", "check_by_hand",
           "ai_suggestion", "ai_note", "university", "checked_by", "comment"]
DECISIONS = ["ai_suggestion", "ai_note", "university", "checked_by", "comment"]   # kept when run again

# words of a higher education institution, used by several rules
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
    """True if the normalised text contains one of the words / phrases (regex alternatives)."""
    return re.search(rf" (?:{words}) ", f" {norm_text(text)} ") is not None


def read(source):
    csv = SOURCES[source][0]
    return pd.read_csv(DATA / csv, dtype=str, keep_default_na=False)


def write_hand_check(source_dir, flagged):
    """flagged: DataFrame with id, name, alt_names, country, city, part_of, why_flagged, group."""
    f = flagged.copy()
    path = source_dir / "hand_check.csv"
    for c in DECISIONS:
        f[c] = "n" if c == "university" else ""
    if path.exists():   # keep decisions already made
        old = pd.read_csv(path, dtype=str, keep_default_na=False).set_index("id")
        known = f["id"].isin(old.index)
        for c in DECISIONS:
            f.loc[known, c] = f.loc[known, "id"].map(old[c])
        gone = old[~old.index.isin(f["id"]) & (old["checked_by"] != "")]
        if len(gone):
            print(f"note: {len(gone)} hand-checked rows are no longer flagged:", "; ".join(gone["name"]))
    # sample of each safe group: the rows with the smallest hash of their id (stable between runs)
    f["_h"] = f["id"].map(lambda i: hashlib.md5(i.encode()).hexdigest())
    sample = set(f[f["group"] != "risky"].sort_values("_h").groupby("group").head(PER_SAFE_GROUP)["id"])
    f["check_by_hand"] = ["yes" if g == "risky" or i in sample or a in ("y", "unclear") else "no"
                          for g, i, a in zip(f["group"], f["id"], f["ai_suggestion"])]
    f = f.sort_values(["check_by_hand", "group", "why_flagged", "country", "name"],
                      ascending=[False, True, True, True, True])[COLUMNS]
    f.to_csv(path, index=False, encoding="utf-8-sig")   # utf-8-sig: Excel shows accents right
    print(f"hand_check.csv: {len(f)} flagged | to check by hand {(f['check_by_hand'] == 'yes').sum()} | "
          f"marked y {(f['university'] == 'y').sum()}, n {(f['university'] == 'n').sum()} | "
          f"checked by a person {(f['checked_by'] != '').sum()}")
    print(f.groupby(["group", "why_flagged"]).size().to_string())


# ---------- duplicates within one source ----------

DUP_COLUMNS = ["id1", "name1", "info1", "id2", "name2", "info2", "why_flagged", "group", "check_by_hand",
               "ai_suggestion", "ai_note", "same", "keep", "checked_by", "comment"]
DUP_DECISIONS = ["ai_suggestion", "ai_note", "same", "keep", "checked_by", "comment"]
LINKS = {"wikidata": ["ror_id", "wikipedia_en"], "ror": ["wikidata_id", "wikipedia_en"], "deqar": ["ror_id"]}
INFO = ["country_code", "country", "city", "website", "founding_year", "closure_year", "status", "alt_names"]


def find_duplicates(source, source_dir):
    """Candidate pairs of rows of one source that may be the same institution: both point to the same
    record of another source (ror_id, wikidata_id, Wikipedia article) or have the same name and country.
    Rows already marked as non-universities are left out (they are removed after matching anyway)."""
    _, id_col, prefix, _ = SOURCES[source]
    d = read(source)
    d["id"] = prefix + d[id_col]
    check = pd.read_csv(source_dir / "hand_check.csv", dtype=str, keep_default_na=False)
    d = d[~d["id"].isin(set(check.loc[check["university"] == "n", "id"]))]
    country = "country_code" if "country_code" in d else "country"
    keys = {f"same {c}": [(v.strip(), i) for vs, i in zip(d[c], d["id"]) for v in vs.split(" | ") if v.strip()]
            for c in LINKS[source]}
    keys["same name + country"] = [((norm_text(n), c), i) for n, c, i in zip(d["name"], d[country], d["id"])]
    why = {}
    for reason, pairs in keys.items():
        groups = pd.DataFrame(pairs, columns=["key", "id"]).groupby("key")["id"].apply(lambda s: sorted(set(s)))
        for ids in groups[groups.map(len) > 1]:
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    why.setdefault((a, b), []).append(reason)
    rows = d.set_index("id")
    info = lambda i: " | ".join(f"{c}: {rows.at[i, c]}" for c in INFO if c in rows and rows.at[i, c])
    filled = lambda i: (rows.loc[i] != "").sum()
    out = pd.DataFrame([dict(id1=a, name1=rows.at[a, "name"], info1=info(a), id2=b, name2=rows.at[b, "name"],
                             info2=info(b), why_flagged=" & ".join(r), keep=a if filled(a) >= filled(b) else b)
                        for (a, b), r in why.items()])
    # safe group: two places and two websites ("Government Medical College" Surat / Nagpur); an empty or
    # differently written city alone is no proof (Wikidata enters the same university twice)
    host = lambda i: re.sub(r"^(https?://)?(www\.)?", "", rows.at[i, "website"].lower()).split("/")[0]
    apart = [all([rows.at[a, "city"], rows.at[b, "city"], host(a), host(b)])
             and norm_text(rows.at[a, "city"]) != norm_text(rows.at[b, "city"]) and host(a) != host(b)
             for a, b in zip(out["id1"], out["id2"])]
    # safe group: the same entry twice - same name, website and city (ROR campuses share name and website)
    twin = [host(a) and host(a) == host(b) and norm_text(rows.at[a, "name"]) == norm_text(rows.at[b, "name"])
            and norm_text(rows.at[a, "city"]) == norm_text(rows.at[b, "city"])
            for a, b in zip(out["id1"], out["id2"])]
    out["group"] = ["same name, other city and website" if w == "same name + country" and x else
                    "same name and website" if t else "risky"
                    for w, x, t in zip(out["why_flagged"], apart, twin)]
    return out


# what the AI should say in a safe group; a pair where it says something else is checked by hand
EXPECTED = {"same name, other city and website": "n", "same name and website": "y"}


def write_duplicate_check(source_dir, pairs):
    """Write duplicate_check.csv: column "same" y = one institution (apply.py removes the row not in
    "keep"), n = two institutions. New pairs start with n. Decisions already in the file are kept."""
    f = pairs.copy()
    path = source_dir / "duplicate_check.csv"
    default_keep = f["keep"].copy()
    for c in DUP_DECISIONS:
        f[c] = "n" if c == "same" else ""
    f["keep"] = default_keep
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False).set_index(["id1", "id2"])
        idx = pd.MultiIndex.from_arrays([f["id1"], f["id2"]])
        known = idx.isin(old.index)
        for c in DUP_DECISIONS:
            f.loc[known, c] = old.loc[idx[known], c].values
    # checked by hand: every pair that would be merged or is unclear and not in a safe group as expected,
    # plus 10 random pairs of each safe group and of the risky pairs the AI keeps apart
    must = [a == "unclear" or (g == "risky" and a == "y") or (g != "risky" and a and a != EXPECTED[g])
            for g, a in zip(f["group"], f["ai_suggestion"])]
    f["_h"] = (f["id1"] + f["id2"]).map(lambda i: hashlib.md5(i.encode()).hexdigest())
    rest = f[[not m for m in must]]
    sample = set(rest.sort_values("_h").groupby("group").head(PER_SAFE_GROUP).index)
    f["check_by_hand"] = ["yes" if m or i in sample else "no" for i, m in zip(f.index, must)]
    f = f.sort_values(["check_by_hand", "group", "name1"], ascending=[False, True, True])[DUP_COLUMNS]
    f.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"duplicate_check.csv: {len(f)} pairs | to check by hand {(f['check_by_hand'] == 'yes').sum()} | "
          f"same y {(f['same'] == 'y').sum()}, n {(f['same'] == 'n').sum()} | checked by a person "
          f"{(f['checked_by'] != '').sum()}")
    print(f.groupby(["group", "why_flagged"]).size().to_string())


# ---------- campuses and branches as a list on their university ----------

def campuses(source, source_dir):
    """campuses.csv: every removed campus or branch (a location, not a research unit) with the university
    it belongs to, which stays. The university is found by, in this order: the parent link (ROR id,
    DEQAR name), the name after "branch of" / "campus of", or the longest start of the name that is
    the exact name of a kept record of the same country
    ("Shandong University of Science and Technology Taian Campus" -> "... Science and Technology")."""
    _, id_col, prefix, _ = SOURCES[source]
    d = read(source)
    d["id"] = prefix + d[id_col]
    check = pd.read_csv(source_dir / "hand_check.csv", dtype=str, keep_default_na=False)
    gone = set(check.loc[check["university"] == "n", "id"])
    location = lambda n: has(n, "campus|branch") and not has(n, r"institut|institute|centre|center|laboratory|faculty")
    places = check[(check["university"] == "n") & check["name"].map(location)]
    kept = d[~d["id"].isin(gone)]
    country = "country_code" if "country_code" in d else "country"
    by_name = {(norm_text(n), c): i for n, c, i in zip(kept["name"], kept[country], kept["id"])}
    rows = d.set_index("id")
    out = []
    for cid in places["id"]:
        r = rows.loc[cid]
        find = lambda name: by_name.get((norm_text(name), r[country]))
        links = r.get("parent_ror_id", "").split(" | ") if source == "ror" else r.get("parent_institutions", "").split(" | ")
        parents = [prefix + p for p in links if source == "ror" and prefix + p in kept["id"].values]
        parents += [find(p) for p in links if source != "ror" and p and find(p)]
        after_of = re.split(r"\b(?:branch|campus) of\b", r["name"], flags=re.I)
        if len(after_of) > 1 and find(after_of[1]):
            parents.append(find(after_of[1]))
        words = norm_text(r["name"]).split()
        parents += [by_name[(" ".join(words[:k]), r[country])] for k in range(len(words) - 1, 1, -1)
                    if (" ".join(words[:k]), r[country]) in by_name and has(" ".join(words[:k]), HE_WORDS)][:1]
        if parents:
            out.append(dict(university_id=parents[0], university=rows.at[parents[0], "name"], campus_id=cid,
                            campus=r["name"], city=r["city"], country=r[country]))
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
    """The source without the ids in `remove`: CSV, and the same rows taken out of the MapForce output
    (it maps one CSV row to one <institution>, so this equals mapping the reduced CSV again)."""
    csv_file, id_col, prefix, xml_file = SOURCES[source]
    src = read(source)
    keep = ~(prefix + src[id_col]).isin(remove)
    out_csv = source_dir / Path(csv_file).name.replace(".csv", f"_{suffix}.csv")
    src[keep].to_csv(out_csv, index=False)
    xml = (DATA / xml_file).read_text(encoding="utf-8")
    blocks = list(re.finditer(r"[ \t]*<institution>.*?</institution>\r?\n", xml, flags=re.S))
    kept = [b.group(0) for b in blocks if re.search(r"<id>(.*?)</id>", b.group(0)).group(1) not in remove]
    out_xml = source_dir / Path(xml_file).name.replace(".xml", f"_{suffix}.xml")
    out_xml.write_text(xml[:blocks[0].start()] + "".join(kept) + xml[blocks[-1].end():], encoding="utf-8")
    assert keep.sum() == len(kept), "CSV and XML do not lose the same rows"
    from lxml import etree
    valid = etree.XMLSchema(etree.parse(str(DATA / "target.xsd"))).validate(etree.parse(str(out_xml)))
    print(f"  {out_xml.name}: {len(src)} -> {keep.sum()} rows, valid against target.xsd: {valid}")


def apply(source, source_dir):
    """Writes two versions of the source next to the checks:
      *_filtered      without the rows marked university = n in hand_check.csv (round 4)
      campuses.csv    the removed campuses and branches with the university they belong to
      *_deduplicated  without the duplicates marked same = y in duplicate_check.csv, keeping the row in
                      "keep" (round 6; there the non-universities are removed after matching)"""
    check = decisions(source_dir / "hand_check.csv", "university", "name")
    non_uni = set(check.loc[check["university"] == "n", "id"])
    print(f"{source}: {len(non_uni)} non-universities ({len(check) - len(non_uni)} flagged rows kept); "
          f"checked by a person {(check['checked_by'] != '').sum()} of {(check['check_by_hand'] == 'yes').sum()}")
    write_version(source, source_dir, non_uni, "filtered")
    campuses(source, source_dir)
    path = source_dir / "duplicate_check.csv"
    if path.exists():
        dup = decisions(path, "same", "name1")
        drop = {b if k == a else a for a, b, k, y in zip(dup["id1"], dup["id2"], dup["keep"], dup["same"]) if y == "y"}
        print(f"{source}: {len(drop)} duplicates; checked by a person {(dup['checked_by'] != '').sum()}")
        write_version(source, source_dir, drop, "deduplicated")
