"""Phase II: token blocking on textual attributes + rule-based matching, evaluated on validation_data.

Token blocking (PyDI TokenBlocker): every record is put into one block per token (word) of a
textual attribute; two records of different datasets become a candidate pair if they share at
least one token.

Attributes (textual)
  name        normalised main name                   'heidelberg university'
  all names   name + alternative names + acronyms    'heidelberg university', 'ruprecht karls universitat'
  city        normalised city                        'heidelberg'
  web domain  parts of the internet domains          'uni-heidelberg.de' -> 'uni', 'heidelberg', 'de'
Token cleaning
  all words   every word with >= 2 characters (as PyDI's default tokenizer)
  distinctive generic words removed ('university', 'of', 'de', 'college', ... see blocking.GENERIC;
              for domains 'www', 'edu', 'ac', 'com', 'org', 'net') and frequent tokens dropped:
              a token in more than MAX_TOKEN_FREQ records of the two datasets is a stop word
  country-scoped  distinctive tokens prefixed with the country code ('de_heidelberg'), so that
              a token only connects records of one country (cap MAX_SCOPED_FREQ per country token)
A variant with more than MAX_CANDIDATES candidate pairs is listed with its estimated number of
pairs but not run (matching them would take too long).

For every run: match with Rule1 (as in standard_blocking.py), choose the threshold on train_data,
report P/R/F1, #Corr and time (blocking + matching) on validation_data.

Output: results/token_blocking_validation.csv, results/logs/token_blocking.log
Run (after gold_standard.py): python scripts/token_blocking.py
"""
import logging
import re
from collections import Counter

import pandas as pd
from PyDI.entitymatching.blocking import TokenBlocker

from blocking import GENERIC, OUTPUT_DIR, add_block_text
from common import RESULTS, load_target
from sorted_neighbourhood_blocking import run_blocker
from standard_blocking import PAIRS
from validation import load_labelled, write_log

logging.basicConfig(level=logging.WARNING)

MAX_TOKEN_FREQ = 100      # distinctive: tokens in more records are dropped
MAX_SCOPED_FREQ = 150     # country-scoped: per country token
MAX_CANDIDATES = 3_000_000
DOMAIN_GENERIC = {"www", "edu", "ac", "com", "org", "net", "info", "gov"}

ATTRIBUTES = ["name", "all names", "city", "web domain"]
# (attribute, cleaning) pairs that are run
VARIANTS = [
    ("name", "all words"),
    ("name", "distinctive"),
    ("all names", "all words"),
    ("all names", "distinctive"),
    ("all names", "country-scoped"),
    ("city", "distinctive"),
    ("web domain", "distinctive"),
]


def words(text):
    return [t for t in re.split(r"[^0-9a-z]+", str(text).lower()) if len(t) >= 2]


def raw_tokens(df, attribute):
    """One set of tokens per record."""
    if attribute == "name":
        return [set(words(n)) for n in df["name_norm"].fillna("")]
    if attribute == "all names":
        return [set(t for n in names for t in words(n)) for names in df["names_all"]]
    if attribute == "city":
        return [set(words(c)) for c in df["city_norm"].fillna("")]
    if attribute == "web domain":
        return [set(t for d in doms for t in words(d)) for doms in df["domains"]]
    raise ValueError(attribute)


def token_texts(left, right, attribute, cleaning):
    """Space-separated blocking tokens per record of both datasets, after cleaning."""
    toks = [raw_tokens(df, attribute) for df in (left, right)]
    if cleaning == "all words":
        return [[" ".join(sorted(t)) for t in side] for side in toks]
    generic = DOMAIN_GENERIC if attribute == "web domain" else GENERIC
    toks = [[{t for t in ts if t not in generic} for ts in side] for side in toks]
    if cleaning == "country-scoped":
        ccs = [df["country_code"].fillna("").str.lower().tolist() for df in (left, right)]
        toks = [[{f"{c}_{t}" for t in ts} if c else set() for ts, c in zip(side, cc)]
                for side, cc in zip(toks, ccs)]
        cap = MAX_SCOPED_FREQ
    else:
        cap = MAX_TOKEN_FREQ
    freq = Counter(t for side in toks for ts in side for t in ts)
    return [[" ".join(sorted(t for t in ts if freq[t] <= cap)) for ts in side] for side in toks]


def prepare(left, right, attribute, cleaning):
    """Copies of the two datasets with the column 'tok' and the TokenBlocker on it."""
    lt, rt = token_texts(left, right, attribute, cleaning)
    l, r = left.assign(tok=lt), right.assign(tok=rt)
    return l, r


def token_blocker(l, r):
    return TokenBlocker(l, r, column="tok", id_column="id", tokenizer=lambda s: str(s).split(),
                        min_token_len=1, output_dir=OUTPUT_DIR)


def main():
    data = load_target()
    add_block_text(data)
    rows = []
    for a, b in PAIRS:
        left, right = data[a], data[b]
        train, valid = load_labelled("train", a, b), load_labelled("validation", a, b)
        for attribute, cleaning in VARIANTS:
            name = f"Token: {attribute}, {cleaning}"
            l, r = prepare(left, right, attribute, cleaning)
            est = token_blocker(l, r).estimate_pairs()
            if est > MAX_CANDIDATES:
                rows.append(dict(pair=f"{a}-{b}", matcher="-", blocker=name, candidates=est,
                                 reduction_ratio=round(1 - est / (len(left) * len(right)), 6),
                                 note=f"not run: {est:,} pairs (estimate)"))
                print(rows[-1], flush=True)
                continue
            def block(x, y, attribute=attribute, cleaning=cleaning):  # token preparation is part of blocking
                return token_blocker(*prepare(x, y, attribute, cleaning)).materialize()
            rows += run_blocker(a, b, left, right, train, valid, name, block)
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "token_blocking_validation.csv", index=False)
    print("log:", write_log(out, "token_blocking", "Token blocking on textual attributes (PyDI TokenBlocker)"))


if __name__ == "__main__":
    main()
