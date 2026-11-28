# Step 2: Filtering

The filter scripts that keep only universities in each source, and the checks of their output.

The five rules are defined in [`rules.md`](rules.md).

## Contents

`<source>` is `wikidata`, `ror` or `deqar`.

| Path | What it is |
|---|---|
| `rules.md` | the definition of a university as five rules |
| `common.py` | shared code: the name rules, the duplicate rule (rule 5), reading `data/<source>/original/` and writing `data/<source>/filtered/` |
| `<source>/filter.py` | one filter per source: the shared rules plus the source's own checks (Wikidata type labels, ROR types, DEQAR parent institutions) |
| `validation/<source>/ai_checks.csv` | records judged by AI agents against `rules.md`, one row per record and check round: id, `name`, `round` (which sample the record came from), `verdict` (`real`, `junk` or `unsure`), `explanation` |
| `validation/<source>/hand_check_removed.csv` | 50 records drawn at random from `removed.csv` and checked by hand: the record fields, `rule`, `reason`, `precheck`, `precheck_note`, `hand_verdict` (`removal_correct`, `real_university` or `unsure`), `hand_note`, `checked_by` |
| `validation/validate.ipynb` | compares the current filter output with `ai_checks.csv`: a table per check round, a summary table and a plot (writes no files) |
| `validation/hand_check_summary.py` | counts the verdicts in the three `hand_check_removed.csv` files and writes `validation/results/hand_check_summary.csv` |
| `validation/results/hand_check_summary.csv` | one row per source: `checked`, `checked_by_hand`, `real_university`, `unsure`, `removal_correct`, `hand_disagrees_with_precheck`, `share_real` |

## Outputs in `data/<source>/filtered/`

| Path | What it is |
|---|---|
| `wikidata_universities.csv`, `ror_education.csv`, `deqar_institutions.csv` | the cleaned source: the kept records, same file name and columns as in `data/<source>/original/` |
| `removed.csv` | one row per removed record: the id, `name`, `country`, a few source columns (`types`, `parent_ror_id`, `parent_institutions`), `rule` (1 to 5) and `reason` (the label or name pattern that matched, or `duplicate of <id>`) |

## Run

- Python 3.12 with the packages in the root `requirements.txt`.
- The filters write CSV only. MapForce maps the cleaned CSV to XML in step 3.
- Run the filters from this folder, and the validation scripts from `validation/`.

```
python wikidata/filter.py         # writes data/wikidata/filtered/
python ror/filter.py              # writes data/ror/filtered/
python deqar/filter.py            # writes data/deqar/filtered/
cd validation
python hand_check_summary.py      # writes results/hand_check_summary.csv
```

Then open `validation/validate.ipynb` (kernel from `ipykernel`) and run all cells.
