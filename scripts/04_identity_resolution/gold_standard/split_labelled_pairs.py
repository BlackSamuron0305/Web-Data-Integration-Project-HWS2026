"""Writes the train / validation / test files from the labelled pairs:
data/golden_set/labelled_pairs/labelled_pairs.csv -> data/golden_set/labelled_pairs/<pair>_<split>.csv

labelled_pairs.csv holds 1,800 pairs, 300 per set (Wikidata-ROR and DEQAR-ROR, each train / validation /
test). Column label (match / non_match) is what the matchers use; pairs labelled unsure are left out and the
script says which sets then drop below 300. labelled_by says which team member labelled the pair by hand.

Usage: python split_labelled_pairs.py
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[3] / "data" / "golden_set" / "labelled_pairs"


def main():
    df = pd.read_csv(OUT / "labelled_pairs.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    label = df["label"].str.strip().str.lower()
    missing = (label == "").sum()
    if missing:
        raise SystemExit(f"{missing} pairs have no label yet")
    df = df[label.isin(["match", "non_match"])].assign(label=label)
    for (pair, split), part in df.groupby(["source_pair", "split"]):
        out = pd.DataFrame({"id1": part["A_record_id"], "id2": part["B_record_id"], "label": part["label"] == "match"})
        name = f"{pair.replace('-', '_')}_{split}.csv"
        out.to_csv(OUT / name, index=False)
        warn = "  <- below 300" if len(out) < 300 else ""
        print(f"  {name}: {len(out)} pairs, {int(out['label'].sum())} matches{warn}")


if __name__ == "__main__":
    main()
