"""Learned matching: classifiers trained on the comparator scores, threshold picked on validation.
Usage: python ml_based.py first_pass | final"""
import sys
from pathlib import Path

from PyDI.entitymatching import FeatureExtractor, MLBasedMatcher
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_rules_tfidf"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_rules_embeddings"))
from common import ALL, PAIRS, Timer, candidates, comparators, labels, load_all, run_argument, run_folder, run_matchers
from embeddings import add_embeddings, embedding_comparators   # 03_rules_embeddings
from tfidf import add_tfidf, tfidf_comparators                 # 02_rules_tfidf

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 2026
VECTORS = ["name_tfidf_words", "name_tfidf_chars", "name_embedding"]   # TF-IDF (02) and embedding (03) scores


def models():
    # name: (model, features); each model alone, with part_word, and with the TF-IDF and embedding
    # similarities of the names
    def three(features, suffix=""):
        return {
            "logistic regression" + suffix: (LogisticRegression(max_iter=2000), features),
            "random forest" + suffix: (RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                                              random_state=SEED, n_jobs=-1), features),
            "gradient boosting" + suffix: (GradientBoostingClassifier(random_state=SEED), features),
        }
    found = three(ALL)
    found.update(three(ALL + ["part_word"], " + part_word"))
    found.update(three(ALL + VECTORS, " + TF-IDF, embedding"))
    return found


def main(run):
    out = run_folder(RESULTS, run)
    data = load_all(run)
    add_tfidf(data)
    add_embeddings(data)
    comps = comparators() | tfidf_comparators() | embedding_comparators()

    for a, b in PAIRS:
        L, R, cand = data[a], data[b], candidates(a, b, run)
        train = labels(a, b, "train", run)

        def match(m):
            model, features = m
            with Timer() as t:
                extractor = FeatureExtractor([comps[c] for c in features])
                X = extractor.create_features(L, R, train[["id1", "id2"]], "id", labels=train["label"].astype(int))
                model.fit(X[extractor.get_feature_names()].fillna(0), X["label"])
                corr = MLBasedMatcher(extractor).match(L, R, cand, "id", trained_classifier=model,
                                                       threshold=0.1, use_probabilities=True)
            return corr, t.seconds

        run_matchers(out, run, a, b, models(), match, labels(a, b, "validation", run))


if __name__ == "__main__":
    main(run_argument())
