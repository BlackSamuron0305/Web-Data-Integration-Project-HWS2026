"""Builds the labelled pairs from the hand check: hand_check_labelled_pairs.csv (repo root) ->
data/golden_set/labelled_pairs/<pair>_<split>.csv (300 pairs per set, train / validation / test).

hand_label filled in (match / non_match): that label is used.
hand_label empty (not checked yet): the current label is used for now, and the script says how many.
hand_label unsure: the pair is left out, and the script says which sets drop below 300.

Usage: python from_hand_check.py   (run again after every round of hand checking)
"""
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
HAND = REPO / "hand_check_labelled_pairs.csv"
OUT = REPO / "data" / "golden_set" / "labelled_pairs"


def main():
    df = pd.read_csv(HAND, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    hand = df["hand_label"].str.strip().str.lower()
    unchecked = hand == ""
    df["final"] = hand.where(~unchecked, df["current_label"])
    df = df[df["final"].isin(["match", "non_match"])]   # unsure is left out
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"{(~unchecked).sum()} pairs labelled by hand, {unchecked.sum()} still use their current label")
    for (pair, split), part in df.groupby(["source_pair", "split"]):
        out = pd.DataFrame({"id1": part["A_record_id"], "id2": part["B_record_id"],
                            "label": part["final"] == "match"})
        name = f"{pair.replace('-', '_')}_{split}.csv"
        out.to_csv(OUT / name, index=False)
        warn = "  <- below 300" if len(out) < 300 else ""
        print(f"  {name}: {len(out)} pairs, {int(out['label'].sum())} matches{warn}")


if __name__ == "__main__":
    main()
