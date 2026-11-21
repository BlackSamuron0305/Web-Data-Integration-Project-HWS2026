"""Wikidata: flags rows that are probably not a university of their own (campuses, faculties, schools,
companies, buildings), mostly by their Wikidata types, and writes hand_check.csv. Run with: python filter.py"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import HE_WORDS, has, read, write_hand_check

# types that make a record part of something else. Many universities also have the type "campus" or
# "faculty" (Heidelberg University), so these only count without a university type or if the name says it too
PART_TYPES = (r"campus|satellite campus|branch campus|university campus|branch|university branch|branch office|faculty|"
              r"faculty of commerce|academic department|residential college|school annex|organizational subdivision")
SCHOOL_TYPES = (r"high school|secondary school|primary school|public school|private school|boarding school|girls' school|"
                r"university-preparatory school|all-through school|sports school|christian school|catholic school|"
                r"jesuit school|military lyceum|military high school")
OTHER_TYPES = (r"public company|production company|media company|education company|video game publisher|government agency|"
               r"swedish government agency|military unit|military base|census-designated place in the united states|"
               r"unincorporated community|historic district|association football team|wikimedia disambiguation page|"
               r"edited volume|version, edition or translation|monastery|consortium|university system|state university system|"
               r"foundation|archives|building|school building|university building|historic building|public building|"
               r"building complex|hospital|museum|military museum|library|academic library|research institute|research center|"
               r"laboratory")
NAME_PART = r"campus|branch|faculty of|faculte de|facultad de|faculdade de|fakultat|facolta di"
# "campus" as part of the university's own name
OWN_NAME = r"campus university|global campus|online campus|world campus|medical branch"


def is_university_type(t):
    return (re.search(r"universit|college|academy|polytechn|higher education|institute of technology|seminary|"
                      r"conservator|hochschule|grande école|grand établissement|school of|medical school|"
                      r"engineering school|business school|law school", t)
            and not re.search(r"campus|building|system|branch|preparatory|constituent|residential", t))


def why(name, types):
    if has(name, "main campus|" + OWN_NAME) or name.lower().startswith("campus"):   # "Campus Bio-Medico University"
        return None
    university = any(is_university_type(t) for t in types)
    part = [t for t in types if re.fullmatch(PART_TYPES, t)]
    school = [t for t in types if re.fullmatch(SCHOOL_TYPES, t)]
    other = [t for t in types if re.fullmatch(OTHER_TYPES, t)]
    if part and (not university or has(name, NAME_PART)):
        return "type: " + part[0]
    if school and not university:
        return "type: " + school[0]
    if other and not university:
        return "type: " + other[0]
    if has(name, NAME_PART) and has(name, HE_WORDS):
        return "name: part of a university"   # "Faculty of Engineering - Kharazmi University"
    return None


def group(name, country, reason):
    """Safe groups are the ones where a mistake is not possible, the rest is risky."""
    if has(name, "islamic azad university"):
        return "Islamic Azad branch"
    if reason.startswith("type: ") and reason[6:] in SCHOOL_TYPES.split("|") and not has(name, HE_WORDS):
        return "school"
    if reason in ("type: campus", "type: satellite campus", "type: faculty", "type: branch"):
        return "campus or faculty by type"
    if reason == "name: part of a university" and re.match(r"(faculty|faculte|facultad|faculdade|fakultat|facolta) ", name.lower()):
        return "faculty of a named university"   # "Faculty of Civil Engineering, University of Osijek"
    # not in the US, there campuses of a system can be accredited on their own (University of Puerto Rico)
    if reason == "name: part of a university" and not has(country, "us|pr") and has(name, "campus|branch") \
            and re.search(rf"\b({HE_WORDS})\b.*\b(campus|branch)\b", name.lower()):
        return "campus or branch of a named university"
    return "risky"


def main():
    w = read("wikidata")
    types = w["types"].map(lambda s: [t.strip().lower() for t in s.split("|") if t.strip()])
    w["why_flagged"] = [why(n, t) for n, t in zip(w["name"], types)]
    f = w[w["why_flagged"].notna()].copy()
    f["group"] = [group(n, c, r) for n, c, r in zip(f["name"], f["country_code"], f["why_flagged"])]
    write_hand_check(HERE, pd.DataFrame({
        "id": "wikidata_" + f["wikidata_id"], "name": f["name"], "alt_names": f["alt_names"],
        "country": f["country_code"], "city": f["city"], "part_of": f["types"],   # Wikidata has no parent, so show the types
        "why_flagged": f["why_flagged"], "group": f["group"]}))


if __name__ == "__main__":
    main()
