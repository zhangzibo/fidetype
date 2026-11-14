"""Print the markdown tables of results.md from results/metrics.json and results/explore.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).with_name("results")
m = json.loads((R / "metrics.json").read_text(encoding="utf-8"))["splits"]
x = json.loads((R / "explore.json").read_text(encoding="utf-8"))["splits"]
f3 = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
rots = [f"rot{k}" for k in range(5)]


def rng(key):
    vals = [key(m[r]) for r in rots]
    return f"{np.mean(vals):.3f} ({min(vals):.3f}-{max(vals):.3f})"


print("## criteria / main + rotations")
rows = [
    ("Raw R²", lambda r: r["raw"]["r2"]), ("Raw Pearson r", lambda r: r["raw"]["pearson"]),
    ("Coverage 0.80 (normalised)", lambda r: r["coverage"]["0.8"]["normalised"]),
    ("Coverage 0.90 (normalised)", lambda r: r["coverage"]["0.9"]["normalised"]),
    ("Coverage 0.95 (normalised)", lambda r: r["coverage"]["0.95"]["normalised"]),
    ("Coverage 0.90 (plain)", lambda r: r["coverage"]["0.9"]["plain"]),
    ("Mean radius 0.90 normalised (mm/s)", lambda r: r["coverage"]["0.9"]["mean_radius_normalised"]),
    ("Radius 0.90 plain (mm/s)", lambda r: r["coverage"]["0.9"]["radius_plain"]),
    ("Mean decoded speed (mm/s)", lambda r: r["gated"]["mean_speed_raw"]),
    ("Mean true speed (mm/s)", lambda r: r["gated"]["mean_speed_true"]),
    ("Gated R² (level 0.90)", lambda r: r["gated"]["r2"]), ("Gated motion fraction", lambda r: r["gated"]["motion_frac"]),
    ("Over-speed rate", lambda r: r["gated"]["overspeed_rate"]),
    ("No-signal output speed (mm/s)", lambda r: r["no_signal_speed"]),
    ("v_max (mm/s)", lambda r: r["v_max"]), ("min_quality", lambda r: r["min_quality"]),
]
print("| Measure | Main split | Rotations mean (min-max) |\n|---|---|---|")
for name, k in rows:
    print(f"| {name} | {k(m['main']):.3f} | {rng(k)} |")
print("\nreasons main:", m["main"]["gated"]["reasons"], m["main"]["gated"]["states"])
print("latency:", m["main"]["latency_ms"])
print("\n## controls (main split)")
print("| Input | Raw R² | Raw mean speed | Gated mean speed | Gated motion fraction | Over-speed |\n|---|---|---|---|---|---|")
for c in ("shuffled", "zero", "reversed", "zero_without_gates"):
    r = m["main"]["controls"][c]
    print(f"| {c} | {f3(r.get('r2_raw'))} | {r['mean_speed_raw']:.2f} | {r['mean_speed_out']:.3f} | {r['motion_frac']:.3f} | {r['overspeed_rate']:.3f} |")
print("controls over rotations: max gated speed",
      max(m[r]["controls"][c]["mean_speed_out"] for r in rots for c in ("shuffled", "zero", "reversed")),
      "raw R2 shuffled", [round(m[r]["controls"]["shuffled"]["r2_raw"], 3) for r in rots],
      "reversed", [round(m[r]["controls"]["reversed"]["r2_raw"], 3) for r in rots])
print("\n## paths (main split)")
p = m["main"]["paths"]
print(f"segments {p['segments']}")
print("| Velocity | Path efficiency | Endpoint error (mm, median) | Reached (7.5 mm) | Time-to-target (s, median) |\n|---|---|---|---|---|")
for k in ("true", "raw", "gated"):
    q = p[k]
    print(f"| {k} | {q['path_efficiency']:.3f} | {q['endpoint_error_mm']:.1f} | {q['reached_frac']:.3f} | {f3(q['time_to_target_s_median'])} |")
print("\n## post-hoc level sweep (main split; rotations mean in brackets)")
for var in ("no_ref", "full"):
    print(f"\n### {var}")
    print("| Level | Motion | Gated R² | Pearson | Over-speed | Mean cos | Reached | Path eff. | Shuffled motion | Shuffled speed | Zero motion |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for lv in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        a = x["main"][f"{var}@{lv}"]
        rm = lambda k: np.mean([x[r][f"{var}@{lv}"][k] for r in rots])  # noqa: E731
        print(f"| {lv} | {a['motion_frac']:.2f} [{rm('motion_frac'):.2f}] | {a['r2']:.3f} [{rm('r2'):.3f}] | {a['pearson']:.3f} | "
              f"{a['overspeed_rate']:.3f} [{rm('overspeed_rate'):.3f}] | {f3(a['mean_cos_moving'])} | {a['reached_frac']:.3f} | "
              f"{a['path_efficiency']:.3f} | {a['shuffled_motion_frac']:.3f} | {a['shuffled_mean_speed_out']:.2f} | {a['zero_motion_frac']:.3f} |")
sys.stdout.flush()
