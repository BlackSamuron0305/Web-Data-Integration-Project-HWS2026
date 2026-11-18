# Integrating worldwide university data from Wikidata, ROR and DEQAR

Web Data Integration project, HWS 2026 (University of Mannheim). The report is in
`submission/final-report/`, the project abstract in `submission/project-proposal/`.

## Layout

- `data/wikidata/`, `data/ror/`, `data/deqar/`: per source the downloaded CSV file, the MapForce
  mapping (`*_Mapping.mfd`) and its output (`*_Mapping.xml`). `data/target.xsd` is the target schema,
  `data/functions.mfd` the functions the three mappings share.
- `scripts/data_collection/`: downloads the three sources (`fetch_wikidata.py`, `build_ror_education.py`,
  `fetch_deqar.py`).
- `scripts/identity_resolution/`: Phase II, one folder per approach, each with its script, a
  `results/` folder and `plots.ipynb` (charts of those results); `common.py` holds the shared code (loading, blocking keys, comparators, evaluation).
- `IDENTITY_RESOLUTION_REASONING.txt`: the journal of the three rounds of Phase II (what we tried, why,
  results).

## Run order

Python 3.12 (PyDI pins numpy 2.1, which has no wheel for 3.14), `pip install -r requirements.txt`.
Run each script from its own folder; each one prints what it writes.

| Step | Folder and script | Results |
|---|---|---|
| Phase I: collect | `scripts/data_collection/*.py` | `data/<source>/*.csv` (already included) |
| Phase I: schema mapping | MapForce: `data/<source>/*_Mapping.mfd` | `data/<source>/*_Mapping.xml` |
| Phase II: labelled pairs | `01_labels/labels.py 1`, then `pool`, check by hand, `2` | `pool_*.csv`, `review_*.csv`, `round1/`, `round2/` |
| Phase II: blocking | `02_blocking/blocking.py 1`, `2`, `3` | `blocking.csv`, `candidates/` |
| Phase II: rule-based | `03_rule_based/rule_based.py 1`, `2`, `3` | `matching.csv`, `best_*` |
| Phase II: learned | `04_ml_based/ml_based.py 2`, `3` | `matching.csv`, `best_*` |
| Phase II: final | `05_final/final.py 1`, `2`, `3` | `final.csv`, `correspondences_*`, `group_sizes_*`, `errors_*` |

The number is the round: 1 = quick labels from the ID links, 2 = hand-checked labels,
3 = round 2 plus the fixes from its error analysis.

## Hand-made files

- `scripts/identity_resolution/01_labels/results/review_*.csv`: the hand check of the round-2 pools:
  every pair whose label was changed (`flip`) or that was left out as unclear (`drop`), with the
  reason. All other pool pairs kept their label.
