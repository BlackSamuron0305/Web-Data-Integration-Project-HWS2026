"""Comparators of Phase II, built on PyDI's comparator classes.

All comparators take two records (rows of the integrated schema plus the helper columns of
common.add_match_columns) and return a similarity in [0, 1]; a missing value gives 0.
"""
import math

import pandas as pd
from PyDI.entitymatching import NumericComparator, StringComparator
from PyDI.entitymatching.base import BaseComparator


def _missing(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or v == ""


class CountryComparator(BaseComparator):
    """1 for the same country, 0.5 if one of the countries is unknown, 0 otherwise."""

    def __init__(self):
        super().__init__("country")

    def compare(self, r1, r2):
        a, b = r1["country_code"], r2["country_code"]
        if _missing(a) or _missing(b):
            return 0.5
        return 1.0 if a == b else 0.0


class DomainComparator(BaseComparator):
    """1 if the two records share an internet domain (of the website), else 0."""

    def __init__(self):
        super().__init__("domain")

    def compare(self, r1, r2):
        a, b = r1["domains"], r2["domains"]
        return 1.0 if len(a) and len(b) and set(a) & set(b) else 0.0


class GeoComparator(BaseComparator):
    """1 up to 2 km apart, falling linearly to 0 at 50 km; 0 if a position is missing."""

    def __init__(self):
        super().__init__("geo")

    def compare(self, r1, r2):
        la1, lo1, la2, lo2 = r1["latitude"], r1["longitude"], r2["latitude"], r2["longitude"]
        if any(_missing(v) for v in (la1, lo1, la2, lo2)):
            return 0.0
        p1, p2 = math.radians(la1), math.radians(la2)
        a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
        km = 12742 * math.asin(math.sqrt(a))
        return 1.0 if km <= 2 else max(0.0, 1 - (km - 2) / 48)


class Has(BaseComparator):
    """1 if both records have a value in the given columns (lets a classifier tell
    'different' from 'unknown')."""

    def __init__(self, name, *columns):
        super().__init__(name)
        self.columns = columns

    def compare(self, r1, r2):
        for c in self.columns:
            for r in (r1, r2):
                v = r[c]
                if _missing(v) or (isinstance(v, list) and not v):
                    return 0.0
        return 1.0


def feature_comparators():
    """name -> comparator; the columns of the feature table of the experiments."""
    best = lambda col, sim: StringComparator(col, sim, list_strategy="best_match")
    comps = {
        "name_jaro_winkler": StringComparator("name_norm", "jaro_winkler"),
        "name_levenshtein": StringComparator("name_norm", "levenshtein"),
        "name_jaccard": StringComparator("name_norm", "jaccard"),
        "name_sorensen_dice": StringComparator("name_norm", "sorensen_dice"),
        "names_best_jaro_winkler": best("names_all", "jaro_winkler"),
        "names_best_jaccard": best("names_all", "jaccard"),
        "domain": DomainComparator(),
        "country": CountryComparator(),
        "city": StringComparator("city_norm", "jaro_winkler"),
        "founding_year": NumericComparator("founding_year", "absolute_difference", max_difference=10),
        "geo": GeoComparator(),
    }
    flags = {
        "has_domain": Has("has_domain", "domains"),
        "has_city": Has("has_city", "city_norm"),
        "has_year": Has("has_year", "founding_year"),
        "has_geo": Has("has_geo", "latitude", "longitude"),
    }
    return comps, flags


def named(comps):
    """Gives a comparator the name used for its feature column."""
    out = []
    for name, c in comps.items():
        out.append({"function": c.compare, "name": name})
    return out
