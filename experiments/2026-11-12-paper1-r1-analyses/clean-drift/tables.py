"""Write clean-drift/results/tables.md from the JSON files (run after run.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common as C  # noqa: E402

f = C.fmt


def block(key: str, r: dict) -> list[str]:
    off, ci = r["offline"]["test"], r["offline"]["test_ci"]["policies"]
    cal = r["offline"]["calibration_set_rate"]
    on = r["online"]["drift"]["online"]
    sh = r["online"]["shuffled"]
    ex = r["exchangeable_reference"]
    L = [f"### {key}", "",
         "Sizes: " + ", ".join(f"{k} {v}" for k, v in r.items() if k.startswith("n_")) +
         f". Frame T {f(r['fit_report'].get('temperature_frame'), 2)}, sentence T {f(r['fit_report'].get('temperature_sentence'), 2)}.", "",
         "| method | λ | test wrong-commit [CI] | commit rate | error among commits | eWPM [CI] | rate on its own calibration data | shuffled order (mean of 20) |",
         "|---|---|---|---|---|---|---|---|"]
    shmap = {"plug-in gate (fit-A)": "old", "CRC (clean cal)": "crc", "LTT (clean cal)": "ltt"}
    for k, m in off.items():
        lam = r["offline"]["thresholds"][k]
        L.append(f"| offline {k} | {f(C.fnum(lam), 4)} | {f(m['wrong_commit'], 4)} {C.fci(ci[k]['wrong_commit'], 4)} | {f(m['commit_rate'])} | "
                 f"{f(m['error_among_commits'])} | {f(m['ewpm'], 3)} {C.fci(ci[k]['ewpm'], 2)} | {f(cal[k]['wrong_commit'], 4)} | "
                 f"{f(sh[shmap[k]]['wrong_commit'], 4)} |")
    for k, m in on.items():
        rep = m.get("report", {})
        note = ""
        if rep.get("certificate") is not None:
            note = f" (certificate {f(rep['certificate'], 4)}" + (f", a-priori bound {f(rep['prior_bound'], 4)}" if rep.get("prior_bound") is not None else "") + ")"
        base = k.split("@")[0]
        shv = sh.get(base, {}).get("wrong_commit") if k.endswith("@d0") else None
        L.append(f"| online {k}{note} | — | {f(m['wrong_commit'], 4)} | {f(m['commit_rate'])} | — | {f(m['ewpm'], 3)} | — | {f(shv, 4)} |")
    old = r.get("old_reused_data_offline")
    L += ["", f"Exchangeable reference (pool calibration + test, {ex['reps']} random splits of the same sizes, CRC on one part): "
               f"test rate mean {f(ex['mean'], 4)} [p05 {f(ex['p05'], 4)}, p95 {f(ex['p95'], 4)}], share > α {f(ex['share_gt_alpha'], 2)}; "
               f"observed clean CRC {f(ex['observed'], 4)}, one-sided p (random split >= observed) {f(ex['p_value_ge_observed'], 3)}.",
          f"Random splits inside the clean test half ({r['within_test_random_splits']['n_cal']} cal): CRC mean "
          f"{f(r['within_test_random_splits']['crc_mean'], 4)}, p95 {f(r['within_test_random_splits']['crc_p95'], 4)}."]
    if old:
        L.append("Old (reused-data) baseline, M2-16: " + "; ".join(f"{k} {f(v['wrong_commit'], 4)}" for k, v in old.items()) + ".")
    L.append("")
    return L


def main() -> None:
    L = ["# Clean drift baseline: generated tables", "",
         "α = 0.05, δ = 0.1. CI: B2T day clusters (14), sEMG participant clusters (19); 95 % percentile bootstrap, B = 2000. "
         "Online methods: warm start on the clean calibration items, test items in order (B2T: file order inside each day, days ascending; "
         "sEMG: participant by participant), delay 0 and 10.", ""]
    for name in ("clean_drift_b2t.json", "clean_drift_emg.json"):
        p = HERE / "results" / name
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if "order_check" in d:
            oc = d["order_check"]
            L += ["## B2T '25 order check", "",
                  f"Pickle keys: {', '.join(oc['keys'])}. Keys that could hold time or order: {oc['time_like_keys'] or 'none'}. "
                  f"Days are contiguous in file order: {oc['days_contiguous']}; ascending: {oc['days_ascending']}. "
                  "So the only order information is the file order inside each post-implant day.", ""]
        for k, r in d.items():
            if k == "order_check":
                continue
            L += block(k, r)
    (HERE / "results" / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
