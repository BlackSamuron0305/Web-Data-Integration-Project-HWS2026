# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026 (University of Mannheim). The report, the presentation and the
project abstract are in `submission/`.

## Pipeline

| Step | Folder | What it does |
|---|---|---|
| 1. Collect | `scripts/01_data_collection/` | downloads the three sources to `data/<source>/original/` |
| 2. Clean | `scripts/02_filtering/` | removes everything that is not a university ([rules](scripts/02_filtering/rules.md)), writes `data/<source>/filtered/` |
| 3. Schema mapping | `scripts/03_schema_mapping/` | MapForce mappings to the target schema (`target.xsd`), output in `<source>/filtered/` |
| 4. Identity resolution | `scripts/04_identity_resolution/` | labelled pairs, blocking, matching, final links |
| 5. Data fusion | `scripts/05_data_fusion/` | one record per university, written to `results/universities_fused.csv` |
| Abandoned approaches | `scripts/06_abandoned_approaches/` | what we tried and dropped, per step (`01_selection/`, `02_filtering/`), with a README on why |

`submission/final-report/scripts/` recomputes the numbers and figures of the report.

We clean before matching on purpose: the project is about universities, so removing non-universities is
part of the data preparation, even if the matching scores get a little worse.

The ID links between the sources (`ror_id`, `wikidata_id`) are our answer key. They are used to build
and check labels, never inside the pipeline.

## Setup

Python 3.12 (PyDI needs numpy 2.1, which does not install on 3.14):

```
pip install -r requirements.txt
```

Run each script from its own folder; each one prints what it writes. Set `PYTHONHASHSEED=0` before
identity resolution, otherwise ties between equal scores can come out differently between runs.

## Run order

| Step | Script | Output |
|---|---|---|
| Collect | `01_data_collection/fetch_wikidata.py`, `fetch_ror.py`, `fetch_deqar.py` | `data/<source>/original/` (already included) |
| Clean | `02_filtering/<source>/filter.py`, then `02_filtering/validation/validate.ipynb` | `data/<source>/filtered/` |
| Schema mapping | `03_schema_mapping/build_lookup_tables.py`, then in MapForce `<source>/filtered/*_Mapping_filtered.mfd` | `03_schema_mapping/<source>/filtered/*_Mapping.xml` |
| Labelled pairs | `04_identity_resolution/01_labels/split_labelled_pairs.py` | `data/golden_set/labelled_pairs/<pair>_<split>.csv` |
| Blocking | `04_identity_resolution/02_blocking/blocking.py 8` | `candidates/` |
| Matching | `03_rule_based/rule_based.py 8`, `04_ml_based/ml_based.py 8` | `matching.csv` |
| Final links | `05_final/final.py 8`, then `05_final/cutoff_check.py` | `correspondences_*`, `cutoff_check.csv` |
| Fusion | `05_data_fusion/fusion.py` | `results/universities_fused.csv` |
| Report | `submission/final-report/scripts/report_numbers.py`, `report_figures.py` (from the repo root) | `submission/final-report/figures/` |

The number after a script is the round. Round 8 is the final pipeline: cleaned data and a strict final
cut-off (0.7 Wikidata-ROR, 0.55 DEQAR-ROR), because a wrong match is worse for us than a duplicate.
Rounds 1-3 are the earlier passes on the uncleaned data; rounds 4-7 were experiments we dropped.
Folders `06_...` to `11_...` in identity resolution are extra matchers we tried; none replaced the
round-8 matchers. Each step folder has a README on what we did, why, and what worked and what did not.

## Gold standards

- `data/golden_set/labelled_pairs/labelled_pairs.csv`: the 1,800 labelled pairs for identity resolution,
  300 per set (Wikidata-ROR and DEQAR-ROR, each train / validation / test), both records side by side.
  486 were labelled by hand (Chellapuram Keerthan Reddy), the others by two independent passes of AI
  agents (Claude), disagreements settled with web research. Columns `hand_check`, `checked_by` and
  `hand_note` are for the team's check of every label. `split_labelled_pairs.py` writes the six set files.
- `data/golden_set/fusion/fusion_gold.csv`: the fusion gold standard, 50 universities in two or more
  sources (40 with conflicting values, 10 random). Name, country code, city, founding year and domain were
  looked up on the web (sources in `sources`) by AI agents; `checked_by` / `hand_note` for the team's check.

## Checked by AI, not yet by a person

These files were filled in or judged by AI agents (Claude) and still need a check by hand:

- `scripts/02_filtering/validation/<source>/ai_checks.csv`: records checked to validate the cleaning.
- `data/golden_set/labelled_pairs/labelled_pairs.csv`: the 1,314 labels with `labelled_by` = AI agents.
- `data/golden_set/fusion/fusion_gold.csv`: the looked-up values of the fusion gold standard.
- `scripts/04_identity_resolution/05_final/results/ai_check_links_r8.csv`: 6,000 round-8 links.
- `scripts/05_data_fusion/results/ai_check_fused*.csv`: every fused university.
- `scripts/06_abandoned_approaches/01_selection/results/sample_200_ai_checked.csv`: 200 items of a
  wider Wikidata selection we dropped (see `scripts/06_abandoned_approaches/README.md`).

The hand check of 150 records removed by the cleaning is in `scripts/02_filtering/validation/<source>/hand_check_removed.csv`.
