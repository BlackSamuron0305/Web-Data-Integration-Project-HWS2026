"""Writes the fusion gold standard in the target schema (like gold.xml of the fusion exercise) and checks it
against target.xsd.  Usage: python gold_to_xml.py

Input:  data/golden_set/fusion/fusion_gold.csv (the file the team looks values up in and checks)
Output: data/golden_set/fusion/fusion_gold.xml (the file fusion.py evaluates against)

The target schema holds one city and one founding year per university, so only the main value is kept;
the other accepted names go to alternativeNames and the other accepted domains to domains.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from lxml import etree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOLD = ROOT / "data" / "golden_set" / "fusion"
XSD = ROOT / "scripts" / "03_schema_mapping" / "target.xsd"


def split(value):
    return [x.strip() for x in str(value).split("|") if x.strip()]


def add(parent, tag, text):
    if str(text).strip():
        ET.SubElement(parent, tag).text = str(text).strip()


def main():
    gold = pd.read_csv(GOLD / "fusion_gold.csv", dtype=str, keep_default_na=False)
    root = ET.Element("institutions")
    for _, row in gold.iterrows():
        # element order as in target.xsd: id, name, alternativeNames, location, web, lifecycle
        inst = ET.SubElement(root, "institution")
        add(inst, "id", row["anchor_id"])
        add(inst, "name", row["name"])
        if split(row["name_alternatives"]):
            names = ET.SubElement(inst, "alternativeNames")
            for name in split(row["name_alternatives"]):
                add(names, "alternativeName", name)
        location = ET.SubElement(inst, "location")
        add(location, "countryCode", row["country_code"])
        add(location, "city", row["city"])
        if split(row["domain"]):
            domains = ET.SubElement(ET.SubElement(inst, "web"), "domains")
            for domain in split(row["domain"]) + split(row["domain_alternatives"]):
                add(domains, "domain", domain)
        if row["founding_year"].strip():
            add(ET.SubElement(inst, "lifecycle"), "foundingYear", row["founding_year"])

    ET.indent(root, space="\t")
    out = GOLD / "fusion_gold.xml"
    ET.ElementTree(root).write(out, encoding="UTF-8", xml_declaration=True)

    schema = etree.XMLSchema(etree.parse(str(XSD)))
    doc = etree.parse(str(out))
    if not schema.validate(doc):
        raise SystemExit(f"{out.name} does not match target.xsd:\n{schema.error_log}")
    print(f"{len(gold)} universities written to {out.relative_to(ROOT)}, valid against target.xsd")


if __name__ == "__main__":
    main()
