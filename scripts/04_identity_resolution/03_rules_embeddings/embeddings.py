"""Embedding matching: compares the names by their meaning, alone and with country and domain.

A small multilingual language model (paraphrase-multilingual-MiniLM-L12-v2) turns every name into a list of
384 numbers (an embedding). Names with a similar meaning get similar lists, even in different languages, so
"Universitat Wien" and "University of Vienna" score high. The score of a pair is the cosine similarity of the
two embeddings. The embeddings are cached in results/cache/ at the repository root (not in git), so only new
names are encoded. The threshold is picked on validation.
05_machine_learning and 07_more_learners use the embedding score as a feature too (add_embeddings,
embedding_comparators).
Usage: python embeddings.py first_pass | final"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import IR, Own, run_argument, run_rules

RESULTS = Path(__file__).resolve().parent / "results"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CACHE = IR.parents[1] / "results" / "cache" / "name_embeddings.npz"   # git-ignored


def embed(names):
    # one embedding (of length 1) per name; names already encoded are read from the cache
    names = names.fillna("").astype(str).str.strip().tolist()
    known = {}
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=False)
        known = dict(zip(z["names"].tolist(), z["vectors"]))
    todo = sorted({n for n in names if n and n not in known})
    if todo:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL, device="cpu")
        vectors = model.encode(todo, batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
        known.update(zip(todo, vectors.astype(np.float32)))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.savez(CACHE, names=np.array(list(known)), vectors=np.stack(list(known.values())))
    zero = np.zeros(len(next(iter(known.values()))), dtype=np.float32)
    return [known.get(n, zero) for n in names]   # no name = no evidence


def add_embeddings(data):
    for df in data.values():
        df["embedding"] = embed(df["name"])


def cosine(r1, r2):
    # the embeddings have length 1, so their dot product is the cosine similarity
    return max(0.0, min(1.0, float(np.dot(r1["embedding"], r2["embedding"]))))


def embedding_comparators():
    return {"name_embedding": Own("name_embedding", cosine)}


# {rule name: (comparators, weights)}
RULES = {
    "name embedding": (["name_embedding"], [1]),
    "rule: embedding 0.5 + country 0.2 + domain 0.3": (["name_embedding", "country", "domain"], [0.5, 0.2, 0.3]),
}


if __name__ == "__main__":
    run_rules(RESULTS, run_argument(), RULES, prepare=add_embeddings, extra=embedding_comparators())
