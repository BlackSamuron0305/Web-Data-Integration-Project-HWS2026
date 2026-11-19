# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026 (University of Mannheim). The report is in
`submission/final-report/`, the project abstract in `submission/project-proposal/`.

## Layout

- `data/wikidata/`, `data/ror/`, `data/deqar/`: per source the downloaded CSV file, the MapForce
  mapping (`*_Mapping.mfd`) and its output (`*_Mapping.xml`). `data/target.xsd` is the target schema,
  `data/functions.mfd` the functions the three mappings share.
- `scripts/data_collection/`: downloads the three sources (`fetch_wikidata.py`, `build_ror_education.py`,
  `fetch_deqar.py`).
- `scripts/additional_filtering/`: one folder per source (`wikidata/`, `ror/`, `deqar/`), each with
  - `filter.py` -> `hand_check.csv`: rows that are not a university of their own (schools, campuses,
    branches, faculties, research units ...); column `university` y / n
  - `duplicates.py` -> `duplicate_check.csv`: pairs of rows of the same source that may be one
    institution; column `same` y / n, column `keep` = the row that stays
  - `apply.py` -> `*_filtered.csv/.xml` (without the `n` rows of `hand_check.csv`), `campuses.csv`
    (removed campuses and branches with their university, for the fusion) and
    `*_deduplicated.csv/.xml` (without the duplicates). `data/` keeps the original sources.
  `common.py` holds the shared code. The XML files are the MapForce output with the same rows taken
  out (the mappings turn one CSV row into one `<institution>`), checked against `data/target.xsd`.
- `scripts/identity_resolution/`: Phase II, one folder per approach, each with its script, a
  `results/` folder and `plots.ipynb` (charts of those results); `common.py` holds the shared code
  (loading, blocking keys, comparators, evaluation).
- `IDENTITY_RESOLUTION_REASONING.txt`: the journal of Phase II (what we tried, why, results).

## Run order

Python 3.12 (PyDI pins numpy 2.1, which has no wheel for 3.14), `pip install -r requirements.txt`.
Run each script from its own folder; each one prints what it writes.

| Step | Folder and script | Results |
|---|---|---|
| Phase I: collect | `scripts/data_collection/*.py` | `data/<source>/*.csv` (already included) |
| Phase I: schema mapping | MapForce: `data/<source>/*_Mapping.mfd` | `data/<source>/*_Mapping.xml` |
| Additional filtering | `additional_filtering/<source>/filter.py`, `duplicates.py`, check the rows with `check_by_hand` = yes, then `apply.py` | `hand_check.csv`, `duplicate_check.csv`, `*_filtered.*`, `*_deduplicated.*` |
| Phase II: labelled pairs | `01_labels/labels.py 1`, then `pool`, check by hand, `2` | `pool_*.csv`, `review_*.csv`, `round1/`, `round2/` |
| Phase II: blocking | `02_blocking/blocking.py 1` ... `4`, `6` | `blocking.csv`, `candidates/` |
| Phase II: rule-based | `03_rule_based/rule_based.py 1` ... `4`, `6` | `matching.csv`, `best_*` |
| Phase II: learned | `04_ml_based/ml_based.py 2` ... `4`, `6` | `matching.csv`, `best_*` |
| Phase II: final | `05_final/final.py 1` ... `6`, then `compare_filtering.py` | `final.csv`, `correspondences_*`, `group_sizes_*`, `errors_*`, `filtering_effect.csv` |

The number is the round:
1 = quick labels from the ID links, 2 = hand-checked labels, 3 = round 2 plus the fixes from its
error analysis, 4 = round 3 with the non-universities removed before matching (rejected: records
whose counterpart was removed in another source got a wrong partner), 5 = round 3 with the links
to non-universities removed after matching (reuses the matching of round 3), 6 = like round 5 on
the deduplicated sources.

## Hand-made files

- `scripts/additional_filtering/<source>/hand_check.csv` and `duplicate_check.csv`: the decisions
  (`university`, `same`, `keep`). `ai_suggestion` / `ai_note` hold an AI pre-check (Claude) of every
  row; `check_by_hand` = yes marks the rows a person checks (every risky row, every row the AI
  doubted, 10 random rows per safe group); `checked_by` names who did.
- `scripts/identity_resolution/01_labels/results/review_*.csv`: the hand check of the round-2 pools:
  every pair whose label was changed (`flip`) or that was left out as unclear (`drop`), with the
  reason. All other pool pairs kept their label.
