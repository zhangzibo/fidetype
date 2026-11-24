r"""Add the adopted safe-wpm/0.2 block to the committed leaderboard score cards (P14-61).

safe-wpm/0.2 (prefix credit + the aac-gaze-v1 reading cost) is the headline metric since 2026-11-22. New cards get
the ``safe_wpm_v02`` block from the scorer itself. This tool adds it to the cards that existed before: for each
card with a ``rescore`` recipe it scores the local submission again with the recorded settings (B, seed), the
same as ``python -m fidetype.benchmark.hub rescore``, and then:

- checks that the fresh ``safe_wpm`` block (safe-wpm/0.1) is identical to the stored one, and that the other
  card fields are the same (the rescore diff may hold only the new keys, plus the train / test overlap check and
  its note for a card scored before that check existed; these are not written); else it stops for that card;
- adds ``safe_wpm_v02`` (right after ``safe_wpm``) and ``safe_wpm_headline``, and the v0.2 metric in the recipe's
  ``scorer.metrics``. Every other key keeps its value and order. A v0.1 number keeps its value and its label.

Cards without a rescore-level recipe, or whose submission is not on this machine, are listed and left as they are
(the leaderboard shows their v0.1 value only).

    python -I tools/benchmark/add_safe_wpm_v02.py --derived <derived>            # dry run: print a summary
    python -I tools/benchmark/add_safe_wpm_v02.py --derived <derived> --write    # update the cards

``<derived>`` is the local folder that the recipes name ``<derived>`` (submissions and truth files; never
committed). CPU only.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.hub.recipe import card_json, rescore  # noqa: E402

NEW_KEYS = ("safe_wpm_v02", "safe_wpm_headline")


def score_step(card: dict) -> tuple[str, str] | None:
    """(submission, truth) of the score command of a rescore recipe, with ``<derived>`` left in."""
    rc = card.get("rerun") or {}
    if rc.get("level") != "rescore":
        return None
    steps = rc.get("steps") or [{"step": "score", "command": rc.get("command", "")}]
    for s in reversed(steps):
        cmd = str(s.get("command", ""))
        if "fidetype.benchmark score" not in cmd:
            continue
        a = shlex.split(cmd, posix=True)
        i = a.index("score")
        truth = a[a.index("--truth") + 1] if "--truth" in a else None
        if truth is None or i + 2 >= len(a):
            return None
        return a[i + 2], truth
    return None


def with_v02(card: dict, new: dict) -> dict:
    """``card`` with the v0.2 block after ``safe_wpm``; every other key keeps its value and order."""
    out: dict = {}
    for k, v in card.items():
        if k in NEW_KEYS:
            continue
        out[k] = v
        if k == "safe_wpm":
            for nk in NEW_KEYS:
                out[nk] = new[nk]
    sc = ((out.get("rerun") or {}).get("scorer") or {})
    if sc:
        sc.setdefault("metrics", {})["safe_wpm_v02"] = new["safe_wpm_v02"]["definition"]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", required=True, help="the local folder the recipes call <derived>")
    ap.add_argument("--results", default=str(REPO / "benchmark" / "results" / "v0.2"))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    done, skipped, failed = [], [], []
    overlap_status: dict[str, str] = {}
    for f in sorted(Path(a.results).glob("*.json")):
        card = json.loads(f.read_text(encoding="utf-8"))
        st = score_step(card)
        if st is None:
            skipped.append((f.name, "no rescore-level score command"))
            continue
        sub, truth = (Path(x.replace("<derived>", a.derived)) for x in st)
        if not sub.is_dir() or not truth.is_file():
            skipped.append((f.name, f"local files missing ({sub.name})"))
            continue
        base = {k: v for k, v in card.items() if k not in NEW_KEYS}
        r = rescore(base, sub, truth)
        new = r["card"]
        other = [k for k in r["diff"] if k not in NEW_KEYS]
        if "overlap_check" not in base and "overlap_check" in new:
            # A card scored before the train / test overlap check: the scorer now adds that check and its note.
            # They are not part of this change (the card keeps its form); only they may differ.
            # Some cards also carry notes added after scoring (for example a data-licence note); they stay.
            extra = [x for x in new.get("notes", []) if x not in base.get("notes", [])]
            if all("overlap" in x.lower() for x in extra):
                other = [k for k in other if k not in ("notes", "overlap_check")]
                overlap_status[f.name] = new["overlap_check"].get("status")
        if other or json.dumps(new["safe_wpm"], sort_keys=True) != json.dumps(base["safe_wpm"], sort_keys=True):
            failed.append((f.name, f"the rescore differs in {other or ['safe_wpm']}"))
            continue
        v1, v2 = base["safe_wpm"], new["safe_wpm_v02"]
        if v1.get("status") != v2.get("status"):
            failed.append((f.name, f"status differs: v0.1 {v1.get('status')} vs v0.2 {v2.get('status')}"))
            continue
        out = with_v02(card, new)
        text = card_json(out)
        changed = text != f.read_text(encoding="utf-8")
        if a.write and changed:
            f.write_text(text, encoding="utf-8", newline="\n")
        done.append((f.name, v1.get("value"), v2.get("value"), v2.get("status"), changed))
    for name, x1, x2, status, changed in done:
        fx = (lambda x: "n/a" if x is None else f"{x:.3f}")
        print(f"{'WRITE' if a.write and changed else 'ok   ' if not changed else 'would'} {name}: v0.1 {fx(x1)}"
              f" -> v0.2 {fx(x2)} ({status})")
    for name, why in skipped:
        print(f"skip  {name}: {why}")
    for name, st in sorted(overlap_status.items()):
        if st != "not checked":
            print(f"note  {name}: card scored before the overlap check; the check today says {st!r} (not written)")
    for name, why in failed:
        print(f"FAIL  {name}: {why}")
    print(f"{len(done)} cards with a v0.2 block, {len(skipped)} skipped, {len(failed)} failed", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
