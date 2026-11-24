"""Builds the data figures of the report from the pipeline's result files.

  groups.pdf    Fig. 2: records per group size, first pass (round 2) against the final result
  cleaning.pdf  Fig. 3: share of each source's records removed, by cleaning rule
  cutoff.pdf    Fig. 4: what the final cut-off removes, checked against the identifier links
  density.pdf   Fig. 5: density per attribute (sources and fused) and consistency per attribute

Run from the repo root:  python submission/final-report/scripts/report_figures.py [out_dir]
(default out_dir: submission/final-report/figures). Needs pandas and matplotlib.
The font is Latin Modern Roman 8 (the LaTeX text font), kept as TrueType in submission/final-report/figures.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.legend_handler import HandlerTuple  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "submission" / "final-report" / "figures"
IR = REPO / "scripts" / "04_identity_resolution" / "05_final" / "results"
FUSION = REPO / "scripts" / "05_data_fusion" / "results"

FONT = REPO / "submission" / "final-report" / "figures" / "lmroman8-regular.ttf"
font_manager.fontManager.addfont(str(FONT))
FONT_NAME = font_manager.FontProperties(fname=str(FONT)).get_name()

INK, INK2, GRID, AXIS, MUTED = "#1a1a1a", "#3d3d3a", "#e1e0d9", "#8f8e87", "#b9b8b0"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
plt.rcParams.update({
    "font.family": "serif", "font.serif": [FONT_NAME], "font.size": 8,
    "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": AXIS, "ytick.color": AXIS,
    "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.major.pad": 2, "ytick.major.pad": 2,
    "axes.labelpad": 2.5, "pdf.fonttype": 42, "svg.fonttype": "none",
})
CM = 1 / 2.54
META = {"Creator": None, "Producer": None, "CreationDate": None}


def axes(fig, box):
    """Axes from a box in cm: (left, bottom, width, height)."""
    W, H = fig.get_size_inches()
    l, b, w, h = box
    return fig.add_axes([l * CM / W, b * CM / H, w * CM / W, h * CM / H])


def clean(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(OUT / name, metadata=META)
    plt.close(fig)
    print("saved", OUT / name)


# ------------------------------------------------------------------ Fig. 2: group sizes
BUCKETS = [("2", 2, 2), ("3", 3, 3), ("4–10", 4, 10), ("11–100", 11, 100), ("over 100", 101, 10**9)]


def records_per_bucket(path):
    g = pd.read_csv(path)
    g["rec"] = g["cluster_size"] * g["frequency"]
    out = []
    for _, lo, hi in BUCKETS:
        s = g[(g["cluster_size"] >= lo) & (g["cluster_size"] <= hi)]
        out.append((int(s["frequency"].sum()), int(s["rec"].sum())))
    return out, int(g["cluster_size"].max())


def fig_groups():
    r2, r2max = records_per_bucket(IR / "group_sizes_r2.csv")
    r8, _ = records_per_bucket(IR / "group_sizes_r8.csv")
    fig = plt.figure(figsize=(12.2 * CM, 2.75 * CM))
    ax = axes(fig, (1.25, 0.72, 10.75, 1.93))
    clean(ax)
    x = range(len(BUCKETS))
    bw = 0.36
    ax.bar([i - bw / 2 - 0.02 for i in x], [r[1] / 1000 for r in r2], bw, color=MUTED, zorder=2,
           label="first pass, round 2")
    ax.bar([i + bw / 2 + 0.02 for i in x], [r[1] / 1000 for r in r8], bw, color=BLUE, zorder=2,
           label="final (one-to-one)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([b[0] for b in BUCKETS])
    ax.set_xlabel("Records in the group", labelpad=1.5)
    ax.set_ylabel("Records\n(thousands)", linespacing=1.1)
    ax.set_ylim(0, 25)
    ax.set_yticks([0, 10, 20])
    ax.tick_params(axis="x", length=0)
    n, rec = r2[-1]
    ax.annotate(f"{n} groups, {rec:,} records,\nthe largest {r2max:,}", (4 - bw / 2 - 0.02, rec / 1000),
                xytext=(0, 2), textcoords="offset points", ha="center", va="bottom", fontsize=7, color=INK2,
                linespacing=1.1)
    for i, (gr, rc) in enumerate(r8):
        if rc:
            ax.annotate(f"{gr:,} groups", (i + bw / 2 + 0.02, rc / 1000), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom", fontsize=7, color=INK2)
    ax.legend(loc="upper center", frameon=False, handlelength=1.1, borderaxespad=0.1, labelspacing=0.3)
    save(fig, "groups.pdf")


# ------------------------------------------------------------------ Fig. 3: cleaning
SOURCES = [("Wikidata", "wikidata", "wikidata_universities.csv"), ("ROR", "ror", "ror_education.csv"),
           ("DEQAR", "deqar", "deqar_institutions.csv")]
RULES = [("Rule 1: below bachelor level or seminary", BLUE, [1]),
         ("Rule 3: part of another organisation", ORANGE, [3]),
         ("Rule 4: main purpose not education", AQUA, [4]),
         ("Rules 2 and 5: not recognised, duplicate", YELLOW, [2, 5])]


def fig_cleaning():
    counts, kept = {}, {}
    for name, folder, kept_file in SOURCES:
        d = REPO / "data" / folder / "filtered"
        rule = pd.read_csv(d / "removed.csv", usecols=["rule"])["rule"].astype(int)
        counts[name] = [int(rule.isin(nums).sum()) for _, _, nums in RULES]
        kept[name] = len(pd.read_csv(d / kept_file, usecols=[0]))
        print(name, "removed by rule", counts[name], "kept", kept[name])
    fig = plt.figure(figsize=(12.2 * CM, 3.05 * CM))
    ax = axes(fig, (1.45, 1.62, 7.0, 1.3))
    clean(ax, grid="x")
    ax.set_xlim(0, 28)
    ax.set_xticks([0, 5, 10, 15, 20, 25])
    ax.set_xticklabels(["0", "5", "10", "15", "20", "25%"])
    ax.set_xlabel("Share of the source's records removed", labelpad=1.5)
    for i, (name, _, _) in enumerate(SOURCES):
        y, total, left = 2 - i, kept[name] + sum(counts[name]), 0.0
        for (label, col, _), cnt in zip(RULES, counts[name]):
            w = 100 * cnt / total
            ax.barh(y, w, left=left, height=0.62, color=col, edgecolor="white", linewidth=0.8, zorder=2)
            if w > 2.2:
                ax.text(left + w / 2, y, f"{cnt:,}", ha="center", va="center", fontsize=6.8, color="white",
                        zorder=3)
            left += w
        ax.text(left + 0.5, y, f"{sum(counts[name]):,} removed, {kept[name]:,} kept", ha="left", va="center",
                fontsize=7.2, color=INK2)
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels([s[0] for s in SOURCES])
    ax.set_ylim(-0.5, 2.5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend([Patch(color=c) for _, c, _ in RULES], [r[0] for r in RULES], ncol=2, loc="upper left",
              bbox_to_anchor=(-0.17, -0.52), frameon=False, handlelength=0.9, handleheight=0.9,
              columnspacing=1.2, labelspacing=0.25, borderaxespad=0)
    save(fig, "cleaning.pdf")


# ------------------------------------------------------------------ Fig. 4: final cut-off
FINAL_CUTOFF = {"wikidata-ror": 0.7, "deqar-ror": 0.55}          # FINAL_CUTOFF in 05_final/final.py
PAIR_STYLE = {
    "wikidata-ror": dict(label="Wikidata–ROR", color=BLUE, ls="-", marker="o", ms=3.2),
    "deqar-ror": dict(label="DEQAR–ROR", color=ORANGE, ls=(0, (3.2, 1.6)), marker="s", ms=2.9),
}


def fig_cutoff():
    df = pd.read_csv(IR / "cutoff_check.csv")
    data = {}
    for pair, g in df.groupby("pair", sort=False):
        g = g.sort_values("cut-off").reset_index(drop=True)
        wrong0 = g.loc[0, "ID key: wrong"]                       # wrong links at the matcher threshold
        g["wrong removed %"] = 100 * g["ID key: wrong removed"] / wrong0
        g["right per wrong"] = g["ID key: right removed"] / g["ID key: wrong removed"].where(
            g["ID key: wrong removed"] > 0)
        data[pair] = g
    fig = plt.figure(figsize=(12.2 * CM, 3.25 * CM))
    ax_a = axes(fig, (1.16, 0.78, 4.58, 2.36))
    ax_b = axes(fig, (7.34, 0.78, 4.74, 2.36))
    for ax in (ax_a, ax_b):
        ax.set_xlim(0.325, 0.925)
        ax.set_xticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        ax.set_xticklabels(["0.4", "0.5", "0.6", "0.7", "0.8", "0.9"])
        ax.set_xlabel("Cut-off on the match score")
        clean(ax)
    ax_a.set_ylim(0, 88)
    ax_a.set_yticks([0, 20, 40, 60, 80])
    ax_a.set_ylabel("Wrong links\nremoved (%)", linespacing=1.15)
    ax_b.set_ylim(0, 7.4)
    ax_b.set_yticks([0, 2, 4, 6])
    ax_b.set_ylabel("Right links lost per\nwrong link removed", linespacing=1.15)
    ax_b.axhline(1, color="#6b6a64", lw=0.6, ls=(0, (1, 1.4)), zorder=1)   # below: more wrong than right removed
    for pair, g in data.items():
        st = PAIR_STYLE[pair]
        kw = dict(color=st["color"], ls=st["ls"], lw=1.1, marker=st["marker"], ms=st["ms"], mfc="white",
                  mec=st["color"], mew=0.9, zorder=3, solid_capstyle="round", dash_capstyle="round", clip_on=False)
        ax_a.plot(g["cut-off"], g["wrong removed %"], **kw)
        gb = g[g["right per wrong"].notna()]
        ax_b.plot(gb["cut-off"], gb["right per wrong"], **kw)
        f = g[g["cut-off"] == FINAL_CUTOFF[pair]].iloc[0]
        fk = dict(marker=st["marker"], ms=st["ms"] + 2.4, mfc=st["color"], mec="white", mew=0.7, ls="none", zorder=5)
        ax_a.plot([f["cut-off"]], [f["wrong removed %"]], **fk)
        ax_b.plot([f["cut-off"]], [f["right per wrong"]], **fk)
    fa, fd = (data[p][data[p]["cut-off"] == FINAL_CUTOFF[p]].iloc[0] for p in ("wikidata-ror", "deqar-ror"))
    ann = dict(fontsize=7.5, color=INK, zorder=6)
    ax_a.annotate(f"{fa['wrong removed %']:.0f}%", (0.7, fa["wrong removed %"]), xytext=(4, -6),
                  textcoords="offset points", ha="left", va="top", **ann)
    ax_a.annotate(f"{fd['wrong removed %']:.0f}%", (0.55, fd["wrong removed %"]), xytext=(-2.5, 3.5),
                  textcoords="offset points", ha="right", va="bottom", **ann)
    ax_b.annotate(f"{fa['right per wrong']:.2f}", (0.7, fa["right per wrong"]), xytext=(-4, 4),
                  textcoords="offset points", ha="right", va="bottom", **ann)
    ax_b.annotate(f"{fd['right per wrong']:.2f}", (0.55, fd["right per wrong"]), xytext=(3.2, -1.6),
                  textcoords="offset points", ha="left", va="top", **ann)
    handles = [Line2D([], [], color=st["color"], ls=st["ls"], lw=1.1, marker=st["marker"], ms=st["ms"],
                      mfc="white", mec=st["color"], mew=0.9) for st in PAIR_STYLE.values()]
    finals = tuple(Line2D([], [], ls="none", marker=st["marker"], ms=st["ms"] + 2.4, mfc=st["color"], mec="white",
                          mew=0.7) for st in PAIR_STYLE.values())
    ax_b.legend(handles + [finals], [st["label"] for st in PAIR_STYLE.values()] + ["final cut-off"],
                handler_map={tuple: HandlerTuple(ndivide=None, pad=0.6)}, loc="upper left",
                bbox_to_anchor=(0.0, 1.03), frameon=False, handlelength=2.4, handletextpad=0.5,
                borderaxespad=0.2, labelspacing=0.35)
    save(fig, "cutoff.pdf")


# ------------------------------------------------------------------ Fig. 5: density and consistency
ROWS = [("Name", "name"), ("Country code", "country_code"), ("City", "city"), ("Website", "website"),
        ("Founding year", "founding_year"), ("Latitude / longitude", "latitude"), ("Alternative names", "alt_names"),
        ("Acronyms", "acronyms"), ("Region / status", "status"), ("Students", "students"),
        ("Memberships", "memberships"), ("QA reports", "qa_reports")]
SOURCE_STYLE = [("Wikidata", "wikidata", BLUE, "o"), ("ROR", "ror", AQUA, "D"), ("DEQAR", "deqar", ORANGE, "s")]
CONSISTENCY_ROWS = ["country_code", "founding_year", "city", "name", "website"]


def fig_density():
    dens = pd.read_csv(FUSION / "density.csv", index_col=0)
    cons = pd.read_csv(FUSION / "consistency.csv", index_col=0)["consistency"]
    fig = plt.figure(figsize=(12.2 * CM, 4.2 * CM))
    ax = axes(fig, (2.75, 0.82, 5.25, 2.93))
    clean(ax, grid="x")
    n = len(ROWS)
    for i, (_, key) in enumerate(ROWS):
        y = n - 1 - i
        ax.axhline(y, color=GRID, lw=0.4, zorder=0)
        ax.plot([0, dens.loc[key, "fused"]], [y, y], color=INK2, lw=2.0, solid_capstyle="butt", zorder=2)
        for _, col, c, m in SOURCE_STYLE:
            v = dens.loc[key, col]
            if pd.notna(v):
                ax.plot([v], [y], marker=m, ms=3.6 if m != "D" else 3.2, mfc=c, mec="white", mew=0.6, ls="none",
                        zorder=3, clip_on=False)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[0] for r in ROWS][::-1])
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", ".25", ".50", ".75", "1"])
    ax.set_xlabel("Density (share of records with a value)", labelpad=1.5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    handles = [Line2D([], [], color=INK2, lw=2.0)] + [
        Line2D([], [], marker=m, ms=3.6, mfc=c, mec="white", mew=0.6, ls="none") for _, _, c, m in SOURCE_STYLE]
    ax.legend(handles, ["fused"] + [s[0] for s in SOURCE_STYLE], ncol=4, loc="lower left",
              bbox_to_anchor=(-0.02, 1.0), frameon=False, handlelength=1.3, columnspacing=1.0, borderaxespad=0.1)

    ax2 = axes(fig, (9.75, 0.82, 2.1, 2.93))
    keys = [r[1] for r in ROWS]
    for key in CONSISTENCY_ROWS:
        v, y = cons[key], n - 1 - keys.index(key)
        ax2.barh(y, v, height=0.6, color=BLUE, zorder=2)
        ax2.text(v + 0.03, y, f"{100 * v:.1f}%" if v > 0.99 else f"{100 * v:.0f}%", va="center", ha="left",
                 fontsize=7, color=INK2)
    ax2.set_ylim(-0.6, n - 0.4)
    ax2.set_xlim(0, 1.32)
    ax2.set_xticks([0, 0.5, 1.0])
    ax2.set_xticklabels(["0", ".5", "1"])
    ax2.set_yticks([])
    ax2.set_xlabel("Consistency", labelpad=1.5)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.grid(axis="x", color=GRID, lw=0.5)
    ax2.set_axisbelow(True)
    for i in range(n):
        ax2.axhline(i, color=GRID, lw=0.4, zorder=0)
    save(fig, "density.pdf")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_groups()
    fig_cleaning()
    fig_cutoff()
    fig_density()
