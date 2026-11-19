"""Generate report figures from saved experimental results."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FINAL = RESULTS / "final_evaluation"
OUTPUT = RESULTS / "figures"

OUTPUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150
})

METHODS = {
    "tfidf": "TF-IDF",
    "semantic_only": "Semantic only",
    "semantic_hybrid": "Semantic hybrid",
    "optimized_rules": "Optimized rules",
    "original_rules": "Original rules (retuned)",
    "ml_original_threshold": "Original ML",
    "ml_retuned_threshold": "Retuned ML"
}

PAIRS = {
    "wikidata-ror": "Wikidata-ROR",
    "deqar-ror": "DEQAR-ROR"
}

results = pd.read_csv(FINAL / "test_results.csv")


def save(fig, name):

    for extension in ["png", "svg"]:

        fig.savefig(
            OUTPUT / f"{name}.{extension}",
            dpi=300,
            bbox_inches="tight"
        )

    plt.close(fig)

    print(f"Saved {name}")


# Figure 1: Validation and test F1

fig, axes = plt.subplots(
    1, 2, figsize=(14, 5.5),
    layout="constrained"
)

for ax, (pair, title) in zip(axes, PAIRS.items()):

    df = results[results["pair"] == pair]
    df = df.set_index("method").loc[list(METHODS)]

    y = np.arange(len(df))

    ax.barh(
        y - 0.18, df["validation_f1"],
        height=0.35, label="Validation",
        color="#8CA9C7"
    )

    bars = ax.barh(
        y + 0.18, df["test_f1"],
        height=0.35, label="Test",
        color="#287271"
    )

    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)

    ax.set_yticks(y, list(METHODS.values()))
    ax.invert_yaxis()
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("F1-score")
    ax.set_title(title)

    ax.grid(axis="x", alpha=0.15)

handles, legend_labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles, legend_labels,
    loc="outside lower center",
    ncol=2,
    frameon=False
)

fig.suptitle("Identity resolution performance")

save(fig, "01_matching_performance")


# Figure 2: False positives and false negatives

fig, axes = plt.subplots(
    1, 2, figsize=(14, 5.5),
    layout="constrained"
)

for ax, (pair, title) in zip(axes, PAIRS.items()):

    df = results[results["pair"] == pair]
    df = df.set_index("method").loc[list(METHODS)]

    y = np.arange(len(df))

    ax.barh(
        y, df["fn"],
        label="False negatives",
        color="#527DA3"
    )

    ax.barh(
        y, df["fp"], left=df["fn"],
        label="False positives",
        color="#DB8A6C"
    )

    for i, count in enumerate(df["fp"] + df["fn"]):

        ax.text(count + 0.5, i, str(count), va="center")

    ax.set_yticks(y, list(METHODS.values()))
    ax.invert_yaxis()
    ax.set_xlim(0, 60)
    ax.set_xlabel("Number of test errors")
    ax.set_title(title)


handles, legend_labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles, legend_labels,
    loc="outside lower center",
    ncol=2,
    frameon=False
)

fig.suptitle("Matching error distribution")

save(fig, "02_matching_errors")


# Figure 3: Attribute weight comparison

best = pd.read_csv(
    RESULTS / "optimized_rules/best_optimized.csv"
).set_index("pair")

features = [
    "names_best_jaro_winkler",
    "country", "domain", "city", "year", "geo"
]

names = [
    "Name", "Country", "Domain",
    "City", "Year", "Geography"
]

weights = np.array([
    [0.35, 0.15, 0.25, 0.10, 0.10, 0.05],
    best.loc["wikidata-ror", features].to_numpy(dtype=float),
    best.loc["deqar-ror", features].to_numpy(dtype=float)
])

fig, ax = plt.subplots(
    figsize=(10, 4), layout="constrained"
)

image = ax.imshow(
    weights, cmap="Blues", vmin=0, vmax=0.4,
    aspect="auto"
)

for i in range(3):
    for j in range(6):

        ax.text(
            j, i, f"{weights[i, j]:.0%}",
            ha="center", va="center",
            color="white" if weights[i, j] >= 0.25 else "black"
        )

ax.set_xticks(range(6), names)

ax.set_yticks(range(3), [
    "Original weights",
    "Optimized Wikidata-ROR",
    "Optimized DEQAR-ROR"
])

ax.set_title("Comparison of attribute weights")

fig.colorbar(image, ax=ax, label="Weight")

save(fig, "03_attribute_weights")

print("\nAll figures generated successfully.")
