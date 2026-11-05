"""Blocking strategies of Phase II built on PyDI's blockers.

The strategies differ in how a record is turned into blocking keys. Every strategy
returns a DataFrame with the candidate pairs (id1 from the left, id2 from the right dataset).
"""
import tempfile
from collections import Counter

import pandas as pd
from PyDI.entitymatching.blocking import (
    SortedNeighbourhoodBlocker,
    StandardBlocker,
    TokenBlocker,
)

OUTPUT_DIR = tempfile.mkdtemp(prefix="pydi_blocking_")  # PyDI writes debug files there

# tokens that name the kind of institution rather than the institution itself
GENERIC = {
    "university", "universite", "universitat", "universidad", "universita", "universidade",
    "universiteit", "of", "de", "la", "del", "di", "der", "des", "the", "and", "for", "und",
    "college", "institute", "school", "national", "state", "faculty", "academy", "campus",
    "technology", "science", "sciences", "higher", "education", "polytechnic", "centre",
    "center", "department", "applied", "international",
}


def tokens(names):
    out = set()
    for n in names:
        out.update(t for t in n.split() if len(t) >= 2 and t not in GENERIC)
    return out


def add_block_text(datasets, scoped_cap=150, global_cap=30):
    """Adds the column ``btext``: space-separated blocking keys of each record.

    A key is a name token (of the name, alternative names and acronyms) scoped to the
    country of the record, e.g. ``DE_heidelberg``; tokens that are rare over all three
    datasets are also used without the country, so that records without a country or
    with a different country in the sources can still meet. Keys that occur in more than
    ``scoped_cap`` (scoped) or ``global_cap`` (global) records are dropped.
    """
    toks = {k: [tokens(n) for n in df["names_all"]] for k, df in datasets.items()}
    scoped, glob = Counter(), Counter()
    for k, df in datasets.items():
        for cc, ts in zip(df["country_code"], toks[k]):
            for t in ts:
                scoped[(cc, t)] += 1
                glob[t] += 1
    for k, df in datasets.items():
        texts = []
        for cc, ts in zip(df["country_code"], toks[k]):
            keys = [f"{cc}_{t}" for t in ts if cc and scoped[(cc, t)] <= scoped_cap]
            keys += [f"*_{t}" for t in ts if glob[t] <= global_cap]
            texts.append(" ".join(keys))
        df["btext"] = texts
        df["name_first"] = [(n.split() or [""])[0] for n in df["name_norm"]]
        df["cc_first"] = df["country_code"] + "|" + df["name_first"]
        df["has_domain"] = df["domain"].where(df["domain"] != "", None)


def _materialize(blocker, limit):
    est = blocker.estimate_pairs()
    if est is not None and est > limit:
        return None, est
    pairs = blocker.materialize()
    return pairs[["id1", "id2"]].drop_duplicates().reset_index(drop=True), est


def strategies(left, right, limit=40_000_000):
    """Name -> function returning the candidate pairs of one blocking strategy."""
    kw = dict(id_column="id", output_dir=OUTPUT_DIR)

    def standard(col):
        return lambda: _materialize(StandardBlocker(left, right, on=[col], **kw), limit)

    def token(col, **extra):
        return lambda: _materialize(
            TokenBlocker(left, right, column=col, tokenizer=lambda s: str(s).split(), **kw, **extra), limit)

    def plain_tokens():
        return _materialize(TokenBlocker(left, right, column="name_norm", **kw), limit)

    def sorted_nb(window):
        return lambda: _materialize(SortedNeighbourhoodBlocker(left, right, key="name_norm", window=window, **kw), limit)

    def union_keys():
        a, _ = token("btext")()
        l, r = left[left["domain"] != ""], right[right["domain"] != ""]
        b, _ = _materialize(StandardBlocker(l, r, on=["domain"], **kw), limit)
        return pd.concat([a, b]).drop_duplicates().reset_index(drop=True), None

    return {
        "standard: normalised name": standard("name_norm"),
        "standard: country + first word": standard("cc_first"),
        "sorted neighbourhood (window 10)": sorted_nb(10),
        "token: words of the name": plain_tokens,
        "token: country-scoped name tokens": token("btext"),
        "token (scoped) + same web domain": union_keys,
    }
