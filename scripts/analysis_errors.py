"""Phase II: which comparators matter and which gold-standard matches the final matcher misses.

Run (after phase2_final.py): python scripts/analysis_errors.py
"""
import json

import pandas as pd

from common import DATA, RESULTS, load_target
from matching import feature_comparators
from phase2_matching import CACHE, PAIRS, models


def main():
    data = load_target()
    comps, flags = feature_comparators()
    cols = list(comps) + list(flags)
    best = json.loads((RESULTS / "matching_best.json").read_text(encoding="utf-8"))
    imp, misses = [], []
    for a, b in PAIRS:
        key = f"{a}-{b}"
        feats = pd.read_csv(CACHE / f"features_{a}_{b}.csv", keep_default_na=False)
        dev, test = feats[feats["split"] == "dev"], feats[feats["split"] == "test"]
        model = models()[best[key]["name"]]
        model.fit(dev[cols], dev["label"])
        if hasattr(model, "feature_importances_"):
            for c, v in zip(cols, model.feature_importances_):
                imp.append(dict(pair=key, feature=c, importance=round(float(v), 4)))
        score = model.predict_proba(test[cols])[:, 1]
        test = test.assign(score=score)
        miss = test[(test["label"] == 1) & (test["score"] < 0.8)]
        names_a, names_b = dict(zip(data[a]["id"], data[a]["name"])), dict(zip(data[b]["id"], data[b]["name"]))
        in_cand = (miss["in_cand"] == 0).mean()
        print(key, "missed matches", len(miss), "of", int(test["label"].sum()), "- lost by blocking:", round(in_cand, 3))
        for r in miss.sample(min(8, len(miss)), random_state=1).itertuples():
            print("   ", names_a[r.id1], "<>", names_b[r.id2], round(r.score, 2), "blocked" if not r.in_cand else "")
        fp = test[(test["label"] == 0) & (test["score"] >= 0.8)]
        print(key, "false positives at 0.8:", len(fp), fp["kind"].value_counts().to_dict())
    pd.DataFrame(imp).to_csv(RESULTS / "feature_importance.csv", index=False)
    print(pd.DataFrame(imp).pivot(index="feature", columns="pair", values="importance").round(3))


if __name__ == "__main__":
    main()
