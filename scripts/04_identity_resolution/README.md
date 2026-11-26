# Step 4: Identity resolution

This step finds the records that describe the same university in different sources. We match
**Wikidata–ROR** and **DEQAR–ROR**. ROR is the largest source and acts as the connector: Wikidata and
DEQAR records that link to the same ROR record end up in one group. We use PyDI and scikit-learn.

The ID links between the sources (a Wikidata or DEQAR record naming its ROR record) are our **answer
key**. We use them to check results, never inside blocking, matching, the cut-off or cleaning.

## One pipeline

```
gold_standard/  ->  blocking/  ->  01_ ... 09_ (nine matching approaches)  ->  global_matching_and_test/  ->  analysis/
labelled pairs      candidates      each writes its best matcher             best of the nine by validation   checks
                                                                             F1, one-to-one, cut-off, test
```

Numbered folders are the matching approaches; the other folders are the steps around them. All nine
approaches run on the same cleaned data (step 2), the same candidate pairs and the same labelled pairs.
Each picks its threshold on the validation pairs (0.30 to 0.95 in steps of 0.05, then 0.96 to 0.99) and writes its best
matcher to `results/<run>/best_<pair>.csv` (`<run>` is `first_pass` or `final`). `global_matching_and_test/final.py` takes the approach with the
best validation F1, and only that script looks at the test pairs.

## Two runs

The whole pipeline runs twice; the word after a script (`final.py final`) says which run.

| Run | Data | Why |
|---|---|---|
| `first_pass` | sources as downloaded | shows what the cleaning changed |
| **`final`** | **cleaned (step 2)** | **the links the fusion uses** |

Only the data differs: both runs use the same blockers, all nine approaches, the same labelled pairs
(the final run leaves out pairs with a record the cleaning removed) and greedy one-to-one matching. So
comparing the same approach across the two runs shows the effect of the cleaning alone. The cut-off is
applied in the final run only, because only its links go into the fusion. Before these two runs we
tried other label sets and other ways of removing non-universities; they are listed under "What did
not work".

## What we did

### Labelled pairs (`gold_standard/`)

`data/golden_set/labelled_pairs/labelled_pairs.csv` holds 1,800 pairs, 300 per set (Wikidata–ROR and
DEQAR–ROR, each train / validation / test), 41-55% matches per set. `split_labelled_pairs.py` writes the
six set files.

- 486 pairs come from a sample labelled by hand (Chellapuram Keerthan Reddy): final links of an earlier
  run, ID links that run missed, and unlinked pairs with similar names.
- The other 1,314 were drawn by kind: random ID links, matches with different names, similar names of
  different universities, a part against its parent, the same name in another country, random
  non-matches. Team members labelled them by hand, settling unclear cases with web research.
  <!-- TODO (team): true only once every one of the 1,314 pairs has a team member's verdict (hand_check_*.csv). -->
- **Weakness:** the 486 pairs of the first sample were drawn from our own earlier results, so they favour
  pairs that pipeline already scored.

Earlier labels (first ID links and random pairs, then pools with half hard cases checked by an AI) were
replaced by this set. The lesson of the first ones stays: random non-matches make every matcher look perfect.

### Blocking (`blocking/`)

Comparing every pair would mean 508 million Wikidata–ROR and 175 million DEQAR–ROR comparisons (cleaned
data). Pair completeness (PC) is the share of validation matches that survive blocking.

| Blocker | Wikidata–ROR PC | DEQAR–ROR PC | Verdict |
|---|---|---|---|
| exercise key (2 letters of 3 words) | 0.55 | 0.45 | loses the hard cases |
| normalised name | 0.46 | 0.34 | loses the hard cases |
| sorted neighbourhood, window 20 | 0.70 | 0.56 | loses the hard cases |
| every name word / name 3-grams | – | – | too many pairs (up to 1.7 billion), not runnable |
| country + name word (`DE_heidelberg`) | 0.92 | 0.93 | good |
| same web domain | 0.76 | 0.75 | finds renamed universities |
| embedding: 10 nearest names | 0.84 | 0.79 | finds other spellings |
| **union of the last three** | **0.993** | **0.987** | **used**: 631,099 and 228,426 candidate pairs |

The embedding search was the slowest: its Wikidata–ROR run grew from 41 s in the first pass to about 2
hours in the second with unchanged code, for reasons we could not find. `analysis/blocking_effect.py`
shows it adds little (51 Wikidata–ROR and 5 DEQAR–ROR links).

### Matching: nine approaches (`01_` to `09_`)

Best variant of each approach on the validation pairs (final run; `<folder>/results/final/matching.csv` has
every variant):

| Folder | Approach | Best variant | Wikidata–ROR F1 | DEQAR–ROR F1 |
|---|---|---|---|---|
| | names only (baseline, in 01) | Jaro-Winkler | 0.751 | 0.785 |
| `01_rules_string_similarity` | rules on string similarity, weights set by hand | all attributes / names + country + domain | 0.887 | 0.894 |
| `02_rules_tfidf` | rules on TF-IDF of name words or letter groups, and Soft TF-IDF (similar words count as shared) | Soft TF-IDF / TF-IDF words 0.5 + country 0.2 + domain 0.3 | 0.883 | 0.887 |
| `03_rules_embeddings` | rules on multilingual sentence embeddings of the names | embedding 0.5 + country 0.2 + domain 0.3 | 0.878 | 0.861 |
| `04_rules_weight_search` | rule weights searched on the training pairs (252 combinations, top 3 kept) | see `matching.csv` | 0.900 | 0.878 |
| `05_machine_learning` | logistic regression, random forest, gradient boosting on 14 features, alone, with the part-word feature, or with the TF-IDF and embedding scores | logistic regression + TF-IDF, embedding | 0.941 | 0.919 |
| `06_rules_more_similarity` | rules on Monge-Elkan, Soundex, Sørensen-Dice, longest common substring, overlap coefficient, extended Jaccard | Monge-Elkan / overlap coefficient + country + domain | 0.856 | 0.905 |
| `07_more_learners` | decision tree, SVM, k-nearest neighbours, naive Bayes on the features of 05 | kNN / SVM | 0.941 | 0.901 |
| `08_fine_tuned_language_model` | small multilingual model fine-tuned on the training pairs, reads both records as one text (like Ditto) | | **0.944** | **0.939** |
| `09_local_llm` | small local LLM (Qwen2.5 3B via Ollama) judges the 3 most similar ROR candidates per record | qwen2.5:3b, 3 candidates, 4 examples | 0.932 | 0.933 |

What we learned:

- A name alone is not enough: the best threshold accepts almost every pair (*Seisen University* exists
  in Tokyo and in Nagano). Which name measure we use hardly matters (01, 02, 03, 06).
- The web domain and the country are what make rules precise: every rule with them reaches 0.86-0.91.
  Searching the weights (04) does not beat weights set by hand by much; on 300 training pairs it even
  picks rules without the name for Wikidata–ROR.
- Learned models (05, 07) gain another 0.02-0.05, mostly because they learn that a missing year or
  website is no evidence against a match. Which learner hardly matters.
- The fine-tuned model (08) is best for both dataset pairs and is the one `final.py` uses, in both runs:
  by 0.003 F1 for Wikidata–ROR and 0.006 for DEQAR–ROR (both small enough to be chance on 300 pairs). It is slow on
  our CPU: 3 minutes of training, about 2 hours of scoring (the GPU route was blocked by a Windows
  security policy). Its threshold for Wikidata–ROR is 0.95, the top of the range we try.
- The local LLM (09) comes close (0.932 / 0.933) but does not win. It is far too slow for all candidate
  pairs (9-12 pairs per second on our GPU), so it only judges the 3 most likely ROR candidates of each
  record (ranked by name similarity, plus a bonus for the same website or city); this shortlist misses
  3% of the validation matches. Its answers are very confident, so we rescale them with a curve fitted
  on the training pairs (`results/<run>/configuration.json`) before the usual threshold search. A strict
  prompt ("answer true only if ...") rejected a third of the true DEQAR matches; the wording was chosen
  on the training pairs only. Free and local: Ollama with `qwen2.5:3b`, about 2 h 15 min, answers cached.

### Global matching, cut-off and test (`global_matching_and_test/`)

A source should list a university only once, so each record may have at most one partner per dataset
pair. For the fine-tuned model, greedy one-to-one raises validation precision from 0.944 to 0.970
(Wikidata–ROR) and from 0.965 to 0.993 (DEQAR–ROR); stable matching is about the same, maximum
bipartite matching loses recall. An earlier version of our script picked "no one-to-one" for DEQAR–ROR
because its validation F1 was 0.013 higher: test precision dropped to 0.87, and **one group held 4,509
records**, which fusion would have merged into a single university. Since then we always use greedy
one-to-one, so every group is a pair or a triple. `results/group_sizes_final_without_one_to_one.csv`
shows the groups the final matcher would form without it.

**Cut-off.** A wrong link merges two universities into one entry; a missed link only lists one
university twice. So `final.py` may raise the threshold after one-to-one matching: it takes the lowest
cut-off, in steps of 0.05, whose links reach precision 0.99 on the validation pairs
(`results/cutoff_final.csv`). For DEQAR–ROR the threshold (0.9) already reaches 0.993; for Wikidata–ROR no
cut-off up to 0.95 does, so the threshold stays. Finer steps would reach 0.99 only at 0.999 and lose a
sixth of the validation matches. An earlier version set the cut-off by hand against the ID links; we
dropped that, because the ID links are our answer key.

**Final results** on the 300 test pairs per dataset pair (`results/final.csv`):

| | Wikidata–ROR P / R / F1 | DEQAR–ROR P / R / F1 | Links |
|---|---|---|---|
| `first_pass` (original data) | .982 / .902 / .941 | .992 / .874 / .929 | 13,316 / 4,433 |
| **`final` (cleaned data)** | **.982 / .902 / .941** | **.992 / .881 / .933** | **12,499 / 4,238** |

Both runs use the fine-tuned model and score almost the same on the test pairs. That is expected: the
labelled pairs only hold records that survive the cleaning, so they cannot show its effect. The effect is
in the links: the final run has 817 fewer Wikidata–ROR and 195 fewer DEQAR–ROR links, and the 1,065
first-pass links to removed records are gone. Checked against the ID links, 115 of the 12,499 Wikidata–ROR links and 69 of the 4,238 DEQAR–ROR links
are wrong (one of the two records names another partner), and the links recover 97% and 95% of the ID
links.

### Checks (`analysis/`)

- `cutoff_check.py`: for the chosen cut-off and every higher one, how many links the ID links confirm or
  contradict and how many validation pairs are wrong or missed (`results/cutoff_check.csv`). It chooses
  nothing.
- `error_analysis.py`: every test pair the final links get wrong and where it was lost
  (`results/error_analysis.csv`). One wrong link per dataset pair (*Hellenic Mediterranean
  University* linked to its research centre). Of 28 missed matches, 20 scored below the threshold, 5
  lost to a higher-scored link, 3 were never candidates; most have names that differ or are in another
  language.
- `blocking_effect.py`: the final setup with fewer blockers (`results/blocking_effect.csv`). Country +
  name word alone reaches validation F1 0.910 / 0.919; with the web domain it is within 0.004 of the
  final result.

## What did not work

- **Labels from the ID links with random non-matches:** far too easy, see above.
- **Picking global matching by validation F1:** produced the 4,509-record group.
- **Maximum bipartite matching:** swaps strong pairs for several weak ones and loses recall.
- **Translating common words** (*universidad* to *university*) and a **"part word" feature** (campus,
  faculty, ...) in the first pass: F1 changed by at most 0.007. The translation stays because it costs nothing.
- **Removing non-universities around matching** (four attempts, before the final run): removed before
  matching, a record taken out of one source left its partner without a match, and the matcher gave it a
  wrong one. Removed after matching (two variants), the records stayed in the data. "Flag, match, remove,
  match again" gained nothing. All replaced by cleaning every source first (step 2).
- **Name-only matchers of any kind** (string, TF-IDF, embeddings, Monge-Elkan, Soundex): F1 0.70-0.79.
- **A cut-off set by hand against the ID links:** it used the answer key inside the pipeline; replaced
  by the validation-chosen cut-off.

## Limits

- 300 pairs per set are few: differences of 0.01-0.02 in F1 between approaches may be chance.
- The 486 pairs of the first hand-labelled sample come from our own earlier results.
- Wikidata and DEQAR are only joined through ROR; universities in both but not in ROR are not linked.

## Files and how to run

| Folder | What it holds |
|---|---|
| `common.py` | shared code: loading, the attribute comparators, labels and candidates, threshold search, `run_rules` / `run_matchers`. Code of one approach stays in its folder (05 and 07 take the TF-IDF and embedding scores from 02 and 03) |
| `gold_standard/` | `split_labelled_pairs.py`: writes the six set files from `labelled_pairs.csv` |
| `blocking/` | `blocking.py`: all blockers, writes `results/blocking.csv` and the candidate pairs (`results/candidates/`, not in git) |
| `01_` to `09_` | one script per approach; `results/first_pass/` and `results/final/`, each with `matching.csv` (every variant) and `best_<pair>*.csv` |
| `global_matching_and_test/` | `final.py`: best approach + one-to-one + cut-off, test scores, links (`correspondences_*`), group sizes, errors |
| `analysis/` | `cutoff_check.py`, `error_analysis.py`, `blocking_effect.py` |

Run each script from its own folder with `PYTHONHASHSEED=0` (otherwise ties between equal scores can
come out differently between runs):

```
cd gold_standard;                 python split_labelled_pairs.py
cd blocking;                      python blocking.py final      # about 3.5 hours (embedding blocker)
cd 01_rules_string_similarity;    python rule_based.py final
cd 02_rules_tfidf;                python tfidf.py final
cd 03_rules_embeddings;           python embeddings.py final
cd 04_rules_weight_search;        python weight_search.py final
cd 05_machine_learning;           python ml_based.py final
cd 06_rules_more_similarity;      python more_similarity.py final
cd 07_more_learners;              python more_learners.py final
cd 08_fine_tuned_language_model;  python fine_tuned_model.py final   # about 2 hours on a CPU, then cached
cd 09_local_llm;                  python local_llm.py final          # needs Ollama with qwen2.5:3b, about 2 hours, then cached
cd global_matching_and_test;      python final.py final
cd analysis;                      python cutoff_check.py; python error_analysis.py; python blocking_effect.py
```

The first pass: the same commands with `first_pass` instead of `final` (the analysis scripts only look
at the final run). The embeddings, the fine-tuned model and the LLM answers are cached in
`results/cache/` at the repository root (not in git). 08 needs `transformers` and `torch`; 09 needs a
running Ollama server (`ollama pull qwen2.5:3b`, best started with `OLLAMA_NUM_PARALLEL=8`).
