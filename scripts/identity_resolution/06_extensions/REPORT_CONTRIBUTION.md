# Identity Resolution: Additional Matching Experiments

## 1. Objective

The existing identity resolution pipeline was extended to
investigate whether statistical text representations,
multilingual semantic embeddings and systematic rule
optimization improve higher education institution matching.

## 2. Experimental setup

The experiments use Wikidata, ROR and DEQAR, with ROR
serving as the connector dataset.

The existing multi-pass blocking strategy was retained.
It combines country-scoped name tokens, shared website
domains and embedding-based candidate retrieval.

Regeneration produced 756,323 Wikidata-ROR candidates
and 274,186 DEQAR-ROR candidates.

Validation pair completeness was 0.9928 and 0.9716,
respectively.

All selected configurations were frozen before final test
evaluation. Greedy one-to-one matching was applied to
resolve conflicting correspondences.

## 3. TF-IDF matching

Word-level and character-level TF-IDF representations
were investigated as alternatives to conventional
string similarity measures.

Cosine similarity was computed using sparse matrices.
The initial experiments used primary institution names.
Subsequent experiments incorporated alternative names,
acronyms and translated name variants.

Including name variants improved validation performance
after greedy matching across both dataset pairs.

The selected configurations achieved test F1-scores
of 0.8426 for Wikidata-ROR and 0.8831 for DEQAR-ROR.

These results suggest that corpus-based lexical similarity
provides useful matching evidence, but remains limited
when used without structured institution attributes.

## 4. Multilingual semantic matching

Multilingual institution names were represented using
the pretrained paraphrase-multilingual-MiniLM-L12-v2
sentence transformer.

The model produces 384-dimensional embeddings.
Cosine similarity was calculated for blocked candidate
pairs without fine-tuning the model.

Two variants were investigated:

- Pure semantic similarity.
- Hybrid similarity combining semantic name similarity
  (0.50), country (0.20) and website domain (0.30).

The hybrid variant improved test F1 from 0.8241 to
0.9397 for Wikidata-ROR, and from 0.7327 to 0.9316
for DEQAR-ROR.

These findings demonstrate the value of combining
semantic representations with structured evidence.
Semantic relatedness alone is insufficient to establish
institutional identity.

## 5. Rule weight optimization

Six similarity features were extracted and cached:
institution name, country, domain, city, founding year
and geographic proximity.

A systematic grid of 252 nonnegative weight combinations
summing to one was evaluated using training labels.
The three highest-ranked grid configurations for each
dataset pair were shortlisted for validation.

The original manually assigned weights were retained
as a controlled comparison.

The optimized weights achieved test F1-scores of
0.8850 and 0.9270, respectively.

Both selected optimized rules assigned zero weight to
name similarity. Although strong during training-pair
screening, they underperformed the original weights
after global matching.

This suggests that local pair classification is not
necessarily an adequate proxy for global entity resolution.

## 6. Controlled baseline reproduction

The existing logistic regression and random forest
classifiers were reproduced using the regenerated blocking
candidates and original feature configurations.

The original validation and test metrics were reproduced.
Correspondence-level Jaccard overlap was 0.999056
for Wikidata-ROR and 0.998304 for DEQAR-ROR.

The classifiers were additionally evaluated with thresholds
optimized after greedy matching.

Retuning did not improve test F1 for either classifier.

## 7. Final evaluation

| Method | W-R Precision | W-R Recall | W-R F1 | D-R Precision | D-R Recall | D-R F1 |
|---|---:|---:|---:|---:|---:|---:|
| TF-IDF | .9785 | .7398 | .8426 | .9444 | .8293 | .8831 |
| Semantic only | .9570 | .7236 | .8241 | .9367 | .6016 | .7327 |
| Semantic hybrid | 1.0000 | .8862 | .9397 | .9820 | .8862 | .9316 |
| Optimized rules | .9709 | .8130 | .8850 | .9818 | .8780 | .9270 |
| Original rules, retuned | .9912 | .9187 | .9536 | .9911 | .9024 | .9447 |
| Original ML | .9821 | .8943 | .9362 | .9910 | .8943 | .9402 |
| Retuned ML | .9821 | .8943 | .9362 | .9910 | .8943 | .9402 |

The original weighted rule with a validation-selected
threshold of 0.50 achieved the highest observed test
F1-score for both dataset pairs.

Compared with the original ML baselines, the observed
improvements were 1.74 and 0.45 percentage points.

## 8. Error analysis

Across all configurations, 308 error observations were
identified, representing 130 unique erroneous record pairs.

Five positive Wikidata-ROR test pairs and two positive
DEQAR-ROR test pairs were absent from the candidate sets.

Test blocking completeness was therefore 0.9593 and
0.9837, respectively.

Common qualitative failure patterns included multilingual
names, institutional renaming, identical names across
countries, shared domains and confusion between parent
institutions and individual campuses.

Competing assignments were frequently observed among
false negatives. Their presence does not independently
establish the cause of each matching failure.

## 9. Limitations

The existing test sets had been evaluated previously.
Consequently, they cannot be considered completely unseen.

Full human verification of the ground truth and additional
review samples remains pending.

The reported precision and recall apply to labeled pairs,
not every correspondence in the complete datasets.

The semantic hybrid's perfect measured precision on
Wikidata-ROR must therefore not be interpreted as perfect
precision across all generated predictions.

Statistical significance of the observed improvements
has not been established.

The weight search was coarse and only three optimized
configurations per dataset pair were evaluated globally.

## 10. Conclusion

Combining textual and structured institution attributes
was more effective than relying on name similarity alone.

The highest observed performance was achieved through
validation-based threshold optimization of the original
weighted rule.

Multilingual hybrid matching also achieved competitive
performance without training a supervised classifier.

The findings highlight the importance of structured
attributes, blocking quality and global matching constraints
in higher education institution identity resolution.
