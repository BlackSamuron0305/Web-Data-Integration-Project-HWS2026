"""Early ROR filter (Rules 1-5 of rules.md) that also removed a ROR record when its one-to-one
Wikidata ID partner was removed by the Wikidata filter. Dropped because the ID links are our answer key.
Run with: python filter.py (after wikidata/filter.py), writes ror_education.csv and removed.csv here."""
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "data" / "ror" / "ror_education.csv"
WIKIDATA = ROOT / "data" / "wikidata" / "wikidata_universities.csv"
WIKIDATA_REMOVED = HERE.parent / "wikidata" / "removed.csv"

# all patterns are matched on the lower-cased name
UNIVERSITY = r"universit|universidad|universidade|universitas|université"

BELOW_BACHELOR = (
    r"junior college|community college|kolej komuniti|kolej vokasional"
    r"|kolej kemahiran|\bc[eé]gep\b|\bakademi\b|tanki daigaku"
)
# Chinese "vocational universities" give bachelor's degrees, so only without a university word
VOCATIONAL = r"vocational"
CJK_BELOW_BACHELOR = r"职业|高等专科|短期大学"
COMMUNITY_PARENT = r"community college|technical college system|community and technical"

SCHOOL = (
    r"high school|secondary school|secondary college|\bgymnas|gymnázium|primary school"
    r"|middle school|elementary school|school district|international school"
    r"|escola básica|educación secundaria|pre.university|public schools"
    r"|kindergarten|高等学校"
)
# only without a university word, "Liceo de Cagayan University" is a university
SCHOOL_NO_UNIVERSITY = r"\bliceo\b|\blycée\b"

RELIGIOUS = r"seminar|theolog|bible|madras|divinity|teologi|\bagama\b"

INSTITUTION = UNIVERSITY + r"|institut|college|school|academy|hochschule|école|escuela"
SYSTEM_PARENT = (
    r"system|network|district|higher education|higher learning|city colleges"
    r"|group|foundation|stichting|pôle"
)
FEDERAL = {  # parents whose members are institutions of their own
    "state university of new york", "city university of new york",
    "university of london", "vietnam national university, hanoi",
    "vietnam national university ho chi minh city", "université du québec",
    "rajamangala university of technology", "amity university",
}

NOT_EDUCATION = r"academy of sciences|\bhospital\b|\blibrar|\bmuseum\b|\bsystem\b"
# these also show up in real university names ("University of the Ministry of Internal Affairs"),
# so only without "University of"
NOT_EDUCATION_BODY = r"\bsociety\b|\bassociation\b|\bministry\b|\bcouncil\b"
UNIVERSITY_OF = r"university of|universidad d|universidade d|université d|universit[àa] d"


def has(text, pattern):
    return text.str.contains(pattern, regex=True)


def split(value):
    if pd.isna(value):
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def wikidata_step(ror):
    """Rule and reason per ROR record whose Wikidata partner was removed (not for duplicates, rule 5)."""
    wd = pd.read_csv(WIKIDATA, dtype=str)
    removed = pd.read_csv(WIKIDATA_REMOVED, dtype=str)
    removed = removed[removed["rule"] != "5"].set_index("wikidata_id")

    # ID links from both sides, only pairs where neither side links to anything else count
    links = set()
    for w, rs in zip(wd["wikidata_id"], wd["ror_id"]):
        for r in split(rs):
            links.add((w, r))
    for r, ws in zip(ror["ror_id"], ror["wikidata_id"]):
        for w in split(ws):
            links.add((w, r))
    links = pd.DataFrame(sorted(links), columns=["wikidata_id", "ror_id"])
    links = links[links["wikidata_id"].isin(wd["wikidata_id"]) & links["ror_id"].isin(ror["ror_id"])]
    one = links[links.groupby("ror_id")["wikidata_id"].transform("size").eq(1)
                & links.groupby("wikidata_id")["ror_id"].transform("size").eq(1)]
    hit = one[one["wikidata_id"].isin(removed.index)].set_index("ror_id")["wikidata_id"]

    out = pd.DataFrame({"rule": "", "reason": ""}, index=ror.index)
    idx = ror.index[ror["ror_id"].isin(hit.index)]
    partner = ror.loc[idx, "ror_id"].map(hit)
    out.loc[idx, "rule"] = partner.map(removed["rule"]).values
    out.loc[idx, "reason"] = ("Wikidata " + partner + " removed: " + partner.map(removed["reason"])).values
    return out


def single_institution(parent):
    return (re.search(INSTITUTION, parent) is not None
            and re.search(SYSTEM_PARENT, parent) is None
            and parent not in FEDERAL)


def college_system_parent(parents):
    for p in parents:
        if re.search(COMMUNITY_PARENT, p):
            return p
    return ""


def institution_parent(parents):
    for p in parents:
        if single_institution(p):
            return p
    return ""


def rules_1_to_4(ror):
    name = ror["name"].fillna("").str.lower()
    alt = ror["alt_names"].fillna("").str.lower()
    uni = has(name, UNIVERSITY)
    # parent names, only parents that are in this file count
    lower_names = ror.set_index("ror_id")["name"].str.lower()
    parents = ror["parent_ror_id"].apply(lambda v: [lower_names[p] for p in split(v) if p in lower_names.index])

    community_parent = parents.apply(college_system_parent)
    part_of = parents.apply(institution_parent)

    def word(pattern):
        return name.str.extract(f"({pattern})", expand=False).fillna("")

    cjk_word = alt.str.extract(f"({CJK_BELOW_BACHELOR})", expand=False).fillna("")
    steps = [  # (rule, condition, reason), the first one that fits wins
        ("1", has(name, BELOW_BACHELOR), "below bachelor: " + word(BELOW_BACHELOR)),
        ("1", has(name, VOCATIONAL) & ~uni, "below bachelor: vocational"),
        ("1", has(alt, CJK_BELOW_BACHELOR) & ~uni, "below bachelor (alternative name): " + cjk_word),
        ("1", community_parent != "", "parent is a college system: " + community_parent),
        ("1", has(name, SCHOOL), "school: " + word(SCHOOL)),
        ("1", has(name, SCHOOL_NO_UNIVERSITY) & ~uni, "school: " + word(SCHOOL_NO_UNIVERSITY)),
        ("1", has(name, RELIGIOUS) & ~uni, "religious: " + word(RELIGIOUS)),
        ("3", part_of != "", "part of: " + part_of),
        ("4", has(name, NOT_EDUCATION), "not education: " + word(NOT_EDUCATION)),
        ("4", has(name, NOT_EDUCATION_BODY) & ~has(name, UNIVERSITY_OF),
         "not education: " + word(NOT_EDUCATION_BODY)),
    ]
    out = pd.DataFrame({"rule": "", "reason": ""}, index=ror.index)
    for rule, condition, reason in steps:
        new = condition & (out["rule"] == "")
        out.loc[new, "rule"] = rule
        if isinstance(reason, pd.Series):
            out.loc[new, "reason"] = reason[new]
        else:
            out.loc[new, "reason"] = reason
    return out


def clean_name(name):
    if pd.isna(name):
        return ""
    return " ".join(re.sub(r"[^\w ]", " ", str(name).lower()).split())


def domain(website):
    if pd.isna(website):
        return ""
    host = re.sub(r"^[a-z]+://", "", str(website).strip().lower()).split("/")[0]
    return host.split(":")[0].removeprefix("www.")


def rule_5(df):
    """Per record the id of the record it duplicates ("" if none): same name, country and website domain.
    The active record stays, then the one with most filled fields, then the lower ROR id."""
    key = pd.DataFrame({
        "name": df["name"].apply(clean_name),
        "country": df["country"].fillna(""),
        "domain": df["website"].apply(domain),
    })
    order = pd.DataFrame({
        "inactive": df["status"].ne("active"),
        "filled": -df.notna().sum(axis=1),
        "ror_id": df["ror_id"],
    })[(key != "").all(axis=1)].join(key).sort_values(["inactive", "filled", "ror_id"])
    keeper = order.groupby(["name", "country", "domain"])["ror_id"].transform("first")
    lost = keeper[keeper != order["ror_id"]]
    duplicate_of = pd.Series("", index=df.index)
    duplicate_of[lost.index] = lost.values
    return duplicate_of


def main():
    df = pd.read_csv(SOURCE, dtype=str)

    linked = wikidata_step(df)
    own = rules_1_to_4(df)
    via_link = linked["rule"] != ""
    df["rule"] = linked["rule"].where(via_link, own["rule"])
    df["reason"] = linked["reason"].where(via_link, own["reason"])
    df["step"] = "wikidata link"
    df.loc[~via_link, "step"] = "ror rules"

    survivors = df["rule"] == ""
    duplicate_of = rule_5(df[survivors].drop(columns=["rule", "reason", "step"]))
    dup = duplicate_of[duplicate_of != ""]
    df.loc[dup.index, "rule"] = "5"
    df.loc[dup.index, "reason"] = "duplicate of " + dup

    removed = df[df["rule"] != ""]
    kept = df[df["rule"] == ""].drop(columns=["rule", "reason", "step"])

    kept.to_csv(HERE / "ror_education.csv", index=False)
    removed[["ror_id", "name", "country", "status", "rule", "step", "reason"]].sort_values(
        ["rule", "step", "reason", "name"]).to_csv(HERE / "removed.csv", index=False)

    print(f"records in: {len(df)}")
    print(f"removed:    {len(removed)}")
    print(f"kept:       {len(kept)}")
    print("\nremoved per rule and step:")
    print(removed.groupby(["rule", "step"]).size().to_string())


if __name__ == "__main__":
    main()
