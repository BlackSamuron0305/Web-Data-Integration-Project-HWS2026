# Identity Resolution - Extensions and Experimental Journal

Project: Web Data Integration HWS 2026
Author: Sanjeevani Rajpurohit
Branch: sanjeevani-identity-resolution
Date started: 2026-11-19
Baseline commit: 95857c778dd5ddbf81e083b18022621582debdac

## 1. Objective

Extend the existing identity resolution pipeline for Wikidata,
ROR and DEQAR by investigating additional matching techniques,
improving code quality and evaluating matching performance.

The main objective is to investigate whether recall can be
improved while maintaining high precision.

## 2. Existing Implementation

The existing implementation by Laith includes:

- Name normalization and multilingual word translation
- Standard blocking
- Sorted neighbourhood blocking
- Token-based blocking
- Embedding-based blocking
- Multi-pass blocking
- Levenshtein similarity
- Jaro-Winkler similarity
- Jaccard similarity
- Weighted rule-based matching
- Logistic Regression
- Random Forest
- Gradient Boosting
- Greedy one-to-one matching
- Stable matching
- Maximum bipartite matching

Detailed methodology and previous experiments are documented
in IDENTITY_RESOLUTION_REASONING.txt.

## 3. Datasets

| Dataset | Records |
|---|---:|
| Wikidata | 22,697 |
| ROR | 30,131 |
| DEQAR | 8,979 |
| Total | 61,807 |

ROR serves as the connector dataset.

Dataset pairs:
- Wikidata-ROR
- DEQAR-ROR

## 4. Existing Baseline Results

| Dataset pair | Precision | Recall | F1 |
|---|---:|---:|---:|
| Wikidata-ROR | 0.982 | 0.894 | 0.936 |
| DEQAR-ROR | 0.991 | 0.894 | 0.940 |

These are previously reported Round 3 test results.
Independent reproduction is pending.

## 5. Proposed Approaches

### 5.1 TF-IDF and Cosine Similarity

Investigate word-level and character-level TF-IDF
representations for institution name matching.

Motivation:
Traditional string similarity measures do not explicitly
account for the relative importance of terms across a corpus.
TF-IDF may help distinguish informative institution names
from commonly occurring words.

Status: Pending

### 5.2 Multilingual Semantic Embedding Matching

Investigate pretrained multilingual sentence embeddings
and cosine similarity for institution matching.

Motivation:
Institution names may differ across languages, translations
and spelling variations. The existing pipeline uses embeddings
for blocking but not directly for matching decisions.

Status: Pending

### 5.3 Optimized Rule-Based Matching

Investigate systematic optimization of attribute weights
and similarity thresholds.

Motivation:
The existing matching rules use manually selected weights.
A systematic search may identify better configurations.

Status: Pending

## 6. Evaluation Methodology

Reuse the existing datasets, labeled pairs, blocking candidates
and evaluation framework for comparable experiments.

Evaluation metrics:

- Precision
- Recall
- F1-score
- Execution time
- Number of correspondences
- Pair completeness
- Reduction ratio
- Cluster size distribution

Parameter selection will be performed using validation data.
The existing test set has already been evaluated in previous
rounds, which limits its independence for further experiments.

## 7. Code Cleanup and Improvements

- Review missing-value handling.
- Reduce redundant feature computation.
- Investigate feature caching.
- Remove unnecessary imports and code duplication.
- Improve reproducibility and configuration management.
- Review ground-truth label quality.
- Add tests for important functions.
- Standardize experimental outputs.

## 8. Experimental Journal

### Experiment 0 - Initial Review (2026-11-19)

Objective:
Understand the existing implementation and identify
potential extensions.

Actions:
- Reviewed the existing repository structure.
- Reviewed the identity resolution research journal.
- Reviewed the Python source code.
- Created a separate development branch.

Observations:
- High reported precision but comparatively lower recall.
- Traditional string similarity methods are already explored.
- Supervised classification methods are already implemented.
- Embeddings are used for blocking rather than matching.
- Rule-based weights are manually selected.
- Ground-truth label verification requires human review.

Decision:
Investigate statistical text similarity, multilingual semantic
similarity and optimized rule-based matching.

Status: Initial review completed. Implementation pending.

## 9. Experimental Results

To be updated after each experiment.

## 10. Limitations and Lessons Learned

To be updated throughout the project.

## 11. References

To be added alongside the relevant experiments.


### Experiment 1 - Environment Setup

Date: 2026-11-19

Objective:
Establish an isolated and reproducible environment compatible
with the existing identity resolution pipeline.

Configuration:
- Python: 3.12.16
- Architecture: arm64
- Operating system: Darwin
- Environment manager: Conda
- Environment directory: .venv

Installed dependencies:

| Package | Version |
|---|---|
| uma-pydi | 0.2.1 |
| pandas | 2.3.3 |
| numpy | 2.1.3 |
| scikit-learn | 1.9.1 |
| rapidfuzz | 3.14.6 |
| lxml | 5.4.0 |
| matplotlib | 3.10.0 |
| sentence-transformers | 5.7.0 |
| torch | 2.15.0 |

Observations:
- All required package imports succeeded.
- pip check reported no broken requirements.
- Sentence Transformers and PyTorch are already available.
- No additional dependencies were required at this stage.
- Blocking candidates are excluded from Git and must be
  regenerated locally.

Reproducibility:
Installed Python package versions are recorded in
requirements-identity-resolution-lock.txt.

Status: Completed successfully.


### Experiment 2 - Baseline Verification (2026-11-19)

Objective:
Verify the evaluation metrics reported by the existing
identity resolution implementation before introducing
additional matching approaches.

Method:
Loaded the saved Round 3 correspondences and evaluated
them against the existing labeled validation and test
sets using the PyDI evaluation framework.

Dataset statistics:

| Dataset pair | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| Wikidata-ROR | 339 | 310 | 312 | 961 |
| DEQAR-ROR | 347 | 328 | 310 | 985 |

Results:

| Dataset pair | Split | Precision | Recall | F1 | Correspondences |
|---|---|---:|---:|---:|---:|
| Wikidata-ROR | Validation | 0.9926 | 0.9710 | 0.9817 | 14824 |
| Wikidata-ROR | Test | 0.9821 | 0.8943 | 0.9362 | 14824 |
| DEQAR-ROR | Validation | 0.9846 | 0.9078 | 0.9446 | 4714 |
| DEQAR-ROR | Test | 0.9910 | 0.8943 | 0.9402 | 4714 |

Observations:
- All reported Round 3 evaluation metrics were reproduced.
- All labeled splits contain at least 300 pairs.
- Both dataset pairs exhibit high precision.
- Recall remains comparatively lower.
- Additional approaches should investigate whether recall
  can be improved without significantly reducing precision.

Limitations:
- Evaluation was performed on saved correspondences.
- The complete matching pipeline was not rerun.
- Ground-truth labels still require human verification.
- The existing test set has been evaluated previously.

Decision:
Reuse the existing Round 3 blocking strategy and labeled
datasets for controlled comparisons of additional methods.
Use validation results for parameter and model selection.

Status: Completed successfully.


### Experiment 3 - Blocking Candidate Regeneration

Date: 2026-11-19

Objective:
Regenerate the Round 3 blocking candidates while keeping
the existing blocking methodology fixed for fair comparison.

Initial results (Wikidata-ROR):
- Country + name tokens: 602373 candidate pairs
- Shared website domain: 12445 candidate pairs
- Embedding-based blocking: failed

Technical issue:
PyTorch attempted to execute embedding generation using
the Apple Silicon MPS backend. Execution terminated due
to an NSInvalidArgumentException involving MPSNDArray.

Proposed solution:
Execute embedding generation on the CPU instead of MPS,
without changing the underlying blocking methodology.

Status: CPU compatibility testing pending.


#### Experiment 3.1 - CPU Compatibility Fix

Environment:
- macOS 14.5
- Apple Silicon ARM64
- PyTorch 2.15.0
- MPS available but incompatible during embedding execution

Compatibility test:
- Model: sentence-transformers/all-MiniLM-L6-v2
- Device: CPU
- Input: three university names
- Output shape: (3, 384)
- Result: successful

Implementation:
Created scripts/03_identity_resolution/06_regenerate_candidates/
regenerate_candidates.py.

The script reuses the existing Round 3 multi-pass blocking
strategy while explicitly setting the embedding device to CPU.

Unchanged parameters:
- Embedding model: all-MiniLM-L6-v2
- Top-k: 10
- Similarity threshold: 0.5
- Country-scoped token blocking
- Shared website domain blocking

Rationale:
Resolve the hardware compatibility issue without changing
the experimental methodology or reinstalling dependencies.

Status: CPU compatibility verified.
Full candidate regeneration pending.


#### Experiment 3.2 - Successful Blocking Regeneration

The Round 3 multi-pass blocking strategy was successfully
executed using CPU-based embedding generation.

| Blocking method | Wikidata-ROR | DEQAR-ROR |
|---|---:|---:|
| Country + name tokens | 602373 | 207638 |
| Shared website domain | 12445 | 4826 |
| Embedding blocking | 220647 | 87153 |
| Union | 756323 | 274186 |
| Pair completeness | 0.9928 | 0.9716 |
| Reduction ratio | 0.998894 | 0.998987 |

Execution time per blocking pass (seconds):

| Blocking method | Wikidata-ROR | DEQAR-ROR |
|---|---:|---:|
| Country + name tokens | 0.9 | 0.6 |
| Shared website domain | 0.2 | 0.1 |
| Embedding blocking | 110.3 | 72.2 |

Observations:
- CPU execution resolved the MPS compatibility issue.
- Both dataset pairs satisfy the pair completeness target.
- A total of 1030509 unique candidate pairs were generated.
- The existing blocking strategy remains unchanged.
- Exact candidate equivalence with the original run has
  not been established.

Decision:
Keep these regenerated candidates fixed for all subsequent
matching experiments.

Candidate file SHA-256 checksums:

- deqar_ror_r3_union__country___name_word___same_domain___embedding.csv: 798e61e57fa6be2492e015cb4c0f5473b1ba269f4b12c8cf8d192e881e201d2d
- wikidata_ror_r3_union__country___name_word___same_domain___embedding.csv: 1fecf1571771f9180f6a12f52f5adba39681caec96a93910d35f86466170abdb

Status: Completed successfully.


### Experiment 4 - TF-IDF and Cosine Similarity

Objective:
Investigate corpus-based text similarity as an alternative
to traditional string similarity measures.

Configuration:
- Fixed Round 3 blocking candidates
- Normalized primary institution names
- Word-level n-grams: 1-2
- Character-level n-grams: 3-5
- L2 normalization
- Sublinear term frequency
- Cosine similarity
- Sparse matrix computation
- Batch size: 4096
- Threshold selection using validation F1
- Greedy one-to-one global matching

Results (validation):

| Pair | Method | Global matching | P | R | F1 | Corr. | Time (s) |
|---|---|---|---:|---:|---:|---:|---:|
| W-R | Word | None | .7273 | .7536 | .7402 | 95235 | 5.4 |
| W-R | Word | Greedy | .9495 | .6812 | .7932 | 15119 | 8.4 |
| W-R | Character | None | .7119 | .9130 | .8000 | 293534 | 15.5 |
| W-R | Character | Greedy | .9444 | .7391 | .8293 | 18141 | 24.6 |
| D-R | Word | None | .7000 | .6950 | .6975 | 25566 | 1.9 |
| D-R | Word | Greedy | .9100 | .6454 | .7552 | 4970 | 2.6 |
| D-R | Character | None | .6686 | .8014 | .7290 | 78807 | 6.6 |
| D-R | Character | Greedy | .9286 | .6454 | .7615 | 6526 | 8.6 |

Observations:
- Character TF-IDF achieved higher F1 on both dataset pairs.
- Greedy matching increased precision but reduced recall.
- TF-IDF was computationally efficient.
- All configurations selected a threshold of 0.30.

Limitations:
- Only primary institution names were considered.
- The selected threshold is at the lower search boundary.
- Thresholds were selected before global matching.
- Other institution attributes were not considered.
- No test-set evaluation was performed.

Next steps:
- Include alternative names and acronyms.
- Expand the threshold search range.
- Optimize thresholds after global matching.

Status: Initial experiment completed successfully.


#### Experiment 4.1 - Refined TF-IDF: Initial Attempt

Extensions:
- Alternative institution names and acronyms
- Translated name variants
- Expanded threshold range: 0.05 to 1.00
- Threshold optimization after greedy matching

Initial results for Wikidata-ROR, primary-name word TF-IDF:

| Metric | Original | Refined |
|---|---:|---:|
| Precision | 0.9495 | 0.9423 |
| Recall | 0.6812 | 0.7101 |
| F1 | 0.7932 | 0.8099 |

Technical issue:
The equivalence assertion between thresholding before and
after greedy matching failed for the all-names configuration.

A possible explanation is inconsistent tie-breaking between
candidate pairs with identical similarity scores. The exact
internal cause has not yet been confirmed.

Solution:
Execute PyDI greedy matching independently at each threshold
and evaluate the resulting correspondences on validation data.
Retain the configuration with the highest F1-score.

Additional verification:
Check that the final correspondences satisfy the one-to-one
matching constraint.

Trade-off:
Additional computational cost due to repeated greedy matching.
Runtime now includes the complete threshold search.

Status: Fix implemented. Full experiment must be rerun.


#### Experiment 4.2 - Refined TF-IDF Results

Objective:
Investigate the impact of alternative institution names,
acronyms, translated names and threshold optimization.

Configuration:
- Word-level n-grams: 1-2
- Character-level n-grams: 3-5
- Primary names versus all available name variants
- Pooled TF-IDF representation for alternative names
- Threshold range: 0.05 to 1.00, step 0.05
- Independent threshold optimization for greedy matching
- Fixed Round 3 blocking candidates
- Validation data only

Results:

| Pair | Method | Names | Global | Threshold | P | R | F1 | Corr. | Time |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| wikidata-ror | word_tfidf | primary_name | none | 0.05 | 0.6739 | 0.8986 | 0.7702 | 456596 | 50.7s |
| wikidata-ror | word_tfidf | primary_name | greedy | 0.05 | 0.9423 | 0.7101 | 0.8099 | 19124 | 50.7s |
| wikidata-ror | word_tfidf | all_names | none | 0.30 | 0.7708 | 0.8043 | 0.7872 | 53407 | 43.2s |
| wikidata-ror | word_tfidf | all_names | greedy | 0.10 | 0.9907 | 0.7681 | 0.8653 | 18481 | 43.2s |
| wikidata-ror | char_tfidf | primary_name | none | 0.25 | 0.7049 | 0.9348 | 0.8037 | 350021 | 92.3s |
| wikidata-ror | char_tfidf | primary_name | greedy | 0.05 | 0.9537 | 0.7464 | 0.8374 | 20158 | 92.3s |
| wikidata-ror | char_tfidf | all_names | none | 0.40 | 0.7346 | 0.8623 | 0.7933 | 105083 | 87.2s |
| wikidata-ror | char_tfidf | all_names | greedy | 0.05 | 0.9730 | 0.7826 | 0.8675 | 20277 | 87.2s |
| deqar-ror | word_tfidf | primary_name | none | 0.10 | 0.6790 | 0.7801 | 0.7261 | 93944 | 14.8s |
| deqar-ror | word_tfidf | primary_name | greedy | 0.10 | 0.9135 | 0.6738 | 0.7755 | 6718 | 14.8s |
| deqar-ror | word_tfidf | all_names | none | 0.30 | 0.7469 | 0.8582 | 0.7987 | 17129 | 14.9s |
| deqar-ror | word_tfidf | all_names | greedy | 0.05 | 0.9508 | 0.8227 | 0.8821 | 6967 | 14.9s |
| deqar-ror | char_tfidf | primary_name | none | 0.15 | 0.6816 | 0.8652 | 0.7625 | 137357 | 28.6s |
| deqar-ror | char_tfidf | primary_name | greedy | 0.25 | 0.9300 | 0.6596 | 0.7718 | 6828 | 28.6s |
| deqar-ror | char_tfidf | all_names | none | 0.10 | 0.6700 | 0.9645 | 0.7907 | 211384 | 30.6s |
| deqar-ror | char_tfidf | all_names | greedy | 0.15 | 0.9391 | 0.7660 | 0.8437 | 6952 | 30.6s |

Observations:
- Alternative names improved greedy matching F1 across
  both TF-IDF methods and both dataset pairs.
- Best Wikidata-ROR configuration: character TF-IDF
  with all names (F1 = 0.8675).
- Best DEQAR-ROR configuration: word TF-IDF
  with all names (F1 = 0.8821).
- Greedy matching consistently improved precision
  at the cost of recall.
- Runtime includes the complete threshold search.

Improvement over initial best TF-IDF results:
- Wikidata-ROR: 0.8293 to 0.8675
- DEQAR-ROR: 0.7615 to 0.8821

Limitations:
- Alternative names are pooled rather than individually
  compared.
- Some optimal thresholds remain at the search boundary.
- Name-only matching underperforms the existing
  multi-attribute classifiers.
- Improvements over the initial experiment cannot be
  attributed solely to alternative names.
- No test-set evaluation was performed.

Conclusion:
TF-IDF provides a computationally efficient statistical
matching approach. Incorporating name variants improves
performance, but additional attributes remain important.

Decision:
Conclude TF-IDF experimentation and proceed to
multilingual semantic embedding matching.

Status: Completed successfully.


### Experiment 5 - Multilingual Semantic Matching

Research question:
Can pretrained multilingual sentence embeddings improve
identity resolution across higher education institution datasets?

Motivation:
Lexical similarity measures rely on surface-level text
similarity and may struggle with multilingual institution names.

Model:
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Reference:
https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Configuration:
- Pretrained multilingual sentence transformer
- 384-dimensional dense embeddings
- Original primary institution names
- L2-normalized vectors
- Cosine similarity clipped to [0, 1]
- CPU execution to avoid the previously observed MPS crash
- Encoding batch size: 32
- Candidate scoring batch size: 4096
- Random seed: 2026
- Fixed Round 3 blocking candidates
- Validation-only threshold optimization
- Greedy one-to-one matching
- No model fine-tuning

Configurations:
1. Pure semantic similarity.
2. Hybrid semantic similarity with country and web domain.

Hybrid weights:
- Semantic name similarity: 0.5
- Country: 0.2
- Web domain: 0.3

The hybrid configuration reuses an existing weighting
scheme from the original experiments.

Efficiency:
Each unique primary name is encoded once per dataset.
ROR embeddings are reused for both dataset pairs.
Candidate similarities are computed in batches.

Limitations:
- Semantic similarity does not necessarily imply identity.
- Only primary names are encoded in this experiment.
- Hybrid weights are not optimized yet.
- Missing domain information contributes zero similarity.

Status: Implementation completed. Execution pending.


#### Experiment 5.1 - Semantic Matching Results

Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Revision: e8f8c211226b894fcb81acc59f3b34ba3efd5f42
Device: cpu
Random seed: 2026

Embedding generation:
- wikidata: 41.4s
- ror: 57.5s
- deqar: 21.9s


Results (validation):

| Pair | Matcher | Global | Threshold | P | R | F1 | Corr. | Search time |
|---|---|---|---:|---:|---:|---:|---:|---:|
| wikidata-ror | semantic_only | none | 0.50 | 0.6683 | 0.9783 | 0.7941 | 579615 | 207.9s |
| wikidata-ror | semantic_only | greedy | 0.45 | 0.9340 | 0.7174 | 0.8115 | 20437 | 207.9s |
| wikidata-ror | semantic_hybrid | none | 0.70 | 0.9915 | 0.8406 | 0.9098 | 13163 | 171.2s |
| wikidata-ror | semantic_hybrid | greedy | 0.25 | 0.9924 | 0.9493 | 0.9704 | 20559 | 171.2s |
| deqar-ror | semantic_only | none | 0.25 | 0.6683 | 0.9716 | 0.7919 | 265190 | 74.8s |
| deqar-ror | semantic_only | greedy | 0.50 | 0.9286 | 0.6454 | 0.7615 | 7763 | 74.8s |
| deqar-ror | semantic_hybrid | none | 0.60 | 0.8344 | 0.8936 | 0.8630 | 19479 | 55.4s |
| deqar-ror | semantic_hybrid | greedy | 0.50 | 0.9766 | 0.8865 | 0.9294 | 5137 | 55.4s |

Observations:
- All 61807 institution records were represented by
  384-dimensional embeddings.
- CPU execution completed without compatibility issues.
- Pure semantic similarity achieved relatively high
  recall but low precision before global matching.
- Combining semantic similarity with country and domain
  information substantially improved matching performance.
- Best Wikidata-ROR validation F1: 0.9704.
- Best DEQAR-ROR validation F1: 0.9294.
- Hybrid matching approached the performance of the
  existing supervised ML approaches without model training.

Limitations:
- Only primary institution names were encoded.
- Semantic similarity does not necessarily imply identity.
- Hybrid attribute weights were manually selected.
- The hybrid matcher generated more correspondences than
  the existing final pipeline, requiring error analysis.
- Validation performance may be optimistic.
- No test-set evaluation was performed.
- Encoding and scoring times are shared across configurations
  and must not be counted twice.

Conclusion:
Combining multilingual semantic representations with
structured attributes is substantially more effective
than using semantic name similarity alone.

Decision:
Proceed to systematic optimization of attribute weights
and matching thresholds.

Status: Completed successfully.


### Experiment 6 - Optimized Rule-Based Matching

Research question:
Can systematically optimized attribute weights improve
identity resolution compared with manually selected weights?

Features:
- Best Jaro-Winkler similarity across institution names
- Country
- Website domain
- City similarity
- Founding year similarity
- Geographic proximity

Original weights:
[0.35, 0.15, 0.25, 0.10, 0.10, 0.05]

Proposed optimization methodology:
- Nonnegative weights summing to one
- Grid search with weight increments of 0.20
- 252 grid configurations plus the original weights
- Initial configuration screening on training labels
- Full candidate matching for shortlisted configurations
- Threshold and configuration selection on validation data
- Greedy one-to-one matching
- Fixed Round 3 blocking candidates
- No test-set tuning

Preliminary compatibility test:
- 25 Wikidata-ROR candidate pairs
- Six similarity features extracted successfully
- Output shape including record identifiers: (25, 8)
- No missing feature values in the sample

Efficiency:
- Extract similarity features once
- Process candidates in batches of 25000
- Cache feature matrices as float32 NumPy arrays
- Record candidate and feature checksums
- Reuse matrices across weight configurations

Limitations:
- Grid search does not guarantee a globally optimal solution.
- Existing comparators retain their original missing-value
  handling.
- A zero similarity can indicate disagreement or missing
  information, depending on the comparator.
- Ground-truth label quality remains a potential limitation.

Status: Feature extraction implementation completed.
Full extraction and weight optimization pending.


#### Experiment 6.1 - Feature Extraction Results

Full similarity feature extraction completed successfully
for both dataset pairs.

All extracted values are finite and within [0, 1].


Dataset pair: wikidata-ror
- candidate_sha256: 1fecf1571771f9180f6a12f52f5adba39681caec96a93910d35f86466170abdb
- feature_sha256: 2e8abde82878d9cc27a7dd4ce8030b509c0fad03c0edd9419b866b8bf056e01a
- rows: 756323
- columns: 6
- seconds: 175.2

| Feature | Min | Max | Mean | Std | Zero fraction |
|---|---:|---:|---:|---:|---:|
| names_best_jaro_winkler | 0.0000 | 1.0000 | 0.7443 | 0.1139 | 0.0011 |
| country | 0.0000 | 1.0000 | 0.8475 | 0.3553 | 0.1462 |
| domain | 0.0000 | 1.0000 | 0.0165 | 0.1271 | 0.9835 |
| city | 0.0000 | 1.0000 | 0.4736 | 0.2875 | 0.1867 |
| year | 0.0000 | 1.0000 | 0.1130 | 0.2691 | 0.8169 |
| geo | 0.0000 | 1.0000 | 0.1239 | 0.3055 | 0.8459 |

Dataset pair: deqar-ror
- candidate_sha256: 798e61e57fa6be2492e015cb4c0f5473b1ba269f4b12c8cf8d192e881e201d2d
- feature_sha256: d2f3df5eaaa26e228f3139bccc8a432d597724044f8b458e0a93c574b9f735d6
- rows: 274186
- columns: 6
- seconds: 55.7

| Feature | Min | Max | Mean | Std | Zero fraction |
|---|---:|---:|---:|---:|---:|
| names_best_jaro_winkler | 0.3510 | 1.0000 | 0.7347 | 0.1080 | 0.0000 |
| country | 0.0000 | 1.0000 | 0.7914 | 0.4055 | 0.2074 |
| domain | 0.0000 | 1.0000 | 0.0176 | 0.1316 | 0.9824 |
| city | 0.0000 | 1.0000 | 0.3952 | 0.3338 | 0.3439 |
| year | 0.0000 | 1.0000 | 0.0905 | 0.2465 | 0.8575 |
| geo | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 |


Observations:
- 1030509 candidate pairs processed.
- 6183054 similarity values computed.
- Combined feature matrix size: 23.59 MiB.
- Wikidata-ROR extraction time: 175.2 seconds.
- DEQAR-ROR extraction time: 55.7 seconds.
- Geographic similarity is zero for every DEQAR-ROR pair.
- Domain similarity is zero for over 98 percent of candidates.
- Zero similarity does not necessarily indicate missing data.
- Feature distributions are influenced by the blocking strategy.

Decision:
Optimize attribute weights separately for each dataset pair.
Reuse cached features throughout the optimization process.

Status: Feature extraction completed successfully.


#### Experiment 6.2 - Weight Optimization Results

Configuration:
- 252 grid weight combinations
- One original weight configuration
- Weight increments of 0.20
- Training-set screening
- Top three grid configurations per dataset pair
- Full candidate matching on shortlisted configurations
- Validation threshold optimization
- Greedy one-to-one matching

Results:

| Pair | Configuration | Global | Threshold | P | R | F1 | Corr. | Time |
|---|---|---|---:|---:|---:|---:|---:|---:|
| wikidata-ror | grid_026 | none | 0.20 | 0.8816 | 0.9710 | 0.9241 | 135369 | 56.7s |
| wikidata-ror | grid_026 | greedy | 0.10 | 0.9841 | 0.8986 | 0.9394 | 18126 | 56.7s |
| wikidata-ror | grid_040 | none | 0.20 | 0.8816 | 0.9710 | 0.9241 | 132701 | 54.7s |
| wikidata-ror | grid_040 | greedy | 0.10 | 0.9843 | 0.9058 | 0.9434 | 18090 | 54.7s |
| wikidata-ror | grid_084 | none | 0.40 | 0.8933 | 0.9710 | 0.9306 | 120598 | 95.8s |
| wikidata-ror | grid_084 | greedy | 0.10 | 0.9921 | 0.9130 | 0.9509 | 19872 | 95.8s |
| wikidata-ror | original | none | 0.65 | 0.9688 | 0.8986 | 0.9323 | 17528 | 136.5s |
| wikidata-ror | original | greedy | 0.50 | 0.9926 | 0.9710 | 0.9817 | 15995 | 136.5s |
| deqar-ror | grid_044 | none | 0.40 | 0.9110 | 0.9433 | 0.9268 | 36445 | 26.3s |
| deqar-ror | grid_044 | greedy | 0.40 | 0.9845 | 0.9007 | 0.9407 | 4726 | 26.3s |
| deqar-ror | grid_085 | none | 0.40 | 0.8940 | 0.9574 | 0.9247 | 46313 | 30.2s |
| deqar-ror | grid_085 | greedy | 0.40 | 0.9923 | 0.9149 | 0.9520 | 4786 | 30.2s |
| deqar-ror | grid_082 | none | 0.35 | 0.9270 | 0.9007 | 0.9137 | 17111 | 21.6s |
| deqar-ror | grid_082 | greedy | 0.20 | 0.9836 | 0.8511 | 0.9125 | 5488 | 21.6s |
| deqar-ror | original | none | 0.60 | 0.9389 | 0.8723 | 0.9044 | 8440 | 45.0s |
| deqar-ror | original | greedy | 0.50 | 0.9924 | 0.9291 | 0.9597 | 4870 | 45.0s |


Best optimized weights:

| Feature | Original | Wikidata-ROR | DEQAR-ROR |
|---|---:|---:|---:|
| Name | 0.35 | 0.00 | 0.00 |
| Country | 0.15 | 0.20 | 0.20 |
| Domain | 0.25 | 0.40 | 0.40 |
| City | 0.10 | 0.20 | 0.20 |
| Year | 0.10 | 0.00 | 0.20 |
| Geography | 0.05 | 0.20 | 0.00 |

Observations:
- Best optimized Wikidata-ROR F1: 0.9509.
- Best optimized DEQAR-ROR F1: 0.9520.
- Original weights achieved F1 of 0.9817 and 0.9597.
- Original weights outperformed all shortlisted grid
  configurations after greedy matching.
- Both optimized configurations assigned zero weight
  to name similarity.
- Local training-pair performance did not translate
  directly into superior global matching performance.

Limitations:
- Coarse weight search with increments of 0.20.
- Only three optimized configurations were shortlisted.
- Initial screening did not account for global conflicts.
- Blocking already incorporates name evidence, even
  when the matching rule assigns zero weight to names.
- Validation results may be optimistic.
- Test-set evaluation has not been performed.

Conclusion:
Systematic optimization did not improve upon the original
weights under the investigated search strategy. The results
demonstrate the importance of considering global matching
constraints during parameter optimization.

Decision:
Conclude matching algorithm development. Preserve all
experimental results, including negative findings, and
proceed to final comparative evaluation.

Status: Completed successfully.


### Experiment 7 - Controlled Baseline Reproduction

Objective:
Reproduce the selected supervised ML baselines on the
same regenerated blocking candidates used by the
extension matchers.

Methodology:
- Reuse the original selected classifiers.
- Preserve original features and model hyperparameters.
- Train using the existing training labels.
- Verify candidate file checksums.
- Score candidates in batches of 25000.
- Reuse PyDI feature extraction and ML-based matching.
- Evaluate the original matching thresholds.
- Additionally optimize thresholds after greedy matching.
- Select thresholds using validation F1.
- Do not evaluate or tune on test data at this stage.

Implementation differences:
- Batched candidate scoring.
- Initial probability cutoff of 0.01 to support the
  expanded threshold search.
- Deterministic candidate presorting for threshold search.

Rationale:
Ensure a more controlled comparison between existing
matchers and the newly implemented approaches.

Limitations:
Candidate regeneration, dependency versions and
tie-breaking may prevent exact historical reproduction.

Status: Implementation completed. Execution pending.


#### Experiment 7.1 - Controlled Baseline Results

Both selected ML classifiers were successfully reproduced
using the regenerated Round 3 blocking candidates.

| Pair | Classifier | Configuration | Threshold | P | R | F1 | Corr. |
|---|---|---|---:|---:|---:|---:|---:|
| wikidata-ror | logistic regression | original_threshold | 0.45 | 0.9926 | 0.9710 | 0.9817 | 14824 |
| wikidata-ror | logistic regression | retuned_threshold | 0.25 | 0.9926 | 0.9710 | 0.9817 | 16637 |
| deqar-ror | random forest | original_threshold | 0.35 | 0.9846 | 0.9078 | 0.9446 | 4714 |
| deqar-ror | random forest | retuned_threshold | 0.20 | 0.9847 | 0.9149 | 0.9485 | 5319 |


Observations:
- Original validation metrics and correspondence counts
  were reproduced for both dataset pairs.
- Exact correspondence-level equivalence remains unverified.
- Logistic regression achieved identical validation F1
  after threshold retuning.
- Random forest improved from 0.9446 to 0.9485.
- Retuned original rule weights outperformed the retuned
  random forest on DEQAR-ROR validation data.
- All matching approaches now share the same regenerated
  blocking candidates.

Decision:
Conclude model development and parameter optimization.
Freeze the selected configurations before test evaluation.

Status: Completed successfully.


### Experiment 8 - Configuration Freezing

All 14 selected configurations were successfully frozen
before final test evaluation.

Verification:
- Saved validation metrics reproduced.
- Correspondence counts verified.
- One-to-one matching constraints verified.
- SHA-256 checksums recorded for prediction files.
- Seven configurations selected per dataset pair.
- No test labels accessed during configuration freezing.

All experimental prediction files will be version-controlled
to support reproducibility and independent evaluation.

Decision:
No further model, weight or threshold optimization.
Proceed to final test-set evaluation.

Limitation:
The existing test sets were previously evaluated in the
original project experiments and are not completely unseen.

Status: Completed successfully.


### Experiment 9 - Final Test Evaluation

Objective:
Evaluate all frozen matching configurations on the
existing test datasets without further optimization.

Verification:
- All frozen prediction checksums verified.
- All one-to-one matching constraints verified.
- PyDI evaluation metrics independently reproduced
  using confusion matrix calculations.
- Fourteen configurations evaluated.
- No parameters changed during test evaluation.

Results:

| Pair | Method | Threshold | P | R | F1 | TP | FP | TN | FN | Corr. |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| wikidata-ror | tfidf | 0.05 | 0.9785 | 0.7398 | 0.8426 | 91 | 2 | 187 | 32 | 20277 |
| wikidata-ror | semantic_only | 0.45 | 0.9570 | 0.7236 | 0.8241 | 89 | 4 | 185 | 34 | 20437 |
| wikidata-ror | semantic_hybrid | 0.25 | 1.0000 | 0.8862 | 0.9397 | 109 | 0 | 189 | 14 | 20559 |
| wikidata-ror | optimized_rules | 0.10 | 0.9709 | 0.8130 | 0.8850 | 100 | 3 | 186 | 23 | 19872 |
| wikidata-ror | original_rules | 0.50 | 0.9912 | 0.9187 | 0.9536 | 113 | 1 | 188 | 10 | 15995 |
| wikidata-ror | ml_original_threshold | 0.45 | 0.9821 | 0.8943 | 0.9362 | 110 | 2 | 187 | 13 | 14824 |
| wikidata-ror | ml_retuned_threshold | 0.25 | 0.9821 | 0.8943 | 0.9362 | 110 | 2 | 187 | 13 | 16637 |
| deqar-ror | tfidf | 0.05 | 0.9444 | 0.8293 | 0.8831 | 102 | 6 | 181 | 21 | 6967 |
| deqar-ror | semantic_only | 0.50 | 0.9367 | 0.6016 | 0.7327 | 74 | 5 | 182 | 49 | 7763 |
| deqar-ror | semantic_hybrid | 0.50 | 0.9820 | 0.8862 | 0.9316 | 109 | 2 | 185 | 14 | 5137 |
| deqar-ror | optimized_rules | 0.40 | 0.9818 | 0.8780 | 0.9270 | 108 | 2 | 185 | 15 | 4786 |
| deqar-ror | original_rules | 0.50 | 0.9911 | 0.9024 | 0.9447 | 111 | 1 | 186 | 12 | 4870 |
| deqar-ror | ml_original_threshold | 0.35 | 0.9910 | 0.8943 | 0.9402 | 110 | 1 | 186 | 13 | 4714 |
| deqar-ror | ml_retuned_threshold | 0.20 | 0.9910 | 0.8943 | 0.9402 | 110 | 1 | 186 | 13 | 5319 |


Findings:
- Retuned original rule weights achieved the highest
  observed test F1 on both dataset pairs.
- Wikidata-ROR F1 improved from 0.9362 to 0.9536.
- DEQAR-ROR F1 improved from 0.9402 to 0.9447.
- Hybrid semantic matching substantially outperformed
  pure semantic similarity.
- Systematic weight optimization did not outperform
  the original weights.
- ML threshold retuning did not improve test F1.
- Original ML test metrics were successfully reproduced.

Limitations:
- Existing test sets were previously evaluated.
- Ground-truth labels require human verification.
- Statistical significance has not been established.
- Evaluation covers labeled pairs rather than all
  generated correspondences.
- Perfect measured precision does not imply that
  every generated correspondence is correct.

Decision:
No further model or threshold optimization.
Proceed to qualitative error analysis.

Status: Completed successfully.


### Experiment 10 - Error Analysis

Objective:
Investigate matching failures, blocking limitations,
competing assignments and baseline reproducibility.

Methodology:
- Analyze false positives and false negatives.
- Inspect institution names and structured attributes.
- Identify missing blocking candidates.
- Identify competing one-to-one assignments.
- Compare original and reproduced ML correspondences.
- Generate additional correspondence samples for review.

Error summary:

| Pair | Method | Error | Diagnostic | Count |
|---|---|---|---|---:|
| wikidata-ror | tfidf | false_negative | competing_assignment_present | 27 |
| wikidata-ror | tfidf | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | tfidf | false_positive | incorrect_labeled_match | 2 |
| wikidata-ror | semantic_only | false_negative | competing_assignment_present | 29 |
| wikidata-ror | semantic_only | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | semantic_only | false_positive | incorrect_labeled_match | 4 |
| wikidata-ror | semantic_hybrid | false_negative | competing_assignment_present | 9 |
| wikidata-ror | semantic_hybrid | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | optimized_rules | false_negative | competing_assignment_present | 18 |
| wikidata-ror | optimized_rules | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | optimized_rules | false_positive | incorrect_labeled_match | 3 |
| wikidata-ror | original_rules | false_negative | competing_assignment_present | 5 |
| wikidata-ror | original_rules | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | original_rules | false_positive | incorrect_labeled_match | 1 |
| wikidata-ror | ml_original_threshold | false_negative | competing_assignment_present | 8 |
| wikidata-ror | ml_original_threshold | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | ml_original_threshold | false_positive | incorrect_labeled_match | 2 |
| wikidata-ror | ml_retuned_threshold | false_negative | competing_assignment_present | 8 |
| wikidata-ror | ml_retuned_threshold | false_negative | not_generated_by_blocking | 5 |
| wikidata-ror | ml_retuned_threshold | false_positive | incorrect_labeled_match | 2 |
| deqar-ror | tfidf | false_negative | competing_assignment_present | 19 |
| deqar-ror | tfidf | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | tfidf | false_positive | incorrect_labeled_match | 6 |
| deqar-ror | semantic_only | false_negative | competing_assignment_present | 47 |
| deqar-ror | semantic_only | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | semantic_only | false_positive | incorrect_labeled_match | 5 |
| deqar-ror | semantic_hybrid | false_negative | competing_assignment_present | 12 |
| deqar-ror | semantic_hybrid | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | semantic_hybrid | false_positive | incorrect_labeled_match | 2 |
| deqar-ror | optimized_rules | false_negative | blocked_but_not_selected | 2 |
| deqar-ror | optimized_rules | false_negative | competing_assignment_present | 11 |
| deqar-ror | optimized_rules | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | optimized_rules | false_positive | incorrect_labeled_match | 2 |
| deqar-ror | original_rules | false_negative | competing_assignment_present | 10 |
| deqar-ror | original_rules | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | original_rules | false_positive | incorrect_labeled_match | 1 |
| deqar-ror | ml_original_threshold | false_negative | competing_assignment_present | 11 |
| deqar-ror | ml_original_threshold | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | ml_original_threshold | false_positive | incorrect_labeled_match | 1 |
| deqar-ror | ml_retuned_threshold | false_negative | competing_assignment_present | 11 |
| deqar-ror | ml_retuned_threshold | false_negative | not_generated_by_blocking | 2 |
| deqar-ror | ml_retuned_threshold | false_positive | incorrect_labeled_match | 1 |


Baseline reproducibility:

| Pair | Original | Reproduced | Intersection | Jaccard |
|---|---:|---:|---:|---:|
| wikidata-ror | 14824 | 14824 | 14817 | 0.999056 |
| deqar-ror | 4714 | 4714 | 4710 | 0.998304 |


Observations:
- 308 error observations across all configurations.
- 80 additional correspondence samples generated.
- Original weighted rules produced the fewest test errors.
- Five Wikidata-ROR positive test pairs were missed by blocking.
- Two DEQAR-ROR positive test pairs were missed by blocking.
- Test blocking completeness: 118/123 for Wikidata-ROR.
- Test blocking completeness: 121/123 for DEQAR-ROR.
- Competing assignments are common among false negatives.
- Original ML predictions were almost exactly reproduced.

Limitations:
- Automated diagnostics do not establish causal explanations.
- Repeated errors across matchers are not independent.
- Unlabeled correspondences are not necessarily incorrect.
- Additional samples exclude test labels but may overlap
  with training or validation labels.
- Human verification remains pending.

Status:
Automated error analysis completed successfully.


#### Experiment 10.1 - Qualitative Error Analysis

Analysis scope:
- 308 error observations
- 130 unique erroneous record pairs
- 112 unique false-negative pairs
- 18 unique false-positive pairs
- 80 additional correspondence samples

Identified failure patterns:
1. Multilingual institution names.
2. Institutional renaming.
3. Identical names across different countries.
4. Parent institutions versus individual campuses.
5. Competing assignments during global matching.
6. Shared domains across distinct institutions.

Externally investigated name changes:

Bloomsbury Institute:
- Formerly London School of Business and Management.
- Renamed in September 2018.
- Source:
  https://find-and-update.company-information.service.gov.uk/company/04511191

IB Hochschule Berlin:
- Renamed Health Innovation University of Applied Sciences
  in March 2026.
- Source:
  https://www.hi-university.de/en/faq

Demiroglu Bilim University:
- Formerly Istanbul Bilim University.
- Renamed in January 2019.
- Source:
  https://apsis.demiroglu.bilim.edu.tr/bilgi-paketi/en/universite-hakkinda

Additional correspondence screening:

| Indicator | Original rules | Semantic hybrid |
|---|---:|---:|
| Samples | 40 | 40 |
| Conflicting country codes | 0 | 6 |
| Shared domains | 4 | 1 |
| Missing country information | 0 | 1 |

Selected externally investigated correspondences:

- Ivan Franko National University of Lviv / Lviv University:
  match.
  https://lnu.edu.ua/en/about/history/

- University of Reggio Calabria / Universita Mediterranea:
  match.
  https://www.international.unirc.it/en/international/international-student

- Indian Institute of Remote Sensing /
  Indian Institute of Geomagnetism: non-match.
  https://www.iirs.gov.in/about-iirs
  https://www.iigm.res.in/about-us

- University of the Arts Singapore /
  University of Glasgow Singapore: non-match.
  https://uas.edu.sg/about-us
  https://www.gla.ac.uk/international/country/singapore/

- University of Karlsruhe /
  Center for Art and Media Karlsruhe: non-match.
  https://www.kit.edu/kit/english/history.php
  https://zkm.de/en/organization

- Instituto Politecnico Jean Piaget do Norte /
  Instituto Politecnico Jean Piaget do Sul: non-match.
  https://www.ipiaget.org/instituicoes-ip/

Conclusions:
- Institutional history is important for identity resolution.
- Semantic similarity alone does not establish identity.
- Identical names and shared domains can be misleading.
- Strong labeled test performance does not guarantee
  equally strong precision across all correspondences.
- Blocking limitations constrain achievable recall.

Limitations:
- Qualitative categories are not exhaustive.
- External verification was AI-assisted.
- Only selected examples were externally investigated.
- Full human annotation remains pending.
- Disagreement samples are not representative of all
  generated correspondences.
- Training and validation overlap has not been excluded.
- No frozen predictions or test labels were modified.

Status: Preliminary qualitative error analysis completed.


### Experiment 11 - Final Verification and Documentation

All regression and integrity checks passed.

Verified:
- Word and character TF-IDF similarity functions.
- Semantic cosine similarity.
- Generation of 252 valid weight configurations.
- Candidate and feature cache integrity.
- All 14 frozen prediction files.
- Candidate membership.
- One-to-one matching constraints.
- Validation and test metric reproducibility.

Generated report figures:
- Matching performance.
- False-positive and false-negative distributions.
- Original and optimized attribute weights.

Final documentation:
- Extension README.
- Academic report contribution.
- Experimental journal.
- Version-controlled experimental results.

No frozen predictions or matching parameters were changed.

Remaining limitation:
Full human ground-truth verification and group report
integration require coordination with the project team.

Status: Technical implementation and evaluation complete.
