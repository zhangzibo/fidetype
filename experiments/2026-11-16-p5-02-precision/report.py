"""Print the aggregate tables of results/results.json as markdown (for results.md). No per-trial data."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results" / "results.json").read_text(encoding="utf-8"))


def f(x, nd=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def iv(v):
    return "-" if not v else f"[{v[0]:.4f}, {v[1]:.4f}]"


for st in ("t15", "t12"):
    if st not in R:
        continue
    s = R[st]
    b = s["base"]
    print(f"\n### {st.upper()} ({s['n_calibration']} calibration, {s['n_held_out']} held out)\n")
    print(f"Base (P14-03) guard `{b['config_id']}`: commit_p {b['commit_p']}. Held out: {b['held_out_can_commit']} "
          f"items pass every commit condition at commit_p 0; top-1 right on {b['held_out_top1_right']}.\n")
    print("| target precision | commit_p | feasible | cal. test commits / wrong | held-out commits / n | commit rate "
          "| wrong | precision [CP95] | P1 | marginal wrong-commit [CP95] | controls |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for tp, r in s["targets"].items():
        tc = r["calibration_test_counts"] or {}
        print(f"| {tp} | {r['commit_p']} | {r['feasible']} | {tc.get('commits', 0)} / {tc.get('wrong', 0)} | "
              f"{r['commits']} / {r['n']} | {f(r['commit_rate'])} | {r['wrong']} | {f(r['precision'])} "
              f"{iv(r['precision_cp95'])} | {r['p1_pass'] if r['p1_pass'] is not None else 'vacuous'} | "
              f"{f(r['wrong_commit_rate'])} {iv(r['wrong_commit_cp95'])} | "
              f"{'PASS' if r['controls_pass'] else 'FAIL'} |")
    for key, title in (("resampling", "with min_commit_p = P14-03 threshold (plan)"),
                       ("resampling_unconstrained", "no min_commit_p (extra diagnostic, not in the plan)")):
        print(f"\nResampling, {title}:\n")
        print("| target | feasible draws | violations | violation rate | limit (0.1 + 3 SE) | pass | mean pop. precision "
              "| mean commit rate |")
        print("|---|---|---|---|---|---|---|---|")
        for tp, r in s[key].items():
            print(f"| {tp} | {r['feasible']} / {r['draws']} | {r['violations']} | {f(r['violation_rate'])} | "
                  f"{f(r['limit'])} | {r['pass'] if r['pass'] is not None else 'n/a (< 50 feasible)'} | "
                  f"{f(r['mean_population_precision'])} | {f(r['mean_commit_rate'])} |")
    print("\nHeld-out precision curve (diagnostic, no guarantee):\n")
    print("| commit_p | " + " | ".join(str(c["commit_p"]) for c in b["held_out_curve"]) + " |")
    print("|---|" + "---|" * len(b["held_out_curve"]))
    print("| commits | " + " | ".join(str(c["commits"]) for c in b["held_out_curve"]) + " |")
    print("| precision | " + " | ".join(f(c["precision"], 3) for c in b["held_out_curve"]) + " |")
