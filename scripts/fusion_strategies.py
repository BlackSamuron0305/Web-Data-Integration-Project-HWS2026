"""Conflict resolution strategies of Phase III, built on PyDI's fusion module."""
from collections import Counter

from PyDI.fusion import DataFusionStrategy, prefer_higher_trust, union
from PyDI.fusion.conflict_resolution import earliest, median

from common import norm_text

DATASETS = ["wikidata", "ror", "deqar"]
LISTS = ["alt_names", "acronyms", "domains", "parent", "types", "memberships", "history"]
SCALARS = ["name", "country", "country_code", "city", "region", "website", "domain", "founding_year",
           "latitude", "longitude"]
# attributes compared against the fusion gold standard
EVALUATED = ["name", "country_code", "city", "founding_year", "domain"]

TRUST = {  # higher = preferred; one ordering per strategy
    "ROR first": {"ror": 3, "wikidata": 2, "deqar": 1},
    "Wikidata first": {"wikidata": 3, "ror": 2, "deqar": 1},
    "DEQAR first": {"deqar": 3, "ror": 2, "wikidata": 1},
}


def vote(values, sources=None, source_datasets=None, trust_map=None, key=None, tie="trust", **kwargs):
    """Majority vote over normalised values; ties go to the most trusted source
    (tie='trust') or to the smallest value (tie='earliest')."""
    key = key or (lambda v: v)
    rows = [(key(v), v, (trust_map or {}).get((source_datasets or {}).get(s), 0))
            for v, s in zip(values, sources or [None] * len(values))]
    rows = [r for r in rows if r[0] not in ("", None)]
    if not rows:
        return None, 0.0, {"reason": "no_valid_values"}
    counts = Counter(k for k, _, _ in rows)
    top = max(counts.values())
    winners = [r for r in rows if counts[r[0]] == top]
    if tie == "earliest":
        pick = min(winners, key=lambda r: r[1])
    else:
        pick = max(winners, key=lambda r: r[2])
    return pick[1], top / len(rows), {"rule": "vote", "votes": top, "values": len(rows)}


def vote_text(values, **kwargs):
    return vote(values, key=norm_text, **kwargs)


def vote_earliest(values, **kwargs):
    return vote(values, tie="earliest", **kwargs)


def strategy(name, scalar_rule):
    """A strategy: union for the list attributes, ``scalar_rule`` (attribute -> (resolver, kwargs))
    for the single-valued ones. Attributes of only one source need no rule."""
    s = DataFusionStrategy(name)
    for a in LISTS:
        s.add_attribute_fuser(a, union)
    for a in SCALARS:
        resolver, kw = scalar_rule(a)
        if resolver is not None:
            s.add_attribute_fuser(a, resolver, **kw)
    return s


def favour(order):
    trust = TRUST[order]
    return lambda a: (prefer_higher_trust, dict(trust_map=trust))


def voting_rule(trust, year_tie="trust", coords="median"):
    def rule(a):
        if a in ("name", "city"):
            return vote_text, dict(trust_map=trust)
        if a in ("country", "country_code", "region", "website", "domain"):
            return vote, dict(trust_map=trust)
        if a == "founding_year":
            return (vote_earliest if year_tie == "earliest" else vote), dict(trust_map=trust)
        if a in ("latitude", "longitude"):
            return (median, {}) if coords == "median" else (prefer_higher_trust, dict(trust_map=trust))
    return rule


def all_strategies():
    out = {"first non-null (PyDI default)": strategy("first", lambda a: (None, {}))}
    for order in TRUST:
        out[order] = strategy(order, favour(order))
    out["vote, tie: ROR"] = strategy("vote-ror", voting_rule(TRUST["ROR first"]))
    out["vote, tie: Wikidata"] = strategy("vote-wd", voting_rule(TRUST["Wikidata first"]))
    out["vote, tie: earliest year"] = strategy("vote-earliest", voting_rule(TRUST["ROR first"], year_tie="earliest"))
    return out
