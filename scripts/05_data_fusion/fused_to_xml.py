"""Writes the fused dataset in the target schema and checks it against target.xsd.  Usage: python fused_to_xml.py

Input:  results/universities_fused.csv (fusion.py writes it and then calls this script)
Output: results/universities_fused.xml

Both files hold the same universities and values. The XML has the ID and the 21 attributes of target.xsd.
The ID is the ROR ID wherever the university has a ROR record, as in the fusion gold standard, so the two
files can be matched by ID. Every link goes to a ROR record, so a university without one has a single
record, and its ID is that record's. (The CSV's _id is PyDI's choice and is the DEQAR ID in every group
with a DEQAR record.) The schema has no place for the records and sources of a fused university, so that
provenance is only in the CSV (_fusion_sources, _fusion_source_datasets, sources).
"""
import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from lxml import etree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
XSD = ROOT / "scripts" / "03_schema_mapping" / "target.xsd"

# element path in target.xsd -> column of the CSV, in the order of the schema. The last element of a list
# attribute (alternativeNames/alternativeName) is repeated once per value
SCHEMA = [
    ("id", "_id"),
    ("name", "name"),
    ("alternativeNames/alternativeName", "alt_names"),
    ("acronyms/acronym", "acronyms"),
    ("location/country", "country"),
    ("location/countryCode", "country_code"),
    ("location/region", "region"),
    ("location/city", "city"),
    ("location/latitude", "latitude"),
    ("location/longitude", "longitude"),
    ("web/website", "website"),
    ("web/domains/domain", "domains"),
    ("lifecycle/foundingYear", "founding_year"),
    ("lifecycle/closureYear", "closure_year"),
    ("lifecycle/history/event", "history"),
    ("parentInstitutions/parentInstitution", "parents"),
    ("institutionTypes/institutionType", "types"),
    ("numberOfStudents", "students"),
    ("memberships/membership", "memberships"),
    ("qualityAssurance/numberOfQAReports", "qa_reports"),
    ("qualityAssurance/lastQAReportDate", "qa_last_report"),
    ("status", "status"),
]
LISTS = {"alt_names", "acronyms", "domains", "history", "parents", "types", "memberships"}
PROVENANCE = {"_fusion_sources", "_fusion_source_datasets", "sources"}


def values(text, is_list):
    """The values of one cell. The CSV writes a list as ['a', 'b'], and a list with one value as a plain a."""
    text = text.strip()
    if not text:
        return []
    if is_list and text.startswith("[") and text.endswith("]"):
        return [str(x).strip() for x in ast.literal_eval(text) if str(x).strip()]
    return [text]


def university_id(row):
    """The ROR ID if the university has a ROR record, else the ID of its only record."""
    records = ast.literal_eval(row["_fusion_sources"])
    ror = [r for r in records if r.startswith("ror_")]
    if not ror and len(records) != 1:
        raise SystemExit(f"{row['_id']}: several records but none from ROR: {records}")
    return ror[0] if ror else records[0]


def institution(row):
    inst = ET.Element("institution")
    for path, column in SCHEMA:
        found = [university_id(row)] if column == "_id" else values(row[column], column in LISTS)
        if not found:
            continue
        *groups, leaf = path.split("/")
        parent = inst
        for tag in groups:
            # a group (location, web, ...) is written once, when its first value comes
            parent = parent.find(tag) if parent.find(tag) is not None else ET.SubElement(parent, tag)
        for value in found:
            ET.SubElement(parent, leaf).text = value
    return inst


def main():
    fused = pd.read_csv(RESULTS / "universities_fused.csv", dtype=str, keep_default_na=False)
    missing = {c for _, c in SCHEMA} - set(fused.columns)
    unmapped = set(fused.columns) - {c for _, c in SCHEMA} - PROVENANCE
    if missing or unmapped:
        raise SystemExit(f"CSV and target.xsd differ: missing {sorted(missing)}, not in the schema {sorted(unmapped)}")

    root = ET.Element("institutions")
    for _, row in fused.iterrows():
        root.append(institution(row))
    ET.indent(root, space="\t")
    out = RESULTS / "universities_fused.xml"
    ET.ElementTree(root).write(out, encoding="UTF-8", xml_declaration=True)

    schema = etree.XMLSchema(etree.parse(str(XSD)))
    doc = etree.parse(str(out))
    if not schema.validate(doc):
        raise SystemExit(f"{out.name} does not match target.xsd:\n{schema.error_log}")
    print(f"{len(fused):,} universities written to {out.relative_to(ROOT)}, valid against target.xsd")


if __name__ == "__main__":
    main()
