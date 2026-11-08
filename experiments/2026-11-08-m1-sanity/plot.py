"""Plots for the M1 sanity check. Reads results/decoding.json, writes 2 small PNGs."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "results"
TIMES = np.arange(-50, 51) / 100.0 * 1000  # ms
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6", "#008300", "#e34948"]
GRAY = "#9a9994"


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    ax.axvline(0, color=GRAY, lw=0.8, ls="--")
    ax.tick_params(labelsize=8)


def main() -> None:
    res = json.loads((OUT / "decoding.json").read_text(encoding="utf-8"))
    subs = sorted(res, key=lambda s: int(s[1:]))

    # Evoked GFP, normalised per subject to its -0.5..-0.3 s mean, so subjects share one axis.
    fig, axs = plt.subplots(1, 2, figsize=(8, 3), dpi=110, sharey=True)
    for ax, t in zip(axs, ("mag", "grad")):
        for i, s in enumerate(subs):
            g = np.array(res[s]["evoked"][t])
            base = g[TIMES <= -300].mean()
            ax.plot(TIMES, g / base, color=COLORS[i], lw=1.6, label=s)
            gr = np.array(res[s]["evoked_random"][t])
            ax.plot(TIMES, gr / base, color=GRAY, lw=0.8, alpha=0.6)
        style(ax)
        ax.set_title(f"GFP, {t} (gray: random non-key times)", fontsize=9)
        ax.set_xlabel("time from key press (ms)", fontsize=8)
    axs[0].set_ylabel("GFP / mean GFP at -500..-300 ms", fontsize=8)
    axs[1].legend(fontsize=7, frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "evoked_gfp.png")
    plt.close(fig)

    # Decoding curves: accuracy minus chance.
    fig, axs = plt.subplots(1, 2, figsize=(8, 3), dpi=110, sharey=False)
    for ax, task, name in zip(axs, ("hand", "char"), ("hand (L/R)", "letter (all a-z)")):
        for i, s in enumerate(subs):
            r = res[s][task]
            ax.plot(TIMES, np.array(r["curve"]) - r["chance"], color=COLORS[i], lw=1.6, label=s)
            for ctl in ("_perm", "_random"):
                c = res[s][task + ctl]
                ax.plot(TIMES, np.array(c["curve"]) - c["chance"], color=GRAY, lw=0.6, alpha=0.6)
        style(ax)
        ax.axhline(0, color="#52514e", lw=0.8)
        ax.set_title(f"{name}: accuracy - chance (gray: controls)", fontsize=9)
        ax.set_xlabel("time from key press (ms)", fontsize=8)
    axs[0].set_ylabel("accuracy - majority-class chance", fontsize=8)
    axs[0].legend(fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "decoding_curves.png")
    plt.close(fig)
    for p in ("evoked_gfp.png", "decoding_curves.png"):
        print(p, (OUT / p).stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
