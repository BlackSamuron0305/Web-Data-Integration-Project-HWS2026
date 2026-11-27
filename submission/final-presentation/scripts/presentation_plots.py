"""Builds the result plots of the final presentation from the pipeline's result files.

  approaches.png  validation F1 of the nine matching approaches and the names-only baseline (final run)
  blocking.png    pair completeness of each blocker on the validation pairs (first pass: all blockers ran)
  groups.png      records per group size: early version (no one-to-one for DEQAR-ROR) against the final run
  cleaning.png    records per source, kept and removed by the cleaning rules
  sources.png     fused universities by number of sources
  fusion.png      accuracy of the conflict resolution functions on the test half of the fusion gold standard

Run from the repo root after the pipeline:  python submission/final-presentation/scripts/presentation_plots.py
Writes to submission/final-presentation/figures. Needs pandas and matplotlib.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "submission" / "final-report" / "scripts"))
from report_tables import APPROACHES, IR, PAIRS, SHORT_BLOCKER, best, matching_log  # noqa: E402

OUT = HERE.parent / "figures"
FUSION = ROOT / "scripts" / "05_data_fusion" / "results"

# colours of the slides: navy and orange of the template, a mid blue for the second series
NAVY, BLUE, ORANGE, GREY, INK, MUTED, GRID = "#003056", "#2F6DB5", "#D96C1E", "#C3CAD3", "#1F2933", "#5B6670", "#E3E7EC"
PAIR_COLOUR = {"wikidata-ror": BLUE, "deqar-ror": ORANGE}
PAIR_NAME = {"wikidata-ror": "Wikidata–ROR", "deqar-ror": "DEQAR–ROR"}
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Calibri", "Carlito", "Arial", "DejaVu Sans"],
    "font.size": 13, "axes.labelsize": 13, "xtick.labelsize": 12, "ytick.labelsize": 13, "legend.fontsize": 12,
    "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
    "axes.edgecolor": GREY, "axes.linewidth": 0.8, "savefig.dpi": 250, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})


def clean(ax, grid="x"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def approaches():
    # dot plot: one row per approach, one dot per dataset pair (F1 differences are small, so no bars from 0)
    rows = [("Names only (baseline)", "01_rules_string_similarity", "name Jaro-Winkler")]
    rows += [(f"{n} {name}", folder, None) for folder, (n, name) in APPROACHES.items()]
    f1 = {}
    for label, folder, matcher in rows:
        log = matching_log(folder)
        if matcher:
            log = log[log["matcher"] == matcher]
        f1[label] = {pair: best(log, "final", pair)["F1"] for pair in PAIRS}
    labels = list(f1)[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for k, label in enumerate(labels):
        vals = [f1[label][p] for p in PAIRS]
        ax.plot([min(vals), max(vals)], [k, k], color=GREY, lw=2, zorder=1)
        for pair in PAIRS:
            ax.scatter(f1[label][pair], k, s=90, color=PAIR_COLOUR[pair], edgecolor="white", lw=1.5, zorder=2,
                       label=PAIR_NAME[pair] if k == 0 else None)
    ax.set_yticks(range(len(labels)), labels)
    for tick in ax.get_yticklabels():
        if tick.get_text() in ("8 Fine-tuned LM", "9 Local LLM"):
            tick.set_fontweight("bold")
    ax.set_xlim(0.72, 0.97)
    ticks = [0.75, 0.80, 0.85, 0.90, 0.95]
    ax.set_xticks(ticks, [f"{t:.2f}" for t in ticks])  # 0.75, like F1 in the text
    ax.set_xlabel("F1 on the validation pairs (final run)")
    clean(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, handletextpad=0.4, borderaxespad=0.2)
    fig.savefig(OUT / "approaches.png")
    plt.close(fig)


def blocking():
    log = pd.read_csv(IR / "blocking" / "results" / "blocking.csv")
    log = log[(log["run"] == "first_pass") & log["pair_completeness"].notna()]
    order = [b for b in SHORT_BLOCKER if b in set(log["blocker"])]
    names = {"standard: exercise key (2 letters x 3 words)": "Exercise key",
             "standard: normalised name": "Same name",
             "sorted neighbourhood: name, window 20": "Sorted neighbourhood",
             "token: country + name word": "Country + name word",
             "token: same web domain": "Same web domain",
             "embedding: name, top 10": "Embedding: 10 nearest",
             "union: country + name word | same domain": "Word + domain",
             "union: country + name word | same domain | embedding": "All three together"}
    order = [b for b in order if b in names][::-1]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    h = 0.38
    for j, pair in enumerate(PAIRS):
        vals = [log[(log["pair"] == pair) & (log["blocker"] == b)]["pair_completeness"].iloc[0] for b in order]
        ys = [k + (h / 2 if j == 0 else -h / 2) for k in range(len(order))]
        ax.barh(ys, vals, height=h - 0.04, color=PAIR_COLOUR[pair], label=PAIR_NAME[pair])
        for y, v in zip(ys, vals):
            ax.text(v + 0.01, y, f"{v:.0%}", va="center", fontsize=11, color=INK)
    ax.set_yticks(range(len(order)), [names[b] for b in order])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_xlim(0, 1.1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Share of the true matches the blocker keeps (validation pairs)")
    clean(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, handletextpad=0.4, borderaxespad=0.2)
    fig.savefig(OUT / "blocking.png")
    plt.close(fig)


def groups():
    res = IR / "global_matching_and_test" / "results"
    runs = {"Early version, no one-to-one": res / "history" / "group_sizes_early_version.csv",
            "Final run": res / "group_sizes_final.csv"}
    buckets = [("2", 2, 2), ("3", 3, 3), ("4–10", 4, 10), ("11–100", 11, 100), ("over 100", 101, 10**9)]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    w = 0.38
    for j, (name, path) in enumerate(runs.items()):
        s = pd.read_csv(path).set_index("cluster_size")["frequency"]
        records = [int((s[(s.index >= lo) & (s.index <= hi)] * s[(s.index >= lo) & (s.index <= hi)].index).sum())
                   for _, lo, hi in buckets]
        xs = [k + (-w / 2 if j == 0 else w / 2) for k in range(len(buckets))]
        ax.bar(xs, records, width=w - 0.04, color=GREY if j == 0 else NAVY, label=name)
        for x, v in zip(xs, records):
            if v:
                ax.text(x, v + 300, f"{v / 1000:.1f}K", ha="center", fontsize=11, color=INK)
    ax.set_xticks(range(len(buckets)), [b[0] for b in buckets])
    ax.set_xlabel("Records in the group")
    ax.set_ylabel("Records")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    clean(ax, grid="y")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, handletextpad=0.4, borderaxespad=0.2)
    fig.savefig(OUT / "groups.png")
    plt.close(fig)


def cleaning():
    files = {"Wikidata": "wikidata/{}/wikidata_universities.csv", "ROR": "ror/{}/ror_education.csv",
             "DEQAR": "deqar/{}/deqar_institutions.csv"}
    kept, removed = [], []
    for f in files.values():
        before = len(pd.read_csv(ROOT / "data" / f.format("original"), usecols=[0]))
        after = len(pd.read_csv(ROOT / "data" / f.format("filtered"), usecols=[0]))
        kept.append(after)
        removed.append(before - after)
    names = list(files)[::-1]
    kept, removed = kept[::-1], removed[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.barh(names, kept, color=NAVY, height=0.6, label="kept")
    ax.barh(names, removed, left=[k + 150 for k in kept], color=ORANGE, height=0.6, label="removed")
    for y, (k, r) in enumerate(zip(kept, removed)):
        ax.text(k / 2, y, f"{k:,}", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
        ax.text(k + r + 500, y, f"−{r:,} ({r / (k + r):.0%})", va="center", fontsize=12, color=INK)
    ax.set_xlim(0, 37000)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    clean(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, handletextpad=0.4, borderaxespad=0.2)
    fig.savefig(OUT / "cleaning.png")
    plt.close(fig)


def sources():
    s = pd.read_csv(FUSION / "group_sizes.csv").set_index("sources per university")["universities"]
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    labels = [f"{k} source" + ("s" if k > 1 else "") for k in s.index]
    ax.bar(labels, s.values, color=[GREY, NAVY, NAVY], width=0.6)
    for k, v in enumerate(s.values):
        ax.text(k, v + 300, f"{v:,}", ha="center", fontsize=12, color=INK)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    fig.savefig(OUT / "sources.png")
    plt.close(fig)


def fusion():
    s = pd.read_csv(FUSION / "strategies.csv")
    s = s[s["gold subset"] == "test"]
    names = {"content-based": "Content-based", "voting": "Voting", "trust: Wikidata first": "Trust Wikidata",
             "trust: ROR first": "Trust ROR", "voting: ties by trust": "Voting, ties by trust (ours)",
             "best per attribute": "Final: best per attribute"}
    order = [k for k in names if k in set(s["strategy"])][::-1]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    h = 0.38
    for j, (comp, colour) in enumerate([("tolerant", NAVY), ("strict", GREY)]):
        vals = [s[(s["strategy"] == k) & (s["comparison"] == comp)]["mean single-valued"].iloc[0] for k in order]
        ys = [k + (h / 2 if j == 0 else -h / 2) for k in range(len(order))]
        ax.barh(ys, vals, height=h - 0.04, color=colour, label=f"{comp} comparison")
        for y, v in zip(ys, vals):
            ax.text(v + 0.01, y, f"{v:.0%}", va="center", fontsize=11, color=INK)
    ax.set_yticks(range(len(order)), [names[k] for k in order])
    for tick in ax.get_yticklabels():
        if "ours" in tick.get_text() or "Final" in tick.get_text():
            tick.set_fontweight("bold")
    ax.set_xlim(0, 1.1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Correct names, country codes, cities and years (test half, 39 universities)")
    clean(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, handletextpad=0.4, borderaxespad=0.2)
    fig.savefig(OUT / "fusion.png")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    for make in (approaches, blocking, groups, cleaning, sources, fusion):
        make()
        print("wrote", make.__name__)


if __name__ == "__main__":
    main()
