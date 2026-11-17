"""Write the P6-01 side-job results into the v0.1 result entries, then rebuild the static board (not published).

- Toronto CRC entries: the ``safe_wpm`` block from exact per-trial decisions (``results/toronto-safe-wpm.json``).
- B2T '25 and SpanishBCBL CRC / LTT entries: ``controls.null_commit`` from the null audit at the entry's own
  threshold (``results/null-audit-b2t.json``, ``results/null-audit-meg.json``). The zero-input stand-in is the
  same as in the v0.1 trust entries: uniform logits (B2T), zeros MEG input (MEG).

Run (repo root): ``.venv\\Scripts\\python.exe -I experiments/2026-11-16-p6-01-tracks/update_results.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.leaderboard import build  # noqa: E402
from fidetype.benchmark.safe_wpm import summarize_controls  # noqa: E402

RES = REPO / "benchmark" / "results" / "v0.1"
NULL_MAX = 0.05
NULL_COND = {"b2t25": ("uniform", "uniform logits stand in for zeros input"), "spanishbcbl": ("zeros_meg", "zeros MEG input")}


def rw(stem: str, fn) -> None:
    p = RES / f"{stem}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    fn(d)
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    changed = []
    tp = HERE / "results" / "toronto-safe-wpm.json"
    if tp.exists():
        tor = json.loads(tp.read_text(encoding="utf-8"))
        for cond, r in tor["conditions"].items():
            if not r["same_as_committed"]:
                print(f"toronto {cond}: rerun differs from the committed aggregates; not written")
                continue

            def put(d, blk=r["safe_wpm"]):
                d["safe_wpm"] = blk

            stem = f"toronto-semg-composed__cnn-{cond}__crc"
            rw(stem, put)
            changed.append(stem)
    for name in ("b2t", "meg"):
        p = HERE / "results" / f"null-audit-{name}.json"
        if not p.exists():
            continue
        aud = json.loads(p.read_text(encoding="utf-8"))
        for stem, e in aud["entries"].items():
            ok = e.get("real_scores_match_m2_13", e.get("real_scores_match_items"))
            if not ok:
                print(f"{stem}: real-input scores do not match the committed items; not written")
                continue
            cond, label = NULL_COND[stem.split("-")[0]]
            a = e["audit"]
            rate = a[cond]["commit_rate"]
            others = ", ".join(f"{c} {v['commits']}/{v['n']}" for c, v in a.items() if c != "real")
            blk = {"status": "pass" if rate <= NULL_MAX else "fail", "commit_rate_zeros": rate,
                   "commit_rate_zeros_cp95": a[cond]["commit_rate_cp95"],
                   "basis": f"P6-01 null audit at this entry's threshold ({e['method'].upper()} lambda "
                            f"{e['threshold']:.4f}), {label}, n={a[cond]['n']}; commits per null input: {others}"}

            def put(d, blk=blk):
                c = d["controls"]
                c["null_commit"] = blk
                c["passed"] = all((c.get(k) or {}).get("status") == "pass" for k in ("shuffled", "zeros", "null_commit"))
                if "safe_wpm" in d:
                    d["safe_wpm"]["controls"] = summarize_controls(c)

            rw(stem, put)
            changed.append(stem)
    info = build(RES, REPO / "benchmark" / "site")
    print("updated:", *changed, sep="\n  ")
    print("leaderboard rebuilt:", info)


if __name__ == "__main__":
    main()
