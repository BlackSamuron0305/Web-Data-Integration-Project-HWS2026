"""Error analysis of the final run on the test pairs: every pair the final links get wrong.

For a missed match it says where the pair was lost, step by step:
  not a candidate        blocking never compared the two records
  below the threshold    the matcher scored it below its threshold (validation-chosen)
  lost to another link   one-to-one matching kept a higher-scored link of one of the two records
  below the cut-off      removed by the final cut-off (chosen on validation by final.py, results/cutoff_final.csv)
For both kinds of error it adds what the two records share (name similarity, country, city, web domain,
founding year, campus/faculty words) and the kind of pair in the labelled set, so the errors can be grouped.

Run after final.py final, from this folder:  python error_analysis.py
Writes results/error_analysis.csv and prints the counts.
"""
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "global_matching_and_test"))
from common import GOLD, PAIRS, candidates, labels, load_all  # noqa: E402
from final import best_matcher  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
FINAL = HERE.parent / "global_matching_and_test" / "results"
PART = ("campus", "faculty", "school of", "college of", "branch", "department", "institute of", "center",
        "centre", "hospital", "academy of sciences", "system")


def pairs_of(df):
    return set(zip(df["id1"], df["id2"]))


def main():
    data = load_all("final")
    kinds = pd.read_csv(GOLD / "labelled_pairs" / "labelled_pairs.csv", dtype=str, keep_default_na=False,
                        encoding="utf-8-sig")
    kind = dict(zip(zip(kinds["A_record_id"], kinds["B_record_id"]), kinds["kind"]))
    rows = []
    for a, b in PAIRS:
        pair = f"{a}-{b}"
        L, R = data[a].set_index("id"), data[b].set_index("id")
        test = labels(a, b, "test", "final")
        cand = pairs_of(candidates(a, b, "final"))
        _, scored = best_matcher(a, b, "final")                 # matcher output above its threshold
        above = pairs_of(scored)
        before = pd.read_csv(FINAL / f"correspondences_{a}_{b}_final_before_cutoff.csv")
        final = pd.read_csv(FINAL / f"correspondences_{a}_{b}_final.csv")
        one_to_one, final_pairs = pairs_of(before), pairs_of(final)
        taken = set(before["id1"]) | set(before["id2"])
        score = dict(zip(zip(scored["id1"], scored["id2"]), scored["score"]))

        for x, y, label in test[["id1", "id2", "label"]].values:
            linked = (x, y) in final_pairs
            if label == linked:
                continue
            if label:
                error = "missed match"
                if (x, y) not in cand:
                    where = "not a candidate"
                elif (x, y) not in above:
                    where = "below the threshold"
                elif (x, y) not in one_to_one:
                    where = "lost to another link" if (x in taken or y in taken) else "lost in one-to-one matching"
                else:
                    where = "below the cut-off"
            else:
                error, where = "wrong match", ""
            r1, r2 = L.loc[x], R.loc[y]
            names1, names2 = r1["names"] or [""], r2["names"] or [""]
            sim = max(fuzz.token_sort_ratio(u, v) for u in names1 for v in names2) / 100
            words = " ".join(names1 + names2)
            rows.append({
                "pair": pair, "error": error, "lost_at": where, "id1": x, "id2": y,
                "name1": r1["name"], "name2": r2["name"], "score": score.get((x, y), ""),
                "kind": kind.get((x, y), ""), "name_similarity": round(sim, 2),
                "same_country": r1["cc"] == r2["cc"] if r1["cc"] and r2["cc"] else "",
                "same_city": r1["city_norm"] == r2["city_norm"] if r1["city_norm"] and r2["city_norm"] else "",
                "same_domain": bool(set(r1["domains"]) & set(r2["domains"])) if r1["domains"] and r2["domains"] else "",
                "same_year": r1["year"] == r2["year"] if pd.notna(r1["year"]) and pd.notna(r2["year"]) else "",
                "part_word": any(w in words for w in PART),
            })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "error_analysis.csv", index=False)
    print(f"{len(out)} test errors -> results/error_analysis.csv")
    print(out.groupby(["pair", "error"]).size().to_string())
    print("\nmissed matches, where they were lost:")
    print(out[out["error"] == "missed match"].groupby(["pair", "lost_at"]).size().to_string())
    print("\nerrors by kind of labelled pair:")
    print(out.groupby(["error", "kind"]).size().to_string())


if __name__ == "__main__":
    main()
