"""Build the M1-C run table (markdown) and example decodes from the run and stream folders.

    python summarize.py m1c-r0-baseline m1c-r1-small ...  > results/table.md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RUNS = Path("C:/Users/zhang/bci-data/runs")
STREAMS = Path("C:/Users/zhang/bci-data/streams")


def _t(line: str) -> datetime:
    return datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")


def run_row(name: str) -> dict:
    rd = RUNS / name
    st = json.loads((rd / "status.json").read_text())
    log = (rd / "train.log").read_text(encoding="utf-8").splitlines()
    stamped = [ln for ln in log if ln.startswith("[")]
    minutes = (_t(stamped[-1]) - _t(stamped[0])).total_seconds() / 60
    recs = [json.loads(line) for line in (rd / "metrics.jsonl").read_text().splitlines()]
    setup = [r for r in recs if r["type"] == "setup"][-1]
    ep = [r for r in recs if r["type"] == "epoch"]
    best = next((r for r in ep if r["epoch"] == st["best_epoch"]), {})
    row = {"run": name, "params": setup["params"]["total"], "status": st["status"], "epochs": st["epoch"],
           "best_epoch": st["best_epoch"], "minutes": minutes, "val_key_acc_best_ep": best.get("val_key_acc"),
           "val_key_acc_max": max((r["val_key_acc"] for r in ep if "val_key_acc" in r), default=None)}
    mpath = STREAMS / name / "metrics.json"
    if mpath.exists():
        m = json.loads(mpath.read_text())
        for sp, v in m["splits"].items():
            row[sp] = v
    return row


def fmt(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def main(names: list[str]) -> None:
    rows = [run_row(n) for n in names]
    print("| Run | Params | Epochs (best) | Min | Split | CER tgt real | shuffled | zeros | Gap shuf-real [95% CI] |"
          " CER typed real | WER tgt | Key acc real / shuf (conv, conformer) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        for sp in ("val", "test"):
            v = r.get(sp)
            if not v:
                continue
            c = v.get("meg_control", {})
            g = v.get("meg_control_gap", {}).get("cer_target", {})
            ms = v["mean_over_sentences"]
            kr, ks = c.get("real", {}), c.get("shuffled", {})
            key = "-"
            if "key_acc_conv" in kr or "key_acc_conformer" in kr:
                key = (f"{fmt(kr.get('key_acc_conv'))}/{fmt(ks.get('key_acc_conv'))}, "
                       f"{fmt(kr.get('key_acc_conformer'))}/{fmt(ks.get('key_acc_conformer'))}")
            gap = f"{g['mean']:+.3f} [{g['ci95_lo']:+.3f}, {g['ci95_hi']:+.3f}]" if g else "-"
            print(f"| {r['run'].replace('m1c-', '')} | {r['params'] / 1e6:.2f}M | {r['epochs']} ({r['best_epoch']}) |"
                  f" {r['minutes']:.0f} | {sp} | {fmt(ms['cer_target'])} | {fmt(c.get('shuffled', {}).get('cer_target'))} |"
                  f" {fmt(c.get('zeros', {}).get('cer_target'))} | {gap} | {fmt(ms['cer_typed'])} |"
                  f" {fmt(ms['wer_target'])} | {key} |")
    print()
    print("Mean over subjects (CER target / typed), keystroke head on true key times, status:")
    print()
    for r in rows:
        parts = [f"- {r['run']}: status {r['status']}"]
        for sp in ("val", "test"):
            v = r.get(sp)
            if v:
                mo = v["mean_over_subjects"]
                parts.append(f"{sp} {mo['cer_target']:.3f}/{mo['cer_typed']:.3f}")
                kh = v.get("keystroke_head")
                if kh:
                    parts.append(f"{sp} key acc " + ", ".join(f"{k[4:]} {kh[k]:.3f}" for k in kh if k.startswith("acc_"))
                                 + f" (majority {kh['majority_class_acc']:.3f}, n {kh['n']})")
        print("; ".join(parts))
    print()
    for r in rows:
        f = STREAMS / r["run"] / "per_sentence_test.jsonl"
        if not f.exists():
            continue
        sent = sorted((json.loads(x) for x in f.read_text().splitlines()), key=lambda s: s["cer_target"])
        pick = [sent[0], sent[len(sent) // 4], sent[len(sent) // 2], sent[3 * len(sent) // 4]]
        print(f"Examples {r['run']} (test; best, p25, median, p75 by CER target):")
        print()
        print("| CER | Subject | Target | Greedy CTC |")
        print("|---|---|---|---|")
        for s in pick:
            print(f"| {s['cer_target']:.2f} | {s['subject']} | {s['target_text']} | {s['hyp']} |")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
