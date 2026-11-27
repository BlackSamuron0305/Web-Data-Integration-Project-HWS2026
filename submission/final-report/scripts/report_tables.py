"""Builds the identity-resolution tables of the report from the pipeline's result files, as LaTeX rows.

  tables/matching.tex     Table: best variant of each approach (final run, validation), the chosen matcher with
                          fewer blockers, and the test result of both runs
  tables/cleaning.tex     Table: validation F1 of each approach in the first pass and the final run
  tables/blocking.tex     Table: blockers (pairs, pair completeness, reduction ratio, time), per dataset pair,
                          the first pass and the final run side by side
  tables/groups.tex       Table: group size distribution of both runs and of the final links without one-to-one

Run from the repo root after the pipeline:  python submission/final-report/scripts/report_tables.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
IR = ROOT / "scripts" / "04_identity_resolution"
OUT = Path(__file__).resolve().parents[1] / "tables"
PAIRS = ["wikidata-ror", "deqar-ror"]

# folder: (number in the report, name in the report)
APPROACHES = {
    "01_rules_string_similarity": (1, "String rule"),
    "02_rules_tfidf": (2, "TF-IDF rule"),
    "03_rules_embeddings": (3, "Embedding rule"),
    "04_rules_weight_search": (4, "Searched weights"),
    "05_machine_learning": (5, "LR, forest, boosting"),
    "06_rules_more_similarity": (6, "More measures"),
    "07_more_learners": (7, "More learners"),
    "08_fine_tuned_language_model": (8, "Fine-tuned LM"),
    "09_local_llm": (9, "Local LLM"),
}
BLOCKERS = {   # blocker in blocking_effect.csv: row label of the middle block of the matching table
    "union: country + name word | same domain | embedding": "Union (all three)",
    "token: country + name word": "Word only",
    "token: same web domain": "Domain only",
    "union: country + name word | same domain": "Word + domain",
}


def num(x, digits=3):
    # 0.942, with the leading zero. Exactly 1 is written 1.0, since 1.000 reads as one thousand to readers
    # used to a decimal comma
    if x == 1:
        return "1.0"
    return f"{x:.{digits}f}"


def best_cell(text):
    # the best value of a column, marked by colour (\best is defined in report.tex)
    return f"\\best{{{text}}}"


def seconds(s):
    if pd.isna(s) or s == "":
        return ""
    s = float(s)
    return f"{s:,.0f}\\,s" if s >= 10 else f"{s:.1f}\\,s"


def matching_log(folder):
    return pd.concat([pd.read_csv(IR / folder / "results" / run / "matching.csv") for run in ["first_pass", "final"]],
                     ignore_index=True)


def best(df, run, pair):
    part = df[(df["run"] == run) & (df["pair"] == pair)]
    return part.loc[part["F1"].idxmax()] if len(part) else None


def cells(r):
    if r is None:
        return ["--"] * 5
    return [num(r["P"]), num(r["R"]), num(r["F1"]), f"{int(r['corr']):,}", seconds(r.get("seconds", ""))]


def matching_table():
    lines = []
    rules = matching_log("01_rules_string_similarity")
    names_only = rules[rules["matcher"] == "name Jaro-Winkler"]
    row = ["", "Baseline"]
    for pair in PAIRS:
        row += cells(best(names_only, "final", pair))
    lines.append(" & ".join(row) + "\\\\")
    best_f1 = {pair: max(best(matching_log(f), "final", pair)["F1"] for f in APPROACHES) for pair in PAIRS}
    for folder, (n, name) in APPROACHES.items():
        df = matching_log(folder)
        row = [str(n), name]
        for pair in PAIRS:
            c = cells(best(df, "final", pair))
            if best(df, "final", pair)["F1"] == best_f1[pair]:
                c[2] = best_cell(c[2])
            row += c
        lines.append(" & ".join(row) + "\\\\")
    lines.append("\\midrule")

    # the chosen matcher after one-to-one matching and the cut-off, with fewer blockers (validation)
    effect = pd.read_csv(IR / "analysis" / "results" / "blocking_effect.csv")
    effect = effect[effect["split"] == "validation"]
    final = pd.read_csv(IR / "global_matching_and_test" / "results" / "final.csv")
    chosen = final[(final["run"] == "final") & (final["note"].fillna("").str.startswith("final choice"))]
    label = {pair: chosen[chosen["pair"] == pair]["matcher"].iloc[0] for pair in PAIRS}
    lines.append("\\multicolumn{12}{@{}l}{\\emph{Chosen matcher (8) + one-to-one matching, by blocker}}\\\\")
    for blocker, short in BLOCKERS.items():
        row = ["", short]
        for pair in PAIRS:
            r = effect[(effect["pair"] == pair) & (effect["blocker"] == blocker)]
            row += cells(r.iloc[0]) if len(r) else ["--"] * 5
        lines.append(" & ".join(row) + "\\\\")
    lines.append("\\midrule")
    lines.append("\\multicolumn{12}{@{}l}{\\emph{Test pairs (300 per dataset pair): best matcher of the run + one-to-one}}\\\\")
    for run, name in [("first_pass", "First pass"), ("final", "Final run")]:
        row = ["", name]
        for pair in PAIRS:
            r = final[(final["run"] == run) & (final["pair"] == pair) & (final["split"] == "test")
                      & (final["note"].fillna("").str.startswith("final choice"))]
            c = cells(r.iloc[0]) if len(r) else ["--"] * 5
            c[4] = ""
            row += c
        lines.append(" & ".join(row) + "\\\\")
    return "\n".join(lines) + "\n", label


def cleaning_table():
    """Per approach: validation F1 of its best variant in both runs, and how many of its first-pass links
    (above its threshold, before one-to-one matching) touch a record the cleaning removed."""
    import sys
    sys.path.insert(0, str(IR))
    from common import removed_ids
    gone = removed_ids()
    lines = []
    for folder, (n, name) in APPROACHES.items():
        df = matching_log(folder)
        row = [str(n), name]
        for pair in PAIRS:
            a, b = best(df, "first_pass", pair), best(df, "final", pair)
            path = IR / folder / "results" / "first_pass" / f"best_{pair.replace('-', '_')}.csv"
            if a is None or not path.exists():
                row += ["--", num(b["F1"]), "--", "--"]
                continue
            links = pd.read_csv(path, usecols=["id1", "id2"])
            bad = int((links["id1"].isin(gone) | links["id2"].isin(gone)).sum())
            row += [num(a["F1"]), num(b["F1"]), f"{len(links):,}", f"{bad:,} ({bad / len(links):.0%})".replace("%", "\\%")]
        lines.append(" & ".join(row) + "\\\\")
    return "\n".join(lines) + "\n"


SHORT_BLOCKER = {
    "no blocking (all pairs)": "No blocking (all pairs)",
    "standard: exercise key (2 letters x 3 words)": "Exercise key (2 letters of 3 words)",
    "standard: normalised name": "Same normalised name",
    "sorted neighbourhood: name, window 20": "Sorted neighbourhood, window 20",
    "token: words of all names": "Any shared name word",
    "token: character 3-grams of the name": "Any shared 3-gram",
    "token: country + name word": "Country + name word",
    "token: same web domain": "Same web domain",
    "embedding: name, top 10": "Embedding, 10 nearest names",
    "union: country + name word | same domain": "Union: word, domain",
    "union: country + name word | same domain | embedding": "Union: word, domain, embedding",
}


def big(n):
    n = float(n)
    return f"{n / 1e9:.1f}B" if n >= 1e9 else f"{n / 1e6:.0f}M" if n >= 2e7 else f"{int(n):,}"


def blocking_table():
    # one block per dataset pair, the first pass and the final run side by side (coloured in report.tex)
    log = pd.read_csv(IR / "blocking" / "results" / "blocking.csv")
    lines = []
    for pair, title in [("wikidata-ror", "Wikidata--ROR"), ("deqar-ror", "DEQAR--ROR")]:
        lines.append(f"\\multicolumn{{9}}{{@{{}}l}}{{\\emph{{{title}}}}}\\\\")
        for blocker, short in SHORT_BLOCKER.items():
            row = [short]
            for run in ["first_pass", "final"]:
                r = log[(log["run"] == run) & (log["pair"] == pair) & (log["blocker"] == blocker)]
                if not len(r):
                    row += ["--"] * 4
                    continue
                r = r.iloc[0]
                skipped = pd.isna(r["pair_completeness"])
                row += [big(r["candidates"]) + ("$^*$" if skipped and "no blocking" not in blocker else ""),
                        "--" if skipped else num(r["pair_completeness"]),
                        "--" if skipped else f"{r['reduction_ratio']:.5f}",
                        "--" if skipped else seconds(r["seconds"])]
            lines.append(" & ".join(row) + "\\\\")
    return "\n".join(lines) + "\n"


def groups_table():
    files = {"early version": "history/group_sizes_early_version.csv", "first pass": "group_sizes_first_pass.csv",
             "final, no one-to-one": "group_sizes_final_without_one_to_one.csv", "final": "group_sizes_final.csv"}
    sizes = {}
    for k, f in files.items():
        path = IR / "global_matching_and_test" / "results" / f
        sizes[k] = (pd.read_csv(path).set_index("cluster_size")["frequency"] if path.exists()
                    else pd.Series(dtype=int))   # not written yet: shown as 0
    buckets = [("2", 2, 2), ("3", 3, 3), ("4--10", 4, 10), ("11--100", 11, 100), ("over 100", 101, 10**9)]
    lines = []
    for label, lo, hi in buckets:
        row = [label]
        for s in sizes.values():
            row.append(f"{int(s[(s.index >= lo) & (s.index <= hi)].sum()):,}")
        lines.append(" & ".join(row) + "\\\\")
    largest = ["Largest group"] + [f"{int(s.index.max()):,}" if len(s) else "--" for s in sizes.values()]
    lines.append("\\midrule")
    lines.append(" & ".join(largest) + "\\\\")
    return "\n".join(lines) + "\n"


def numbers():
    """The numbers the report text uses, as LaTeX commands (\\wrTestF, \\nFused, ...)."""
    import ast
    import sys
    sys.path.insert(0, str(IR))
    from common import links, removed_ids

    v = {}
    res = IR / "global_matching_and_test" / "results"
    final = pd.read_csv(res / "final.csv")
    final["note"] = final["note"].fillna("")
    cut = pd.read_csv(res / "cutoff_final.csv").set_index("pair")
    key = links()
    gone = removed_ids()
    for pair, p in [("wikidata-ror", "wr"), ("deqar-ror", "dr")]:
        a = pair.split("-")[0]
        for run, r in [("final", "Test"), ("first_pass", "First")]:
            t = final[(final["run"] == run) & (final["pair"] == pair) & (final["split"] == "test")
                      & final["note"].str.startswith("final choice")].iloc[0]
            v[f"{p}{r}P"], v[f"{p}{r}R"], v[f"{p}{r}F"] = num(t["P"]), num(t["R"]), num(t["F1"])
            v[f"{p}{r}Links"] = f"{int(t['corr']):,}"
        val = final[(final["run"] == "final") & (final["pair"] == pair) & (final["split"] == "validation")]
        v[f"{p}ValPnone"] = num(val[val["matcher"].str.endswith("+ no global matching")]["P"].iloc[0])
        v[f"{p}ValPone"] = num(val[val["matcher"].str.endswith("+ greedy one-to-one")]["P"].iloc[0])
        v[f"{p}Threshold"] = num(cut.at[pair, "matcher_threshold"], 2)
        v[f"{p}Cutoff"] = num(cut.at[pair, "cutoff"], 2)
        v[f"{p}CutoffValP"] = num(cut.at[pair, "validation_P"])
        # best approach on validation (final run)
        found = [(best(matching_log(f), "final", pair), name) for f, (_, name) in APPROACHES.items()]
        (row, name) = max(found, key=lambda x: x[0]["F1"])
        v[f"{p}Best"], v[f"{p}BestF"] = name, num(row["F1"])
        second = sorted(found, key=lambda x: -x[0]["F1"])[1]
        v[f"{p}SecondF"], v[f"{p}Second"] = num(second[0]["F1"]), second[1]
        # identifier links: how many final links they confirm or contradict, and how many they recover
        chosen = pd.read_csv(IR / "analysis" / "results" / "cutoff_check.csv")
        chosen = chosen[(chosen["pair"] == pair) & chosen["chosen"]].iloc[0]
        v[f"{p}KeyWrong"] = f"{int(chosen['ID key: wrong']):,}"
        kept_links = [(x, y) for x, y in key[(a, "ror")] if x not in gone and y not in gone]   # cleaned data
        v[f"{p}KeyRecovered"] = f"{chosen['ID key: right'] / len(kept_links):.0%}".replace("%", "\\%")
        v[f"{p}IdLinks"] = f"{len(kept_links):,}"
        # first-pass links that touch a record the cleaning removed
        fp = pd.read_csv(res / f"correspondences_{a}_ror_first_pass.csv")
        v[f"{p}FirstRemoved"] = f"{int((fp['id1'].isin(gone) | fp['id2'].isin(gone)).sum()):,}"
    v["firstRemoved"] = f"{sum(int(v[f'{p}FirstRemoved'].replace(',', '')) for p in ['wr', 'dr']):,}"

    errors = pd.read_csv(IR / "analysis" / "results" / "error_analysis.csv")
    missed = errors[errors["error"] == "missed match"]
    v["errWrong"] = str((errors["error"] == "wrong match").sum())
    v["errMissed"] = str(len(missed))
    for stage, name in [("below the threshold", "missThreshold"), ("not a candidate", "missCandidate"),
                        ("below the cut-off", "missCutoff")]:
        v[name] = str((missed["lost_at"] == stage).sum())
    v["missLost"] = str(missed["lost_at"].str.startswith("lost").sum())

    sizes = pd.read_csv(res / "group_sizes_final.csv").set_index("cluster_size")["frequency"]
    v["groupsTwo"], v["groupsThree"] = f"{int(sizes.get(2, 0)):,}", f"{int(sizes.get(3, 0)):,}"
    v["groupsMax"] = f"{int(sizes.index.max())}"

    # fusion
    fused = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "universities_fused.csv", low_memory=False)
    n_src = fused["_fusion_source_datasets"].map(lambda s: len(ast.literal_eval(s)))
    with_ror = fused["_fusion_source_datasets"].str.contains("ror")
    n_ror = int(with_ror.sum())
    v["nFused"] = f"{len(fused):,}"
    v["nSingle"], v["nTwo"], v["nThree"] = (f"{int((n_src == k).sum()):,}" for k in (1, 2, 3))
    v["nMulti"] = f"{int((n_src >= 2).sum()):,}"
    v["nRor"] = f"{n_ror:,}"
    v["nAdded"] = f"{len(fused) - n_ror:,}"
    ror_raw = len(pd.read_csv(ROOT / "data" / "ror" / "original" / "ror_education.csv", usecols=[0]))
    v["nAddedRaw"] = f"{len(fused) - ror_raw:,}"
    # share of each approach's first-pass links (best variant) that touch a removed record
    shares = []
    for folder in APPROACHES:
        for pair in PAIRS:
            path = IR / folder / "results" / "first_pass" / f"best_{pair.replace('-', '_')}.csv"
            if path.exists():
                links_fp = pd.read_csv(path, usecols=["id1", "id2"])
                shares.append((links_fp["id1"].isin(gone) | links_fp["id2"].isin(gone)).mean())
    v["removedShareMin"] = f"{min(shares):.0%}".replace("%", "")
    v["removedShareMax"] = f"{max(shares):.0%}".replace("%", "\\%")
    v["pctAdded"] = f"{(len(fused) - n_ror) / n_ror:.0%}".replace("%", "\\%")
    v["pctMulti"] = f"{(n_src >= 2).mean():.0%}".replace("%", "\\%")
    v["pctWithRor"] = f"{with_ror.mean():.0%}".replace("%", "\\%")
    density = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "density.csv", index_col=0)
    total = density.loc["all attributes"]   # mean over the 21 attributes, written by fusion.py
    v["densRor"] = num(total["ror"])
    v["densWikidata"] = num(total["wikidata"])
    v["densDeqar"] = num(total["deqar"])
    v["densFused"] = num(total["fused"])
    v["densFusedRor"] = num(total["fused, with ROR record"])
    ror = pd.read_csv(ROOT / "data" / "ror" / "filtered" / "ror_education.csv", dtype=str, keep_default_na=False)
    ror_year = dict(zip("ror_" + ror["ror_id"], ror["founding_year"].str.strip() != ""))
    multi = fused[n_src >= 2]
    ror_of = multi["_fusion_sources"].map(lambda s: next(i for i in ast.literal_eval(s) if i.startswith("ror_")))
    v["yearRor"] = f"{ror_of.map(ror_year).mean():.1%}".replace("%", "\\%")
    v["yearFused"] = f"{multi['founding_year'].notna().mean():.1%}".replace("%", "\\%")
    strategies = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "strategies.csv")
    # the final strategy on the test half of the gold standard (not used to choose it), compared tolerantly
    bestrow = strategies[(strategies["strategy"] == "best per attribute") & (strategies["gold subset"] == "test")
                         & (strategies["comparison"] == "tolerant")].iloc[0]
    v["accFinal"] = f"{bestrow['mean single-valued']:.0%}".replace("%", "\\%")
    v["goldUsed"] = str(int(bestrow["universities"]))
    strict = strategies[(strategies["strategy"] == "best per attribute") & (strategies["gold subset"] == "test")
                        & (strategies["comparison"] == "strict")].iloc[0]
    v["accFinalStrict"] = f"{strict['mean single-valued']:.0%}".replace("%", "\\%")
    ours = strategies[(strategies["strategy"] == "voting: ties by trust") & (strategies["gold subset"] == "test")
                      & (strategies["comparison"] == "tolerant")].iloc[0]
    v["accOursTest"] = f"{ours['mean single-valued']:.0%}".replace("%", "\\%")
    rand = strategies[(strategies["strategy"] == "best per attribute") & (strategies["gold subset"] == "random")
                      & (strategies["comparison"] == "tolerant")].iloc[0]
    v["accRandom"] = f"{rand['mean single-valued']:.0%}".replace("%", "\\%")
    v["goldRandomUsed"] = str(int(rand["universities"]))
    every = strategies[(strategies["strategy"] == "best per attribute") & (strategies["gold subset"] == "all")].iloc[0]
    v["goldEvaluated"] = str(int(every["universities"]))
    gold = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "gold_candidates.csv", dtype=str)
    v["goldTotal"] = str(len(gold))
    v["goldConflict"] = str(int((gold["selected_because"] != "random").sum()))
    v["goldRandom"] = str(int((gold["selected_because"] == "random").sum()))
    # list functions for domains: accuracy on the choose half and universities left without a domain
    lists = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "list_functions.csv")
    lists = lists[lists["gold subset"] == "choose"].set_index("function")
    v["domUnion"] = num(lists.at["union", "domains"])
    v["domKTwo"] = num(lists.at["in at least 2 sources", "domains"])
    v["domRor"] = num(lists.at["trust: ROR first", "domains"])
    v["domKTwoEmpty"] = f"{int(lists.at['in at least 2 sources', 'universities without domain']):,}"
    # wrong gold-standard values of the final strategy, per attribute
    every_err = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "fusion_errors.csv",
                            dtype=str).to_dict("records")
    # the five attributes of the gold standard; websites are counted apart (they are judged by the domains)
    errs = [e for e in every_err if e["attribute"] in {"name", "country_code", "city", "founding_year", "domains"}]
    v["fusWrong"] = str(len(errs))
    for attribute, name in [("name", "fusWrongName"), ("country_code", "fusWrongCountry"), ("city", "fusWrongCity"),
                            ("founding_year", "fusWrongYear"), ("domains", "fusWrongDomain")]:
        v[name] = str(sum(e["attribute"] == attribute for e in errs))
    v["fusWrongWebsite"] = str(sum(e["attribute"] == "website" for e in every_err))

    # websites, compared like domains (the host must be an accepted domain), tolerant comparison
    web = strategies[strategies["comparison"] == "tolerant"].set_index(["strategy", "gold subset"])["website"]
    v["webRorChoose"] = num(web[("trust: ROR first", "choose")])
    v["webRorTest"] = num(web[("trust: ROR first", "test")])

    # coordinates: share of fused points within 1 km / 5 km of the gold point (the gold points come from a
    # geocoder and were then checked by hand, see scripts/05_data_fusion/README.md)
    coords = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "coordinate_functions.csv")
    coords = coords.set_index(["function", "gold subset"])
    for function, key in [("trust: Wikidata first", "Wd"), ("median", "Median"), ("trust: ROR first", "Ror")]:
        for column, k in [("within 1 km", "One"), ("within 5 km", "Five")]:
            v[f"coord{key}{k}Choose"] = num(coords.at[(function, "choose"), column])
            v[f"coord{key}{k}Test"] = num(coords.at[(function, "test"), column])
        v[f"coord{key}DistTest"] = f"{coords.at[(function, 'test'), 'median distance km']:.2f}"
    v["coordChooseN"] = str(int(coords.at[("median", "choose"), "universities"]))
    v["coordTestN"] = str(int(coords.at[("median", "test"), "universities"]))
    fusion_gold = pd.read_csv(ROOT / "data" / "golden_set" / "fusion" / "fusion_gold.csv", dtype=str,
                              keep_default_na=False)
    v["coordGold"] = str(int((fusion_gold["latitude"].str.strip() != "").sum()))
    # why ROR's points lose: in most cities with several ROR universities they all share one point
    located = ror[(ror["latitude"].str.strip() != "") & (ror["city"].str.strip() != "")]
    located = located.assign(point=located["latitude"] + "," + located["longitude"])
    cities = located.groupby(["country_code", "city"])["point"].agg(["size", "nunique"])
    several = cities[cities["size"] >= 2]
    v["rorCitiesSeveral"] = f"{len(several):,}"
    v["rorCitiesOnePoint"] = f"{(several['nunique'] == 1).mean():.0%}".replace("%", "\\%")

    lines = [f"\\newcommand{{\\{k}}}{{{x}}}" for k, x in v.items()]
    return "\n".join(lines) + "\n"


def fusion_table():
    # accuracy of each conflict resolution strategy (single-valued attributes, tolerant comparison):
    # per attribute on the half of the gold standard used to choose, then the mean on the test half.
    # The mean is over name, country code, city and founding year (websites are judged by the domains)
    s = pd.read_csv(ROOT / "scripts" / "05_data_fusion" / "results" / "strategies.csv")
    names = {"content-based": "Content-based", "voting": "Voting", "trust: Wikidata first": "Trust, Wikidata first",
             "trust: ROR first": "Trust, ROR first", "voting: ties by trust": "Voting, ties by trust (ours)",
             "best per attribute": "Final: best per attribute"}
    cols = ["name", "country_code", "city", "founding_year", "website", "mean single-valued"]
    rows = []
    for key, label in names.items():
        part = s[s["strategy"] == key].set_index(["comparison", "gold subset"])
        rows.append([label] + [part.at[("tolerant", "choose"), c] for c in cols]
                    + [part.at[("tolerant", "test"), "mean single-valued"],
                       part.at[("strict", "test"), "mean single-valued"]])
    table = pd.DataFrame(rows)
    top = table.iloc[:-1, 1:].max()   # best per column among the five strategies
    lines = []
    for i, r in table.iterrows():
        if i == len(table) - 1:
            lines.append("\\midrule")
        cells = [r[0]] + [best_cell(num(x)) if i < len(table) - 1 and x == top[j] else num(x)
                          for j, x in r.iloc[1:].items()]
        lines.append(" & ".join(cells) + "\\\\")
    return "\n".join(lines) + "\n"


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "fusion.tex").write_text(fusion_table(), encoding="utf-8")
    (OUT / "numbers.tex").write_text(numbers(), encoding="utf-8")
    text, label = matching_table()
    (OUT / "matching.tex").write_text(text, encoding="utf-8")
    (OUT / "cleaning.tex").write_text(cleaning_table(), encoding="utf-8")
    (OUT / "blocking.tex").write_text(blocking_table(), encoding="utf-8")
    (OUT / "groups.tex").write_text(groups_table(), encoding="utf-8")
    print("chosen matchers:", label)
    for f in sorted(OUT.glob("*.tex")):
        print(f"--- {f.name}\n{f.read_text(encoding='utf-8')}")


if __name__ == "__main__":
    main()
