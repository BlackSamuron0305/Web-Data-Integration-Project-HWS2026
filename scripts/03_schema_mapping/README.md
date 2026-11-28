# Step 3: Schema mapping

This folder holds the target schema, the MapForce mappings of the three sources, their XML outputs and the lookup tables the mappings read.

## Contents

| Path | What it is |
|---|---|
| `target.xsd` | the target schema: root `<institutions>`, one `<institution>` per record with an `id` (source prefix and source key, e.g. `ror_00003ef66`) and 21 optional attributes |
| `functions.mfd` | MapForce function library the three mappings share (list splitting and trimming, domain from URL) |
| `build_lookup_tables.py` | reads the CSVs in `data/<source>/original/` and writes the two lookup tables below |
| `ror/ror_names.csv` | lookup table, one row per ROR record (`ror_id`, `name`), used to turn parent ROR ids into names |
| `deqar/country_codes.csv` | lookup table, one row per DEQAR country name (`country`, `code`), 135 names |
| `<source>/original/<Source>_Mapping.mfd` | mapping of the downloaded CSV in `data/<source>/original/` |
| `<source>/original/<Source>_Mapping.xml` | its output, one `<institution>` per source record |
| `<source>/filtered/<Source>_Mapping_filtered.mfd` | the same mapping, reading the cleaned CSV in `data/<source>/filtered/` |
| `<source>/filtered/<Source>_Mapping.xml` | its output, the input of identity resolution and fusion |

`<source>` / `<Source>` is `ror` / `ROR`, `wikidata` / `Wikidata` or `deqar` / `deqar`.

## Inputs and outputs of the mappings

| Mapping | Reads | Writes |
|---|---|---|
| `ror/*/ROR_Mapping*.mfd` | `data/ror/<run>/ror_education.csv`, `ror/ror_names.csv` | `ror/<run>/ROR_Mapping.xml` |
| `wikidata/*/Wikidata_Mapping*.mfd` | `data/wikidata/<run>/wikidata_universities.csv` | `wikidata/<run>/Wikidata_Mapping.xml` |
| `deqar/*/deqar_Mapping*.mfd` | `data/deqar/<run>/deqar_institutions.csv`, `deqar/country_codes.csv` | `deqar/<run>/deqar_Mapping.xml` |

`<run>` is `original` or `filtered`. All paths in the `.mfd` files are relative, so the repository can sit anywhere.

## Requirements

- Python 3.12 with pandas (see `requirements.txt` in the repository root) for `build_lookup_tables.py`.
- Altova MapForce to open and run the `.mfd` mappings.
- The lookup tables are UTF-8 with BOM, CRLF line ends and every field in quotes, as MapForce reads them.
- The XML outputs are UTF-8 and point to `../../target.xsd` for validation.

## Run

From this folder:

    python build_lookup_tables.py     # writes ror/ror_names.csv and deqar/country_codes.csv

Then open each `.mfd` in MapForce and run it. Each one writes its `*_Mapping.xml` next to it.
The pipeline needs only the three `<source>/filtered/*_Mapping_filtered.mfd`.
