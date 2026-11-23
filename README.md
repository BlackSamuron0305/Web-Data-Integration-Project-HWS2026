# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026 (University of Mannheim). The report is in
`submission/final-report/`, the project abstract in `submission/project-proposal/`.

## Pipeline

1. **Collect** the three sources (`scripts/01_data_collection/`).
2. **Clean** each source: remove everything that is not a university in the sense of
   [`rules.md`](rules.md) (`scripts/02_filtering/`).
3. **Schema mapping** on the cleaned data: the MapForce output without the removed records
   (`data/<source>/filtered/`).
4. **Identity resolution** on the cleaned mapping (`scripts/03_identity_resolution/`, round 8).
5. **Data fusion** of the matched records (`scripts/04_data_fusion/fusion.py`).

Cleaning comes before matching on purpose: the project is about universities, so removing
non-universities is part of the data preparation, even if the matching scores get a little worse.

## Layout

- `rules.md`: what counts as a university (Rules 1-5).
- `data/<source>/` (wikidata, ror, deqar):
  - `original/`: the downloaded CSV file and its schema mapping (`*_Mapping.xml`, MapForce output).
    Never changed by the later steps.
  - `filtered/`: the same two files after cleaning (same names) and `removed.csv` (every removed
    record with rule and reason). Written by `scripts/02_filtering/`.
  - the MapForce mapping (`*_Mapping.mfd`, reads `original/`), and for ROR and DEQAR its lookup table:
    `ror/ror_names.csv` (ROR id -> name), `deqar/country_codes.csv` (DEQAR country name -> ISO code).
  `data/target.xsd` is the target schema, `data/functions.mfd` the functions the three mappings share.
- `scripts/01_data_collection/`: downloads the three sources (`fetch_wikidata.py`, `build_ror_education.py`,
  `fetch_deqar.py`); `build_lookup_tables.py` builds the two lookup tables from the downloaded CSV files
  (ROR: id and name columns of the ROR file; DEQAR: codes from the country/code pairs of ROR and
  Wikidata, 12 DEQAR-specific country names set by hand).
- `scripts/02_filtering/`: the cleaning step, see `scripts/02_filtering/README.md`. `common.py` holds the
  rules shared by all sources, `<source>/filter.py` writes `data/<source>/filtered/`;
  `<source>/validation/ai_checks.csv` holds the AI-checked records, `validate.py` compares the filters
  with them.
- `scripts/03_identity_resolution/`: Phase II, one folder per approach, each with its script, a
  `results/` folder and `plots.ipynb` (charts of those results); `common.py` holds the shared code
  (loading, blocking keys, comparators, evaluation).
- `scripts/04_data_fusion/`: Phase III. `build_gold.py` picks 1,000 universities found in two or more
  sources (half with conflicting values) for the gold standard `fusion_gold_new.csv`; `fusion.py` (built
  like the PyDI fusion exercise) groups the records linked in round 8, compares content-based, voting
  and trust-based conflict resolution on the gold standard (with `fusion_gold.csv`, 39 well-known
  universities), picks the best function per attribute and fuses everything with it; results in
  `results/` (`universities_fused.csv`, `strategies.csv`, `consistency.csv`, `density.csv`,
  `group_sizes.csv`, `fusion_errors.jsonl` = the wrong values left, for the error analysis).
- `scripts/05_checks/report_numbers.py`: recomputes the report numbers that no pipeline script writes
  (re-linked records, Sect. 4.1, and LLM verdicts by number of sources, Sect. 5); run it from the
  repo root.
- `scripts/05_checks/report_figures.py`: rebuilds the data figures of the report (group sizes,
  cleaning, cut-off, density and consistency) from the result files into
  `submission/final-report/figures/`; run it from the repo root.
- `IDENTITY_RESOLUTION_REASONING.txt`: the journal of Phase II (what we tried, why, results).
- `scripts/03_identity_resolution/06_...` to `11_...` and `IDENTITY_RESOLUTION_EXTENSIONS.md`: extra
  matchers tried on round 3, one folder each (06 candidates rebuilt without a GPU, 07 TF-IDF,
  08 multilingual embeddings, 09 searched rule weights, 10 learned models rerun, 11 test comparison,
  error analysis and figures); none of them replaced the round-8 matchers. Overview in
  `11_comparison/README.md`.

## Run order

Python 3.12 (PyDI pins numpy 2.1, which has no wheel for 3.14), `pip install -r requirements.txt`.
Run each script from its own folder; each one prints what it writes. Set `PYTHONHASHSEED=0` before
running identity resolution: otherwise Python orders the candidate pairs differently on every run, and
ties between equal scores can come out differently (a handful of links).

| Step | Folder and script | Results |
|---|---|---|
| Phase I: collect | `scripts/01_data_collection/fetch_*.py`, `build_ror_education.py`, then `build_lookup_tables.py` | `data/<source>/original/*.csv` (already included) |
| Phase I: schema mapping | MapForce: `data/<source>/*_Mapping.mfd` | `data/<source>/original/*_Mapping.xml` |
| Cleaning | `scripts/02_filtering/<source>/filter.py` (wikidata, ror, deqar), then `scripts/02_filtering/validate.py` | `data/<source>/filtered/`, `validation_summary.csv` |
| Phase II: labelled pairs | `scripts/03_identity_resolution/01_labels/labels.py 1`, then `pool`, check by hand, `2`; `extra` adds 200 test pairs per pair | `pool_*.csv`, `review_*.csv`, `round1/`, `round2/` |
| Phase II: blocking | `02_blocking/blocking.py 1`, `2`, `3`, `8` | `blocking.csv`, `candidates/` |
| Phase II: rule-based | `03_rule_based/rule_based.py 1`, `2`, `3`, `8` | `matching.csv`, `best_*` |
| Phase II: learned | `04_ml_based/ml_based.py 2`, `3`, `8` | `matching.csv`, `best_*` |
| Phase II: final | `05_final/final.py 1`, `2`, `3`, `8`, then `05_final/cutoff_check.py` | `final.csv`, `correspondences_*`, `group_sizes_*`, `errors_*`, `cutoff_check.csv` |
| Phase III: fusion | `scripts/04_data_fusion/fusion.py` | `results/universities_fused.csv`, `strategies.csv`, `consistency.csv`, `density.csv`, `group_sizes.csv`, `fusion_errors.jsonl` |

The number is the round: 1 = quick labels from the ID links, 2 = hand-checked labels, 3 = round 2
plus the fixes from its error analysis (first pass on all records), **8 = the final pipeline: all
three sources cleaned by `scripts/02_filtering/` before matching, and a stricter final cut-off (0.7
Wikidata-ROR, 0.55 DEQAR-ROR) because a wrong match is worse for us than a duplicate; the trade-off
is checked against the ID links by `05_final/cutoff_check.py`**. In round 8 the labelled pairs that
touch a removed record are left out of the evaluation (those records are out of scope). Rounds 4-7
were experiments that we dropped.

The ID links between the sources (`ror_id`, `wikidata_id` in the CSV files) are the answer key: they
are used to build and check labels, never inside the pipeline.

## Hand-made and AI-checked files

- `scripts/03_identity_resolution/01_labels/results/review_*.csv`: the hand check of the round-2 pools:
  every pair whose label was changed (`flip`) or that was left out as unclear (`drop`), with the
  reason. All other pool pairs kept their label.
- `scripts/03_identity_resolution/01_labels/results/pool_extra_*.csv` and `review_extra_*.csv`: 200 more
  test pairs per source pair (slide 34: more than 500 test pairs), same mix as the pool. **Checked by
  AI agents, not by hand yet.**
- `scripts/02_filtering/<source>/validation/ai_checks.csv`: records checked by AI agents (Claude
  subagents) to validate the cleaning. **Not checked by a person yet.**
- `scripts/04_data_fusion/fusion_gold.csv` (39 universities, from the earlier attempt, commit `6679e95`)
  and `fusion_gold_new.csv` (1,000 universities, column `confidence`; rows with `low` are not used):
  the expected values for the fusion evaluation. **Filled in by AI agents (Claude), not checked by hand
  yet.** The agents saw the source values as hints, so a check by hand matters.
- `scripts/04_data_fusion/results/ai_check_fused.csv` (final cut-off) and `ai_check_fused_before_cutoff.csv`:
  every fused university judged by AI agents (in scope, same institution, values correct); only rows
  with a doubt carry a note. **AI verdicts, not checked by hand.**
- `scripts/03_identity_resolution/05_final/results/ai_check_links_r8.csv`: 6,000 links of round 8 (before
  the final cut-off) judged by AI agents.
