"""Wikidata: flag rows that are probably not a university of their own.  Usage: python filter.py
Writes hand_check.csv (see ../common.py). The Wikidata query keeps everything that is an instance of
some kind of university; that also catches campuses, faculties, military units, secondary schools,
buildings and companies. Most rules use the Wikidata types ("instance of"), which can be several.
"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import HE_WORDS, has, read, write_hand_check

# a type that makes the record a part of something else. Many universities also carry the type
# "campus" or "faculty" (Heidelberg University, University of Tehran), so a part type only counts if
# the record has no university type or its name says it too. Not used (the AI check found many
# independent institutions): theological faculty types (pontifical faculties) and "constituent
# college" (King's College London, Birkbeck).
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
# "campus" as part of the university's own name, not a part of it
OWN_NAME = r"campus university|global campus|online campus|world campus|medical branch"


def is_university_type(t):
    """A type that says: an institution of higher education of its own."""
    return (re.search(r"universit|college|academy|polytechn|higher education|institute of technology|seminary|"
                      r"conservator|hochschule|grande école|grand établissement|school of|medical school|"
                      r"engineering school|business school|law school", t)
            and not re.search(r"campus|building|system|branch|preparatory|constituent|residential", t))


def why(name, types):
    if has(name, "main campus|" + OWN_NAME) or name.lower().startswith("campus"):   # "Campus Bio-Medico University"
        return None
    full = lambda pattern: [t for t in types if re.fullmatch(pattern, t)]
    university = any(is_university_type(t) for t in types)
    if full(PART_TYPES) and (not university or has(name, NAME_PART)):
        return "type: " + full(PART_TYPES)[0]
    if full(SCHOOL_TYPES) and not university:
        return "type: " + full(SCHOOL_TYPES)[0]
    if full(OTHER_TYPES) and not university:
        return "type: " + full(OTHER_TYPES)[0]
    if has(name, NAME_PART) and has(name, HE_WORDS):
        return "name: part of a university"   # "Faculty of Engineering - Kharazmi University"
    return None


def group(name, country, reason):
    """Safe groups: a mistake is not possible there. All other rows are risky."""
    if has(name, "islamic azad university"):
        return "Islamic Azad branch"
    if reason.startswith("type: ") and reason[6:] in SCHOOL_TYPES.split("|") and not has(name, HE_WORDS):
        return "school"
    if reason in ("type: campus", "type: satellite campus", "type: faculty", "type: branch"):
        return "campus or faculty by type"   # the type says it, and the name too or there is no university type
    if reason == "name: part of a university" and re.match(r"(faculty|faculte|facultad|faculdade|fakultat|facolta) ", name.lower()):
        return "faculty of a named university"   # "Faculty of Civil Engineering, University of Osijek"
    # "Shandong University of Science and Technology Taian Campus"; not in the US, where campuses of a
    # system can be separately accredited (University of Puerto Rico, Medical Sciences Campus)
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
        "country": f["country_code"], "city": f["city"], "part_of": f["types"],   # no parent in Wikidata: show the types
        "why_flagged": f["why_flagged"], "group": f["group"]}))


if __name__ == "__main__":
    main()
