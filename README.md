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
| 5. Data fusion | `scripts/05_data_fusion/` | one record per university, written to `results/universities_fused.csv` and, in the target schema, `results/universities_fused.xml` |
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
| Labelled pairs | `04_identity_resolution/gold_standard/split_labelled_pairs.py` | `data/golden_set/labelled_pairs/<pair>_<split>.csv` |
| Blocking | `04_identity_resolution/blocking/blocking.py final` | `candidates/` |
| Matching | the nine approach folders `01_` to `09_` (string similarity, TF-IDF, embeddings, weight search, machine learning, more similarity measures, more learners, fine-tuned language model, local LLM); commands in the step-4 README | `matching.csv`, best matcher per folder |
| Final links | `global_matching_and_test/final.py final` (best of the nine by validation F1, one-to-one, cut-off, test) | `correspondences_*` |
| Checks | `analysis/cutoff_check.py`, `error_analysis.py`, `blocking_effect.py` | `cutoff_check.csv`, `error_analysis.csv`, `blocking_effect.csv` |
| Fusion | `05_data_fusion/fusion.py` | `results/universities_fused.csv`, `results/universities_fused.xml` |
| Report | `submission/final-report/scripts/report_numbers.py`, `report_figures.py` (from the repo root) | `submission/final-report/figures/` |
| Presentation plots | `submission/final-presentation/scripts/presentation_plots.py` (from the repo root) | `submission/final-presentation/figures/` |

The word after a script is the run: `final` is the pipeline on the cleaned data, `first_pass` the same
pipeline on the data as downloaded, kept to show what the cleaning changed (step-4 README). In the final run, the nine matching approaches (folders `01_` to `09_`) all run on the same cleaned data, candidates and labels, and
`global_matching_and_test` takes the one with the best validation F1 (the fine-tuned language model),
applies one-to-one matching and a cut-off chosen on the validation pairs (a wrong match is worse for us
than a duplicate), and scores it once on the test pairs. Each step folder has a README on what we did,
why, and what worked and what did not.

## Gold standards

- `data/golden_set/labelled_pairs/labelled_pairs.csv`: the 1,800 labelled pairs for identity resolution,
  300 per set (Wikidata-ROR and DEQAR-ROR, each train / validation / test), both records side by side.
  Team members labelled every pair by hand (`labelled_by`), unclear cases settled with web research. `split_labelled_pairs.py` writes the six set files.
- `data/golden_set/fusion/fusion_gold.csv`: the fusion gold standard, 80 universities in two or more
  sources (64 with conflicting values, 16 random), split into halves to choose and to test. Name, country code, city, founding year and domain were
  looked up in external sources (in `sources`), never in our three sources, and checked by hand
  (`checked_by`, `hand_note`).
  `scripts/05_data_fusion/gold_to_xml.py` writes it as `fusion_gold.xml` in the target schema (one city
  and one founding year each), which is what fusion is evaluated against.

## Checked by AI, not yet by a person

These files were filled in or judged by AI agents (Claude) and still need a check by hand:

- `scripts/02_filtering/validation/<source>/ai_checks.csv`: records checked to validate the cleaning.
- `scripts/06_abandoned_approaches/01_selection/results/sample_200_ai_checked.csv`: 200 items of a
  wider Wikidata selection we dropped (see `scripts/06_abandoned_approaches/README.md`).

The hand check of 150 records removed by the cleaning is in `scripts/02_filtering/validation/<source>/hand_check_removed.csv`.
