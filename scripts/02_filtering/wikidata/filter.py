"""Wikidata: clean the type labels, apply Rules 1-5 from rules.md and write the result to data/wikidata/filtered/.

Within each rule the type labels are checked first, then the name. Usage: python filter.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import finish, name_rule, read_original  # noqa: E402

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

# an arts label means it's e.g. a conservatory, so a religious label doesn't remove it
ARTS = {"conservatory", "music school", "art academy", "college of music"}

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

# a label with one of these in it is a higher education label
HIGHER_PARTS = (
    "universit", "polytechn", "higher education", "hochschule", "college",
    "academy", "conservatory", "école", "grand établissement", "sekolah tinggi",
    "institute of technology", "institutes of technology", "school of",
    "medical school", "law school", "business school", "engineering school",
    "graduate school", "art school", "design school", "drama school", "film school",
    "music school", "architecture school", "dental school", "veterinary school",
    "pharmacy school", "nursing school", "studium generale",
)

# labels that don't say what kind of institution it is (publishers, buildings, places ...)
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


def clean_label(label):
    return " ".join(label.replace("’", "'").split()).lower()


def is_higher(label):
    return label not in EXCLUDING and any(part in label for part in HIGHER_PARTS)


def is_noise(label):
    if label in EXCLUDING or is_higher(label):
        return False
    # short parts only count if they are the whole label
    return any(part == label or (len(part) > 6 and part in label) for part in NOISE_PARTS)


def clean_types(value):
    if pd.isna(value):
        return []
    labels = {clean_label(x) for x in str(value).split("|") if x.strip()}
    return sorted(x for x in labels if not is_noise(x))


def first(labels, group):
    for x in labels:
        if x in group:
            return x
    return ""


def protected(labels, label, name, students):
    # some general christian universities are labelled "seminary" because a seminary is part of them
    if any(x in ARTS for x in labels):
        return True
    name = "" if pd.isna(name) else str(name)
    return (re.search(r"\buniversit", name, re.IGNORECASE) is not None
            and not RELIGIOUS_NAME.search(name)
            and label != "catholic seminary"
            and not pd.isna(students))


def rules_1_to_4(labels, name, students, country):
    """Returns (rule, reason) of the first rule that removes the record, or ("", "")."""
    higher = [x for x in labels if is_higher(x)]
    general = [x for x in higher if "universit" in x]

    label = first(labels, BELOW_BACHELOR)
    if label:
        return "1", label
    label = first(labels, RELIGIOUS)
    if label and not general and not protected(labels, label, name, students):
        return "1", label
    label = first(labels, SCHOOL)
    if label and not higher:
        return "1", label
    reason = name_rule("1", name, country)
    if reason:
        return "1", reason
    label = first(labels, NOT_RECOGNIZED)
    if label:
        return "2", label
    label = first(labels, PART)
    if label and not higher:
        return "3", label
    reason = name_rule("3", name, country)
    if reason:
        return "3", reason
    label = first(labels, NOT_EDUCATION)
    if label and not higher:
        return "4", label
    reason = name_rule("4", name, country)
    if reason:
        return "4", reason
    return "", ""


def main():
    df = read_original("wikidata", "wikidata_universities.csv")
    labels = df["types"].apply(clean_types)
    df["types"] = labels.str.join(" | ").replace("", pd.NA)
    rules = []
    reasons = []
    for lab, name, students, country in zip(labels, df["name"], df["students"], df["country"]):
        rule, reason = rules_1_to_4(lab, name, students, country)
        rules.append(rule)
        reasons.append(reason)
    df["rule"] = rules
    df["reason"] = reasons
    finish(df, "wikidata", "wikidata_universities.csv", "Wikidata_Mapping.xml", "wikidata_id",
           lambda q: int(q[1:]), ["wikidata_id", "name", "country", "types"])


if __name__ == "__main__":
    main()
