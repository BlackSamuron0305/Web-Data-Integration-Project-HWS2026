# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026 (University of Mannheim). The report is in
`submission/final-report/`, the project abstract in `submission/project-proposal/`.

## Run order

Python 3.12 (PyDI pins numpy 2.1, which has no wheel for 3.14), `pip install -r requirements.txt`.
Run the scripts from the repository root; each one prints what it writes.

| Step | Script | Result |
|---|---|---|
| Phase I: collect | `scripts/fetch_wikidata.py`, `build_ror_education.py`, `fetch_deqar.py` | `data/*.csv` (already included) |
| Phase I: translate | `scripts/translate_to_xml.py` | `data/*_Mapping.xml` and `data/target.xsd` |
| Phase II: blocking | `scripts/phase2_blocking.py` | `results/blocking.csv`, candidate pairs in `results/cache/` |
| Phase II: gold standard | `scripts/gold_standard.py` | `data/gold_standard/gold_*.csv` |
| Phase II: matching experiments | `scripts/phase2_matching.py` | `results/matching_experiments.csv`, `matching_best.json` |
| Phase II: final matching | `scripts/phase2_final.py` | `data/correspondences/all_*.csv` |
| Phase II: threshold | `scripts/phase2_threshold.py` | `data/correspondences/corr_*.csv`, `results/threshold_analysis.csv` |
| Phase II: analysis | `scripts/analysis_errors.py` | feature importance, missed matches |
| Phase III: fusion gold standard | `scripts/build_fusion_gold.py` | `data/gold_standard/fusion_gold.csv` |
| Phase III: fusion | `scripts/phase3_fusion.py` | `data/fused/universities_fused.csv`, `results/fusion_*.csv` |
| Report tables | `scripts/make_report_tables.py` | `submission/final-report/tables/*.tex` |

`scripts/common.py` (loading, normalisation, links), `blocking.py`, `matching.py` and
`fusion_strategies.py` hold the shared code; `fetch_dbpedia.py`, `fetch_osm.py` and
`build_the_rankings.py` belong to the sources that were considered and dropped (`old_data/`).

## Hand-made files

- `data/gold_standard/manual_check_*.csv`: 60 correspondences per dataset pair that are not in the gold
  standard, judged by hand (column `label`, 1 = same institution).
- `data/gold_standard/fusion_gold.csv`: expected values of 39 well-known universities, compiled by hand
  (`scripts/build_fusion_gold.py` holds the list).
- `data/*_Mapping.xml`: the translated data. They started as MapForce output (ROR empty, lists with stray
  spaces, lower-cased names, DEQAR parents missing) and are now written by `scripts/translate_to_xml.py`.
