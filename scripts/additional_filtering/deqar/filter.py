"""DEQAR: flag rows that are probably not a university of their own.  Usage: python filter.py
Writes hand_check.csv (see ../common.py). DEQAR lists every unit that has its own quality assurance
report: faculties and schools of a university (most in Spain and Croatia), institutes of academies of
sciences, campuses, the European university alliances themselves, and a few secondary schools.

"parent_institutions" is not a safe sign on its own: it also holds alliances (several countries),
French university groups (COMUE) and company groups. So a parent counts only together with a
"part" word in the name, for Spain (where the parent is always the university), or for an academy.
"High school" is NOT a rule here: in DEQAR it is a translation of a higher education word
(Polish "Wyzsza Szkola", Spanish "Escuela Superior").
"""
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import HE_WORDS, has, norm_text, read, write_hand_check

SCHOOL = r"lycee|lyceum|liceo|gymnasium|secondary"   # not "liceu": Conservatori del Liceu is a conservatory
TECHNIKUM = r"технікум|tekhnikum"   # Ukrainian professional pre-higher education
PART = (r"faculty|facultad|faculte|fakultat|facolta|faculdade|fakultet|wydzial|school of|escuela|escola|department|"
        r"departamento|institute|instituto|institut|campus|branch|centre|center|centro|college|laboratory|doctoral school")
UMBRELLA = r"comue|communaute|group|groupe|confederale|federale|bretagne loire|epe"   # French groups, company groups
# Not used after the AI check: a parent in France (27 of 37 flagged were independent grandes ecoles:
# INSA, Sciences Po, INALCO) and "campus" in the name (CAMPUS 02, Link Campus University, US main campuses).
NOT_ALLIANCE = r"university of london|epitech"   # institutions with members in several countries


def main():
    d = read("deqar")
    parents = d["parent_institutions"].map(lambda s: [p.strip() for p in s.split(" | ") if p.strip()])
    countries = defaultdict(set)
    for ps, c in zip(parents, d["country"]):
        for p in ps:
            countries[p].add(c)
    alliances = {p for p, c in countries.items() if len(c) >= 2}   # parents in several countries
    real = [[p for p in ps if p not in alliances and p != n] for ps, n in zip(parents, d["name"])]

    def why(name, alt, country, ps):
        uni_parent = [p for p in ps if has(p, HE_WORDS + "|universite|sveuciliste") and not has(p, UMBRELLA)]
        if has(f"{name} {alt}", TECHNIKUM):
            return "technikum (Ukraine)", "school"
        if has(f"{name} {alt}", SCHOOL):
            return "secondary school", "school"
        if name in alliances and not has(name, NOT_ALLIANCE):
            return "European university alliance", "alliance"
        if any(has(p, "academy of sciences") for p in ps):
            return "institute of an academy of sciences", "academy institute"
        if country == "Spain" and ps and not (has(name, HE_WORDS) and not has(name, PART)):   # "CUNEF Universidad"
            return "part of a Spanish university", "Spanish faculty or school"
        if uni_parent and has(name, PART) and country != "France":
            starts = norm_text(name).split(" ")[0] in {"faculty", "fakultet", "wydzial", "faculte", "department", "school"}
            return "part of a university", "faculty of a named university" if starts else "risky"
        if has(name, "branch|consortium") and not has(name, "medical branch|inter branch"):
            return "branch / consortium", "risky"
        return None, None

    hits = [why(n, a, c, ps) for n, a, c, ps in zip(d["name"], d["alt_names"], d["country"], real)]
    d["why_flagged"], d["group"] = [h[0] for h in hits], [h[1] for h in hits]
    f = d[d["why_flagged"].notna()]
    write_hand_check(HERE, pd.DataFrame({
        "id": "deqar_" + f["deqar_id"], "name": f["name"], "alt_names": f["alt_names"], "country": f["country"],
        "city": f["city"], "part_of": f["parent_institutions"], "why_flagged": f["why_flagged"], "group": f["group"]}))


if __name__ == "__main__":
    main()
