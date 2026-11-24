"""ROR: apply Rules 1-5 from rules.md and write the result to data/ror/filtered/.

Usage: python filter.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import finish, name_rule, read_original  # noqa: E402

NOT_EDUCATION_TYPES = {"healthcare", "facility", "government"}
HIGHER_WORD = re.compile(r"universit|college|school|academy|institute of technology|polytechn|hochschule",
                         re.IGNORECASE)


def decide(name, country, types, has_parent):
    """Returns (rule, reason) of the first rule that removes the record, or ("", "")."""
    reason = name_rule("1", name, country)
    if reason:
        return "1", reason
    reason = name_rule("3", name, country, has_parent)
    if reason:
        return "3", reason
    # ROR has no finer types, but a second type like healthcare says it's not mainly education
    other = {t.strip() for t in str(types).split("|")} & NOT_EDUCATION_TYPES
    if other and not HIGHER_WORD.search(str(name)):
        return "4", f"ROR type: {sorted(other)[0]}"
    reason = name_rule("4", name, country)
    if reason:
        return "4", reason
    return "", ""


def main():
    df = read_original("ror", "ror_education.csv")
    rules = []
    reasons = []
    for name, country, types, parent in zip(df["name"], df["country"], df["types"], df["parent_ror_id"]):
        rule, reason = decide(name, country, types, pd.notna(parent))
        rules.append(rule)
        reasons.append(reason)
    df["rule"] = rules
    df["reason"] = reasons
    finish(df, "ror", "ror_education.csv", "ror_id", lambda x: x,
           ["ror_id", "name", "country", "types", "parent_ror_id"])


if __name__ == "__main__":
    main()
