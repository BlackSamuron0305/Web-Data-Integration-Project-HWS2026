"""Learned matching.  Usage: python ml_based.py <round>   (round 2 or 3)"""
import sys
from pathlib import Path

from PyDI.entitymatching import FeatureExtractor, MLBasedMatcher
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ALL, PAIRS, Timer, candidates, comparators, labels, load_all, reset_log, run_matchers

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 2026


def models(features):
    # name: (model, features)
    return {
        "logistic regression": (LogisticRegression(max_iter=2000), features),
        "random forest": (RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=SEED, n_jobs=-1), features),
        "gradient boosting": (GradientBoostingClassifier(random_state=SEED), features),
    }


MODELS = {2: models(ALL)}
MODELS[3] = models(ALL)
MODELS[3].update({f"{name} + part_word": m for name, m in models(ALL + ["part_word"]).items()})
MODELS[4] = MODELS[6] = models(ALL)   # round 3 without part_word (did not help); 4: filtered, 6: deduplicated data


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

        run_matchers(RESULTS, round_, a, b, MODELS[round_], run, labels(a, b, "validation", round_))


if __name__ == "__main__":
    main(int(sys.argv[1]))
