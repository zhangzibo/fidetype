"""P15-15: re-score the committed hallucination-benchmark outcomes under protocol 0.2 (plan: plan.md). CPU, seconds.

Inputs (flags only, no text): benchmark/results/halluc-v0.1/*.outcomes.json (P15-07) and any
benchmark/results/halluc-v0.2/*.outcomes.json (for example the M4-13 entries of add_m4_13.py).
Outputs: benchmark/results/halluc-v0.2/<stem>.card.json (protocol 0.2 cards) and results/results.json
(0.1 vs 0.2 verdict per entry, with the paired counts). The 0.1 cards are not touched.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p15-15-halluc-0.2/rescore.py
Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark import hallucination as HB  # noqa: E402

V01 = REPO / "benchmark/results/halluc-v0.1"
V02 = REPO / "benchmark/results/halluc-v0.2"
OUT = HERE / "results"
#: P15-07 cards were made with these point checks (run.py); keep them so the 0.2 cards carry the same extras.
ALPHA_WRONG, ALPHA_FLUENT = 0.05, 0.01


def v01_verdict(card01: dict) -> str:
    return HB.PASS if card01["controls_passed"] else HB.FAIL


def main() -> int:
    V02.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    sources = [(p, "halluc-v0.1") for p in sorted(V01.glob("*.outcomes.json"))]
    sources += [(p, "halluc-v0.2") for p in sorted(V02.glob("*.outcomes.json"))]
    rows = []
    for path, where in sources:
        oc = json.loads(path.read_text(encoding="utf-8"))
        stem = path.name[: -len(".outcomes.json")]
        c01 = HB.score_outcomes(oc, protocol="0.1", alpha_wrong=ALPHA_WRONG, alpha_fluent=ALPHA_FLUENT)
        ref01 = path.with_name(stem + ".card.json")
        if where == "halluc-v0.1":  # the 0.1 path must still give the committed card
            assert json.loads(json.dumps(c01)) == json.loads(ref01.read_text(encoding="utf-8")), f"0.1 drift: {stem}"
        c02 = HB.score_outcomes(oc, alpha_wrong=ALPHA_WRONG, alpha_fluent=ALPHA_FLUENT)
        c02["meta"] = {**c02["meta"], "outcomes_file": f"benchmark/results/{where}/{path.name}"}
        (V02 / f"{stem}.card.json").write_text(json.dumps(c02, indent=1) + "\n", encoding="utf-8")
        sw01 = c01["tracks"]["swapped"]
        sw02 = c02["tracks"]["swapped"]
        pr = sw02.get("paired", {})
        row = {"entry": stem, "outcomes": f"{where}/{path.name}", "dataset": oc.get("dataset"),
               "system": oc.get("system"), "fluency": oc.get("fluency", {}).get("mode"),
               "v01": {"controls": v01_verdict(c01), "swapped_pass": sw01.get("pass")},
               "v02": {"controls": c02["controls_verdict"], "swapped": sw02.get("verdict"),
                       "null": c02["tracks"]["null"].get("verdict"),
                       "scrambled": c02["tracks"]["scrambled"].get("verdict")},
               "paired": {k: pr.get(k) for k in ("n", "n10", "n01", "n11", "m", "Y", "ratio_estimate",
                                                 "theta_upper", "theta_r", "n01_share_lower")},
               "summary_v02": HB.summary_line(c02)}
        row["changed"] = row["v01"]["controls"] != row["v02"]["controls"]
        rows.append(row)
        print(f"{stem}: 0.1 {row['v01']['controls']} -> 0.2 {row['v02']['controls']}"
              f"{'  CHANGED' if row['changed'] else ''}  |  {row['summary_v02']}")
    # check: both fluency modes of one system give the same swapped verdict (commit flags do not depend on fluency)
    by = {}
    for r in rows:
        by.setdefault((r["dataset"], r["system"]), set()).add(r["v02"]["swapped"])
    mismatch = [k for k, v in by.items() if len(v) > 1]
    res = {"task": "P15-15", "protocol": HB.PROTOCOL, "rules": {"swap_ratio_max": HB.SWAP_RATIO_MAX,
           "swap_alpha": HB.SWAP_ALPHA, "swap_m_min": HB.SWAP_M_MIN, "control_commit_max": HB.CONTROL_COMMIT_MAX},
           "n_entries": len(rows), "n_changed": sum(r["changed"] for r in rows),
           "fluency_mode_mismatch": [list(k) for k in mismatch], "entries": rows}
    (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} entries, {res['n_changed']} changed verdict; fluency-mode mismatches: {mismatch or 'none'}")
    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
