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
