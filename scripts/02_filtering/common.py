"""Code shared by the three filters (<source>/filter.py): the name rules, Rule 5 and writing the outputs.

The rules themselves are described in rules.md in the repo root.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"

# in these countries a "polytechnic" gives diplomas below bachelor level
DIPLOMA_POLYTECHNIC_COUNTRIES = {
    "India", "Bangladesh", "Pakistan", "Nepal", "Sri Lanka", "Nigeria", "Ghana",
    "Kenya", "Zimbabwe", "Malaysia", "China",
}
# here a "college" (koledzh / kolledzh) is a short-cycle school below bachelor level
SHORT_CYCLE_COLLEGE_COUNTRIES = {"Ukraine", "Russia", "Belarus", "Kazakhstan", "Moldova", "Uzbekistan"}


def name_pattern(rule, reason, pattern, exception=None, countries=None):
    return (rule, reason, re.compile(pattern, re.IGNORECASE),
            re.compile(exception, re.IGNORECASE) if exception else None, countries)


# (rule, reason, pattern, exception, countries): the record goes if the pattern matches and the exception doesn't
NAME_RULES = [
    # "jamia" is left out, it just means "university" (Jamia Millia Islamia)
    name_pattern("1", "name: seminary, theology, bible, madrasa",
                 r"semin|theolog|bible|divinity|\bmadras(?:a|ah)\b|darul uloom|\buloom\b"),
    name_pattern("1", "name: community or junior college", r"community college|junior college"),
    # "High School of ..." is the usual English name of a Polish or Bosnian higher school
    name_pattern("1", "name: school, school board or district",
                 r"\bhigh school|secondary school|matriculation|school board|school district|public schools"
                 r"|board of education|unified school",
                 r"military|command|aviation|administration|engineering|technical|high school of"
                 r"|high school for|^high school"),
    # cadet academies and naval schools often give bachelor's degrees
    name_pattern("1", "name: infantry, training centre, cadet school",
                 r"infantry|training cent|\bcadet", r"statistical|academy|universit|naval"),
    # exceptions are Serbian and Polish vocational higher schools and applied sciences, they give bachelor's
    # degrees (\b keeps "polytechnical" out)
    name_pattern("1", "name: vocational or technical college",
                 r"vocational|\btechnical college|\btechnical institute|training institute",
                 r"universit|vocational studies|higher vocational school|vocational (?:academy|higher school)"
                 r"|state school of higher vocational|higher school of vocational|applied sciences|military"),
    name_pattern("1", "name: diploma-level polytechnic", r"polytechnic", r"universit",
                 DIPLOMA_POLYTECHNIC_COUNTRIES),
    # added after checking ROR and DEQAR
    name_pattern("1", "name: primary or K-12 school",
                 r"elementary school|primary school|kindergarten|pre-?school|early childhood|charter school"
                 r"|middle school|grammar school|\bk-12\b"),
    name_pattern("1", "name: technical or vocational school",
                 r"\btechnikum\b|\btechnical school|professional college|vocational school|\bkolej\b",
                 r"universit|higher technical school|polytechnic"),
    name_pattern("1", "name: vocational training or adult education",
                 r"institut de formation|formation en soins|croix-rouge|promotion sociale"
                 r"|enseignement pour adultes|adult education|continuing education|further education"
                 r"|formation continue"),
    name_pattern("1", "name: college (short-cycle in Eastern Europe and Central Asia)", r"\bcollege\b",
                 r"universit|academy|institute", SHORT_CYCLE_COLLEGE_COUNTRIES),
    name_pattern("1", "name: Japanese college of technology (kosen)",
                 r"national institute of technology,.*college|college of technology|kosen", r"universit",
                 {"Japan"}),
    # keep universities that just have "campus" in the name (Hochschule Campus Wien) and "X - Main Campus"
    name_pattern("3", "name: campus", r"\bcampus\b",
                 r"global campus|campus university|main campus|e-campus|campus\b[^,–-]*\b(?:universit|hochschule)"
                 r"|(?:universit\w*|hochschule)\s+campus\b"),
    name_pattern("3", "name: branch or unit", r"\bbranch\b|\bunit\b"),
    # only used when the source names a parent organisation (see name_rule)
    name_pattern("3", "name: faculty",
                 r"\bfaculty of|\bfaculty$|\bfacult(?:é|e|ad) (?:de|des|d')|fakultät|\bfakultas|facoltà"
                 r"|kulliyyah",
                 r"facultaire|faculteiten"),
    name_pattern("3", "name: centre for, research unit, laboratory",
                 r"\bcent(?:er|re) (?:for|of|on)\b|research (?:unit|lab|station)|laborator",
                 r"higher education|advanced scientific|educación superior|educational|technological education"
                 r"|academic studies|universit\w* cent"
                 r"|cent\w* (?:of|for) .*universit|universit\w* .*cent(?:er|re) of|of the center"),
    name_pattern("3", "name: school, college or department of a university",
                 r"(?:school|college|faculty|department|institute|division|program)\b.*\b(?:of|at)\b.*\buniversit"
                 r"|universit\w*.*\b(?:school|college|faculty|department) of\b",
                 r"university college|higher school|graduate university|deemed university"
                 r"|institute of technology university"),
    name_pattern("3", "name: branch of Islamic Azad or Payame Noor University", r"islamic azad|payame noor",
                 r"^(?:islamic azad|payame noor) university$"),
    # Spanish "escuelas técnicas superiores" are schools of a university
    name_pattern("3", "name: engineering school of a university (Spain)",
                 r"higher technical school of|school of .*engineering", r"universit|polytechnic", {"Spain"}),
    name_pattern("3", "name: department", r"^department of|\bdepartment$"),
    name_pattern("4", "name: research institute",
                 r"research institute|scientific-research|research cent(?:er|re)|academy of sciences"
                 r"|centro de investiga|centre de recherche|zentrum f(?:ü|u)r|forschung|research station"
                 r"|cercetare|instituto de investiga|institut de recherche",
                 r"universit|college|school|graduate|higher education|deemed|educational|hochschule"),
    name_pattern("4", "name: library, museum or clinic", r"\blibrary\b|biblioteca|\bmuseum\b|\bclinic\b",
                 r"universit|college|school"),
    name_pattern("4", "name: system of universities",
                 r"universit(?:y|ies) system|system of (?:higher|universit|state|public)|state system"
                 r"|college system|school system"),
    # keep colleges run by an "Education Society" (India) and "University of ... Association"
    name_pattern("4", "name: consortium, alliance, association, society",
                 r"consorti|alliance|association|society",
                 r"society's|education society|memorial society|and society|^university of"),
]


def name_rule(rule, name, country, has_parent=None):
    """Returns the reason of the first matching name rule with this rule number, or ""."""
    name = "" if pd.isna(name) else str(name)
    for number, reason, pattern, exception, countries in NAME_RULES:
        if number != rule:
            continue
        # a faculty without a parent is its own institution (e.g. in Slovenia)
        if reason == "name: faculty" and has_parent is False:
            continue
        if pattern.search(name) and not (exception and exception.search(name)) \
                and (countries is None or country in countries):
            return reason
    return ""


def clean_name(name):
    if pd.isna(name):
        return ""
    return " ".join(re.sub(r"[^\w ]", " ", str(name).lower()).split())


def domain(website):
    # "https://www.uni-mannheim.de/" gives "uni-mannheim.de"
    if pd.isna(website):
        return ""
    host = re.sub(r"^[a-z]+://", "", str(website).strip().lower()).split("/")[0]
    return host.split(":")[0].removeprefix("www.")


def duplicates(df, id_col, number):
    """Rule 5: returns the duplicate records, the value is the id of the record that is kept."""
    group = ["name", "country", "domain"]
    # the links to the other sources are the answer key of identity resolution, so they don't count
    links = [c for c in ("ror_id", "wikidata_id") if c in df and c != id_col]
    key = pd.DataFrame({
        "name": df["name"].apply(clean_name),
        "country": df["country"].fillna(""),
        "domain": df["website"].apply(domain),
        "filled": df.drop(columns=[id_col] + links).notna().sum(axis=1),
        "number": df[id_col].map(number),
        "id": df[id_col],
    })
    # without website or country a record is never a duplicate
    key = key[(key[group] != "").all(axis=1)]
    # the one with the most filled fields stays, on a tie the lower number
    key = key.sort_values(["filled", "number"], ascending=[False, True])
    kept = key.groupby(group)["id"].transform("first")
    return kept[key["id"] != kept]


def read_original(source, csv_name):
    # keep_default_na=False: "NA" is Namibia (country code) or an acronym, not a missing value
    return pd.read_csv(DATA / source / "original" / csv_name, dtype=str, keep_default_na=False, na_values=[""])


def finish(df, source, csv_name, xml_name, id_col, number, removed_columns):
    """Applies Rule 5 to the records left after Rules 1-4 and writes the outputs."""
    stays = df["rule"] == ""
    dup = duplicates(df[stays].drop(columns=["rule", "reason"]), id_col, number)
    df.loc[dup.index, "rule"] = "5"
    df.loc[dup.index, "reason"] = "duplicate of " + dup

    out = DATA / source / "filtered"
    removed = df[df["rule"] != ""]
    kept = df[df["rule"] == ""].drop(columns=["rule", "reason"])
    kept.to_csv(out / csv_name, index=False)
    removed = removed[removed_columns + ["rule", "reason"]].sort_values(["rule", "reason", "name"])
    removed.to_csv(out / "removed.csv", index=False)
    write_mapping_without(DATA / source / "original" / xml_name,
                          set(f"{source}_" + removed[id_col]), out / xml_name)

    print(f"records in: {len(df)}\nremoved:    {len(removed)}\nkept:       {len(kept)}")
    print("\nremoved per rule:\n" + removed["rule"].value_counts().sort_index().to_string())


def write_mapping_without(source_xml, gone, out):
    # the mapping turns one csv row into one <institution>, so we just drop the removed ones from the xml
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    tree = ET.parse(source_xml)
    root = tree.getroot()
    for inst in list(root):
        if inst.findtext("id") in gone:
            root.remove(inst)
    # binary mode so the line ends are "\n" on windows too
    with open(out, "wb") as f:
        tree.write(f, encoding="UTF-8", xml_declaration=True)
