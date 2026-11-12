"""Draft v3 (M3-18): small derived numbers from committed R3 files (CPU, seconds).

Inputs (committed): ../repeated-splits/results/per_split.json
Output: results/v3_derived.json, results/tables.md

1. Speed cost of the guaranteed rule. Per repeated split (R = 50), paired eWPM difference
   between a rule and the same fit-A policy with commits switched off (lambda = +inf; the
   beta = 0.05 selective controllers commit nothing in every split, so their eWPM row is this
   no-commit policy). Mean, 5th / 95th percentile, share of splits > 0.
2. Paired eWPM difference LTT max-rule - CRC max-rule and LTT max-rule - plug-in per split.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PS = json.loads((HERE.parent / "repeated-splits/results/per_split.json").read_text(encoding="utf-8"))
RULES = ["plug-in (fit-A)", "CRC pure (clean)", "CRC max-rule (clean)", "LTT pure (clean)", "LTT max-rule (clean)"]


def summ(x: np.ndarray) -> dict:
    return {"mean": float(np.mean(x)), "p05": float(np.percentile(x, 5)), "p95": float(np.percentile(x, 95)),
            "share_pos": float(np.mean(x > 0)), "n": int(x.size)}


out: dict = {}
lines = ["# Draft v3 derived numbers (from repeated-splits/per_split.json)", "",
         "Paired eWPM per split (R = 50). 'no commit' = the same fit-A policy with lambda = +inf "
         "(the eWPM of the beta = 0.05 selective controllers, which never commit).", "",
         "| condition | difference | mean [p05, p95] | share of splits > 0 |", "|---|---|---|---|"]
for cond in ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession"):
    splits = PS[cond]
    nocommit = np.array([s["selective"]["0.05"]["SGR"]["ewpm"] for s in splits])
    assert all(s["selective"]["0.05"]["SGR"]["n_commit"] == 0 for s in splits)
    res = {}
    for r in RULES:
        e = np.array([s["test"][r]["ewpm"] for s in splits])
        res[f"{r} - no commit"] = summ(e - nocommit)
    ltt = np.array([s["test"]["LTT max-rule (clean)"]["ewpm"] for s in splits])
    for r in ("CRC max-rule (clean)", "plug-in (fit-A)"):
        e = np.array([s["test"][r]["ewpm"] for s in splits])
        res[f"LTT max-rule (clean) - {r}"] = summ(ltt - e)
    res["no commit eWPM mean"] = float(nocommit.mean())
    out[cond] = res
    for k, v in res.items():
        if isinstance(v, dict):
            lines.append(f"| {cond} | {k} | {v['mean']:+.3f} [{v['p05']:+.3f}, {v['p95']:+.3f}] | {v['share_pos']:.2f} |")
(HERE / "results/v3_derived.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
(HERE / "results/tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
