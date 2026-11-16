"""P15-06 report: arm table against the matching P15-05 arm, and the pre-registered checks (plan.md).

    .venv\\Scripts\\python.exe -I experiments/2026-11-16-p15-06-halluc-bound/report.py
Reads results/results-t15.json, the P15-05 results, and the per-trial top-1 texts of both runs (derived folders,
read only). Writes results/summary-t15.json (aggregates only) and prints markdown tables.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DER = Path("C:/Users/zhang/bci-data/derived")
SRC, OWN = DER / "f2-e3-llm-grounding", DER / "p15-06-halluc-bound"


def f(v, fmt=".4f"):
    return "-" if v is None else format(v, fmt)


def main() -> None:
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    res = json.loads((HERE / "results/results-t15.json").read_text(encoding="utf-8"))
    p5 = json.loads((REPO / cfg["p15_05_results"]).read_text(encoding="utf-8"))["arms"]
    alpha_h = cfg["halluc"]["alpha_h"]
    rows = {}
    print("| arm | rule | selected (commit_p, tau_commit, tau_word) | P15-05 commits / wrong / fluent-wrong | "
          "P15-06 commits / wrong / fluent-wrong | blocked by gate | fluent-wrong rate [CP95] | wrong-commit rate "
          "[CP95] | uniform | shuffled | swapped (not truth / = lang. truth) | P15-05 swapped | WER | top-1 = P15-05 |")
    print("|" + "---|" * 15)
    for name, r in res["arms"].items():
        if r.get("status") != "ok":
            print(f"| {name} | refused |")
            continue
        a = r["p15_05_arm"]
        q = p5[a]
        h = r["sheet"]["halluc"]
        sel = h["selected"]
        c = r["controls_held_out"]
        qc = q["controls_held_out"]["swapped"]
        fn = name.replace("@", "-")
        tops = json.loads((OWN / f"trials-{fn}.json").read_text(encoding="utf-8"))["tops"]
        tops5 = json.loads((SRC / f"trials-t15-{a}.json").read_text(encoding="utf-8"))["tops"]
        same = sum(x == y for x, y in zip(tops, tops5))
        right5 = q["n_commit"] - q["n_wrong_commit"]
        right6 = r["n_commit"] - r["n_wrong_commit"]
        rows[name] = {
            "p15_05_arm": a, "select": r["select"], "selected": sel, "feasible": h["feasible"],
            "n_certified": h["n_certified"], "n_tested": h["n_tested"], "chain_length": h["chain_length"],
            "base_commit_p": h["base_commit_p"], "base_config_matches_p15_05": r["base_config_matches_p15_05"],
            "in_sample_order": h["order_counts"], "in_sample_test": h["test_counts"],
            "p15_05": {"commits": q["n_commit"], "wrong": q["n_wrong_commit"], "right": right5,
                       "fluent_wrong": q["fluent_wrong_commits"], "swapped_not_truth": qc["commits_not_truth_of_signal"]},
            "p15_06": {"commits": r["n_commit"], "wrong": r["n_wrong_commit"], "right": right6,
                       "fluent_wrong": r["fluent_wrong_commits"], "blocked": r["halluc_gate_blocked"],
                       "fluent_wrong_rate": r["fluent_wrong_rate"], "fluent_wrong_cp95": r["fluent_wrong_cp95"],
                       "wrong_rate": r["wrong_commit_rate"], "wrong_cp95": r["wrong_commit_cp95"],
                       "uniform": c["uniform"]["commits"], "shuffled": c["shuffled"]["commits"],
                       "swapped": c["swapped"], "wer": r["wer"], "sentence_acc": r["sentence_acc"],
                       "hallucination_rate": r["hallucination_rate"], "unsupported_committed_words":
                           r["unsupported_committed_words"]},
            "top1_equal_p15_05": same, "n": len(tops),
            "controls_final": [(x["name"], x["n_commit"], x["allowed"], x["passed"]) for x in r["sheet"]["controls"]],
            "cache": r.get("cache"), "seconds": r.get("seconds"),
        }
        print(f"| {name} | {r['select']} | ({sel['commit_p']}, {sel['tau_commit']}, {sel['tau_word']}) | "
              f"{q['n_commit']} / {q['n_wrong_commit']} / {q['fluent_wrong_commits']} | "
              f"{r['n_commit']} / {r['n_wrong_commit']} / {r['fluent_wrong_commits']} | {r['halluc_gate_blocked']} | "
              f"{f(r['fluent_wrong_rate'])} [{f(r['fluent_wrong_cp95'][0])}, {f(r['fluent_wrong_cp95'][1])}] | "
              f"{f(r['wrong_commit_rate'])} [{f(r['wrong_commit_cp95'][0])}, {f(r['wrong_commit_cp95'][1])}] | "
              f"{c['uniform']['commits']}/300 | {c['shuffled']['commits']}/300 | "
              f"{c['swapped']['commits_not_truth_of_signal']} / {c['swapped']['commits_equal_truth_of_language_trial']}"
              f" | {qc['commits_not_truth_of_signal']} | {f(r['wer'])} | {same}/{len(tops)} |")
    checks = {}
    b = rows.get("B1_rescore_G")
    if b:
        a0 = p5["A0_ngram"]
        p6 = b["p15_06"]
        checks = {
            "H1_bound": bool(b["feasible"] and p6["fluent_wrong_rate"] <= alpha_h and p6["wrong_rate"] <= 0.05),
            "H2_fluent_wrong_le_A0": p6["fluent_wrong"] <= a0["fluent_wrong_commits"],
            "H3_controls": bool(p6["uniform"] <= 1 and p6["shuffled"] <= 1
                                and p6["swapped"]["commits_not_truth_of_signal"] <= 2
                                and all(x[3] for x in b["controls_final"])),
            "H4_wer_kept": b["top1_equal_p15_05"] == b["n"],
            "utility_right_commits": {"p15_06": p6["right"], "p15_05": b["p15_05"]["right"],
                                      "kept_half": p6["right"] >= b["p15_05"]["right"] / 2},
        }
        checks["P15_06_pass"] = all(checks[k] for k in ("H1_bound", "H2_fluent_wrong_le_A0", "H3_controls",
                                                        "H4_wer_kept"))
        print("\nchecks (B1, primary):", json.dumps(checks))
    out = {"set": "t15", "alpha_h": alpha_h, "delta_h": cfg["halluc"]["delta_h"], "arms": rows, "checks_B1": checks}
    (HERE / "results/summary-t15.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
