"""Rule-based matching: weighted sum of similarity scores, threshold picked on validation.
Usage: python rule_based.py <round>"""
import sys
from pathlib import Path

from PyDI.entitymatching import RuleBasedMatcher

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import THRESHOLDS, PAIRS, Timer, candidates, comparators, labels, load_all, reset_log, run_matchers

RESULTS = Path(__file__).resolve().parent / "results"
NAMES = "names_best_jaro_winkler"   # best match over all names of the two records

# round: {rule name: (comparators, weights)}
RULES = {
    1: {
        "name Levenshtein 0.5 + year 0.5": (["name_levenshtein", "year"], [0.5, 0.5]),
        "name Levenshtein 0.7 + year 0.3": (["name_levenshtein", "year"], [0.7, 0.3]),
        "name Levenshtein only": (["name_levenshtein"], [1]),
    },
    2: {
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
    },
}
# rounds 3 and 8 keep the two best rules of round 2
RULES[3] = RULES[8] = {k: RULES[2][k] for k in ["best of all names, Jaro-Winkler",
                                                "rule: all attributes (+ year, position)"]}


def main(round_):
    RESULTS.mkdir(exist_ok=True)
    reset_log(RESULTS / "matching.csv", round_)
    data = load_all(round_)
    comps = comparators()

    for a, b in PAIRS:
        L, R, cand = data[a], data[b], candidates(a, b, round_)

        def run(rule):
            cols, weights = rule
            with Timer() as t:
                corr = RuleBasedMatcher().match(L, R, cand, "id", [comps[c] for c in cols],
                                                weights=weights, threshold=THRESHOLDS[0])
            return corr, t.seconds

        run_matchers(RESULTS, round_, a, b, RULES[round_], run, labels(a, b, "validation", round_))


if __name__ == "__main__":
    main(int(sys.argv[1]))
