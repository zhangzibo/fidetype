"""P14-04: score a `fidetype live --json` run on a KT-sEMG LSL replay against the replay's truth file.

Usage (paths are local; outputs hold aggregates only, no text):

    python experiments/2026-11-16-p14-04-live/score_kt.py DECISIONS.jsonl TRUTH.json [--out SCORE.json]

DECISIONS.jsonl: the stdout of `fidetype live --json` (one decision per line, in segment order).
TRUTH.json: written by `fidetype live replay-kt --truth` (texts of the sent segments; local only).
Decisions and segments are matched in order; the script checks that the counts are equal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fidetype.demo.live.keys import normalize
from fidetype.utils.binomial import clopper_pearson


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions")
    ap.add_argument("truth")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    dec = [json.loads(x) for x in Path(a.decisions).read_text(encoding="utf-8").splitlines() if x.strip()]
    tr = json.loads(Path(a.truth).read_text(encoding="utf-8"))["segments"]
    if len(dec) != len(tr):
        print(f"count mismatch: {len(dec)} decisions, {len(tr)} segments", file=sys.stderr)
    n = min(len(dec), len(tr))
    out = {"commit-correct": 0, "commit-wrong": 0, "offer-hit": 0, "offer-miss": 0, "withhold": 0}
    top1 = 0
    for d, t in zip(dec[:n], tr[:n]):
        truth = normalize(t["text"])
        ch = [normalize(c) for c in d.get("choices") or []]
        if ch and ch[0] == truth:
            top1 += 1
        if d["action"] == "commit":
            out["commit-correct" if normalize(d.get("text") or "") == truth else "commit-wrong"] += 1
        elif d["action"] == "offer":
            out["offer-hit" if truth in ch else "offer-miss"] += 1
        else:
            out["withhold"] += 1
    lo, hi = clopper_pearson(out["commit-wrong"], n, 0.95) if n else (0.0, 1.0)
    res = {"segments": n, "decisions": len(dec), "truth_segments": len(tr), "outcomes": out,
           "top1_exact_shown": top1, "wrong_commit_rate": round(out["commit-wrong"] / n, 4) if n else None,
           "wrong_commit_cp95": [round(lo, 4), round(hi, 4)]}
    print(json.dumps(res, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
