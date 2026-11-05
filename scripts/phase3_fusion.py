"""Phase III: data fusion.

1. Groups the records that the three correspondence sets (Phase II) link, with the
   constraint that a group holds at most one record per dataset.
2. Fuses each group with every strategy of fusion_strategies.py (PyDI DataFusionEngine) and
   evaluates the strategies on the fusion gold standard (data/gold_standard/fusion_gold.csv).
3. Fuses everything with the best strategy per attribute and measures the quality and
   completeness of the fused dataset.

Run (after phase2_final.py and build_fusion_gold.py): python scripts/phase3_fusion.py
"""
import json

import numpy as np
import pandas as pd
from PyDI.fusion import DataFusionEngine

from blocking import add_block_text  # noqa: F401  (keeps the helper columns identical to Phase II)
from common import DATA, RESULTS, SCHEMA, load_target, norm_text
from fusion_strategies import DATASETS, EVALUATED, LISTS, SCALARS, TRUST, all_strategies, strategy, voting_rule, favour

FUSED = DATA / "fused"
FUSED.mkdir(exist_ok=True)
PAIRS = [("wikidata", "ror"), ("deqar", "ror"), ("wikidata", "deqar")]
FUSE_COLUMNS = [c for c in SCHEMA if c != "id"] + ["domain"]


def dataset_of(record_id):
    return record_id.split("_", 1)[0]


def constrained_groups(corrs):
    """Accepts correspondences from the highest score down unless they would put two
    records of one dataset into the same group. Returns the accepted correspondences."""
    parent, members = {}, {}

    def find(x):
        parent.setdefault(x, x)
        members.setdefault(x, {dataset_of(x)})
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    accepted, rejected = [], 0
    for row in corrs.sort_values("score", ascending=False).itertuples(index=False):
        ra, rb = find(row.id1), find(row.id2)
        if ra == rb:
            accepted.append(row)
            continue
        if members[ra] & members[rb]:
            rejected += 1
            continue
        parent[rb] = ra
        members[ra] |= members[rb]
        accepted.append(row)
    return pd.DataFrame(accepted, columns=corrs.columns), rejected


def prepare(data):
    """Datasets as the fusion engine needs them: schema columns plus the primary domain."""
    out = []
    for name in DATASETS:
        df = data[name][["id"] + FUSE_COLUMNS].copy()
        for c in ("founding_year", "closure_year", "students", "qa_reports", "latitude", "longitude"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["domain"] = df["domains"].map(lambda L: L[0] if len(L) else None)
        for c in SCHEMA[1:] + ["domain"]:
            if c in LISTS or c in ("domains",):
                continue
            df[c] = df[c].replace({"": None})
        df.attrs["dataset_name"] = name
        out.append(df)
    return out


def fuse(datasets, corrs, strat):
    engine = DataFusionEngine(strat)
    fused = engine.run(datasets, corrs, id_column="id", include_singletons=True)
    return fused


def equal(attr, fused_value, expected, alternatives=""):
    """Compares a fused value with the expected value of the fusion gold standard."""
    if fused_value is None or (isinstance(fused_value, float) and np.isnan(fused_value)):
        return False
    if attr == "founding_year":
        return int(fused_value) == int(expected)
    if attr == "domain":
        accepted = {str(expected).lower()} | {a.lower() for a in str(alternatives).split("|") if a}
        return str(fused_value).lower().removeprefix("www.") in accepted
    if attr in ("name", "city"):
        accepted = {norm_text(expected)} | {norm_text(a) for a in str(alternatives).split("|") if a}
        return norm_text(str(fused_value)) in accepted
    return str(fused_value) == str(expected)


def evaluate(fused, gold):
    """Accuracy per attribute on the fusion gold standard."""
    index = {}
    for i, srcs in enumerate(fused["_fusion_sources"]):
        for s in srcs:
            index[s] = i
    res = {a: [] for a in EVALUATED}
    for g in gold.itertuples(index=False):
        row = fused.iloc[index[g.anchor_id]]
        for a in EVALUATED:
            alt = getattr(g, a + "_alternatives", "") if a in ("name", "city", "domain") else ""
            res[a].append(equal(a, row.get(a), getattr(g, a), alt if isinstance(alt, str) else ""))
    return {a: float(np.mean(v)) for a, v in res.items()}


def agreement(datasets, groups_fused):
    """Share of fused groups with at least two values in which all values agree."""
    out = {}
    recs = {}
    for df in datasets:
        recs.update({r: i for r, i in zip(df["id"], df.to_dict("records"))})
    for a in EVALUATED:
        agree = total = 0
        for srcs in groups_fused["_fusion_sources"]:
            if len(srcs) < 2:
                continue
            vals = []
            for s in srcs:
                v = recs[s].get(a)
                if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
                    continue
                vals.append(norm_text(str(v)) if a in ("name", "city") else str(v))
            if len(vals) >= 2:
                total += 1
                agree += len(set(vals)) == 1
        out[a] = (agree / total if total else None, total)
    return out


def is_filled(v):
    if isinstance(v, (list, np.ndarray)):
        return len(v) > 0
    return not (v is None or (isinstance(v, float) and np.isnan(v)) or v == "")


def completeness(datasets, fused):
    """Share of filled values per attribute. 'all entities' compares the fused dataset with each
    source over all its records; 'multi-source entities' compares, for the entities that are in at
    least two sources, the fused record with the records of each source."""
    recs = {}
    for df in datasets:
        recs.update({r: i for r, i in zip(df["id"], df.to_dict("records"))})
    multi = fused[fused["_fusion_sources"].map(len) >= 2]
    rows = []
    for a in FUSE_COLUMNS:
        row = {"attribute": a}
        for df in datasets:
            row[df.attrs["dataset_name"]] = float(df[a].map(is_filled).mean())
        row["fused"] = float(fused[a].map(is_filled).mean())
        for d in DATASETS:  # a group without a record of this source counts as not filled
            filled = []
            for srcs in multi["_fusion_sources"]:
                mine = [recs[x] for x in srcs if x.startswith(d + "_")]
                filled.append(bool(mine) and is_filled(mine[0][a]))
            row[f"multi_{d}"] = float(np.mean(filled)) if filled else None
        row["multi_fused"] = float(multi[a].map(is_filled).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    data = load_target()
    datasets = prepare(data)
    corrs = pd.concat([pd.read_csv(DATA / "correspondences" / f"corr_{a}_{b}.csv") for a, b in PAIRS],
                      ignore_index=True)
    accepted, rejected = constrained_groups(corrs)
    print("correspondences", len(corrs), "accepted", len(accepted), "rejected (two records of one dataset)", rejected)
    accepted.to_csv(DATA / "correspondences" / "accepted_all.csv", index=False)

    gold = pd.read_csv(DATA / "gold_standard" / "fusion_gold.csv", keep_default_na=False)
    strategies = all_strategies()
    rows = []
    fused_by = {}
    for name, strat in strategies.items():
        # only the groups with the gold-standard entities are needed for the comparison
        fused = fuse(datasets, accepted, strat)
        fused_by[name] = fused
        acc = evaluate(fused, gold)
        rows.append(dict(strategy=name, **{a: round(v, 3) for a, v in acc.items()}))
        print(name, acc)
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "fusion_strategies.csv", index=False)

    # best strategy per attribute (ties: the earlier, simpler one)
    # ties go to the strategy that comes first in the list, voting before favouring a source
    priority = ["vote, tie: ROR", "vote, tie: Wikidata", "vote, tie: earliest year", "ROR first",
                "Wikidata first", "DEQAR first", "first non-null (PyDI default)"]
    ranked = table.set_index("strategy").loc[priority]
    best_of = {a: ranked[a].idxmax() for a in EVALUATED}
    print("best per attribute", best_of)
    (RESULTS / "fusion_best.json").write_text(json.dumps(best_of, indent=1), encoding="utf-8")
    base = best_of["name"]
    final = fused_by[base].copy().set_index("_id")
    for a, s in best_of.items():
        final[a] = fused_by[s].set_index("_id")[a].reindex(final.index)
    final = final.reset_index()

    final_out = final.drop(columns=["_fusion_metadata", "id"], errors="ignore")
    final_out = final_out.rename(columns={"_id": "entity_id"})
    for c in LISTS:
        final_out[c] = final_out[c].map(lambda v: " | ".join(map(str, v)) if isinstance(v, (list, np.ndarray)) else "")
    final_out["_fusion_sources"] = final_out["_fusion_sources"].map(" | ".join)
    final_out["_fusion_source_datasets"] = final_out["_fusion_source_datasets"].map(lambda L: " | ".join(sorted(set(L))))
    final_out.to_csv(FUSED / "universities_fused.csv", index=False)

    comp = completeness(datasets, final)
    comp.to_csv(RESULTS / "fusion_completeness.csv", index=False)
    agr = agreement(datasets, final)
    pd.DataFrame([dict(attribute=a, agreement=v[0], groups_with_two_values=v[1]) for a, v in agr.items()]).to_csv(
        RESULTS / "fusion_agreement.csv", index=False)
    combos = final["_fusion_source_datasets"].map(lambda L: " + ".join(sorted(set(L)))).value_counts()
    combos.to_csv(RESULTS / "fusion_source_combinations.csv", header=["entities"])
    print(comp.round(3).to_string())
    print(agr)
    print(combos)
    print("fused entities", len(final))


if __name__ == "__main__":
    main()
