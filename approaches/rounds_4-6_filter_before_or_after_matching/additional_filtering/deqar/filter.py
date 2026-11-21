"""DEQAR: flags rows that are probably not a university of their own (faculties, academy institutes,
alliances, schools) and writes hand_check.csv. Run with: python filter.py"""
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import HE_WORDS, has, norm_text, read, write_hand_check

SCHOOL = r"lycee|lyceum|liceo|gymnasium|secondary"   # not "liceu", Conservatori del Liceu is a conservatory
TECHNIKUM = r"технікум|tekhnikum"   # Ukrainian schools below higher education
PART = (r"faculty|facultad|faculte|fakultat|facolta|faculdade|fakultet|wydzial|school of|escuela|escola|department|"
        r"departamento|institute|instituto|institut|campus|branch|centre|center|centro|college|laboratory|doctoral school")
# French university groups (COMUE) and company groups, a parent like that does not make a row a part
UMBRELLA = r"comue|communaute|group|groupe|confederale|federale|bretagne loire|epe"
NOT_ALLIANCE = r"university of london|epitech"   # have members in several countries but are no alliance
# "high school" is not a rule: in DEQAR it is a translation of Polish "Wyzsza Szkola" or Spanish "Escuela Superior"


def why(name, alt, country, parents, alliances):
    uni_parent = [p for p in parents if has(p, HE_WORDS + "|universite|sveuciliste") and not has(p, UMBRELLA)]
    if has(f"{name} {alt}", TECHNIKUM):
        return "technikum (Ukraine)", "school"
    if has(f"{name} {alt}", SCHOOL):
        return "secondary school", "school"
    if name in alliances and not has(name, NOT_ALLIANCE):
        return "European university alliance", "alliance"
    if any(has(p, "academy of sciences") for p in parents):
        return "institute of an academy of sciences", "academy institute"
    # in Spain the parent is always the university, except for names like "CUNEF Universidad"
    if country == "Spain" and parents and not (has(name, HE_WORDS) and not has(name, PART)):
        return "part of a Spanish university", "Spanish faculty or school"
    # not France: most rows with a parent there were grandes ecoles of their own (INSA, Sciences Po)
    if uni_parent and has(name, PART) and country != "France":
        starts = norm_text(name).split(" ")[0] in {"faculty", "fakultet", "wydzial", "faculte", "department", "school"}
        return "part of a university", "faculty of a named university" if starts else "risky"
    if has(name, "branch|consortium") and not has(name, "medical branch|inter branch"):
        return "branch / consortium", "risky"
    return None, None


def main():
    d = read("deqar")
    parents = d["parent_institutions"].map(lambda s: [p.strip() for p in s.split(" | ") if p.strip()])
    # a parent with members in several countries is an alliance, not a university
    countries = defaultdict(set)
    for ps, c in zip(parents, d["country"]):
        for p in ps:
            countries[p].add(c)
    alliances = {p for p, c in countries.items() if len(c) >= 2}

    hits = []
    for n, a, c, ps in zip(d["name"], d["alt_names"], d["country"], parents):
        real = [p for p in ps if p not in alliances and p != n]
        hits.append(why(n, a, c, real, alliances))
    d["why_flagged"], d["group"] = [h[0] for h in hits], [h[1] for h in hits]
    f = d[d["why_flagged"].notna()]
    write_hand_check(HERE, pd.DataFrame({
        "id": "deqar_" + f["deqar_id"], "name": f["name"], "alt_names": f["alt_names"], "country": f["country"],
        "city": f["city"], "part_of": f["parent_institutions"], "why_flagged": f["why_flagged"], "group": f["group"]}))


if __name__ == "__main__":
    main()
