"""More learners: the learned matching of 05_machine_learning with four other kinds of classifier, to see
whether the choice of learner matters. Same features (all attributes + TF-IDF and embedding similarity of the
names), same training pairs, threshold picked on validation.
- decision tree: a short list of yes/no questions on the scores (depth 6, so it stays readable)
- SVM: draws the best dividing line between matches and non-matches (scores scaled first)
- k-nearest neighbours: a pair is a match if the 15 most similar training pairs mostly are (scores scaled first)
- naive Bayes: combines the scores as if they were independent pieces of evidence
The scores of the candidate pairs are computed once per source pair and shared by the four learners (the slow
part); each learner's time in matching.csv includes that shared step, so it compares with 05.
Usage: python more_learners.py first_pass | final"""
import sys
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import FeatureExtractor
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_rules_tfidf"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_rules_embeddings"))
from common import ALL, PAIRS, Timer, candidates, comparators, labels, load_all, run_argument, run_folder, run_matchers
from embeddings import add_embeddings, embedding_comparators   # 03_rules_embeddings
from tfidf import add_tfidf, tfidf_comparators                 # 02_rules_tfidf

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 2026
FEATURES = ALL + ["name_tfidf_words", "name_tfidf_chars", "name_embedding"]   # as in 05
THRESHOLD = 0.1   # as in 05: keep pairs with a match probability of at least 0.1, validation picks the real one


def models():
    return {
        "decision tree": DecisionTreeClassifier(max_depth=6, random_state=SEED),
        "SVM": make_pipeline(StandardScaler(), SVC(probability=True, random_state=SEED)),
        "k-nearest neighbours": make_pipeline(StandardScaler(),
                                              KNeighborsClassifier(n_neighbors=15, weights="distance")),
        "naive Bayes": GaussianNB(),
    }


def main(run):
    out = run_folder(RESULTS, run)
    data = load_all(run)
    add_tfidf(data)
    add_embeddings(data)
    comps = comparators() | tfidf_comparators() | embedding_comparators()
    extractor = FeatureExtractor([comps[c] for c in FEATURES])
    names = extractor.get_feature_names()

    for a, b in PAIRS:
        L, R = data[a], data[b]
        train = labels(a, b, "train", run)
        X = extractor.create_features(L, R, train[["id1", "id2"]], "id", labels=train["label"].astype(int))
        X_train, y_train = X[names].fillna(0), X["label"].astype(int)
        with Timer() as shared:
            pairs = extractor.create_features(L, R, candidates(a, b, run), "id")
        print(f"  {a}-{b}: scores of {len(pairs):,} candidate pairs in {shared.seconds}s", flush=True)
        X_cand = pairs[names].fillna(0)

        def match(model):
            with Timer() as t:
                model.fit(X_train, y_train)
                score = model.predict_proba(X_cand)[:, list(model.classes_).index(1)]
                keep = score >= THRESHOLD
                corr = pd.DataFrame({"id1": pairs.loc[keep, "id1"].to_numpy(),
                                     "id2": pairs.loc[keep, "id2"].to_numpy(),
                                     "score": score[keep],
                                     "notes": f"ml_classifier={type(model).__name__}"})
            return corr, round(t.seconds + shared.seconds, 1)

        run_matchers(out, run, a, b, models(), match, labels(a, b, "validation", run))


if __name__ == "__main__":
    main(run_argument())
