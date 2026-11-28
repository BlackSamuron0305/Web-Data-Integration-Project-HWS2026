# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026, University of Mannheim, group 2.

## Contents

| Path | What it is |
|---|---|
| `data/<source>/original/` | the three sources as downloaded (Wikidata, ROR, DEQAR), one CSV each |
| `data/<source>/filtered/` | the cleaned sources, and `removed.csv` with every removed record, its rule and reason |
| `data/golden_set/labelled_pairs/` | the 1,800 labelled pairs for identity resolution (`labelled_pairs.csv`) and the six set files (train, validation and test for Wikidata–ROR and DEQAR–ROR) |
| `data/golden_set/fusion/` | the fusion gold standard (`fusion_gold.csv`, 80 universities) |
| `scripts/01_data_collection/` | download scripts for the three sources |
| `scripts/02_filtering/` | cleaning rules and scripts, and the checks of the cleaning |
| `scripts/03_schema_mapping/` | target schema, MapForce mappings and their XML output |
| `scripts/04_identity_resolution/` | labelled-pair split, blocking, the nine matching approaches, final links and checks |
| `scripts/05_data_fusion/` | data fusion, gold standard scripts and the fused dataset (CSV and XML) |
| `scripts/06_abandoned_approaches/` | scripts and results of approaches that are not part of the pipeline |
| `submission/` | final report (PDF and LaTeX source, `contributions.md`, AI declaration), presentation and project proposal |
| `requirements.txt` | Python packages and the versions used |

Every folder in `scripts/` has a README that lists its files.

## Setup

Python 3.12:

```
pip install -r requirements.txt
```

Run each script from its own folder. Set `PYTHONHASHSEED=0` before identity resolution. The word after a
script is the run: `final` uses the cleaned data, `first_pass` the data as downloaded.

## Run order

| Step | Script | Output |
|---|---|---|
| Collect | `01_data_collection/fetch_wikidata.py`, `fetch_ror.py`, `fetch_deqar.py` | `data/<source>/original/` (already included) |
| Clean | `02_filtering/<source>/filter.py`, then `02_filtering/validation/validate.ipynb` | `data/<source>/filtered/` |
| Schema mapping | `03_schema_mapping/build_lookup_tables.py`, then in MapForce `<source>/filtered/*_Mapping_filtered.mfd` | `03_schema_mapping/<source>/filtered/*_Mapping.xml` |
| Labelled pairs | `04_identity_resolution/gold_standard/split_labelled_pairs.py` | `data/golden_set/labelled_pairs/<pair>_<split>.csv` |
| Blocking | `04_identity_resolution/blocking/blocking.py final` | candidate pairs |
| Matching | the nine approach folders `01_` to `09_` (commands in the step-4 README, approach 8 retrains its model as the weights are not included) | `matching.csv`, best matcher per folder |
| Final links | `global_matching_and_test/final.py final` | `correspondences_*` |
| Checks | `analysis/cutoff_check.py`, `error_analysis.py`, `blocking_effect.py` | `cutoff_check.csv`, `error_analysis.csv`, `blocking_effect.csv` |
| Fusion | `05_data_fusion/fusion.py` | `scripts/05_data_fusion/results/universities_fused.csv` and `.xml` |
| Report | `submission/final-report/scripts/report_tables.py`, `report_figures.py`, `report_numbers.py` (from the repo root) | `submission/final-report/tables/*.tex`, `figures/`, printed checks |
| Presentation plots | `submission/final-presentation/scripts/presentation_plots.py` (from the repo root) | `submission/final-presentation/figures/` |
