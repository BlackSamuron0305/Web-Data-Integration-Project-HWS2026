"""Learned matching: classifiers trained on the comparator scores, threshold picked on validation.
Usage: python ml_based.py <round>   (round 2, 3 or 8)"""
import sys
from pathlib import Path

from PyDI.entitymatching import FeatureExtractor, MLBasedMatcher
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ALL, PAIRS, Timer, candidates, comparators, labels, load_all, reset_log, run_matchers

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 2026


def models(round_):
    # name: (model, features); round 3 also tries each model with part_word
    def three(features, suffix=""):
        return {
            "logistic regression" + suffix: (LogisticRegression(max_iter=2000), features),
            "random forest" + suffix: (RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                                              random_state=SEED, n_jobs=-1), features),
            "gradient boosting" + suffix: (GradientBoostingClassifier(random_state=SEED), features),
        }
    found = three(ALL)
    if round_ == 3:
        found.update(three(ALL + ["part_word"], " + part_word"))
    return found


def main(round_):
    RESULTS.mkdir(exist_ok=True)
    reset_log(RESULTS / "matching.csv", round_)
    data = load_all(round_)
    comps = comparators()

    for a, b in PAIRS:
        L, R, cand = data[a], data[b], candidates(a, b, round_)
        train = labels(a, b, "train", round_)

        def run(m):
            model, features = m
            with Timer() as t:
                extractor = FeatureExtractor([comps[c] for c in features])
                X = extractor.create_features(L, R, train[["id1", "id2"]], "id", labels=train["label"].astype(int))
                model.fit(X[extractor.get_feature_names()].fillna(0), X["label"])
                corr = MLBasedMatcher(extractor).match(L, R, cand, "id", trained_classifier=model,
                                                       threshold=0.1, use_probabilities=True)
            return corr, t.seconds

        run_matchers(RESULTS, round_, a, b, models(round_), run, labels(a, b, "validation", round_))


if __name__ == "__main__":
    main(int(sys.argv[1]))
