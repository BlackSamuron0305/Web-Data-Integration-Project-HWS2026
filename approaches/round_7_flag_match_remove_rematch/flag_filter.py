"""Round 7 (flag, match, remove, match again): removes the flagged Wikidata records and, through the
confident links of run 1, their partners in ROR and DEQAR, then writes the XML input for run 2.
Run with: python flag_filter.py (after the Wikidata filter and final.py 3)"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
IR = HERE.parent
sys.path.insert(0, str(IR))
from common import DATA, FILES

RESULTS = HERE / "results"
FLAGS = IR.parents[1] / "scripts" / "02_filtering" / "wikidata" / "wikidata_flagged.csv"
RUN1 = IR / "05_final" / "results"
CONFIDENT = 0.9   # below 0.9 the links were mostly wrong in an earlier check
OUTPUT = {"wikidata": "Wikidata_Mapping", "ror": "ROR_Mapping", "deqar": "deqar_Mapping"}


def write_xml(name, gone):
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    tree = ET.parse(DATA / FILES[name])
    root = tree.getroot()
    removed = 0
    for inst in list(root):
        if inst.findtext("id") in gone:
            root.remove(inst)
            removed += 1
    folder = RESULTS / name
    folder.mkdir(parents=True, exist_ok=True)
    tree.write(folder / f"{OUTPUT[name]}_flagfiltered.xml", encoding="UTF-8", xml_declaration=True)
    return len(root), removed


def main():
    RESULTS.mkdir(exist_ok=True)
    flags = pd.read_csv(FLAGS, dtype=str)
    flags = flags[flags["flag_rule"].notna()]
    flags["id"] = "wikidata_" + flags["wikidata_id"]
    # only the match score decides, the ID links are the answer key and can't be used here
    wr = pd.read_csv(RUN1 / "correspondences_wikidata_ror_r3.csv")
    wr = wr[wr["score"] >= CONFIDENT]
    dr = pd.read_csv(RUN1 / "correspondences_deqar_ror_r3.csv")
    dr = dr[dr["score"] >= CONFIDENT]

    rows = [dict(source="wikidata", id=i, rule=r, reason=s, via="own flag")
            for i, r, s in zip(flags["id"], flags["flag_rule"], flags["flag_reason"])]

    # carry the flag over to the ROR partner, but not for duplicates (rule 5), their partner is a real university
    carried = flags[flags["flag_rule"] != "5"].set_index("id")
    ror_gone = {}
    for w, r in zip(wr["id1"], wr["id2"]):
        if w in carried.index:
            ror_gone[r] = (carried.at[w, "flag_rule"], carried.at[w, "flag_reason"], w)
    rows += [dict(source="ror", id=r, rule=x[0], reason=x[1], via=x[2]) for r, x in ror_gone.items()]

    # and from ROR on to DEQAR
    deqar_gone = {}
    for d, r in zip(dr["id1"], dr["id2"]):
        if r in ror_gone:
            deqar_gone[d] = (ror_gone[r][0], ror_gone[r][1], r)
    rows += [dict(source="deqar", id=d, rule=x[0], reason=x[1], via=x[2]) for d, x in deqar_gone.items()]

    removed = pd.DataFrame(rows)
    removed.to_csv(RESULTS / "removed.csv", index=False)

    print(f"confident links of run 1: wikidata-ror {len(wr):,}, deqar-ror {len(dr):,}")
    for name in FILES:
        left, n = write_xml(name, set(removed.loc[removed["source"] == name, "id"]))
        print(f"  {name}: removed {n:,}, left {left:,}")
    print(removed.groupby(["source", "rule"]).size().to_string())


if __name__ == "__main__":
    main()
