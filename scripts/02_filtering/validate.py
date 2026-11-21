"""Compares the output of the three filters with the records checked by AI agents (<source>/validation/ai_checks.csv).

Prints a table per source and round and writes validation_summary.csv.
Usage: python validate.py (run the three filter.py first)
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data"
SOURCES = {"wikidata": ("wikidata_id", "wikidata_universities.csv"),
           "ror": ("ror_id", "ror_education.csv"),
           "deqar": ("deqar_id", "deqar_institutions.csv")}


def main():
    pd.set_option("display.width", 200)
    rows = []
    for source, (id_col, csv_name) in SOURCES.items():
        checks = pd.read_csv(HERE / source / "validation" / "ai_checks.csv", dtype=str)
        kept = pd.read_csv(DATA / source / "filtered" / csv_name, dtype=str)
        removed = pd.read_csv(DATA / source / "filtered" / "removed.csv", dtype=str)
        status = pd.concat([pd.Series("kept", index=kept[id_col]),
                            pd.Series("removed", index=removed[id_col])])
        checks["now"] = checks[id_col].map(status).fillna("missing")

        print(f"===== {source}: how the current filter treats the checked records (rows = AI verdict)")
        for round_name, part in checks.groupby("round"):
            print(f"-- round {round_name} ({len(part)} records)")
            print(pd.crosstab(part["verdict"], part["now"]).to_string(), "\n")

        checks = checks.drop_duplicates(id_col, keep="last")
        gone = checks[checks["now"] == "removed"]
        # round 3a is a fresh random sample of kept records
        sample = checks[checks["round"].str.startswith("3a") & (checks["now"] == "kept")]
        junk_share = (sample["verdict"] == "junk").mean()
        rows.append({
            "source": source,
            "records": len(kept) + len(removed),
            "removed": len(removed),
            "kept": len(kept),
            "checked removed": len(gone),
            "real among them": int((gone["verdict"] == "real").sum()),
            "share real": round((gone["verdict"] == "real").mean(), 3),
            "fresh kept sample": len(sample),
            "junk in sample": round(junk_share, 3),
            "unsure in sample": round((sample["verdict"] == "unsure").mean(), 3),
            "estimated junk left": round(junk_share * len(kept)),
        })
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    out.to_csv(HERE / "validation_summary.csv", index=False)


if __name__ == "__main__":
    main()
