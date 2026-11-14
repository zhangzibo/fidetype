"""M2-18: count empty and short top-1 texts in the Paper 1 per-temperature decode caches.

The Paper 1 round-3/4 analyses decoded every Brain-to-Text '25 (T15) trial and every
sEMG sentence at each snapped frame temperature that a split used. The caches live
outside the repo (C:/Users/zhang/bci-data/cache/paper1-r3, paper1-r4). Each file holds
the n-best lists of the REAL trials at one temperature (control streams were decoded into
other cache files). If no real trial has an empty top-1 at any temperature, no Paper 1
number on real trials can contain an empty commit, whatever the fitted commit_max_risk.

Writes results/cache-scan.json (counts only). Run (repo root):
  .venv\Scripts\python.exe -I experiments/2026-11-13-m2-18-empty-commits/scan_caches.py
"""

from __future__ import annotations

import json
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
CACHES = [Path("C:/Users/zhang/bci-data/cache/paper1-r3"), Path("C:/Users/zhang/bci-data/cache/paper1-r4")]


def main() -> None:
    out: dict = defaultdict(lambda: {"files": 0, "n": 0, "top1_empty": 0, "top1_1word": 0, "top1_le3chars": 0, "temps": []})
    for d in CACHES:
        for p in sorted(d.glob("decode-*-T*.pkl")):
            m = re.match(r"decode-(.+)-T([0-9.]+)\.pkl", p.name)
            fam = m.group(1)
            nbs = pickle.loads(p.read_bytes())
            o = out[fam]
            o["files"] += 1
            o["temps"].append(float(m.group(2)))
            for nb in nbs.values():
                top = nb.candidates[0].text if len(nb) else ""
                o["n"] += 1
                o["top1_empty"] += top.strip() == ""
                o["top1_1word"] += len(top.split()) == 1
                o["top1_le3chars"] += 0 < sum(not c.isspace() for c in top) <= 3
            print(p.parent.name, p.name, len(nbs), flush=True)
    res = {k: {**v, "temps": sorted(set(v["temps"]))} for k, v in out.items()}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "cache-scan.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for k, v in res.items():
        print(k, {kk: vv for kk, vv in v.items() if kk != "temps"})


if __name__ == "__main__":
    main()
