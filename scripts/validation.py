"""Evaluation helpers of Phase II: precision, recall and F1 of a set of correspondences
against one labelled set (train_data / validation_data / test_data of gold_standard.py).

Definition (PyDI's EntityMatchingEvaluator): a predicted pair is a true positive if the
labelled set marks it as a match and a false positive if it marks it as a non-match;
predicted pairs that are not in the labelled set are ignored. Every labelled match that is
not predicted -- also one that blocking lost -- is a false negative.

Usage:
    from validation import load_labelled, tune_threshold, evaluate
    train = load_labelled("train", "wikidata", "ror")
    t = tune_threshold(corr, train)["threshold"]          # choose on train_data
    evaluate(corr[corr.score >= t], load_labelled("validation", "wikidata", "ror"))
"""
import logging

import numpy as np
import pandas as pd
from PyDI.entitymatching import EntityMatchingEvaluator

from gold_standard import load_split

THRESHOLDS = np.round(np.arange(0.30, 1.0001, 0.01), 2)


def load_labelled(split, a, b):
    """One labelled set: columns id1, id2, label, kind, split."""
    return load_split(split, a, b)


def evaluate(corr, labelled):
    """P/R/F1 and counts of ``corr`` (columns id1, id2, score) with PyDI's evaluator."""
    level = logging.getLogger().level
    logging.getLogger().setLevel(logging.WARNING)
    try:
        res = EntityMatchingEvaluator.evaluate_matching(corr[["id1", "id2", "score"]], labelled[["id1", "id2", "label"]],
                                                        max_logged_instances=0)
    finally:
        logging.getLogger().setLevel(level)
    return dict(precision=res["precision"], recall=res["recall"], f1=res["f1"],
                tp=res["true_positives"], fp=res["false_positives"], fn=res["false_negatives"])


def scores_of(corr, labelled):
    """The labelled pairs with the score the matcher gave them (NaN = not a correspondence)."""
    s = corr[["id1", "id2", "score"]].drop_duplicates(["id1", "id2"])
    return labelled[["id1", "id2", "label"]].merge(s, on=["id1", "id2"], how="left")


def prf_curve(corr, labelled, thresholds=THRESHOLDS):
    """P/R/F1 for every threshold, vectorised; same definition as ``evaluate``."""
    m = scores_of(corr, labelled)
    score = m["score"].to_numpy(dtype=float)
    label = m["label"].to_numpy()
    n_pos = int((label == 1).sum())
    rows = []
    for t in thresholds:
        pred = score >= t  # NaN (not a correspondence) compares False
        tp = int((pred & (label == 1)).sum())
        fp = int((pred & (label == 0)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / n_pos if n_pos else 0.0
        rows.append(dict(threshold=float(t), precision=p, recall=r, f1=2 * p * r / (p + r) if p + r else 0.0))
    return pd.DataFrame(rows)


def tune_threshold(corr, labelled, thresholds=THRESHOLDS):
    """The threshold with the best F1 on ``labelled`` (ties: the lower threshold)."""
    curve = prf_curve(corr, labelled, thresholds)
    return curve.loc[curve["f1"].idxmax()].to_dict()


def pair_completeness(candidates, labelled):
    """Share of the labelled matches that are among the candidate pairs."""
    pos = labelled[labelled["label"] == 1]
    found = pos.merge(candidates[["id1", "id2"]].drop_duplicates(), on=["id1", "id2"])
    return len(found) / len(pos) if len(pos) else None
