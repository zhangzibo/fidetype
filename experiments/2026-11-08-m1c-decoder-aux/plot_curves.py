"""Plot M1-C training curves (val CER and val keystroke-head accuracy) for several runs.

    python plot_curves.py results/curves.png C:/Users/zhang/bci-data/runs/m1c-r0-baseline ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = ["#2a78d6", "#eb6834", "#1f9e6e", "#8a5cd1", "#c9a227"]
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def main(out: str, run_dirs: list[str]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), dpi=100, facecolor=SURFACE)
    panels = [(axes[0], "Train loss (total)", "train_loss"), (axes[1], "Val greedy CER (typed)", "val_cer_typed"),
              (axes[2], "Val keystroke-head accuracy", "val_key_acc")]
    for i, rd in enumerate(run_dirs):
        recs = [json.loads(line) for line in (Path(rd) / "metrics.jsonl").read_text().splitlines()]
        ep = [r for r in recs if r["type"] == "epoch"]
        label = Path(rd).name.replace("m1c-", "")
        for ax, _, key in panels:
            xs = [r["epoch"] for r in ep if key in r]
            ys = [r[key] for r in ep if key in r]
            if ys:
                ax.plot(xs, ys, color=COLORS[i % len(COLORS)], lw=1.6, label=label)
    for ax, title, _ in panels:
        ax.set_facecolor(SURFACE)
        ax.set_title(title, color=INK, fontsize=10, loc="left")
        ax.set_xlabel("epoch", color=INK2, fontsize=8)
        ax.grid(True, color="#e6e5e0", lw=0.6)
        ax.tick_params(colors=INK2, labelsize=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color("#c9c8c2")
    axes[1].legend(frameon=False, fontsize=7, labelcolor=INK2)
    fig.tight_layout()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=SURFACE)
    print(f"wrote {out} ({Path(out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
