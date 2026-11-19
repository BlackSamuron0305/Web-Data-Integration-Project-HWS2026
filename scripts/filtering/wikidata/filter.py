"""Wikidata: clean the type labels and apply Rules 1-5 (see rules.md in the repo root).

Every record was fetched as an instance of university (Q3918) or one of its
subclasses. A record stays unless one of the fixed conditions below matches;
the first matching rule decides. There is no review list.

Preparation: clean the types (trim, lower case, drop duplicates, drop labels
that do not describe an institution such as publishers, buildings, places).

Rule 1, level
  goes if a type is in BELOW_BACHELOR (always), or
  goes if a type is in RELIGIOUS and no type is a general university label,
    unless the record is protected (see below), or
  goes if a type is in SCHOOL and no type is a higher-education label.

  Protected against the RELIGIOUS labels (Wikidata only; added after checking
  the removed records, where general Christian universities were labelled
  "seminary" or "bible college" because a seminary is one of their parts):
  - a type is an arts label (ARTS), e.g. a pontifical institute of sacred music
    that is a conservatory; or
  - the name contains "University", the name has no religious word
    (RELIGIOUS_NAME), the label is not "catholic seminary" and Wikidata gives
    a student count.
Rule 2, recognized
  goes if a type is in NOT_RECOGNIZED (always).
Rule 3, own organisation
  goes if a type is in PART and no other type is a higher-education label.
Rule 4, purpose is education
  goes if a type is in NOT_EDUCATION and no other type is a higher-education label.
Rule 5, duplicates
  records with the same cleaned name, same country and same website domain are
  one institution; the city is ignored. A record without website or country is
  never a duplicate. The record with the most filled fields stays, on a tie the
  one with the lower Wikidata number.

Usage: python filter.py
Reads data/wikidata/wikidata_universities.csv (never changed). Writes next to this script:
  wikidata_universities.csv   the records that stay, with cleaned types
  removed.csv                 the records that go, with rule and reason
"""

import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2] / "data" / "wikidata" / "wikidata_universities.csv"

# ---------------------------------------------------------------- label sets

BELOW_BACHELOR = {
    "junior college", "junior college in japan", "korean junior college",
    "women's junior college", "professional and vocational junior college",
    "community college", "community college district",
    "college of technology in japan",  # kosen: five years from age 15
}

RELIGIOUS = {
    "seminary", "catholic seminary", "minor seminary", "jewish seminary",
    "jezuit seminary", "seminary of nobles", "redemptoris mater", "bible college",
    "catholic theological faculty", "protestant faculty of theology",
    "faculty of theology", "higher center for theological studies",
    "higher institute of religious sciences", "philosophical-theological university",
    "ecclesiastical university", "pontifical institute", "novitiate",
    "jesuit scholastic", "religious school", "madrasa", "qawmi madrasa",
    "alia madrasa", "nizamiyya", "teachers' seminar",
}

# Arts labels that protect a record against the RELIGIOUS labels.
ARTS = {"conservatory", "music school", "art academy", "college of music"}

# Words in a name that show a religious school (case does not matter).
RELIGIOUS_NAME = re.compile(
    r"semin|theolog|bible|divinity|faculty|fakult|facult|ecclesiast|religio|"
    r"ministry|school of|institute|pontific|kolleg|priest", re.IGNORECASE)

SCHOOL = {
    "high school", "secondary school", "primary school", "elementary school",
    "gymnasium", "academic gymnasium", "liceo", "boarding school", "girls' school",
    "university-preparatory school", "private school", "public school",
    "independent school", "day school", "all-through school", "christian school",
    "catholic school", "jesuit school", "urban school", "black school",
    "american indian boarding school", "academy school", "specialist school",
    "vocational school", "technical school", "further education college",
    "language school", "sports school", "military lyceum", "military high school",
    "suvorov military school", "nakhimov naval school", "cadet corps",
    "junker school", "orphanage", "virtual school",
}

NOT_RECOGNIZED = {
    "diploma mill", "unaccredited institution of higher education",
    "fake organization", "abandoned project", "proposed university",
    "proposed entity",
}

PART = {
    "faculty", "faculty of law", "faculty of commerce", "academic department",
    "division of an educational institution", "organizational subdivision",
    "campus", "satellite campus", "branch", "branch office", "university branch",
    "school annex", "affiliated school", "constituent college", "residential college",
    "college of the university of cambridge",
    "location in japan of a foreign university",
}

NOT_EDUCATION = {
    "research institute", "research center", "biological research institute",
    "institute for medical research", "institute of the russian academy of science",
    "laboratory", "hospital", "university hospital", "teaching hospital",
    "public hospital", "tertiary referral hospital", "medical facility", "clinic",
    "library", "academic library", "museum", "university museum", "art museum",
    "science museum", "national museum", "military museum", "archives",
    "university system", "state university system", "university network",
    "consortium", "european university alliance",
    "group of universities and institutions (france)", "government agency",
    "think tank", "learned society",
}

EXCLUDING = BELOW_BACHELOR | RELIGIOUS | SCHOOL | NOT_RECOGNIZED | PART | NOT_EDUCATION

# Word parts that mark a higher-education label.
HIGHER_PARTS = (
    "universit", "polytechn", "higher education", "hochschule", "college",
    "academy", "conservatory", "école", "grand établissement", "sekolah tinggi",
    "institute of technology", "institutes of technology", "school of",
    "medical school", "law school", "business school", "engineering school",
    "graduate school", "art school", "design school", "drama school", "film school",
    "music school", "architecture school", "dental school", "veterinary school",
    "pharmacy school", "nursing school", "studium generale",
)

# Labels that do not describe what kind of institution it is. Short parts
# only count as the whole label.
NOISE_PARTS = (
    "publisher", "publishing", "building", "built structure", "construction",
    "structure", "landmark", "heritage", "monument", "cultural property",
    "historic site", "historic district", "internet registry", "census",
    "wikimedia", "place", "location", "geographic", "neighborhood", "settlement",
    "unincorporated", "house", "palace", "palazzo", "château", "mansion",
    "bungalow", "tower block", "company", "enterprise", "corporation",
    "corporate body", "business", "production", "team", "club", "brewpub",
    "street", "airport", "cemetery", "painting", "edited volume",
    "version, edition", "award", "competition", "racing", "name",
    "date of establishment", "standardized test", "computing platform",
    "news website", "radio network", "photovoltaic", "set", "dyad",
    "aspect of history", "duplicate entry",
)

# ------------------------------------------------------------- preparation


def clean_label(label: str) -> str:
    return " ".join(label.replace("’", "'").split()).lower()


def is_higher(label: str) -> bool:
    return label not in EXCLUDING and any(part in label for part in HIGHER_PARTS)


def is_noise(label: str) -> bool:
    if label in EXCLUDING or is_higher(label):
        return False
    return any(part == label or (len(part) > 6 and part in label) for part in NOISE_PARTS)


def clean_types(value) -> list[str]:
    if pd.isna(value):
        return []
    labels = {clean_label(x) for x in str(value).split("|") if x.strip()}
    return sorted(x for x in labels if not is_noise(x))


# ------------------------------------------------------------- rules 1 to 4


def first(labels: list[str], group: set[str]) -> str:
    return next((x for x in labels if x in group), "")


def protected(labels: list[str], label: str, name, students) -> bool:
    """True if a RELIGIOUS label must not remove this record (see the docstring)."""
    if any(x in ARTS for x in labels):
        return True
    name = "" if pd.isna(name) else str(name)
    return (re.search(r"\buniversit", name, re.IGNORECASE) is not None
            and not RELIGIOUS_NAME.search(name)
            and label != "catholic seminary"
            and not pd.isna(students))


def rules_1_to_4(labels: list[str], name, students) -> tuple[str, str]:
    """Return (rule, label) of the first rule that removes the record, else ("", "")."""
    higher = [x for x in labels if is_higher(x)]
    general = [x for x in higher if "universit" in x]

    if label := first(labels, BELOW_BACHELOR):
        return "1", label
    label = first(labels, RELIGIOUS)
    if label and not general and not protected(labels, label, name, students):
        return "1", label
    if (label := first(labels, SCHOOL)) and not higher:
        return "1", label
    if label := first(labels, NOT_RECOGNIZED):
        return "2", label
    if (label := first(labels, PART)) and not higher:
        return "3", label
    if (label := first(labels, NOT_EDUCATION)) and not higher:
        return "4", label
    return "", ""


# ------------------------------------------------------------------ rule 5


def clean_name(name) -> str:
    if pd.isna(name):
        return ""
    return " ".join(re.sub(r"[^\w ]", " ", str(name).lower()).split())


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
    filled = df.drop(columns=["wikidata_id"]).notna().sum(axis=1)
    number = df["wikidata_id"].str[1:].astype(int)
    usable = (key != "").all(axis=1)

    order = pd.DataFrame({"filled": -filled, "number": number})[usable]
    order = order.join(key).sort_values(["filled", "number"])
    keeper = order.groupby(["name", "country", "domain"])["filled"].transform(
        lambda s: s.index[0])
    duplicate_of = pd.Series("", index=df.index)
    lost = keeper[keeper != keeper.index]
    duplicate_of[lost.index] = df.loc[lost.values, "wikidata_id"].values
    return duplicate_of


# -------------------------------------------------------------------- main


def main() -> None:
    df = pd.read_csv(SOURCE, dtype=str)
    labels = df["types"].apply(clean_types)
    df["types"] = labels.str.join(" | ").replace("", pd.NA)

    decided = pd.Series(
        [rules_1_to_4(lab, name, students)
         for lab, name, students in zip(labels, df["name"], df["students"])],
        index=df.index)
    df["rule"] = decided.str[0]
    df["reason"] = decided.str[1]

    survivors = df["rule"] == ""
    duplicate_of = rule_5(df[survivors].drop(columns=["rule", "reason"]))
    dup = duplicate_of[duplicate_of != ""]
    df.loc[dup.index, "rule"] = "5"
    df.loc[dup.index, "reason"] = "duplicate of " + dup

    removed = df[df["rule"] != ""]
    kept = df[df["rule"] == ""].drop(columns=["rule", "reason"])

    kept.to_csv(HERE / "wikidata_universities.csv", index=False)
    removed[["wikidata_id", "name", "country", "types", "rule", "reason"]].sort_values(
        ["rule", "reason", "name"]).to_csv(HERE / "removed.csv", index=False)

    print(f"records in: {len(df)}")
    print(f"removed:    {len(removed)}")
    print(f"kept:       {len(kept)}")
    print("\nremoved per rule:")
    print(removed["rule"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
