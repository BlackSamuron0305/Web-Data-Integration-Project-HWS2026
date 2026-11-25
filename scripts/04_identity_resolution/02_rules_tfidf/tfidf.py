"""TF-IDF matching: compares the names by their TF-IDF vectors, alone and with country and domain.

TF-IDF gives every word of a name a weight: rare words (a city, a founder) get a high weight, words that
almost every name has ("university", "of") a low one. Two names are similar if they share heavy words
(cosine similarity of the two weight vectors). We try three versions:
- words: the words of the name and pairs of neighbouring words
- letter groups: pieces of 3 to 5 letters, so small spelling differences still share most pieces
- Soft TF-IDF: like words, but two words also count as shared if they are spelled almost the same
  (Jaro-Winkler at least 0.9, e.g. "Institute" and "Instituto"); the shared weight is then lowered by
  that similarity. Computed in both directions and averaged.
The weights are learned from the names of all three sources. The threshold is picked on validation.
05_machine_learning and 07_more_learners use the TF-IDF scores as features too (add_tfidf, tfidf_comparators).
Usage: python tfidf.py first_pass | final"""
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from rapidfuzz.distance import JaroWinkler
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import Own, run_argument, run_rules

RESULTS = Path(__file__).resolve().parent / "results"

# how a name is cut into terms (column name: settings of the TF-IDF vectorizer)
SETTINGS = {
    "tfidf_words": dict(analyzer="word", ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b"),
    "tfidf_chars": dict(analyzer="char_wb", ngram_range=(3, 5)),
    "tfidf_soft": dict(analyzer="word", ngram_range=(1, 1), token_pattern=r"(?u)\b\w+\b"),
}
SOFT_THRESHOLD = 0.9   # two words with a Jaro-Winkler similarity of at least this count as the same word


def add_tfidf(data):
    # learns the word weights from the names of all three sources and gives every record its vector,
    # stored as {term: weight} (only the terms the name has)
    for column, settings in SETTINGS.items():
        vectorizer = TfidfVectorizer(**settings, sublinear_tf=True, dtype=np.float32)
        vectorizer.fit([n for df in data.values() for n in df["name_norm"].fillna("")])
        terms = vectorizer.get_feature_names_out()
        for df in data.values():
            m = vectorizer.transform(df["name_norm"].fillna("")).tocsr()
            if column == "tfidf_soft":   # Soft TF-IDF compares the words themselves, so keep them as text
                df[column] = [dict(zip(terms[m.indices[s:e]].tolist(), m.data[s:e].tolist()))
                              for s, e in zip(m.indptr[:-1], m.indptr[1:])]
            else:
                df[column] = [dict(zip(m.indices[s:e].tolist(), m.data[s:e].tolist()))
                              for s, e in zip(m.indptr[:-1], m.indptr[1:])]


def cosine(column):
    # cosine similarity of two weight vectors (they already have length 1, so it is the sum of products)
    def score(r1, r2):
        x, y = r1[column], r2[column]
        if len(x) > len(y):
            x, y = y, x
        return min(1.0, sum(w * y.get(term, 0.0) for term, w in x.items()))
    return score


@lru_cache(maxsize=1_000_000)
def word_similarity(w1, w2):
    return JaroWinkler.normalized_similarity(w1, w2)


def soft_one_way(x, y):
    # every word of x is paired with its most similar word of y; pairs at or above SOFT_THRESHOLD add
    # weight in x * weight in y * how similar the two words are
    total = 0.0
    for word, weight in x.items():
        if word in y:
            total += weight * y[word]
            continue
        best, partner = 0.0, None
        for other in y:
            s = word_similarity(word, other)
            if s > best:
                best, partner = s, other
        if best >= SOFT_THRESHOLD:
            total += weight * y[partner] * best
    return total


def soft_tfidf(r1, r2):
    x, y = r1["tfidf_soft"], r2["tfidf_soft"]
    if not x or not y:
        return 0.0
    return min(1.0, (soft_one_way(x, y) + soft_one_way(y, x)) / 2)


def tfidf_comparators():
    return {
        "name_tfidf_words": Own("name_tfidf_words", cosine("tfidf_words")),
        "name_tfidf_chars": Own("name_tfidf_chars", cosine("tfidf_chars")),
        "name_soft_tfidf": Own("name_soft_tfidf", soft_tfidf),
    }


# {rule name: (comparators, weights)}
RULES = {
    "name TF-IDF (words)": (["name_tfidf_words"], [1]),
    "name TF-IDF (letter groups)": (["name_tfidf_chars"], [1]),
    "name Soft TF-IDF (similar words count)": (["name_soft_tfidf"], [1]),
    "rule: TF-IDF words 0.5 + country 0.2 + domain 0.3": (["name_tfidf_words", "country", "domain"], [0.5, 0.2, 0.3]),
    "rule: TF-IDF letter groups 0.5 + country 0.2 + domain 0.3": (["name_tfidf_chars", "country", "domain"],
                                                                  [0.5, 0.2, 0.3]),
    "rule: Soft TF-IDF 0.5 + country 0.2 + domain 0.3": (["name_soft_tfidf", "country", "domain"], [0.5, 0.2, 0.3]),
}


if __name__ == "__main__":
    run_rules(RESULTS, run_argument(), RULES, prepare=add_tfidf, extra=tfidf_comparators())
