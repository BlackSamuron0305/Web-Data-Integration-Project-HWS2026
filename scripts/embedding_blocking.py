"""Phase II: embedding-based blocking + rule-based matching, evaluated on validation_data.

Embedding blocking (PyDI EmbeddingBlocker):
  1. turn the text of every record into a vector with a sentence-transformer model,
  2. index the vectors of the right dataset for nearest-neighbour search (scikit-learn, cosine),
  3. for every record of the left dataset, the top_k most similar right records (cosine
     similarity >= SIM_THRESHOLD) become candidate pairs.
Unlike token blocking, records need not share a word: 'Universität Wien' and 'University of
Vienna' can be close in a multilingual embedding space.

Variants
  model  English    sentence-transformers/all-MiniLM-L6-v2 (PyDI's default)
         multilingual sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  text   name                  'Heidelberg University'
         name + city + country 'Heidelberg University Heidelberg Germany'
  top_k  5, 10, 20 neighbours per left record
Each dataset is embedded once per model and text and the vectors are reused for all dataset
pairs; the embedding time of both datasets is added to the blocking time of every run.

For every run: match with Rule1 (as in standard_blocking.py), choose the threshold on train_data,
report P/R/F1, #Corr and time (embedding + blocking + matching) on validation_data.

Output: results/embedding_blocking_validation.csv, results/logs/embedding_blocking.log
Run (after gold_standard.py): python scripts/embedding_blocking.py
"""
import logging
import time
import warnings

import pandas as pd
from PyDI.entitymatching.blocking import EmbeddingBlocker
from sentence_transformers import SentenceTransformer

from blocking import OUTPUT_DIR, add_block_text
from common import RESULTS, load_target
from sorted_neighbourhood_blocking import run_blocker
from standard_blocking import PAIRS
from validation import load_labelled, write_log

logging.basicConfig(level=logging.WARNING)
# scikit-learn's cosine distance (a @ b) raises spurious 'divide by zero / overflow / invalid value
# encountered in matmul' warnings with numpy's Apple Accelerate backend; the results are not affected
warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)

MODELS = {
    "English": "sentence-transformers/all-MiniLM-L6-v2",
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}
TEXTS = {
    "name": ["name"],
    "name + city + country": ["name", "city", "country"],
}
TOP_K = [5, 10, 20]
SIM_THRESHOLD = 0.3   # PyDI's default; top_k decides the number of candidates


def record_text(df, cols):
    """The text that is embedded: the columns joined by spaces (empty values left out)."""
    parts = [df[c].fillna("").astype(str) for c in cols]
    return [" ".join(p for p in ps if p.strip()) for ps in zip(*parts)]


class Embeddings:
    """Embeddings per (model, text, dataset), computed once; remembers the seconds it took."""

    def __init__(self, data):
        self.data, self.models, self.cache = data, {}, {}

    def get(self, model, text, dataset):
        key = (model, text, dataset)
        if key not in self.cache:
            if model not in self.models:
                self.models[model] = SentenceTransformer(MODELS[model])
            t = time.time()
            vec = self.models[model].encode(record_text(self.data[dataset], TEXTS[text]), batch_size=256,
                                            convert_to_numpy=True, normalize_embeddings=True,
                                            show_progress_bar=False)
            self.cache[key] = (vec, time.time() - t)
            print(f"  embedded {dataset} ({model}, {text}): {len(vec):,} records in {self.cache[key][1]:.0f} s",
                  flush=True)
        return self.cache[key]


def embedding_block(emb_left, emb_right, k):
    def block(left, right):
        return EmbeddingBlocker(left, right, text_cols=["name"], id_column="id", index_backend="sklearn",
                                metric="cosine", top_k=k, threshold=SIM_THRESHOLD,
                                left_embeddings=emb_left, right_embeddings=emb_right,
                                output_dir=OUTPUT_DIR).materialize()
    return block


def main():
    data = load_target()
    add_block_text(data)
    emb = Embeddings(data)
    rows = []
    for a, b in PAIRS:
        left, right = data[a], data[b]
        train, valid = load_labelled("train", a, b), load_labelled("validation", a, b)
        for model in MODELS:
            for text in TEXTS:
                (el, sl), (er, sr) = emb.get(model, text, a), emb.get(model, text, b)
                for k in TOP_K:
                    name = f"Embedding: {model}, {text} (top_k={k})"
                    new = run_blocker(a, b, left, right, train, valid, name, embedding_block(el, er, k))
                    for row in new:  # the embedding is part of blocking
                        row["embed_s"] = round(sl + sr, 1)
                        row["block_s"] = round(row["block_s"] + sl + sr, 1)
                        row["time_s"] = round(row["time_s"] + sl + sr, 1)
                    rows += new
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "embedding_blocking_validation.csv", index=False)
    print("log:", write_log(out, "embedding_blocking", "Embedding-based blocking (PyDI EmbeddingBlocker)"))


if __name__ == "__main__":
    main()
