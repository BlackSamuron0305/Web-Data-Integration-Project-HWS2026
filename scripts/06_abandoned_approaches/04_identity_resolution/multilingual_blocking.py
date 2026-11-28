"""Blocking with a multilingual embedding model instead of PyDI's default English one.

The embedding blocker of the pipeline (04_identity_resolution/blocking/blocking.py) takes the ten nearest
names by PyDI's default model, the English all-MiniLM-L6-v2. Would a multilingual model find more of the
matches whose names are in other languages (Universitat Wien, University of Vienna)? Lakpa first tried
this on 23 November 2026 with our older labels and dropped it. This script redoes the test on the final
labelled pairs, for both runs, with the pipeline's settings (ten nearest, similarity at least 0.5). Like
the first test, it embeds the main name alone and the name with city and country.

For each run, dataset pair, model and text it logs the candidate pairs, the pair completeness (PC: share
of the validation matches kept), alone and in the union with the pipeline's other two blockers (country +
name word, same web domain), and the seconds the embedding blocker took on the CPU, model loading and
embedding included. Both models run on the CPU, one after the other, so their times compare.

Run from the repository root (about 25 minutes on our CPU):
    python scripts/06_abandoned_approaches/04_identity_resolution/multilingual_blocking.py
Output: results/multilingual_blocking.csv (scores) and results/multilingual_only_matches.csv (validation
matches that only the multilingual union keeps, and the other way round)
"""
import sys
import time
from pathlib import Path

import pandas as pd
from PyDI.entitymatching import EmbeddingBlocker, TokenBlocker

ROOT = Path(__file__).resolve().parents[3]
IR = ROOT / "scripts" / "04_identity_resolution"
sys.path.insert(0, str(IR))
sys.path.insert(0, str(IR / "blocking"))
from common import PAIRS, RUNS, labels, load_all  # noqa: E402
from blocking import add_block_keys  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PYDI_OUT = str(RESULTS / "pydi_output")   # PyDI's debug files, not kept in git
MODELS = {
    "English (PyDI default)": "sentence-transformers/all-MiniLM-L6-v2",
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}
TEXTS = {"name": "name", "name + city + country": "name_city_country"}
TOP_K, THRESHOLD = 10, 0.5   # as in blocking.py


def add_text(df):
    # name, city and country as one text, empty values left out
    parts = [df[c] if c in df.columns else pd.Series([""] * len(df), index=df.index)
             for c in ("name", "location_city", "location_country")]
    df["name_city_country"] = [" ".join(str(x) for x in xs if isinstance(x, str) and x.strip())
                               for xs in zip(*parts)]


def pair_set(pairs):
    return set(map(tuple, pairs[["id1", "id2"]].drop_duplicates().values))


def main():
    RESULTS.mkdir(exist_ok=True)
    rows, only = [], []
    for run in RUNS:
        data = load_all(run)
        for df in data.values():
            add_text(df)
        for a, b in PAIRS:
            L, R = data[a], data[b]
            add_block_keys(L, R)
            val = labels(a, b, "validation", run)
            matches = set(map(tuple, val[val["label"]][["id1", "id2"]].values))
            kw = dict(id_column="id", output_dir=PYDI_OUT)
            # the pipeline's other two blockers, for the union
            others = pair_set(TokenBlocker(L, R, column="scoped_tokens", tokenizer=str.split, **kw).materialize())
            others |= pair_set(TokenBlocker(L, R, column="domain_text", tokenizer=str.split, **kw).materialize())
            kept = {}
            for model, path in MODELS.items():
                for text, column in TEXTS.items():
                    start = time.time()
                    pairs = pair_set(EmbeddingBlocker(L, R, text_cols=[column], model=path, top_k=TOP_K,
                                                      threshold=THRESHOLD, device="cpu", **kw).materialize())
                    seconds = round(time.time() - start, 1)
                    union = pairs | others
                    kept[model, text] = matches & union
                    row = dict(run=run, pair=f"{a}-{b}", model=model, text=text, candidates=len(pairs),
                               pc=round(len(matches & pairs) / len(matches), 3),
                               union_candidates=len(union), union_pc=round(len(matches & union) / len(matches), 3),
                               validation_matches=len(matches), seconds=seconds)
                    rows.append(row)
                    print(row, flush=True)
            # validation matches that only one model's union keeps (main name, as in the pipeline)
            english, multi = kept["English (PyDI default)", "name"], kept["multilingual", "name"]
            names = {**dict(zip(L["id"], L["name"])), **dict(zip(R["id"], R["name"]))}
            for which, ids in (("only multilingual", multi - english), ("only English", english - multi)):
                for x, y in sorted(ids):
                    only.append(dict(run=run, pair=f"{a}-{b}", kept_by=which, id1=x, name1=names.get(x),
                                     id2=y, name2=names.get(y)))
    pd.DataFrame(rows).to_csv(RESULTS / "multilingual_blocking.csv", index=False)
    pd.DataFrame(only, columns=["run", "pair", "kept_by", "id1", "name1", "id2", "name2"]).to_csv(
        RESULTS / "multilingual_only_matches.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
