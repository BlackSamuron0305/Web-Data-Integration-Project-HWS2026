# Step 4: Identity resolution

This step finds the records that describe the same university in different sources. We match
**Wikidata–ROR** and **DEQAR–ROR**. ROR is the largest source and acts as the connector: Wikidata and
DEQAR records that link to the same ROR record end up in one group. We use PyDI and scikit-learn.

The ID links between the sources (a Wikidata or DEQAR record naming its ROR record) are our **answer
key**. We use them to sample labelled pairs and to check results, never inside blocking, matching or
cleaning.

## How we got here: rounds

We worked in rounds; the number after a script (`final.py 8`) is the round.

| Round | Data | What changed | Outcome |
|---|---|---|---|
| 1 | original | labels straight from the ID links, random non-matches, like the exercise | dropped: every matcher reached precision 1.000, the evaluation was too easy |
| 2 | original | checked labels with 50% hard cases, more blockers, all matcher types | honest scores; showed we need one-to-one matching |
| 3 | original | fixes from the error analysis; always one-to-one | end of the first pass |
| 4-7 | original | ways of removing non-universities around matching | dropped (see below) |
| **8** | **cleaned (step 2)** | same methods on the cleaned data, plus a stricter final cut-off | **final pipeline** |

## What we did

### 1. Labelled pairs (`01_labels/`)

**Round 1** took 900 pairs per dataset pair: ID links as matches, random pairs as non-matches. Every
matcher got precision 1.000, and Wikidata–ROR produced 133,694 links for only 22,697 Wikidata records.
The random non-matches were so different that nothing could look like a wrong match, so the threshold
fell to the floor. The evaluation set was too easy, not the matcher good.

**Round 2** follows the course: a pool of about 1,000 pairs per dataset pair, half of them hard cases
(names that differ, similar names of different universities, a campus against its university, the same
name in another country), 20% random matches from the ID links and 30% random non-matches. Every pair
was checked against both records and corrected or dropped where needed (`01_labels/results/review_*.csv`
says which and why). This gave about 340 training, 320 validation and 310 test pairs per dataset pair,
42-45% of them matches. Later we added 200 test pairs per dataset pair in the same mix, so each test set
has 510 pairs. Typical corrections: wrong ID links (*University of Glamorgan* linked to *Glamorgan
Archives*), campus against university, a predecessor linked to its successor, and the same university
with two country codes (Vatican universities VA vs IT). DEQAR's ID links needed more corrections than
Wikidata's.

### 2. Blocking (`02_blocking/`)

Comparing every pair would mean 684 million Wikidata–ROR and 271 million DEQAR–ROR comparisons, so
blocking picks the candidate pairs. What matters is how many true matches survive (pair completeness).

| Blocker | Wikidata–ROR | DEQAR–ROR | Verdict |
|---|---|---|---|
| exercise key (2 letters of 3 words) | 0.53 | 0.39 | loses the hard cases |
| normalised name | 0.42 | 0.27 | loses the hard cases |
| sorted neighbourhood, window 20 | 0.66 | 0.53 | loses the hard cases |
| every name word / name 3-grams | – | – | too many pairs (up to 2.1 billion), not runnable |
| country + name word (`DE_heidelberg`) | 0.89 | 0.92 | good |
| same web domain | 0.80 | 0.76 | finds renamed universities |
| embedding: 10 nearest names | 0.80 | 0.72 | finds other spellings |
| **union of the last three** | **0.993** | **0.972** | **used** |

The three blockers each find matches the others miss. The embedding search was the slowest: its
Wikidata–ROR run grew from 41 s in the first pass to about 2 hours in the second with unchanged code,
for reasons we could not find. `05_final/blocking_effect.py` shows it adds little: without it the final
Wikidata–ROR result is the same and DEQAR–ROR loses one validation match.

### 3. Matching (`03_rule_based/`, `04_ml_based/`)

A matcher scores each candidate pair; pairs above a threshold (chosen on the validation pairs) become
links. On the validation pairs of the final round:

| Matcher | Wikidata–ROR F1 | DEQAR–ROR F1 |
|---|---|---|
| name only (Jaro-Winkler) | 0.79 | 0.80 |
| rule over all attributes, weights set by hand | 0.93 | 0.91 |
| logistic regression | **0.97** | 0.94 |
| random forest | 0.97 | **0.95** |
| gradient boosting | 0.97 | 0.93 |

- A name alone is not enough: the best threshold accepts almost every pair (*Seisen University*
  exists in Tokyo and in Nagano). Which name measure we used hardly mattered.
- The web domain is what makes rules precise. The hand-set rule is precise but misses matches where a
  value is missing.
- The learned models (14 features on name, country, domain, city, founding year, distance and missing
  values) win, mostly because they learn that a missing year or website is no evidence against a match.
  We use logistic regression for Wikidata–ROR and random forest for DEQAR–ROR.

### 4. Global matching and group sizes (`05_final/`)

A source should list a university only once, so each record may have at most one partner per dataset
pair. Greedy one-to-one and stable matching raised validation precision to 0.98-1.00; maximum bipartite
matching lost too much recall. In round 2 our script picked "no one-to-one" for DEQAR–ROR because its
validation F1 was 0.013 higher: test precision dropped to 0.87, and **one group held 4,509 records**,
which fusion would have merged into a single university. A score on a few hundred pairs cannot show
this; the group sizes can. Since round 3 we always use greedy one-to-one, so every group is a pair or a
triple.

### 5. Final cut-off (`05_final/cutoff_check.py`)

A wrong link merges two universities into one entry; a missed link only lists one university twice. We
think the first is worse, so after one-to-one matching we raise the threshold: 0.45 to **0.7** for
Wikidata–ROR and 0.35 to **0.55** for DEQAR–ROR. Checked against the ID links, this removes 150 of 359
wrong Wikidata–ROR links for 338 right ones, and 66 of 174 wrong DEQAR–ROR links for 62 right ones.
Going higher would cost more than 3 right links per wrong one.

### 6. Final results

On the test pairs whose two records survive the cleaning (441 Wikidata–ROR, 447 DEQAR–ROR):

| | Wikidata–ROR P / R / F1 | DEQAR–ROR P / R / F1 | Links |
|---|---|---|---|
| first pass (round 3) | .986 / .916 / .950 | .986 / .912 / .948 | 14,824 / 4,714 |
| second pass before the cut-off | .986 / .923 / .953 | .987 / .931 / .958 | 13,673 / 4,477 |
| **final (round 8)** | **.993 / .865 / .924** | **1.000 / .906 / .950** | **12,266 / 4,026** |

Cleaning did not lower the scores, and the 1,628 first-pass links to removed records are gone. The cut-off
trades recall for fewer wrong merges, as intended.

### 7. Check on 500 hand-labelled pairs (`12_gold_check/`)

99% of the test matches have an ID link, so the test set says little about links without one. A team
member therefore labelled 500 harder pairs by hand (`data/golden_set/hand_labelled_pairs/`), 250 per
dataset pair, oversampling links the ID links contradict or cannot confirm. A blind relabelling by AI
agents agreed with nearly all hand labels. Weighted back to all final links, **about 97% of the links
are correct** (precision 0.966 Wikidata–ROR, 0.974 DEQAR–ROR). Most wrong links join different
institutions in the same city whose names share a word (*Guangzhou Sport University* and *Guangzhou
Police College*). Of the 94 missed matches, 42 fell to the cut-off, 27 to a stronger competing link and
25 scored below the threshold; blocking lost none.

## What did not work

- **Round 1 labels** (ID links and random pairs): far too easy, see above. An even earlier version
  (commit `6679e95`) used 50,000 unchecked pairs and reported F1 96-99% for the same reason.
- **Picking global matching by validation F1** (round 2): produced the 4,509-record group.
- **Maximum bipartite matching:** swaps strong pairs for several weak ones and loses recall.
- **Translating common words** (*universidad* to *university*) and a **"part word" feature** (campus,
  faculty, ...) in round 3: F1 changed by at most 0.007. The translation stays because it costs nothing.
- **Removing non-universities around matching** (rounds 4-7): removed before matching (round 4), a
  record taken out of one source left its partner without a match, and the matcher gave it a wrong one
  (76 new links for 78 records). Removed after matching (rounds 5 and 6), 383 links to non-universities
  disappeared without new errors, but the records stayed in the data. "Flag, match, remove, match again"
  (round 7) gained nothing (test F1 -0.007 / +0.007). All replaced by cleaning every source first
  (step 2).
- **Extra matchers** (folders `06_` to `11_`), tried on the round-3 candidates with the same labels,
  validation thresholds and one-to-one matching, test F1 on the original test pairs:

  | Matcher | Wikidata–ROR | DEQAR–ROR |
  |---|---|---|
  | TF-IDF on words and character n-grams of all names (`07_tfidf/`) | 0.843 | 0.883 |
  | multilingual sentence embeddings of the names only (`08_semantic/`) | 0.824 | 0.733 |
  | embeddings + country + domain (`08_semantic/`) | 0.940 | 0.932 |
  | 252 searched rule weightings (`09_optimized_rules/`) | 0.885 | 0.927 |
  | hand-set rule weights, threshold retuned | 0.954 | 0.945 |
  | our learned matcher (`10_ml_baseline_reproduction/` reproduces it) | 0.936 | 0.940 |

  Names alone fall short again; country and domain are what lift the embeddings. The searched weights
  looked best on single training pairs but lost after one-to-one matching. The retuned hand-set rule
  found 3 more of 123 Wikidata–ROR test matches than our learned matcher, and 1 more for DEQAR–ROR, but
  these test pairs had already informed earlier choices, so we kept the learned matchers.
- **Not tried:** an LLM as matcher (needs a paid API) and character 3-gram blocking (2.1 billion
  candidate pairs).

## Limits

- We saw the test scores during development and extended the test sets, so they may be slightly
  optimistic.
- Wikidata and DEQAR are only joined through ROR; universities in both but not in ROR are not linked.
- **Checked by AI, not yet by a person:** the 200 extra test pairs per dataset pair
  (`01_labels/results/pool_extra_*.csv`, `review_extra_*.csv`), the corrections of the round-2 pool
  (`review_*.csv`, to be spot-checked) and the 6,000 round-8 links in
  `05_final/results/ai_check_links_r8.csv`.

## Files and how to run

| Folder | What it holds |
|---|---|
| `common.py` | shared code: loading, blocking keys, comparators, labels, evaluation |
| `01_labels/` | `labels.py`: builds the labelled pairs (written to `data/golden_set/labelled_pairs/`) |
| `02_blocking/` | `blocking.py`: all blockers, writes `results/blocking.csv` and the candidate pairs |
| `03_rule_based/` | `rule_based.py`: name measures and hand-set rules |
| `04_ml_based/` | `ml_based.py`: logistic regression, random forest, gradient boosting |
| `05_final/` | `final.py`: best matcher + one-to-one + cut-off, test scores, links (`correspondences_*`), group sizes, errors; `cutoff_check.py`; `blocking_effect.py` |
| `06_` to `11_` | the extra matchers; `11_comparison/` freezes their choices, evaluates them on test, analyses the errors and draws the figures |
| `12_gold_check/` | `gold_check.py`: evaluation on the 500 hand-labelled pairs |

Each step folder has a `results/` folder (one row per run, column `round`) and a `plots.ipynb` with the
charts. Run each script from its own folder and set `PYTHONHASHSEED=0` first; otherwise ties between
equal scores can come out differently between runs.

```
cd 01_labels;      python labels.py 2      # not "pool" or "extra": they overwrite the checked files
cd 02_blocking;    python blocking.py 8
cd 03_rule_based;  python rule_based.py 8
cd 04_ml_based;    python ml_based.py 8
cd 05_final;       python final.py 8; python cutoff_check.py; python blocking_effect.py
cd 12_gold_check;  python gold_check.py
```

The extra matchers run from the repository root, in folder order:
`python -u scripts/04_identity_resolution/<folder>/<script>.py` (`06_regenerate_candidates`,
`07_tfidf/tfidf_matching.py`, `tfidf_refined.py`, `08_semantic`, `09_optimized_rules/extract_rule_features.py`,
`optimized_rules.py`, `10_ml_baseline_reproduction`, then in `11_comparison/` `freeze_configurations.py`,
`evaluate_final.py`, `error_analysis.py`, `verify_extensions.py`, `plot_results.py`). The embeddings need
`sentence-transformers` and `torch` from `requirements.txt`. Blocking candidates and feature caches are
not in git; rerun the blocking to get them.
