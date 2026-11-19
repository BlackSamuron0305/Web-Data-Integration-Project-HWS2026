"""ROR: apply Rules 1-5 (see rules.md in the repo root) to the ROR education records.

A record stays unless one of the fixed conditions below matches; the first
matching step decides. There is no review list.

Step 0, Wikidata link
  Run wikidata/filter.py first. A ROR record goes if it is linked one-to-one
  to a Wikidata record that wikidata/filter.py removed with Rules 1-4. The link
  is the ID link of either source (Wikidata ror_id or ROR wikidata_id); only
  pairs where neither side links to anything else count. Wikidata Rule 5
  (duplicates) is not passed on: the institution still exists in Wikidata.
  The record gets the rule number of its Wikidata partner.

Rule 1, level (name = the ROR display name; alternative names hold old names
and are only used for the Chinese/Japanese level words)
  goes if the name contains a BELOW_BACHELOR word, or "vocational" and no
    university word, or
  goes if an alternative name contains a CJK_BELOW_BACHELOR word and the name
    has no university word, or
  goes if a parent is a community or technical college system or district, or
  goes if the name contains a SCHOOL word, or liceo/lycée and no university word, or
  goes if the name contains a RELIGIOUS word and no university word.
Rule 2, recognized
  ROR has no field for it; nothing goes.
Rule 3, own organisation
  goes if a parent (parent_ror_id, resolved to its name inside this file) is a
  single institution: its name has an INSTITUTION word and is not a system
  (SYSTEM_PARENT words or the FEDERAL list). Parents outside the file do not count.
Rule 4, purpose is education
  goes if the name contains a NOT_EDUCATION word, or a NOT_EDUCATION_BODY word
    and no "University of".
Rule 5, duplicates
  records with the same cleaned name, same country and same website domain are
  one institution; the city is ignored. A record without website is never a
  duplicate. The active record stays, then the one with the most filled
  fields, then the lower ROR id.

Usage: python filter.py
Reads data/ror/ror_education.csv and data/wikidata/wikidata_universities.csv
(never changed) and wikidata/removed.csv. Writes next to this script:
  ror_education.csv   the records that stay
  removed.csv         the records that go, with rule, step and reason
"""

import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "data" / "ror" / "ror_education.csv"
WIKIDATA = ROOT / "data" / "wikidata" / "wikidata_universities.csv"
WIKIDATA_REMOVED = HERE.parent / "wikidata" / "removed.csv"
SEP = " | "

# ------------------------------------------------------------------ word lists
# All patterns are matched on the lower-cased text.

UNIVERSITY = r"universit|universidad|universidade|universitas|université"

BELOW_BACHELOR = (
    r"junior college|community college|kolej komuniti|kolej vokasional"
    r"|kolej kemahiran|\bc[eé]gep\b|\bakademi\b|tanki daigaku"
)
# Chinese "vocational universities" award bachelor's degrees, so "vocational"
# only counts when the name has no university word.
VOCATIONAL = r"vocational"
CJK_BELOW_BACHELOR = r"职业|高等专科|短期大学"
COMMUNITY_PARENT = r"community college|technical college system|community and technical"

SCHOOL = (
    r"high school|secondary school|secondary college|\bgymnas|gymnázium|primary school"
    r"|middle school|elementary school|school district|international school"
    r"|escola básica|educación secundaria|pre.university|public schools"
    r"|kindergarten|高等学校"
)
# "Liceo de Cagayan University" is a university: these two only count without a
# university word.
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
# Bodies that also appear in university names ("University of the Ministry of
# Internal Affairs", "University of Turkish Aeronautical Association"): they
# only count when the name has no "University of".
NOT_EDUCATION_BODY = r"\bsociety\b|\bassociation\b|\bministry\b|\bcouncil\b"
UNIVERSITY_OF = r"university of|universidad d|universidade d|université d|universit[àa] d"


def has(text: pd.Series, pattern: str) -> pd.Series:
    return text.str.contains(pattern, regex=True)


# ------------------------------------------------------------- step 0: link


def split(value) -> list[str]:
    return [] if pd.isna(value) else [x.strip() for x in str(value).split("|") if x.strip()]


def wikidata_step(ror: pd.DataFrame) -> pd.DataFrame:
    """Per ROR record: Wikidata partner, rule and reason, if that partner was removed."""
    wd = pd.read_csv(WIKIDATA, dtype=str)
    removed = pd.read_csv(WIKIDATA_REMOVED, dtype=str)
    removed = removed[removed["rule"] != "5"].set_index("wikidata_id")

    links = {(w, r) for w, rs in zip(wd["wikidata_id"], wd["ror_id"]) for r in split(rs)}
    links |= {(w, r) for r, ws in zip(ror["ror_id"], ror["wikidata_id"]) for w in split(ws)}
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


# ---------------------------------------------------------- rules 1, 3 and 4


def parent_names(ror: pd.DataFrame) -> pd.Series:
    name = ror.set_index("ror_id")["name"].str.lower()
    return ror["parent_ror_id"].apply(lambda v: [name[p] for p in split(v) if p in name.index])


def single_institution(parent: str) -> bool:
    return (re.search(INSTITUTION, parent) is not None
            and re.search(SYSTEM_PARENT, parent) is None
            and parent not in FEDERAL)


def rules_1_to_4(ror: pd.DataFrame) -> pd.DataFrame:
    name = ror["name"].fillna("").str.lower()
    alt = ror["alt_names"].fillna("").str.lower()
    uni = has(name, UNIVERSITY)
    parents = parent_names(ror)

    community_parent = parents.apply(lambda ps: next((p for p in ps if re.search(COMMUNITY_PARENT, p)), ""))
    part_of = parents.apply(lambda ps: next((p for p in ps if single_institution(p)), ""))

    def word(pattern: str) -> pd.Series:
        return name.str.extract(f"({pattern})", expand=False).fillna("")

    steps = [  # (rule, condition, reason)
        ("1", has(name, BELOW_BACHELOR), "below bachelor: " + word(BELOW_BACHELOR)),
        ("1", has(name, VOCATIONAL) & ~uni, "below bachelor: vocational"),
        ("1", has(alt, CJK_BELOW_BACHELOR) & ~uni,
         "below bachelor (alternative name): " + alt.str.extract(f"({CJK_BELOW_BACHELOR})", expand=False).fillna("")),
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
        out.loc[new, "reason"] = reason[new] if isinstance(reason, pd.Series) else reason
    return out


# ------------------------------------------------------------------ rule 5


def clean_name(name) -> str:
    return "" if pd.isna(name) else " ".join(re.sub(r"[^\w ]", " ", str(name).lower()).split())


def domain(website) -> str:
    if pd.isna(website):
        return ""
    host = re.sub(r"^[a-z]+://", "", str(website).strip().lower()).split("/")[0]
    return host.split(":")[0].removeprefix("www.")


def rule_5(df: pd.DataFrame) -> pd.Series:
    """Return, per record, the id of the record it duplicates ("" if none)."""
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


# -------------------------------------------------------------------- main


def main() -> None:
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
