"""Rule-based matching: weighted sum of string and attribute similarities, threshold picked on validation.
Usage: python rule_based.py first_pass | final"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import run_argument, run_rules

RESULTS = Path(__file__).resolve().parent / "results"
NAMES = "names_best_jaro_winkler"   # best match over all names of the two records

# {rule name: (comparators, weights)}
RULES = {
    "name Levenshtein": (["name_levenshtein"], [1]),
    "name Jaro-Winkler": (["name_jaro_winkler"], [1]),
    "name Jaccard (words)": (["name_jaccard"], [1]),
    "best of all names, Jaro-Winkler": ([NAMES], [1]),
    "best of all names, Jaccard": (["names_best_jaccard"], [1]),
    "rule: names 0.8 + country 0.2": ([NAMES, "country"], [0.8, 0.2]),
    "rule: names 0.5 + country 0.2 + domain 0.3": ([NAMES, "country", "domain"], [0.5, 0.2, 0.3]),
    "rule: names 0.6 + country 0.1 + domain 0.3": ([NAMES, "country", "domain"], [0.6, 0.1, 0.3]),
    "rule: names + country + domain + city": ([NAMES, "country", "domain", "city"], [0.45, 0.15, 0.3, 0.1]),
    "rule: all attributes (+ year, position)": ([NAMES, "country", "domain", "city", "year", "geo"],
                                                [0.35, 0.15, 0.25, 0.1, 0.1, 0.05]),
}


if __name__ == "__main__":
    run_rules(RESULTS, run_argument(), RULES)
