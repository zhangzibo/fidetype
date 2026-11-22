"""P4-22 converter: write real decoder output as CSV / JSON Lines n-best files (see plan.md).

No tool on this machine writes these file forms. This script copies real decoder output into them.
It changes no text and no number. It writes only to ``<bci-data>/derived/p4-22``.

R1: ``decoded_sentence`` of the 1,718 copy-task trials in ``t15_copyTask.pkl`` (Card et al. 2024
    online decoder; the file is checked against the Dryad SHA-256).
R2: the n-best lists of the 816 M4-06 hypothesis streams (``streams/hyp-ours``).

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-22-p4-22-nbest-readers/convert.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.adapters.b2t25 import load_copytask  # noqa: E402

DATA = Path.home() / "bci-data"
PKL = DATA / "brain-to-text-25" / "t15_copyTask.pkl"
HYP = DATA / "derived" / "m4-06-real-replay" / "streams" / "hyp-ours"
OUT = DATA / "derived" / "p4-22"


def r1_rows() -> list[tuple[str, str]]:
    return [(f"copytask-{t.index:04d}", t.decoded_sentence) for t in load_copytask(PKL, verify=True)]


def r2_records() -> list[dict]:
    recs = []
    for f in sorted(HYP.glob("trial-*.jsonl")):
        evs = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
        hyps = [e for e in evs if e.get("type") == "hypothesis"]
        assert len(hyps) == 1, f
        h = hyps[0]
        rec = {"id": f.stem, "nbest": h["nbest"]}
        for k in ("t_start", "t_end"):
            if h.get(k) is not None:
                rec[k] = h[k]
        recs.append(rec)
    return recs


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = r1_rows()
    with open(OUT / "r1-online-1best.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "text"])
        w.writerows(rows)
    with open(OUT / "r1-online-1best.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for i, t in rows:
            fh.write(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n")
    recs = r2_records()
    with open(OUT / "r2-ours-nbest.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "text", "score"])
        for r in recs:
            for it in r["nbest"]:
                w.writerow([r["id"], it["text"], repr(float(it["score"]))])
    with open(OUT / "r2-ours-nbest.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"R1 {len(rows)} trials; R2 {len(recs)} trials, {sum(len(r['nbest']) for r in recs)} items -> {OUT}")


if __name__ == "__main__":
    main()
