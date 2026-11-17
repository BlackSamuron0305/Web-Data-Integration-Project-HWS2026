# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026 (University of Mannheim). The report is in
`submission/final-report/`, the project abstract in `submission/project-proposal/`.

## Run order

Python 3.12, `pip install -r requirements.txt`.
Run the scripts from the repository root; each one prints what it writes.

| Step | Script | Result |
|---|---|---|
| Phase I: collect | `scripts/fetch_wikidata.py`, `build_ror_education.py`, `fetch_deqar.py` | `data/*.csv` (already included) |
| Phase I: translate | `scripts/translate_to_xml.py` | `data/*_Mapping.xml` and `data/target.xsd` |

`scripts/common.py` holds the shared code (loading, normalisation); `fetch_dbpedia.py`, `fetch_osm.py` and
`build_the_rankings.py` belong to the sources that were considered and dropped (`old_data/`).

## Hand-made files

- `data/*_Mapping.xml`: the translated data. They started as MapForce output (ROR empty, lists with stray
  spaces, lower-cased names, DEQAR parents missing) and are now written by `scripts/translate_to_xml.py`.
