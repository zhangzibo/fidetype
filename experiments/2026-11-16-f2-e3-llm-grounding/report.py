"""P15-05 report: arm table, paired bootstrap against A0, and the pre-registered checks (plan.md).

    .venv\\Scripts\\python.exe -I experiments/2026-11-16-f2-e3-llm-grounding/report.py t15
Reads results/results-<set>.json and the per-trial top-1 texts in the derived folder (truths are re-read from the
same read-only inputs). Writes results/summary-<set>.json (aggregates only) and prints a markdown table.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def held_texts(R, name: str) -> list[str]:
    """Held-out truths in the run order (as run.data_t15), without loading logits or decoders."""
    import numpy as np

    if name == "t15":
        d_in = R.DER / "m4-01-02-lookahead"
        texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
        sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
        order = {s: j for j, s in enumerate(sessions)}
        with np.load(d_in / "logprobs-m4-12-fixed0.npz") as z:  # keys only; arrays are not read
            keys = sorted((k for k in z.files if "|val_eval|" in k),
                          key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
        return [" ".join(texts[k.split("|")[0]][k.split("|")[1]][int(k.split("|")[2])].split()) for k in keys]
    _, (_, ht, _), _ = R.data_t12()
    return ht


def fmt(v, f: str = ".4f") -> str:
    return "-" if v is None else format(v, f)


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "t15"
    spec = importlib.util.spec_from_file_location("f2e3run", HERE / "run.py")
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    res = json.loads((R.OUT / f"results-{name}.json").read_text(encoding="utf-8"))
    ht = held_texts(R, name)
    tops = {a: json.loads((R.OWN / f"trials-{name}-{a}.json").read_text(encoding="utf-8"))["tops"]
            for a in res["arms"]}
    cfg = res["config"]
    rows = {}
    for a, r in res["arms"].items():
        c = r.get("controls_held_out", {})
        rows[a] = {
            "status": r["status"], "wer": r["wer"], "sentence_acc": r["sentence_acc"],
            "commits": r.get("n_commit"), "wrong": r.get("n_wrong_commit"), "wrong_rate": r.get("wrong_commit_rate"),
            "wrong_cp95": r.get("wrong_commit_cp95"), "offers": (r.get("actions") or {}).get("offer"),
            "withholds": (r.get("actions") or {}).get("withhold"), "hallucination_rate": r.get("hallucination_rate"),
            "unsupported_words": r.get("unsupported_words"), "shown_words": r.get("shown_words"),
            "fluent_wrong_commits": r.get("fluent_wrong_commits"),
            "sheet_controls": [(x["name"], x["n_commit"], x["allowed"], x["passed"]) for x in r.get("sheet", {}).get("controls", [])],
            "uniform": c.get("uniform", {}).get("commits"), "shuffled": c.get("shuffled", {}).get("commits"),
            "swapped_commits": c.get("swapped", {}).get("commits"),
            "swapped_unsupported": c.get("swapped", {}).get("commits_not_truth_of_signal"),
            "swapped_leak": c.get("swapped", {}).get("commits_equal_truth_of_language_trial"),
            "top1_changed_vs_base": r.get("top1_changed_vs_base"), "stats": r.get("stats"),
            "frame_temperature": r.get("frame_temperature"),
        }
        if a != "A0_ngram" and "A0_ngram" in tops:
            rows[a]["wer_diff_vs_A0"] = R.paired_bootstrap(ht, tops["A0_ngram"], tops[a], cfg["bootstrap_B"], cfg["seed"])

    def checks(a: str) -> dict:
        r, b = rows[a], rows["A0_ngram"]
        s1 = r["wer"] < b["wer"] and r["wer_diff_vs_A0"]["ci95"][1] < 0
        s2 = r["status"] == "ok" and r["wrong_rate"] is not None and r["wrong_rate"] <= cfg["alpha"]
        s3 = (r["status"] == "ok" and r["uniform"] <= cfg["null_max_commits"] and r["shuffled"] <= cfg["null_max_commits"]
              and r["swapped_unsupported"] <= cfg["swapped_max_commits"])
        s4 = (r["status"] == "ok" and r["hallucination_rate"] <= b["hallucination_rate"]
              and r["fluent_wrong_commits"] <= b["fluent_wrong_commits"])
        return {"S1_accuracy": bool(s1), "S2_bound": bool(s2), "S3_controls": bool(s3), "S4_hallucination": bool(s4),
                "all": bool(s1 and s2 and s3 and s4)}

    out = {"set": name, "prep": res.get("prep"), "ground_prep": res.get("ground_prep"), "arms": rows,
           "checks": {a: checks(a) for a in ("B1_rescore_G", "C1_rewrite_G") if a in rows and "A0_ngram" in rows}}
    (R.OUT / f"summary-{name}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("| arm | WER | sent. acc | dWER vs A0 [95 %] | commits | wrong | wrong rate [CP95] | offers | halluc. rate "
          "(unsup./shown) | fluent-wrong | uniform | shuffled | swapped commits (unsupported) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for a, r in rows.items():
        d = r.get("wer_diff_vs_A0")
        ds = f"{d['diff']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]" if d else "-"
        cpi = r["wrong_cp95"] or [None, None]
        print(f"| {a} | {r['wer']:.4f} | {r['sentence_acc']:.3f} | {ds} | {r['commits']} | {r['wrong']} | "
              f"{fmt(r['wrong_rate'])} [{fmt(cpi[0])}, {fmt(cpi[1])}] | {r['offers']} | {fmt(r['hallucination_rate'])} "
              f"({r['unsupported_words']}/{r['shown_words']}) | {r['fluent_wrong_commits']} | {r['uniform']}/300 | "
              f"{r['shuffled']}/300 | {r['swapped_commits']} ({r['swapped_unsupported']}) |")
    print(json.dumps(out["checks"], indent=1))


if __name__ == "__main__":
    main()
