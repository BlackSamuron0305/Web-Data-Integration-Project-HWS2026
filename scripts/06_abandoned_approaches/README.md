# Abandoned approaches

Scripts and results of approaches that are not part of the pipeline, in one subfolder per pipeline step.

## Contents

| Path | What it is |
|---|---|
| `01_selection/fetch_dbpedia.py` | DBpedia universities as a source. Downloads every `dbo:University` resource from the DBpedia SPARQL endpoint and writes `results/dbpedia_universities.csv` (not in the repository). |
| `01_selection/build_the_rankings.py` | The Times Higher Education (THE) World University Rankings 2026 as a source. Turns the table data of the ranking page into one row per university and writes `results/the_rankings_2026.csv` (git-ignored, not included). |
| `01_selection/wider_wikidata.py` | Wikidata selected by *higher education institution* (Q38723) instead of *university* (Q3918). `fetch` downloads the items of the wider class that are not in `data/wikidata/original/` and writes `results/wider_new_records.csv`. `check` runs the Wikidata cleaning rules 1-4 on them, counts the overlap with the cleaned ROR and the fused result and writes `results/summary.csv` and `results/sample_200.csv`. |
| `01_selection/results/wider_new_records.csv` | One row per new item of the wider class: `wikidata_id`, `name`, `country`, `types`, `students`, `ror_id`. Download of 24 November 2026. |
| `01_selection/results/summary.csv` | The counts of `check` (`what`, `count`). |
| `01_selection/results/sample_200.csv` | Random sample of 200 items kept by the rules, 100 with and 100 without a ROR id (`stratum`). |
| `01_selection/results/sample_200_ai_checked.csv` | The same 200 items with the AI agents' `verdict` (`university`, `not_university`, `unsure`) and `reason`. |
| `02_filtering/university_word_rule.py` | A cleaning rule that keeps only names containing "univers". Reads the original source files and `scripts/02_filtering/validation/<source>/ai_checks.csv` and prints per source the records it would remove and the AI verdicts on them. Writes no file. |
| `02_filtering/local_llm_cleaning.py` | A local LLM (Qwen2.5 via Ollama) that answers keep or drop for each record. `test` asks 300 records with a known answer (from `hand_check_removed.csv` and `ai_checks.csv` in `scripts/02_filtering/validation/<source>/`), once with the record only and once with web text (title, description and start of the homepage, or the Wikidata description). `rescue` asks every record in `data/<source>/filtered/removed.csv`, record only. Writes `results/llm_<mode>_<model>.csv` and `results/evaluation_<mode>_<model>.csv`. |
| `02_filtering/results/llm_test_<model>.csv` | One row per test record (300): `set` (`hand` = 150 removals checked by hand, `kept` = 150 kept records), `source`, `id`, `name`, `truth` (hand verdict for `hand`, AI agents' verdict for `kept`), the model's answer with the record only (`plain`) and with web text (`web`). |
| `02_filtering/results/llm_rescue_<model>.csv` | One row per removed record: `source`, `id`, `name`, the cleaning `rule` that removed it, the AI agents' verdict (`agent`), the hand verdict if there is one (`hand`), the model's answer (`plain`, `True` = keep). |
| `02_filtering/results/evaluation_test_<model>.csv` | Counts per variant (record only, with homepage) and set: records, universities, others, model right, rules right, universities kept, others dropped, no answer. |
| `02_filtering/results/evaluation_rescue_<model>.csv` | Records brought back per group: all, per source, per AI agents' verdict, per hand verdict. |
| `04_identity_resolution/multilingual_blocking.py` | A multilingual embedding model (*paraphrase-multilingual-MiniLM-L12-v2*) for the embedding blocker, next to PyDI's default English *all-MiniLM-L6-v2*. Embeds the name alone and name + city + country, for both runs and both dataset pairs, with the pipeline's settings (ten nearest names, similarity at least 0.5). Writes the two files below. |
| `04_identity_resolution/results/multilingual_blocking.csv` | One row per run, dataset pair, model and text: `candidates`, `pc` (pair completeness), `union_candidates` and `union_pc` (with the pipeline's other two blockers), `validation_matches`, `seconds`. |
| `04_identity_resolution/results/multilingual_only_matches.csv` | Validation matches that only one of the two unions keeps (`kept_by`), with both ids and names. |
| `README.md` | This file. |

`<mode>` is `test` or `rescue`, `<model>` is `qwen2.5_3b` or `qwen2.5_7b`.

- Python 3.12 with the packages in `requirements.txt` at the repository root.
- The THE output is not included: THE's terms do not allow republishing the data.
- `local_llm_cleaning.py` needs a running Ollama server (`127.0.0.1:11434`) with `qwen2.5:3b` and `qwen2.5:7b` pulled.
- Its model answers and fetched web text are cached in `results/cache/local_llm_cleaning/` at the repository root (not in git). A rerun asks only what is missing.
- PyDI's debug files go to `04_identity_resolution/results/pydi_output/` (not in git).
- CSV files are UTF-8, list values are separated by ` | `.

## Run

From the repository root:

    python scripts/06_abandoned_approaches/01_selection/fetch_dbpedia.py
    python scripts/06_abandoned_approaches/01_selection/build_the_rankings.py [downloaded.json]   # without a file it downloads the data
    python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py fetch                   # about 20 minutes
    python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py check
    python scripts/06_abandoned_approaches/02_filtering/university_word_rule.py                   # prints a table
    ollama pull qwen2.5:3b
    ollama pull qwen2.5:7b
    python scripts/06_abandoned_approaches/02_filtering/local_llm_cleaning.py test qwen2.5:3b      # about 2 minutes
    python scripts/06_abandoned_approaches/02_filtering/local_llm_cleaning.py rescue qwen2.5:3b    # about 20 minutes
    python scripts/06_abandoned_approaches/04_identity_resolution/multilingual_blocking.py         # about 25 minutes on a CPU

The model argument defaults to `qwen2.5:3b`. Run the same two commands with `qwen2.5:7b` for the 7B files.
The local LLM times are for the 3B model on a laptop GPU (RTX 5070, 8 GB).
