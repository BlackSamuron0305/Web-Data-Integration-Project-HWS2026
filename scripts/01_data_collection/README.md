# Step 1: Data collection

Scripts that download Wikidata, ROR and DEQAR and save each source as one CSV file in `data/<source>/original/`.

## Contents

| Path | What it is |
|---|---|
| `fetch_wikidata.py` | queries the Wikidata SPARQL endpoint for every instance of *university* (Q3918) or one of its subclasses and writes `data/wikidata/original/wikidata_universities.csv` |
| `fetch_ror.py` | downloads the ROR data dump v2.13 from Zenodo (or reads a given zip), keeps the records of type *education* that are not withdrawn and writes `data/ror/original/ror_education.csv` |
| `fetch_deqar.py` | downloads the DEQAR institutions CSV from `backend.deqar.eu` (or reads a given CSV), merges the rows of one institution (one row per location) into one and writes `data/deqar/original/deqar_institutions.csv` |
| `common.py` | helpers shared by the three scripts: path of `data/`, user agent, value separator, text cleaning and the CSV writer |
| `README.md` | this file |

## Output files

| File | What it holds |
|---|---|
| `data/wikidata/original/wikidata_universities.csv` | one row per Wikidata university (22,697 rows), key `wikidata_id`, columns `name`, `alt_names`, `acronyms`, `country`, `country_code`, `city`, `website`, `founding_year`, `latitude`, `longitude`, `students`, `types`, `member_of`, `ror_id`, `wikipedia_en` |
| `data/ror/original/ror_education.csv` | one row per ROR education record (30,131 rows), key `ror_id`, columns `name`, `alt_names`, `acronyms`, `country`, `country_code`, `region`, `city`, `website`, `domains`, `founding_year`, `latitude`, `longitude`, `types`, `status`, `parent_ror_id`, `wikidata_id`, `wikipedia_en` |
| `data/deqar/original/deqar_institutions.csv` | one row per DEQAR institution (8,979 rows), key `deqar_id`, columns `name`, `alt_names`, `country`, `city`, `website`, `founding_year`, `closure_year`, `parent_institutions`, `history`, `qa_reports`, `last_qa_report`, `ror_id` |

## Run

From this folder:

```
python fetch_wikidata.py                                # writes data/wikidata/original/wikidata_universities.csv
python fetch_ror.py   [path/to/ror-data.zip]            # writes data/ror/original/ror_education.csv
python fetch_deqar.py [path/to/deqar-institutions.csv]  # writes data/deqar/original/deqar_institutions.csv
```

- Python 3.12 with `requests` (`pip install -r requirements.txt` in the repository root).
- The optional argument is a local copy of the source file. Without it the script downloads the file.
- `fetch_ror.py` keeps the downloaded dump in the system temp folder and reuses it on the next run.
- `fetch_wikidata.py` sends its queries in batches of 250 ids and retries a failed query up to 6 times.
- All files are UTF-8 CSV with a header row. A field with several values separates them with ` | `.
- The files in `data/` were downloaded in October 2026. A new run overwrites them.
