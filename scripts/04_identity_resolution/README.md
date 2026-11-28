# Step 4: Identity resolution

Scripts and results that link Wikidata and DEQAR records to ROR records: labelled pairs, blocking, nine matching approaches, global matching with the test, and checks.

## Contents

`<run>` is `first_pass` (sources as downloaded) or `final` (cleaned sources). `<pair>` is `wikidata_ror` or `deqar_ror`.

| Path | What it is |
|---|---|
| `common.py` | shared code: loads the step 3 XML of a run, prepares names, reads the ID links between the sources, attribute comparators, labelled and candidate pairs, threshold search, `run_rules` / `run_matchers` |
| `gold_standard/split_labelled_pairs.py` | reads `data/golden_set/labelled_pairs/labelled_pairs.csv` (1,800 pairs labelled by hand) and writes the six files `<pair>_<split>.csv` (train, validation, test) next to it |
| `blocking/blocking.py` | runs every blocker, writes `results/blocking.csv` and the candidate pairs to `results/candidates/` (not in git) |
| `blocking/multi_pass_snm.py` | multi-pass sorted neighbourhood (four keys, window 20), writes `results/multi_pass_snm.csv`. The matchers do not use its pairs |
| `blocking/results/blocking.csv` | one row per run, dataset pair and blocker: candidate pairs, pair completeness, reduction ratio, seconds |
| `blocking/results/multi_pass_snm.csv` | one row per run, dataset pair and pass: candidate pairs, pair completeness, matches not in the union |
| `*/plots.ipynb` | plots of the results CSV files of their folder (`blocking/`, `01_`, `05_`, `global_matching_and_test/`) |

### Matching approaches (`01_` to `09_`)

| Path | What it is |
|---|---|
| `01_rules_string_similarity/rule_based.py` | weighted rules on string and attribute similarities, including name-only rules |
| `02_rules_tfidf/tfidf.py` | rules on TF-IDF of name words or letter groups, and Soft TF-IDF |
| `03_rules_embeddings/embeddings.py` | rules on multilingual name embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) |
| `04_rules_weight_search/weight_search.py` | rules whose weights are searched on the training pairs |
| `05_machine_learning/ml_based.py` | logistic regression, random forest and gradient boosting on the comparator scores |
| `06_rules_more_similarity/more_similarity.py` | rules on Monge-Elkan, Soundex, Sørensen-Dice, longest common substring, overlap coefficient, extended Jaccard |
| `07_more_learners/more_learners.py` | decision tree, SVM, k-nearest neighbours and naive Bayes on the features of 05 |
| `08_fine_tuned_language_model/fine_tuned_model.py` | fine-tuned cross-encoder (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) that reads both records as one text |
| `08_fine_tuned_language_model/search.py` | tries training settings of 08 on the validation pairs (final run only) |
| `09_local_llm/local_llm.py` | local LLM (`qwen2.5:3b` via Ollama) that judges the 3 most similar ROR candidates per record |
| `0X_*/results/<run>/matching.csv` | one row per variant: threshold, P, R, F1 on the validation pairs, correspondences, seconds |
| `0X_*/results/<run>/best_<pair>.csv` | correspondences of the variant with the best validation F1 (`id1`, `id2`, `score`, `notes`) |
| `0X_*/results/<run>/best_<pair>_info.csv` | one row: name, threshold, validation F1 and seconds of that variant |
| `08_*/results/final/search.csv`, `search_log.txt` | one row per training setting of `search.py` (epochs, learning rate, batch, validation P, R, F1 per pair), and its printed output |
| `09_*/results/<run>/configuration.json` | model and Ollama version, prompt version, shortlist rule and the calibration on the training pairs, per pair |

### Global matching, test and checks (`global_matching_and_test/`, `analysis/`)

| Path | What it is |
|---|---|
| `global_matching_and_test/final.py` | takes the approach with the best validation F1 per pair, applies greedy one-to-one matching (and in the final run the cut-off), scores the test pairs, writes the `results/` files below |
| `results/final.csv` | one row per run, pair, matcher with global matching variant, and split: P, R, F1, correspondences |
| `results/correspondences_<pair>_<run>.csv`, `correspondences_<pair>_final_before_cutoff.csv` | the links (`id1`, `id2`, `score`), and the final run's links before the cut-off. The final run's links go into the fusion step |
| `results/cutoff_final.csv` | one row per pair: matcher threshold, cut-off, precision target, validation P, R, F1 |
| `results/errors_wikidata-ror_<run>.csv`, `errors_deqar-ror_<run>.csv` | validation pairs the links get wrong (`error` is missed match or wrong match, with both names) |
| `results/group_sizes_<run>.csv`, `group_sizes_<run>_without_one_to_one.csv` | size distribution of the groups the links form across the three sources, after and before one-to-one matching (`cluster_size`, `frequency`, `percentage`) |
| `results/history/` | `group_sizes_early_version.csv` from an earlier version of `final.py`, described in its own README |
| `analysis/cutoff_check.py` | for the chosen cut-off and every higher one: links the ID links confirm or contradict, wrong and missed validation pairs. Writes `analysis/results/cutoff_check.csv` |
| `analysis/error_analysis.py` | every test pair the final links get wrong, the step where it was lost and what the two records share. Writes `analysis/results/error_analysis.csv` |
| `analysis/blocking_effect.py` | P, R, F1 of the final matcher on subsets of the blockers. Writes `analysis/results/blocking_effect.csv` (one row per pair, blocker and split) |

## Run

- Python 3.12 with `requirements.txt` from the repository root.
- Input: the step 3 XML (`scripts/03_schema_mapping/<source>/original/` for `first_pass`, `filtered/` for `final`) and the labelled pairs.
- Set `PYTHONHASHSEED=0` and run each script from its own folder.
- 03, 08 and the embedding blocker download their base models on first use. The trained model of 08 is not included: a run trains it again.
- Embeddings, the trained model of 08 and the answers of 09 are cached in `results/cache/` at the repository root (not in git).
- 09 needs a running Ollama server with `qwen2.5:3b` pulled (`ollama pull qwen2.5:3b`, weights not included), best started with `OLLAMA_NUM_PARALLEL=8`.

```
# each line from scripts/04_identity_resolution/, <run> = first_pass or final
cd gold_standard                && python split_labelled_pairs.py
cd blocking                     && python blocking.py <run>
cd blocking                     && python multi_pass_snm.py <run>
cd 01_rules_string_similarity   && python rule_based.py <run>
cd 02_rules_tfidf               && python tfidf.py <run>
cd 03_rules_embeddings          && python embeddings.py <run>
cd 04_rules_weight_search       && python weight_search.py <run>
cd 05_machine_learning          && python ml_based.py <run>
cd 06_rules_more_similarity     && python more_similarity.py <run>
cd 07_more_learners             && python more_learners.py <run>
cd 08_fine_tuned_language_model && python fine_tuned_model.py <run>  # about 2 hours on a CPU, then cached
cd 08_fine_tuned_language_model && python search.py                  # optional, final run only
cd 09_local_llm                 && python local_llm.py <run>         # about 2 hours, then cached (--speed: time 200 pairs only)
cd global_matching_and_test     && python final.py <run>
cd analysis                     && python cutoff_check.py && python error_analysis.py && python blocking_effect.py   # after final.py final
```
