"""Plot the training curves of a ConvCTC run (metrics.jsonl) to a small PNG.

    python plot_curves.py C:/Users/zhang/bci-data/runs/<run> results/<run>-curves.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"  # categorical slots 1 and 2
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def main(run_dir: str, out: str) -> None:
    recs = [json.loads(line) for line in (Path(run_dir) / "metrics.jsonl").read_text().splitlines()]
    ep = [r for r in recs if r["type"] == "epoch"]
    e = [r["epoch"] for r in ep]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3), dpi=110, facecolor=SURFACE)
    panels = [
        (axes[0], "CTC loss", [("train", "train_loss", BLUE), ("val", "val_loss", ORANGE)]),
        (axes[1], "Validation greedy CER", [("vs typed", "val_cer_typed", BLUE),
                                            ("vs target", "val_cer_target", ORANGE)]),
    ]
    for ax, title, series in panels:
        ax.set_facecolor(SURFACE)
        for label, key, color in series:
            xs = [x for x, r in zip(e, ep) if key in r]
            ys = [r[key] for r in ep if key in r]
            if ys:
                ax.plot(xs, ys, color=color, lw=2, label=label)
        ax.set_title(title, color=INK, fontsize=10, loc="left")
        ax.set_xlabel("epoch", color=INK2, fontsize=8)
        ax.grid(True, color="#e6e5e0", lw=0.6)
        ax.tick_params(colors=INK2, labelsize=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color("#c9c8c2")
        ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=SURFACE)
    print(f"wrote {out} ({Path(out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
