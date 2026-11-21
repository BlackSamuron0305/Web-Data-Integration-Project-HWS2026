"""Phase II: blocking key 'country code + normalised name without "university" and "of"'.

Key: the country code followed by the normalised name from which the words 'university' and
'of' are removed, e.g.
    'University of Heidelberg', DE  -> 'de heidelberg'
    'Heidelberg University',    DE  -> 'de heidelberg'
Records without a country code or with nothing left of the name are left out.

The key is used with
  - standard blocking (PyDI StandardBlocker): records with an equal key are compared,
  - the Sorted Neighbourhood Method (PyDI SortedNeighbourhoodBlocker) with w = 5, 10, 20, 40:
    records sorted by the key, each record compared with the next w-1 records.
For every run: match with Rule1 (as in standard_blocking.py), choose the threshold on
train_data, report P/R/F1, #Corr and time (blocking + matching) on validation_data.

Output: results/name_country_blocking_validation.csv, results/logs/name_country_blocking.log
Run (after gold_standard.py): python scripts/snm_name_country_blocking.py
"""
import logging

import pandas as pd

from blocking import add_block_text
from common import RESULTS, load_target
from sorted_neighbourhood_blocking import run_blocker, snm
from standard_blocking import PAIRS, block as standard_block
from validation import load_labelled, write_log

logging.basicConfig(level=logging.WARNING)

REMOVE = {"university", "of"}
KEY = "nc_key"
WINDOWS = [5, 10, 20, 40]


def clean_name(name):
    """Normalised name without the words in REMOVE: 'university of heidelberg' -> 'heidelberg'."""
    return " ".join(t for t in str(name).split() if t not in REMOVE)


def add_key(data):
    """Adds the key column; empty if the country code or the cleaned name is missing."""
    for df in data.values():
        cc = df["country_code"].fillna("").str.lower()
        names = df["name_norm"].fillna("").map(clean_name)
        df[KEY] = [f"{c} {n}" if c and n else "" for c, n in zip(cc, names)]


def main():
    data = load_target()
    add_block_text(data)
    add_key(data)
    rows = []
    for a, b in PAIRS:
        left, right = data[a], data[b]
        train, valid = load_labelled("train", a, b), load_labelled("validation", a, b)
        rows += run_blocker(a, b, left, right, train, valid, "Standard: country + name w/o 'university','of'",
                            lambda l, r: standard_block(l, r, [KEY]))
        for w in WINDOWS:
            rows += run_blocker(a, b, left, right, train, valid,
                                f"SNM: country + name w/o 'university','of' (w={w})", snm(KEY, w))
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "name_country_blocking_validation.csv", index=False)
    print("log:", write_log(out, "name_country_blocking",
                            "Blocking key: country code + normalised name without 'university' and 'of'"))


if __name__ == "__main__":
    main()
