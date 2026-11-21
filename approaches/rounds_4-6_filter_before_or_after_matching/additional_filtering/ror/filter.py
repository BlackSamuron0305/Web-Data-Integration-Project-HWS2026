"""ROR: flags rows that are probably not a university of their own (schools, school districts,
campuses, faculties, research units, museums) and writes hand_check.csv. Run with: python filter.py"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import HE_WORDS, has, norm_text, read, write_hand_check

SCHOOL = (r"high school|senior high|junior high|secondary school|secondary college|primary school|elementary school|"
          r"middle school|grammar school|lycee|kantonsschule|gymnasium|koto gakko")
# (reason, words, condition), the first rule that fits wins
RULES = [
    ("school, not higher education", SCHOOL, "always"),
    ("department", r"department of|departamento de|dipartimento di|departement", "always"),
    ("school district", r"school district|public schools|agrupamento de escolas|college district", "always"),
    # not "lab" (LAB University in Finland), and not with a university word ("Federal College of Medical Laboratory Science")
    ("laboratory", r"laboratory|laboratories|laboratoire|laboratorio", "no university word"),
    ("school, not higher education", r"kindergarten", "no university word"),   # "Kindergarten Teachers College"
    ("museum", r"museum|museu|musee|museo", "name does not start with a university word"),
    # these words are also in names of standalone institutions, so only if ROR has a parent
    ("campus", r"campus", "parent"),
    ("branch", r"branch|satellite|extension centre|extension center|learning centre|learning center|study centre|"
               r"study center|regional centre|regional center|islamic azad university", "parent"),
    ("faculty", r"faculty of|faculte de|faculte des|fakultat|facolta|facultad de|faculdade de", "parent"),
    ("research unit", r"research centre|research center|research institute|research unit|centre for|center for|"
                      r"centro de estudos|centro de investigacao|centro de investigacion|forschungs",
     "parent, no 'college'"),   # "Dental College and Research Institute"
]


def why(name, parent):
    if has(name, "main campus"):   # "X University-Main Campus" is the university itself
        return None
    first = norm_text(name).split(" ")[0]
    ok = {"always": True,
          "no university word": not has(name, HE_WORDS),
          "name does not start with a university word": not has(first, HE_WORDS + "|school|escuela|ecole|scuola|instituto|institute"),
          "parent": bool(parent),
          "parent, no 'college'": bool(parent) and not has(name, "college")}
    for reason, words, cond in RULES:
        if has(name, words) and ok[cond]:
            return reason
    return None


def group(name, parent, reason):
    """Safe groups are the ones where a rule word cannot mean something else, the rest is risky."""
    p = norm_text(parent)
    if reason == "school, not higher education" and not has(name, HE_WORDS) and not norm_text(name).startswith("high school of"):
        return "school"   # "High School of Music of Sakha" is a Higher School
    if reason == "school district" and not has(name, "college district"):
        return "school district"
    if has(name, "islamic azad university"):
        return "Islamic Azad branch"
    if has(parent, HE_WORDS + "|universite|institute of technology") and not has(parent, "system|systems") \
            and not has(name, HE_WORDS):
        return "part of a named university"   # "Laboratoire de Mathematiques d'Avignon"
    if len(p) > 3 and p in norm_text(name) and "system" not in p:
        return "named after its parent"   # "Capiz State University-Burias Campus"
    return "risky"


def main():
    r = read("ror")
    names = dict(zip(r["ror_id"], r["name"]))
    r["part_of"] = r["parent_ror_id"].map(lambda p: " | ".join(names.get(x, "") for x in p.split(" | ")).strip(" |"))
    r["why_flagged"] = [why(n, p) for n, p in zip(r["name"], r["parent_ror_id"])]
    f = r[r["why_flagged"].notna()].copy()
    f["group"] = [group(n, p, w) for n, p, w in zip(f["name"], f["part_of"], f["why_flagged"])]
    write_hand_check(HERE, pd.DataFrame({
        "id": "ror_" + f["ror_id"], "name": f["name"], "alt_names": f["alt_names"], "country": f["country_code"],
        "city": f["city"], "part_of": f["part_of"], "why_flagged": f["why_flagged"], "group": f["group"]}))


if __name__ == "__main__":
    main()
