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
Created scripts/identity_resolution/06_extensions/
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
