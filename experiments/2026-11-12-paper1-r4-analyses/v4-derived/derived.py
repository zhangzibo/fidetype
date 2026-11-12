"""v4-derived: small numbers used in draft v4 that no committed file holds yet.

1. Worked example for the selective bound (editor minor 13): one-sided exact
   (Clopper-Pearson) 90 % upper bounds on the error among commits for 0/40 and
   3/40 calibration commits (level delta = 0.1, as in LTT-sel without the grid
   correction), and with the Bonferroni level delta/20 used by LTT-sel.
2. MEG seed gaps to the shuffled control (editor minor 12), from the committed
   seed numbers (Tab. S3 of v3 / R3 MEG seeds): greedy CER seed s minus shuffled seed s.
3. Share of always-commit eWPM kept by the guaranteed rule on the published
   gate, fixed split A (Tab. 1): 18.65 / 19.61, from the committed unified-CI
   and deployable-rule files.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/v4-derived/derived.py
"""

from __future__ import annotations

import json
from pathlib import Path

from scipy.stats import beta

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
R3 = REPO / "experiments/2026-11-12-paper1-r3-analyses"


def cp_upper(k: int, n: int, level: float) -> float:
    """One-sided exact upper bound with coverage 1 - level."""
    return 1.0 if k >= n else float(beta.ppf(1 - level, k + 1, n - k))


def main() -> None:
    out: dict = {"description": __doc__.strip().splitlines()[0]}
    out["selective_bound_examples"] = {
        f"{k}/40": {"one_sided_upper_90": cp_upper(k, 40, 0.1), "one_sided_upper_bonferroni_delta_over_20": cp_upper(k, 40, 0.1 / 20)}
        for k in (0, 3)}
    # MEG seeds: values as printed in the committed R3 seed table (greedy CER, shuffled greedy CER)
    seeds = {"0": (0.506, 0.760), "1": (0.502, 0.745), "2": (0.592, 0.732)}
    out["meg_seed_gap_to_shuffled_greedy"] = {s: round(sh - g, 3) for s, (g, sh) in seeds.items()}
    base = json.loads((R3 / "unified-ci/results/ci.json").read_text(encoding="utf-8"))["table2_baselines"]["b2t-published"]["point"]
    dep = json.loads((R3 / "deployable-rule/results/deployable.json").read_text(encoding="utf-8"))["rows"]
    a = dep["b2t-published/split A"]["point"]["LTT max-rule (clean)"]["ewpm"]
    c = base["always_commit"]["ewpm"]
    out["published_guaranteed_A_share_of_always_commit_ewpm"] = {"guaranteed_A": a, "always_commit": c, "share": a / c}
    (HERE / "results" / "derived.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
