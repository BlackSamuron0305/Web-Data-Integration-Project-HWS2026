"""Writes the result tables of the report (submission/final-report/tables.tex) from the CSV files
in results/, so that every number in the report's tables comes from the code.

Run (after all other scripts): python scripts/make_report_tables.py
"""
import pandas as pd

from common import RESULTS, ROOT

OUT = ROOT / "submission" / "final-report" / "tables"
NAMES = {"wikidata": "Wikidata", "ror": "ROR", "deqar": "DEQAR"}
PAIR_ORDER = ["wikidata-ror", "deqar-ror", "wikidata-deqar"]
PAIR_HEAD = {"wikidata-ror": "Wikidata--ROR", "deqar-ror": "DEQAR--ROR", "wikidata-deqar": "Wikidata--DEQAR"}


def pct(x, digits=1):
    return "--" if pd.isna(x) else f"{100 * x:.{digits}f}"


def n(x):
    return f"{int(x):,}".replace(",", "{,}")


def table(name, caption, label, head, rows, spec, note=None):
    lines = [r"\begin{table}[t]", rf"\caption{{{caption}}}\label{{{label}}}", r"\scriptsize",
             r"\setlength{\tabcolsep}{4pt}", rf"\begin{{tabular}}{{{spec}}}", r"\toprule", head + r"\\", r"\midrule"]
    lines += [r + r"\\" if not r.startswith(r"\midrule") else r for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    if note:
        lines += [r"\smallskip", r"\par\scriptsize " + note]
    lines += [r"\end{table}", ""]
    return "\n".join(lines)


def gold():
    s = pd.read_csv(RESULTS / "gold_standard_summary.csv")
    t = s.groupby(["pair", "kind"])["pairs"].sum().unstack(fill_value=0)
    rows = []
    for p in PAIR_ORDER:
        r = t.loc[p]
        rows.append(" & ".join([PAIR_HEAD[p], n(r["match"]), n(r["hard"]), n(r["random"]), n(r["part_of"]),
                                n(r.get("predecessor", 0)), n(r["same_name_other_country"])]))
    return table("gold", "Gold standard: matches and non-matches by kind", "tab:gold",
                 r"Pair & Matches & Hard & Random & Part of & Predecessor & Same name",
                 rows, "lrrrrrr")


def blocking():
    b = pd.read_csv(RESULTS / "blocking.csv")
    order = list(dict.fromkeys(b["strategy"]))
    rows = []
    for s in order:
        cells = [s.replace("standard:", "Standard:").replace("token:", "Token:").replace("sorted", "Sorted")
                 .replace("token (scoped)", "Token (scoped)")]
        for p in PAIR_ORDER:
            r = b[(b["pair"] == p) & (b["strategy"] == s)].iloc[0]
            if pd.isna(r["pair_completeness"]):
                cells.append(f"-- & {r['candidates'] / 1e6:.0f}M")
            else:
                cells.append(f"{pct(r['pair_completeness'])} & {r['candidates'] / 1e3:,.0f}k".replace(",", "{,}"))
        rows.append(" & ".join(cells))
    head = "Strategy & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{{PAIR_HEAD[p]}}}" for p in PAIR_ORDER)
    head += r"\\ & " + " & ".join("PC (\\%) & Cand." for _ in PAIR_ORDER)
    return table("blocking", "Blocking: pair completeness (PC) and number of candidate pairs", "tab:blocking",
                 head, rows, "lrrrrrr")


def matching():
    m = pd.read_csv(RESULTS / "matching_experiments.csv")
    short = {
        "name_jaro_winkler": "Name, Jaro-Winkler", "name_levenshtein": "Name, Levenshtein",
        "name_jaccard": "Name, Jaccard", "name_sorensen_dice": "Name, Sørensen-Dice",
        "names_best_jaro_winkler": "All names, best match, Jaro-Winkler",
        "names_best_jaccard": "All names, best match, Jaccard",
    }
    m["label"] = m["config"].map(lambda c: short.get(c, c.split(" {")[0]))
    rows, last = [], None
    for _, r in m[m["pair"] == PAIR_ORDER[0]].iterrows():
        if last is not None and r["group"] != last:
            rows.append(r"\midrule")
        last = r["group"]
        cells = [r["label"]]
        for p in PAIR_ORDER:
            q = m[(m["pair"] == p) & (m["label"] == r["label"])].iloc[0]
            cells.append(f"{pct(q['test_precision'])} & {pct(q['test_recall'])} & {pct(q['test_f1'])}")
        rows.append(" & ".join(cells))
    head = "Matcher & " + " & ".join(rf"\multicolumn{{3}}{{c}}{{{PAIR_HEAD[p]}}}" for p in PAIR_ORDER)
    head += r"\\ & " + " & ".join("P & R & F1" for _ in PAIR_ORDER)
    return table("matching", "Matching on the test part of the gold standard (precision, recall, F1 in \%); "
                 "thresholds and weights tuned on the development part", "tab:matching", head, rows, "lrrrrrrrrr")


def final():
    f = pd.read_csv(RESULTS / "matching_final.csv")
    t = pd.read_csv(RESULTS / "threshold_analysis.csv")
    rows = []
    for p in PAIR_ORDER:
        for name in ["none (all pairs above threshold)", "greedy one-to-one", "maximum bipartite matching",
                     "stable matching"]:
            r = f[(f["pair"] == p) & (f["post_clustering"] == name)].iloc[0]
            label = "no post-clustering" if name.startswith("none") else name.capitalize()
            rows.append(" & ".join([PAIR_HEAD[p] if name.startswith("none") else "", label, n(r["correspondences"]),
                                    pct(r["test_precision"]), pct(r["test_recall"]), pct(r["test_f1"])]))
    t1 = table("post", "Post-clustering of the correspondences (threshold of the matcher, test part of the gold standard)",
               "tab:post", r"Pair & Post-clustering & Correspondences & P & R & F1", rows, "llrrrr")
    rows = []
    for p in PAIR_ORDER:
        for th in [0.5, 0.7, 0.8, 0.9]:
            r = t[(t["pair"] == p) & (t["threshold"] == th)].iloc[0]
            rows.append(" & ".join([PAIR_HEAD[p] if th == 0.5 else "", f"{th:.1f}", n(r["correspondences"]),
                                    pct(r["test_precision"]), pct(r["test_recall"]), pct(r["test_f1"]),
                                    n(r["manual_sample_pairs"]), pct(r["manual_sample_precision"])]))
    t2 = table("thr", "Threshold analysis after greedy one-to-one matching: gold standard (test part) and hand-checked "
               "sample of the correspondences that are not in the gold standard", "tab:threshold",
               r"Pair & Threshold & Corr. & P & R & F1 & Sample & Sample precision", rows, "lrrrrrrr")
    return t1 + "\n" + t2


def fusion():
    s = pd.read_csv(RESULTS / "fusion_strategies.csv")
    heads = {"name": "Name", "country_code": "Country", "city": "City", "founding_year": "Founding year",
             "domain": "Domain"}
    rows = [" & ".join([r["strategy"].replace("PyDI default", "PyDI default")] + [pct(r[c]) for c in heads])
            for _, r in s.iterrows()]
    return table("fusion", "Accuracy (\\%) of the fusion strategies on the 39 entities of the fusion gold standard",
                 "tab:fusion", "Strategy & " + " & ".join(heads.values()), rows, "lrrrrr")


def completeness():
    c = pd.read_csv(RESULTS / "fusion_completeness.csv").set_index("attribute")
    attrs = [("alt_names", "Alternative names"), ("acronyms", "Acronyms"), ("country_code", "Country code"),
             ("city", "City"), ("region", "Region"), ("domain", "Web domain"), ("founding_year", "Founding year"),
             ("latitude", "Coordinates"), ("types", "Institution types"), ("students", "Number of students"),
             ("memberships", "Memberships"), ("parent", "Parent institutions"), ("qa_reports", "QA reports")]
    rows = []
    for a, label in attrs:
        r = c.loc[a]
        best = max(r["multi_wikidata"], r["multi_ror"], r["multi_deqar"])
        rows.append(" & ".join([label, pct(r["wikidata"], 0), pct(r["ror"], 0), pct(r["deqar"], 0), pct(r["fused"], 0),
                                pct(best, 0), pct(r["multi_fused"], 0)]))
    return table("complete", "Share of entities with a value (\\%): source datasets and fused dataset over all records, "
                 "and best single source versus fused record for the entities that are in at least two sources",
                 "tab:completeness",
                 r"Attribute & Wikidata & ROR & DEQAR & Fused & Best source & Fused \\ & \multicolumn{4}{c}{all entities}"
                 r" & \multicolumn{2}{c}{entities in $\geq 2$ sources}", rows, "lrrrrrr")


def main():
    OUT.mkdir(exist_ok=True)
    tables = {"gold": gold(), "blocking": blocking(), "matching": matching(), "final": final(),
              "fusion": fusion(), "completeness": completeness()}
    for name, text in tables.items():
        (OUT / f"{name}.tex").write_text(text, encoding="utf-8")
    print("written", ", ".join(tables), "to", OUT)


if __name__ == "__main__":
    main()
