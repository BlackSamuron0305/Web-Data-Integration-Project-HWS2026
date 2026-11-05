"""Phase II, step 2: experiments with similarity measures and matching rules.

For each dataset pair the comparators of matching.py are computed once for all pairs of
the gold standard (PyDI FeatureExtractor). A rule-based matcher is the weighted average of
comparator values (the score PyDI's RuleBasedMatcher computes), so rules with different
measures, weights and thresholds are compared on these features; learned matchers are
trained on the same features. Everything is tuned on the development part of the gold
standard and reported on the test part.

Metrics follow PyDI's EntityMatchingEvaluator: a predicted pair is a false positive only if
the gold standard labels it as a non-match; matches that blocking lost count as missed.

Run (after phase2_blocking.py and gold_standard.py): python scripts/phase2_matching.py
"""
import json

import numpy as np
import pandas as pd
from PyDI.entitymatching import FeatureExtractor
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

from blocking import add_block_text
from common import DATA, RESULTS, load_target
from matching import feature_comparators, named

PAIRS = [("wikidata", "ror"), ("deqar", "ror"), ("wikidata", "deqar")]
CACHE = RESULTS / "cache"
SEED = 2026

NAME_MEASURES = ["name_jaro_winkler", "name_levenshtein", "name_jaccard", "name_sorensen_dice",
                 "names_best_jaro_winkler", "names_best_jaccard"]
RULES = {
    "names": ["names_best_jaro_winkler"],
    "names+country": ["names_best_jaro_winkler", "country"],
    "names+country+domain": ["names_best_jaro_winkler", "country", "domain"],
    "names+country+domain+city": ["names_best_jaro_winkler", "country", "domain", "city"],
    "all attributes": ["names_best_jaro_winkler", "country", "domain", "city", "founding_year", "geo"],
}


def gold_features(a, b, data):
    """Comparator values for every gold-standard pair (cached)."""
    path = CACHE / f"features_{a}_{b}.csv"
    if path.exists():
        return pd.read_csv(path, keep_default_na=False)
    gold = pd.read_csv(DATA / "gold_standard" / f"gold_{a}_{b}.csv")
    comps, flags = feature_comparators()
    fe = FeatureExtractor(named({**comps, **flags}))
    feats = fe.create_features(data[a], data[b], gold[["id1", "id2"]], "id", labels=gold["label"])
    feats = feats.merge(gold[["id1", "id2", "kind", "split"]], on=["id1", "id2"])
    cand = pd.read_csv(CACHE / f"candidates_{a}_{b}.csv")
    cand["in_cand"] = 1
    feats = feats.merge(cand, on=["id1", "id2"], how="left")
    feats["in_cand"] = feats["in_cand"].fillna(0).astype(int)
    feats.to_csv(path, index=False)
    return feats


def prf(pred, label, n_pos):
    tp = int((pred & (label == 1)).sum())
    fp = int((pred & (label == 0)).sum())
    fn = n_pos - tp
    p = tp / max(tp + fp, 1)
    r = tp / max(n_pos, 1)
    return p, r, 2 * p * r / max(p + r, 1e-12)


def best_threshold(score, label, in_cand, n_pos, grid=np.arange(0.3, 1.0001, 0.01)):
    best = (0, 0.5, 0, 0)
    for t in grid:
        p, r, f = prf((score >= t) & (in_cand == 1), label, n_pos)
        if f > best[0]:
            best = (f, t, p, r)
    return best


def evaluate(score, part, t):
    label = part["label"].to_numpy()
    return prf((score >= t) & (part["in_cand"].to_numpy() == 1), label, int(label.sum()))


def rule_score(part, cols, w):
    return part[cols].to_numpy() @ (np.asarray(w, float) / np.sum(w))


def tune_weights(dev, cols, rng, draws=400):
    """Random search over small integer weights; the name comparator keeps weight >= 1."""
    label, in_cand, n_pos = dev["label"].to_numpy(), dev["in_cand"].to_numpy(), int(dev["label"].sum())
    best = None
    candidates = [np.ones(len(cols), int)] + [rng.integers(0, 7, len(cols)) for _ in range(draws)]
    for w in candidates:
        w = w.copy()
        w[0] = max(w[0], 1)
        f, t, p, r = best_threshold(rule_score(dev, cols, w), label, in_cand, n_pos,
                                    grid=np.arange(0.3, 1.0001, 0.02))
        if best is None or f > best[0]:
            best = (f, t, w)
    return best


def models():
    return {
        "logistic regression": LogisticRegression(max_iter=2000, C=5),
        "random forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=SEED, n_jobs=-1),
        "gradient boosting": GradientBoostingClassifier(random_state=SEED),
    }


def main():
    data = load_target()
    add_block_text(data)
    comps, flags = feature_comparators()
    ml_cols = list(comps) + list(flags)
    rng = np.random.default_rng(SEED)
    rows, best = [], {}
    for a, b in PAIRS:
        feats = gold_features(a, b, data)
        dev, test = feats[feats["split"] == "dev"], feats[feats["split"] == "test"]
        print(a, b, "dev", len(dev), "test", len(test), "positives", int(dev.label.sum()), int(test.label.sum()))
        key = f"{a}-{b}"

        def record(group, config, t, dev_f1, test_score):
            p, r, f = evaluate(test_score, test, t)
            rows.append(dict(pair=key, group=group, config=config, threshold=round(float(t), 3),
                             dev_f1=round(dev_f1, 4), test_precision=round(p, 4),
                             test_recall=round(r, 4), test_f1=round(f, 4)))
            return f

        candidates = {}
        # 1. single similarity measures on the name
        for m in NAME_MEASURES:
            f, t, _, _ = best_threshold(dev[m].to_numpy(), dev["label"].to_numpy(), dev["in_cand"].to_numpy(),
                                        int(dev.label.sum()))
            record("similarity measure", m, t, f, test[m].to_numpy())
        # 2. weighted rules over several attributes
        for name, cols in RULES.items():
            f, t, w = tune_weights(dev, cols, rng)
            record("rule", name + " " + str(dict(zip(cols, map(int, w)))), t, f, rule_score(test, cols, w))
            candidates[("rule", name)] = (f, t, dict(zip(cols, map(int, w))))
        # 3. learned matchers
        X_dev, y_dev = dev[ml_cols].to_numpy(), dev["label"].to_numpy()
        for name, model in models().items():
            proba = cross_val_predict(model, X_dev, y_dev, cv=5, method="predict_proba")[:, 1]
            f, t, _, _ = best_threshold(proba, y_dev, dev["in_cand"].to_numpy(), int(y_dev.sum()),
                                        grid=np.arange(0.1, 0.96, 0.02))
            model.fit(X_dev, y_dev)
            record("learned", name, t, f, model.predict_proba(test[ml_cols].to_numpy())[:, 1])
            candidates[("learned", name)] = (f, t, None)
        (grp, name), (f, t, w) = max(candidates.items(), key=lambda kv: kv[1][0])
        best[key] = dict(kind=grp, name=name, threshold=float(t), weights=w, dev_f1=f)
        print(key, "best on dev:", best[key])
    pd.DataFrame(rows).to_csv(RESULTS / "matching_experiments.csv", index=False)
    (RESULTS / "matching_best.json").write_text(json.dumps(best, indent=1), encoding="utf-8")
    print(pd.DataFrame(rows).to_string())


if __name__ == "__main__":
    main()
