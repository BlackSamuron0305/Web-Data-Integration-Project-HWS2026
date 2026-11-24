"""DEQAR: apply Rules 1-5 from rules.md and write the result to data/deqar/filtered/.

Usage: python filter.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import finish, name_rule, read_original  # noqa: E402

UNIVERSITY = re.compile(r"universit", re.IGNORECASE)
ALLIANCE = re.compile(r"alliance|european universit|network|league|consortium|eutopia|una europa|circle u",
                      re.IGNORECASE)
PART_WORD = re.compile(r"school|college|institut|faculty|department|cent(?:er|re)|escuela|escola", re.IGNORECASE)


def part_of_university(name, country, parent):
    """True if the parent is a university (not an alliance) and the record is a school, institute etc. of it."""
    # in France the parent is usually a group of universities (ComUE), not the owner
    if pd.isna(parent) or country == "France" or UNIVERSITY.search(str(name)):
        return False
    university_parent = False
    for p in str(parent).split("|"):
        if UNIVERSITY.search(p) and not ALLIANCE.search(p):
            university_parent = True
    return university_parent and PART_WORD.search(str(name)) is not None


def decide(name, country, parent):
    """Returns (rule, reason) of the first rule that removes the record, or ("", "")."""
    # rule 2 always holds, DEQAR only lists reviewed institutions
    reason = name_rule("1", name, country)
    if reason:
        return "1", reason
    reason = name_rule("3", name, country, pd.notna(parent))
    if reason:
        return "3", reason
    if part_of_university(name, country, parent):
        return "3", "parent institution is a university"
    reason = name_rule("4", name, country)
    if reason:
        return "4", reason
    return "", ""


def main():
    df = read_original("deqar", "deqar_institutions.csv")
    rules = []
    reasons = []
    for name, country, parent in zip(df["name"], df["country"], df["parent_institutions"]):
        rule, reason = decide(name, country, parent)
        rules.append(rule)
        reasons.append(reason)
    df["rule"] = rules
    df["reason"] = reasons
    finish(df, "deqar", "deqar_institutions.csv", "deqar_id",
           lambda x: int(x.removeprefix("DEQARINST")), ["deqar_id", "name", "country", "parent_institutions"])


if __name__ == "__main__":
    main()
