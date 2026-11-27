"""Builds the data figures of the report from the pipeline's result files.

  cleaning.pdf  Fig. 2: share of each source's records removed, by cleaning rule
  density.pdf   Fig. 3: density per attribute (sources and fused) and consistency per attribute
(The group sizes are a table in the report, built by report_tables.py.)

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
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "submission" / "final-report" / "figures"
FUSION = REPO / "scripts" / "05_data_fusion" / "results"

FONT = REPO / "submission" / "final-report" / "figures" / "lmroman8-regular.ttf"
font_manager.fontManager.addfont(str(FONT))
FONT_NAME = font_manager.FontProperties(fname=str(FONT)).get_name()

INK, INK2, GRID, AXIS, MUTED = "#1a1a1a", "#3d3d3a", "#e1e0d9", "#8f8e87", "#b9b8b0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
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


# ------------------------------------------------------------------ Fig. 2: cleaning
SOURCES = [("Wikidata", "wikidata", "wikidata_universities.csv"), ("ROR", "ror", "ror_education.csv"),
           ("DEQAR", "deqar", "deqar_institutions.csv")]
# (label, colour, hatch, rules): a red ramp, as red means removed or problem throughout the report (blue and
# orange mean first pass and final run). Rules 2 and 5 are near-black red, and the hatch keeps rule 4 apart
# from rule 3, also in greyscale.
RED_DARK, RED_MID, RED_LIGHT, RED_INK = "#9e2a2b", "#d9534f", "#f2b6b2", "#4a1414"
RULES = [("Rule 1: below bachelor level or seminary", RED_DARK, "", [1]),
         ("Rule 3: part of another organisation", RED_MID, "", [3]),
         ("Rule 4: main purpose not education", RED_LIGHT, "////", [4]),
         ("Rules 2 and 5: not recognised, duplicate", RED_INK, "", [2, 5])]
# colour of the counts inside the bars: white on the dark greys, dark on the light ones
BAR_LABEL = {RED_DARK: "white", RED_MID: "white", RED_LIGHT: INK, RED_INK: "white"}


def fig_cleaning():
    counts, kept = {}, {}
    for name, folder, kept_file in SOURCES:
        d = REPO / "data" / folder / "filtered"
        rule = pd.read_csv(d / "removed.csv", usecols=["rule"])["rule"].astype(int)
        counts[name] = [int(rule.isin(nums).sum()) for _, _, _, nums in RULES]
        kept[name] = len(pd.read_csv(d / kept_file, usecols=[0]))
        print(name, "removed by rule", counts[name], "kept", kept[name])
    # the figure is as high as its content: no blank band above the bars or below the legend
    fig = plt.figure(figsize=(12.2 * CM, 2.72 * CM))
    ax = axes(fig, (1.3, 1.38, 8.3, 1.3))
    clean(ax, grid="x")
    ax.set_xlim(0, 28)
    ax.set_xticks([0, 5, 10, 15, 20, 25])
    ax.set_xticklabels(["0", "5", "10", "15", "20", "25%"])
    ax.set_xlabel("Share of the source's records removed", labelpad=1.5)
    for i, (name, _, _) in enumerate(SOURCES):
        y, total, left = 2 - i, kept[name] + sum(counts[name]), 0.0
        for (label, col, hatch, _), cnt in zip(RULES, counts[name]):
            w = 100 * cnt / total
            ax.barh(y, w, left=left, height=0.62, color=col, hatch=hatch, edgecolor="white", linewidth=0.8,
                    zorder=2)
            if w > 2.2:
                ax.text(left + w / 2, y, f"{cnt:,}", ha="center", va="center", fontsize=6.8, color=BAR_LABEL[col],
                        zorder=3)
            left += w
        # a white box, so the vertical gridlines do not run through the text
        ax.text(left + 0.5, y, f"{sum(counts[name]):,} removed, {kept[name]:,} kept", ha="left", va="center",
                fontsize=7.2, color=INK2, zorder=3, bbox=dict(facecolor="white", edgecolor="none", pad=0.8))
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels([s[0] for s in SOURCES])
    ax.set_ylim(-0.5, 2.5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend([Patch(facecolor=c, hatch=h, edgecolor="white") for _, c, h, _ in RULES], [r[0] for r in RULES],
              ncol=2, loc="upper left",
              bbox_to_anchor=(-0.14, -0.52), frameon=False, handlelength=0.9, handleheight=0.9,
              columnspacing=1.2, labelspacing=0.25, borderaxespad=0)
    save(fig, "cleaning.pdf")


# ------------------------------------------------------------------ Fig. 3: density and consistency
ROWS = [("Name", "name"), ("Country code", "country_code"), ("City", "city"), ("Website", "website"),
        ("Founding year", "founding_year"), ("Latitude / longitude", "latitude"), ("Alternative names", "alt_names"),
        ("Acronyms", "acronyms"), ("Region / status", "status"), ("Students", "students"),
        ("Memberships", "memberships"), ("QA reports", "qa_reports")]
SOURCE_STYLE = [("Wikidata", "wikidata", BLUE, "o"), ("ROR", "ror", AQUA, "D"), ("DEQAR", "deqar", ORANGE, "s")]
CONSISTENCY_ROWS = ["country_code", "founding_year", "city", "name", "website"]


def fig_density():
    dens = pd.read_csv(FUSION / "density.csv", index_col=0)
    cons = pd.read_csv(FUSION / "consistency.csv", index_col=0)["consistency"]
    # the legend sits in the empty lower part of the right panel, so no band above the plot is needed
    fig = plt.figure(figsize=(12.2 * CM, 3.86 * CM))
    ax = axes(fig, (2.75, 0.82, 6.45, 2.93))   # up to the right panel, no blank band between the two
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
    ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1"])
    ax.set_xlabel("Density (share of records with a value)", labelpad=1.5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    handles = [Line2D([], [], color=INK2, lw=2.0)] + [
        Line2D([], [], marker=m, ms=3.6, mfc=c, mec="white", mew=0.6, ls="none") for _, _, c, m in SOURCE_STYLE]

    ax2 = axes(fig, (9.75, 0.82, 2.1, 2.93))
    keys = [r[1] for r in ROWS]
    for key in CONSISTENCY_ROWS:
        v, y = cons[key], n - 1 - keys.index(key)
        ax2.barh(y, v, height=0.6, color=INK2, zorder=2)   # INK2 like the fused bars (BLUE means Wikidata)
        ax2.text(v + 0.03, y, f"{100 * v:.1f}%" if v > 0.99 else f"{100 * v:.0f}%", va="center", ha="left",
                 fontsize=7, color=INK2)
    ax2.set_ylim(-0.6, n - 0.4)
    ax2.set_xlim(0, 1.32)
    ax2.set_xticks([0, 0.5, 1.0])
    ax2.set_xticklabels(["0", "50", "100%"])  # percent, like the bar labels
    ax2.set_yticks([])
    ax2.set_xlabel("Consistency", labelpad=1.5)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.grid(axis="x", color=GRID, lw=0.5)
    ax2.set_axisbelow(True)
    for key in CONSISTENCY_ROWS:   # row lines only where a bar is: the rows below hold the legend
        ax2.axhline(n - 1 - keys.index(key), color=GRID, lw=0.4, zorder=0)
    ax2.legend(handles, ["fused"] + [s[0] for s in SOURCE_STYLE], ncol=1, loc="lower center",
               bbox_to_anchor=(0.5, 0.0), frameon=True, facecolor="white", edgecolor="none", framealpha=1.0,
               handlelength=1.3, labelspacing=0.2, borderpad=0.5, borderaxespad=0.0, title="Left panel",
               title_fontsize=7.5)
    save(fig, "density.pdf")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_cleaning()
    fig_density()
