"""Phase I, data translation: writes the three datasets in the integrated schema.

Result: one XML file per source (data/Wikidata_Mapping.xml, ROR_Mapping.xml,
deqar_Mapping.xml) plus the schema file data/target.xsd. The element structure is the one of the
first MapForce mapping, which this script replaces. Corrections against that mapping: ROR is
translated (its file was empty), lists are split and trimmed (alternative names, memberships,
institution types), names and countries keep their spelling (the mapping lower-cased them),
DEQAR parent institutions, the region and the status of ROR are mapped, and the schema is
referenced relatively instead of by a path on one laptop.

Run: python scripts/translate_to_xml.py
"""
import xml.etree.ElementTree as ET

import pandas as pd

from common import DATA, FILES, SCHEMA, load_schema

OUT = DATA
XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("xsi", XSI)


def put(parent, tag, value):
    """Adds <tag>value</tag> unless the value is missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    el = ET.SubElement(parent, tag)
    el.text = str(int(value)) if isinstance(value, float) and float(value).is_integer() and tag in (
        "foundingYear", "closureYear", "numberOfStudents", "numberOfQAReports") else str(value)
    return el


def put_list(parent, outer, inner, values):
    if values:
        o = ET.SubElement(parent, outer)
        for v in values:
            ET.SubElement(o, inner).text = v


def record(root, r):
    e = ET.SubElement(root, "institution")
    put(e, "id", r.id)
    put(e, "name", r.name)
    put_list(e, "alternativeNames", "alternativeName", r.alt_names)
    put_list(e, "acronyms", "acronym", r.acronyms)
    loc = ET.SubElement(e, "location")
    for tag, v in (("country", r.country), ("countryCode", r.country_code), ("region", r.region),
                   ("city", r.city), ("latitude", r.latitude), ("longitude", r.longitude)):
        put(loc, tag, v)
    web = ET.SubElement(e, "web")
    put(web, "website", r.website)
    put_list(web, "domains", "domain", r.domains)
    life = ET.SubElement(e, "lifecycle")
    put(life, "foundingYear", r.founding_year)
    put(life, "closureYear", r.closure_year)
    put_list(life, "history", "event", r.history)
    put_list(e, "parentInstitutions", "parentInstitution", r.parent)
    put_list(e, "institutionTypes", "institutionType", r.types)
    put(e, "numberOfStudents", r.students)
    put_list(e, "memberships", "membership", r.memberships)
    qa = ET.SubElement(e, "qualityAssurance")
    put(qa, "numberOfQAReports", r.qa_reports)
    put(qa, "lastQAReportDate", r.last_qa_report)
    put(e, "status", r.status)
    for parent in (loc, web, life, qa):
        if len(parent) == 0:
            e.remove(parent)


def write(df, path):
    root = ET.Element("institutions", {f"{{{XSI}}}noNamespaceSchemaLocation": "target.xsd"})
    for r in df[SCHEMA].itertuples(index=False):
        record(root, r)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)


XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified">
	<xs:element name="institutions">
		<xs:complexType><xs:sequence>
			<xs:element name="institution" maxOccurs="unbounded">
				<xs:complexType><xs:sequence>
					<xs:element name="id" type="xs:string"/>
					<xs:element name="name" type="xs:string" minOccurs="0"/>
					<xs:element name="alternativeNames" type="list" minOccurs="0"/>
					<xs:element name="acronyms" type="list" minOccurs="0"/>
					<xs:element name="location" minOccurs="0"><xs:complexType><xs:sequence>
						<xs:element name="country" type="xs:string" minOccurs="0"/>
						<xs:element name="countryCode" type="xs:string" minOccurs="0"/>
						<xs:element name="region" type="xs:string" minOccurs="0"/>
						<xs:element name="city" type="xs:string" minOccurs="0"/>
						<xs:element name="latitude" type="xs:decimal" minOccurs="0"/>
						<xs:element name="longitude" type="xs:decimal" minOccurs="0"/>
					</xs:sequence></xs:complexType></xs:element>
					<xs:element name="web" minOccurs="0"><xs:complexType><xs:sequence>
						<xs:element name="website" type="xs:string" minOccurs="0"/>
						<xs:element name="domains" type="list" minOccurs="0"/>
					</xs:sequence></xs:complexType></xs:element>
					<xs:element name="lifecycle" minOccurs="0"><xs:complexType><xs:sequence>
						<xs:element name="foundingYear" type="xs:integer" minOccurs="0"/>
						<xs:element name="closureYear" type="xs:integer" minOccurs="0"/>
						<xs:element name="history" type="list" minOccurs="0"/>
					</xs:sequence></xs:complexType></xs:element>
					<xs:element name="parentInstitutions" type="list" minOccurs="0"/>
					<xs:element name="institutionTypes" type="list" minOccurs="0"/>
					<xs:element name="numberOfStudents" type="xs:integer" minOccurs="0"/>
					<xs:element name="memberships" type="list" minOccurs="0"/>
					<xs:element name="qualityAssurance" minOccurs="0"><xs:complexType><xs:sequence>
						<xs:element name="numberOfQAReports" type="xs:integer" minOccurs="0"/>
						<xs:element name="lastQAReportDate" type="xs:string" minOccurs="0"/>
					</xs:sequence></xs:complexType></xs:element>
					<xs:element name="status" type="xs:string" minOccurs="0"/>
				</xs:sequence></xs:complexType>
			</xs:element>
		</xs:sequence></xs:complexType>
	</xs:element>
	<xs:complexType name="list"><xs:sequence>
		<xs:any minOccurs="0" maxOccurs="unbounded" processContents="skip"/>
	</xs:sequence></xs:complexType>
</xs:schema>
"""


if __name__ == "__main__":
    data, _ = load_schema()
    for name, df in data.items():
        write(df, OUT / FILES[name])
        print(f"{name}: {len(df)} institutions -> data/{FILES[name]}")
    (OUT / "target.xsd").write_text(XSD, encoding="utf-8")
    print("schema -> data/target.xsd")
