"""Fine-tuned language model: a small multilingual model reads both records of a pair as one text
("name: ... | country: ... | city: ... | web: ... | founded: ... | also: ...") and gives the probability
that they are the same university (like Ditto). It is trained on the train pairs of both source pairs
together, then scores every blocked candidate pair; the threshold is picked on validation.
The trained model and the scores are cached per run in results/cache/ (git-ignored), so a rerun is quick.
Usage: python fine_tuned_model.py first_pass | final"""
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IR, PAIRS, as_list, candidates, labels, load_all, run_argument, run_folder, run_matchers

RESULTS = Path(__file__).resolve().parent / "results"
CACHE = IR.parents[1] / "results" / "cache" / "fine_tuned_language_model"   # git-ignored, one folder per run
SEED = 2026

BASE_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"   # multilingual, 12 small layers, 118M weights
MAX_LENGTH = 96          # tokens for both records together
EPOCHS = 4               # fixed, no early stopping
TRAIN_BATCH = 16
LEARNING_RATE = 3e-5
SCORE_BATCH = 256
CHUNK = 20_000           # scores are saved every CHUNK pairs, so a stopped run goes on where it stopped
MIN_SCORE = 0.1          # pairs below this are dropped (the lowest threshold tried is 0.3)


def first(value):
    found = as_list(value)
    return found[0] if found else ""


def record_text(r):
    # the most telling fields first, because a text that is too long gets cut at the end
    name = str(r["name"]).strip()
    seen = {name.lower()}
    also = []
    for n in as_list(r.get("acronyms_acronym")) + as_list(r.get("alternativeNames_alternativeName")):
        n = n.strip()
        if n and n.lower() not in seen and not ("." in n and " " not in n):   # skip web addresses
            seen.add(n.lower())
            also.append(n)
    parts = [f"name: {name}"]
    if r["cc"]:
        parts.append(f"country: {r['cc']}")
    if first(r.get("location_city")):
        parts.append(f"city: {first(r.get('location_city'))}")
    if r["domains"]:
        parts.append("web: " + " ".join(r["domains"][:2]))
    if not pd.isna(r["year"]):
        parts.append(f"founded: {int(r['year'])}")
    if also:
        parts.append("also: " + "; ".join(also[:3]))
    return " | ".join(parts)


def texts(df):
    return {r["id"]: record_text(r) for _, r in df.iterrows()}


def seed_everything():
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


def train(data, run):
    """Fine-tunes the model on the train pairs of both source pairs; returns (model, tokenizer, seconds)."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    model_dir = CACHE / run / "model"
    info = CACHE / run / "train_seconds.txt"
    if (model_dir / "config.json").exists() and info.exists():
        print(f"  loading the trained model from {model_dir}", flush=True)
        return (AutoModelForSequenceClassification.from_pretrained(model_dir),
                AutoTokenizer.from_pretrained(model_dir), float(info.read_text()))

    model, tokenizer, seconds = fit(data, EPOCHS, LEARNING_RATE, TRAIN_BATCH, run)
    model_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)
    info.write_text(str(seconds))
    return model, tokenizer, seconds


def fit(data, epochs, learning_rate, batch, run):
    """Trains one model with the given settings (search.py tries several); returns (model, tokenizer, seconds)."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    seed_everything()
    start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=1)
    left, right, y = [], [], []
    for a, b in PAIRS:
        t1, t2 = texts(data[a]), texts(data[b])
        pairs = labels(a, b, "train", run)
        left += [t1[i] for i in pairs["id1"]]
        right += [t2[i] for i in pairs["id2"]]
        y += pairs["label"].astype(float).tolist()
    y = torch.tensor(y)
    print(f"  training on {len(y)} pairs ({int(y.sum())} matches), {epochs} epochs, "
          f"learning rate {learning_rate}, batch {batch}", flush=True)

    steps = epochs * ((len(y) + batch - 1) // batch)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    schedule = get_linear_schedule_with_warmup(optimizer, int(0.1 * steps), steps)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    generator = torch.Generator().manual_seed(SEED)
    model.train()
    for epoch in range(epochs):
        order = torch.randperm(len(y), generator=generator).tolist()
        total = 0.0
        for s in range(0, len(order), batch):
            idx = order[s:s + batch]
            enc = tokenizer([left[i] for i in idx], [right[i] for i in idx], truncation="longest_first",
                            max_length=MAX_LENGTH, padding=True, return_tensors="pt")
            loss = loss_fn(model(**enc).logits.squeeze(-1), y[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            schedule.step()
            optimizer.zero_grad()
            total += loss.item() * len(idx)
        print(f"  epoch {epoch + 1}: training loss {total / len(y):.4f}", flush=True)

    seconds = round(time.time() - start, 1)
    model.eval()
    print(f"  trained in {seconds}s", flush=True)
    return model, tokenizer, seconds


@torch.inference_mode()
def predict(model, tokenizer, left, right):
    # pairs of similar length go in one batch, so little padding is needed
    model.eval()
    order = np.argsort([len(x) + len(z) for x, z in zip(left, right)], kind="stable")
    out = np.empty(len(left), dtype=np.float32)
    for s in range(0, len(order), SCORE_BATCH):
        idx = order[s:s + SCORE_BATCH]
        enc = tokenizer([left[i] for i in idx], [right[i] for i in idx], truncation="longest_first",
                        max_length=MAX_LENGTH, padding=True, return_tensors="pt")
        out[idx] = torch.sigmoid(model(**enc).logits.squeeze(-1)).numpy()
    return out


def score(model, tokenizer, data, a, b, run):
    """Scores all candidate pairs of a-b in chunks; returns (scores, seconds spent scoring)."""
    cand = candidates(a, b, run)
    folder = CACHE / run / f"scores_{a}_{b}"
    folder.mkdir(parents=True, exist_ok=True)
    t1, t2 = texts(data[a]), texts(data[b])
    parts, seconds = [], 0.0
    for c, s in enumerate(range(0, len(cand), CHUNK)):
        file = folder / f"chunk_{c:04d}.npz"
        if file.exists():
            z = np.load(file)
            parts.append(z["scores"])
            seconds += float(z["seconds"])
            continue
        part = cand.iloc[s:s + CHUNK]
        start = time.time()
        scores = predict(model, tokenizer, [t1[i] for i in part["id1"]], [t2[i] for i in part["id2"]])
        took = time.time() - start
        np.savez(file, scores=scores, seconds=took)
        parts.append(scores)
        seconds += took
        done = s + len(part)
        print(f"  {a}-{b}: {done:,}/{len(cand):,} pairs scored ({len(part) / took:.0f} pairs/s)", flush=True)
    cand = cand[["id1", "id2"]].copy()
    cand["score"] = np.concatenate(parts)
    return cand, seconds


def main(run):
    out = run_folder(RESULTS, run)
    data = load_all(run)
    model, tokenizer, train_seconds = train(data, run)

    for a, b in PAIRS:
        def match(_):
            corr, seconds = score(model, tokenizer, data, a, b, run)
            return corr[corr["score"] >= MIN_SCORE].reset_index(drop=True), round(train_seconds + seconds, 1)

        run_matchers(out, run, a, b, {"fine-tuned multilingual MiniLM cross-encoder": None}, match,
                     labels(a, b, "validation", run))


if __name__ == "__main__":
    main(run_argument())
