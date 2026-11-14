"""M3-02 repeated-split rows (B2T R 200) from a rebuilt split-table folder vs the committed splits.json.

Usage (repo root): python -I m302_rows.py REBUILT_DIR
r < 50 guard-on tables still come from the R3 cache (the rebuild covers r 50-199 guard on, r 0-199 guard off).
"""
import json
import sys
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO / "experiments/2026-11-14-m3-01-02-ablations"))
import abl as A  # noqa: E402

Q = A.Q
ref = json.loads((REPO / "experiments/2026-11-14-m3-01-02-ablations/results/splits.json").read_text(encoding="utf-8"))
out = {}
for label, tab in (("cache", Q.TAB4), ("rebuilt", Path(sys.argv[1]))):
    Q.TAB4 = tab
    out[label] = {c: A.split_arm_outcomes(c, 200) for c in ("b2t-ours", "b2t-published")}
for c in ("b2t-ours", "b2t-published"):
    a = json.dumps(out["rebuilt"][c], sort_keys=True)
    b = json.dumps(ref[c], sort_keys=True)
    k = json.dumps(out["cache"][c], sort_keys=True)
    v4 = out["rebuilt"][c]["v4 (baseline)"]
    print(c, "rebuilt == committed splits.json:", a == b, "| cache == committed:", k == b,
          "| v4 row: mean %.4f share>alpha %.3f" % (v4["wrong_commit_mean"], v4["share_gt_alpha"]), "R", out["rebuilt"][c]["R"])
