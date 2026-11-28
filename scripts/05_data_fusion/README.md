# Step 5: Data fusion

This folder holds the fusion scripts, the drawn gold standard candidates and the fused dataset with its evaluation files.

## Contents

| Path | What it is |
|---|---|
| `fusion.py` | reads the cleaned sources (`03_schema_mapping/<source>/filtered/*_Mapping.xml`), the final links (`04_identity_resolution/global_matching_and_test/results/correspondences_<source>_ror_final.csv`), `gold_candidates.csv` and `fusion_gold.xml`, fuses the records with PyDI, scores the strategies on the gold standard and writes every file in `results/` (it calls `fused_to_xml.py` for the XML) |
| `build_gold.py` | reads the cleaned sources and the final links, draws the gold standard universities (seed 2026) and writes `gold_candidates.csv`, keeping the rows already in it |
| `gold_to_xml.py` | reads `data/golden_set/fusion/fusion_gold.csv`, writes `fusion_gold.xml` next to it and validates it against `03_schema_mapping/target.xsd` |
| `fused_to_xml.py` | reads `results/universities_fused.csv`, writes `results/universities_fused.xml` and validates it against `target.xsd` |
| `gold_candidates.csv` | one row per drawn university (80): the name, alternative names, country code, city, founding year, website and domains each source gives, `selected_because` (a conflicting attribute or `random`) and `half` (`choose` or `test`) |
| `results/universities_fused.csv` | one row per fused university (35,551): `_id`, its record IDs (`_fusion_sources`), their sources (`_fusion_source_datasets`, `sources`) and the 21 attributes of the target schema |
| `results/universities_fused.xml` | the same universities and values in the target schema, with the ROR ID as ID wherever the university has a ROR record, and without the record and source lists |
| `results/strategies.csv` | one row per strategy, comparison (`strict`, `tolerant`) and gold subset (`all`, `choose`, `test`, `conflict`, `random`): accuracy per attribute and the means. Strategies: `content-based`, `voting`, `voting: ties by trust`, `trust: ROR first`, `trust: Wikidata first` and `best per attribute` (the final one) |
| `results/list_functions.csv` | one row per function for domains and gold subset: accuracy, domains per university, universities without a domain |
| `results/coordinate_functions.csv` | one row per function for coordinates and gold subset: share of fused points within 0.1, 0.5, 1, 5 and 10 km of the gold point, median distance in km |
| `results/density.csv` | share of filled values per attribute (rows, plus `all attributes` and `universities`) in each source, in the fused table and in the fused universities with a ROR record (columns) |
| `results/consistency.csv` | one row per attribute: share of groups whose records all give the same value, over the groups where at least two records have one |
| `results/group_sizes.csv` | number of fused universities with 1, 2 and 3 sources |
| `results/fusion_errors.csv` | one row per wrong value of `best per attribute` on the `test` half (tolerant comparison): attribute, ID, fused value, accepted value, what each source offered, conflict rule and evaluation rule |

## Gold standard files (`data/golden_set/fusion/`)

| Path | What it is |
|---|---|
| `fusion_gold.csv` | one row per gold university (80), keyed by `anchor_id` (its ROR ID). Correct values: `name`, `country_code`, `city`, `founding_year`, `domain`, with other accepted values in `name_alternatives`, `city_alternatives`, `founding_year_alternatives` and `domain_alternatives` (separated by a vertical bar). Also `selected_because`, `sources` (the external pages the values come from), `checked_by` and `hand_note` (the hand check) |
| `fusion_gold.csv`, coordinate columns | `latitude` and `longitude`: a point found by a geocoder and checked by hand. `coordinates_source` links the point, `coordinates_checked_by` names who checked it, `coordinates_note` explains it or why no point was kept |
| `fusion_gold.xml` | the same 80 universities in the target schema, written by `gold_to_xml.py` and read by `fusion.py`: ID, name, alternative names, country code, city, coordinates, all accepted domains and founding year |

## Run

From this folder:

```
python build_gold.py     # gold_candidates.csv (rows already there are kept)
python gold_to_xml.py    # data/golden_set/fusion/fusion_gold.xml from fusion_gold.csv
python fusion.py         # every file in results/, including universities_fused.xml
python fused_to_xml.py   # only results/universities_fused.xml again, from the CSV
```

- Python 3.12 with the packages of `requirements.txt` (PyDI as `uma-pydi`, pandas, lxml).
- No run arguments.
- `fusion.py` needs the step 3 XML files and the step 4 `final` correspondences.
- List cells in `universities_fused.csv` are Python lists (`['SGGW']`), a list with one value is written as the plain value.
