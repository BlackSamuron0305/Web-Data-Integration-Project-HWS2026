"""Searches the training settings of the fine-tuned language model on the validation pairs only.
Each setting trains one model on the train pairs of both source pairs and scores the validation pairs
that blocking kept (the others count as non-matches, as in fine_tuned_model.py). For each source pair the
threshold with the best F1 is taken; the setting with the best mean F1 of the two pairs wins (on a tie
the one listed first). The test pairs are not used. Writes results/final/search.csv.
The search was done once, on the final run.
Usage: python search.py   (then set the winning values in fine_tuned_model.py and rerun it)"""
import itertools
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PAIRS, best_threshold, candidates, labels, load_all
from fine_tuned_model import EPOCHS, LEARNING_RATE, TRAIN_BATCH, fit, predict, texts

RESULTS = Path(__file__).resolve().parent / "results"
RUN = "final"
LEARNING_RATES = [2e-5, 3e-5, 5e-5]
EPOCH_CHOICES = [2, 4, 6]
BATCHES = [TRAIN_BATCH]


def main():
    data = load_all(RUN)
    val = {}
    for a, b in PAIRS:
        pairs = labels(a, b, "validation", RUN)
        cand = candidates(a, b, RUN)
        kept = set(zip(cand["id1"], cand["id2"]))
        scored = pairs[[(i, j) in kept for i, j in zip(pairs["id1"], pairs["id2"])]][["id1", "id2"]]
        t1, t2 = texts(data[a]), texts(data[b])
        val[(a, b)] = (pairs, scored.reset_index(drop=True), [t1[i] for i in scored["id1"]],
                       [t2[i] for i in scored["id2"]])
        print(f"  {a}-{b}: {len(pairs)} validation pairs, {len(scored)} of them in the candidates", flush=True)

    # the current setting first, so it wins a tie
    settings = [(EPOCHS, LEARNING_RATE, TRAIN_BATCH)]
    settings += [s for s in itertools.product(EPOCH_CHOICES, LEARNING_RATES, BATCHES) if s != settings[0]]

    out = RESULTS / RUN / "search.csv"
    rows = []
    for epochs, lr, batch in settings:
        model, tokenizer, seconds = fit(data, epochs, lr, batch, RUN)
        row = dict(epochs=epochs, learning_rate=lr, batch=batch, train_seconds=seconds)
        f1s = []
        for (a, b), (pairs, scored, left, right) in val.items():
            corr = scored.copy()
            corr["score"] = predict(model, tokenizer, left, right)
            t, p, r, f = best_threshold(corr, pairs)
            key = f"{a}_{b}"
            row.update({f"{key}_threshold": t, f"{key}_P": round(p, 3), f"{key}_R": round(r, 3),
                        f"{key}_F1": round(f, 3)})
            f1s.append(f)
        row["mean_F1"] = round(sum(f1s) / len(f1s), 4)
        rows.append(row)
        print(f"  -> {row}", flush=True)
        pd.DataFrame(rows).to_csv(out, index=False)   # saved after every setting

    df = pd.DataFrame(rows)
    best = df.loc[df["mean_F1"].idxmax()]
    print(f"\nbest: {int(best['epochs'])} epochs, learning rate {best['learning_rate']}, "
          f"batch {int(best['batch'])}, mean validation F1 {best['mean_F1']}")


if __name__ == "__main__":
    main()
