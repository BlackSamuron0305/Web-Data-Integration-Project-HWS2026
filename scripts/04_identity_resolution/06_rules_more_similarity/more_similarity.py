"""More name similarity measures: rules with the token-based, hybrid and phonetic measures from the course that
the other folders do not use yet, threshold picked on validation like the other rules.
- Monge-Elkan: every word of one name is paired with its most similar word of the other name (Jaro-Winkler) and
  the scores are averaged, in both directions. Word order and extra words matter less than in plain Jaro-Winkler.
- Phonetic: the words are turned into Soundex codes (how they sound in English) and the code sets compared
  (Jaccard), so small spelling differences like "Tecnico" and "Technico" count as the same word.
- Sorensen-Dice on letter pairs (bigrams): share of letter pairs the two names have in common.
- Longest common substring: length of the longest piece of text both names contain, divided by the longer name.
- Overlap coefficient: shared words divided by the number of words of the SHORTER name, so "Pacific University"
  and "Pacific University Oregon" score 1 (extra words in the longer name do not count against it).
- Extended Jaccard: like Jaccard on words, but two words count as shared if they are spelled almost the same
  (Jaro-Winkler at least 0.9, e.g. "Institute" and "Instituto"): shared pairs / (shared pairs + words of
  either name without a similar partner).
All scores are between 0 and 1. All but the longest common substring are also tried as the best match over
all names of the records.
Usage: python more_similarity.py first_pass | final"""
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PyDI.entitymatching import RuleBasedMatcher
from PyDI.entitymatching.base import BaseComparator
from rapidfuzz.distance import JaroWinkler
from rapidfuzz.process import cdist

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (PAIRS, THRESHOLDS, Timer, candidates, comparators, labels, load_all,
                    run_argument, run_folder, run_matchers)

RESULTS = Path(__file__).resolve().parent / "results"


# --- the measures, each on two lists of names (one name = list with one entry) ---------------------------------

# Monge-Elkan and extended Jaccard both start from a table m with the Jaro-Winkler similarity of every word of
# one name (rows) with every word of the other name (columns)

def monge_elkan_table(m):
    # every word is paired with its most similar word of the other name; the average, in both directions
    return float((m.max(axis=1).mean() + m.max(axis=0).mean()) / 2)


EXTENDED_THRESHOLD = 0.9   # words with a Jaro-Winkler similarity of at least this count as shared


def extended_jaccard_table(m):
    close = m >= EXTENDED_THRESHOLD
    shared = int(close.sum())                      # pairs of similar words
    unique1 = int((~close.any(axis=1)).sum())      # words of the first name without a similar word
    unique2 = int((~close.any(axis=0)).sum())      # words of the second name without a similar word
    return shared / (shared + unique1 + unique2)


def on_words(table_score):
    # the measure for two word lists
    def score(words1, words2):
        if not words1 or not words2:
            return 0.0
        return table_score(cdist(words1, words2, scorer=JaroWinkler.normalized_similarity))
    return score


def best_over_names(table_score):
    # one Jaro-Winkler table over all words of the two records, then the measure for every pair of names
    def score(names1, names2):
        split1, split2 = [n.split() for n in names1], [n.split() for n in names2]
        vocab1 = sorted({w for ws in split1 for w in ws})
        vocab2 = sorted({w for ws in split2 for w in ws})
        if not vocab1 or not vocab2:
            return 0.0
        m = cdist(vocab1, vocab2, scorer=JaroWinkler.normalized_similarity)
        pos1, pos2 = {w: i for i, w in enumerate(vocab1)}, {w: i for i, w in enumerate(vocab2)}
        best = 0.0
        for ws1 in split1:
            if not ws1:
                continue
            rows = m[[pos1[w] for w in ws1]]
            for ws2 in split2:
                if not ws2:
                    continue
                best = max(best, table_score(rows[:, [pos2[w] for w in ws2]]))
        return best
    return score


SOUNDEX = {c: str(d) for d, letters in enumerate(["aeiouyhw", "bfpv", "cgjkqsxz", "dt", "l", "mn", "r"])
           for c in letters}


def soundex(word):
    # American Soundex: first letter + 3 digits; a word without letters (like "8") is kept as it is
    letters = [c for c in word if c in SOUNDEX]
    if not letters:
        return word
    code, last = letters[0].upper(), SOUNDEX[letters[0]]
    for c in letters[1:]:
        digit = SOUNDEX[c]
        if digit != "0" and digit != last:
            code += digit
        if c not in "hw":   # h and w do not separate two equal codes
            last = digit
    return (code + "000")[:4]


def jaccard(s1, s2):
    return len(s1 & s2) / len(s1 | s2) if s1 and s2 else 0.0


def bigrams(name):
    name = " ".join(name.split())
    return {name[i:i + 2] for i in range(len(name) - 1)} if len(name) > 1 else {name} - {""}


def dice(s1, s2):
    return 2 * len(s1 & s2) / (len(s1) + len(s2)) if s1 and s2 else 0.0


def overlap(s1, s2):
    # shared words divided by the number of words of the shorter name
    return len(s1 & s2) / min(len(s1), len(s2)) if s1 and s2 else 0.0


def lcs(name1, name2):
    if not name1 or not name2:
        return 0.0
    m = SequenceMatcher(None, name1, name2, autojunk=False).find_longest_match(0, len(name1), 0, len(name2))
    return m.size / max(len(name1), len(name2))


def prepare(df):
    # precomputed word lists, Soundex code sets and bigram sets so the comparators only compare
    df["words"] = df["name_norm"].map(str.split)
    df["soundex"] = df["words"].map(lambda ws: {soundex(w) for w in ws})
    df["names_soundex"] = df["names"].map(lambda ns: [{soundex(w) for w in n.split()} for n in ns])
    df["bigrams"] = df["name_norm"].map(bigrams)
    df["names_bigrams"] = df["names"].map(lambda ns: [bigrams(n) for n in ns])
    df["word_set"] = df["words"].map(set)
    df["names_word_sets"] = df["names"].map(lambda ns: [set(n.split()) for n in ns])


def best_of(measure):
    # best score over all pairs of names
    def score(l1, l2):
        return max((measure(x, y) for x in l1 for y in l2), default=0.0)
    return score


class Measure(BaseComparator):
    # compares one precomputed column; with keep=True the scores are kept (by record ids) so the combined rules
    # do not compute them again
    def __init__(self, name, column, measure, keep=False):
        super().__init__(name)
        self.column, self.measure, self.memo = column, measure, {} if keep else None

    def compare(self, r1, r2):
        if self.memo is None:
            return self.score(r1, r2)
        k = (r1.name, r2.name)   # PyDI passes the records indexed by id
        if k not in self.memo:
            self.memo[k] = self.score(r1, r2)
        return self.memo[k]

    def score(self, r1, r2):
        return min(1.0, max(0.0, float(self.measure(r1[self.column], r2[self.column]))))


def more_comparators():
    comps = comparators()
    comps.update({
        "name_monge_elkan": Measure("name_monge_elkan", "words", on_words(monge_elkan_table)),
        "names_best_monge_elkan": Measure("names_best_monge_elkan", "names", best_over_names(monge_elkan_table),
                                          keep=True),
        "name_soundex": Measure("name_soundex", "soundex", jaccard),
        "names_best_soundex": Measure("names_best_soundex", "names_soundex", best_of(jaccard), keep=True),
        "name_dice": Measure("name_dice", "bigrams", dice),
        "names_best_dice": Measure("names_best_dice", "names_bigrams", best_of(dice)),
        "name_lcs": Measure("name_lcs", "name_norm", lcs),
        "name_overlap": Measure("name_overlap", "word_set", overlap),
        "names_best_overlap": Measure("names_best_overlap", "names_word_sets", best_of(overlap), keep=True),
        "name_extended_jaccard": Measure("name_extended_jaccard", "words", on_words(extended_jaccard_table)),
        "names_best_extended_jaccard": Measure("names_best_extended_jaccard", "names",
                                               best_over_names(extended_jaccard_table), keep=True),
    })
    return comps


RULES = {
    "name Monge-Elkan (Jaro-Winkler on words)": (["name_monge_elkan"], [1]),
    "name phonetic (Soundex, Jaccard)": (["name_soundex"], [1]),
    "name Sorensen-Dice (letter pairs)": (["name_dice"], [1]),
    "name longest common substring": (["name_lcs"], [1]),
    "best of all names, Monge-Elkan": (["names_best_monge_elkan"], [1]),
    "best of all names, phonetic": (["names_best_soundex"], [1]),
    "best of all names, Sorensen-Dice": (["names_best_dice"], [1]),
    "rule: Monge-Elkan 0.5 + country 0.2 + domain 0.3": (["names_best_monge_elkan", "country", "domain"],
                                                         [0.5, 0.2, 0.3]),
    "rule: phonetic 0.5 + country 0.2 + domain 0.3": (["names_best_soundex", "country", "domain"],
                                                      [0.5, 0.2, 0.3]),
    "name overlap coefficient (words)": (["name_overlap"], [1]),
    "name extended Jaccard (similar words count)": (["name_extended_jaccard"], [1]),
    "best of all names, overlap coefficient": (["names_best_overlap"], [1]),
    "best of all names, extended Jaccard": (["names_best_extended_jaccard"], [1]),
    "rule: overlap 0.5 + country 0.2 + domain 0.3": (["names_best_overlap", "country", "domain"], [0.5, 0.2, 0.3]),
    "rule: extended Jaccard 0.5 + country 0.2 + domain 0.3": (["names_best_extended_jaccard", "country", "domain"],
                                                              [0.5, 0.2, 0.3]),
}


def main(run):
    out = run_folder(RESULTS, run)
    data = load_all(run)
    for df in data.values():
        prepare(df)

    for a, b in PAIRS:
        comps = more_comparators()   # fresh results memory per pair
        L, R, cand = data[a], data[b], candidates(a, b, run)

        def match(rule):
            cols, weights = rule
            with Timer() as t:
                corr = RuleBasedMatcher().match(L, R, cand, "id", [comps[c] for c in cols],
                                                weights=weights, threshold=THRESHOLDS[0])
            return corr, t.seconds

        run_matchers(out, run, a, b, RULES, match, labels(a, b, "validation", run))


if __name__ == "__main__":
    main(run_argument())
