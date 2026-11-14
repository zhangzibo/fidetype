"""M0-24: compare serial and parallel outputs.

Usage (repo root):
  python -I check_equal.py json A.json B.json [--drop key ...]
      JSON equal after removing wall-time keys ("seconds", "wall_s" and --drop keys).
  python -I check_equal.py dir DIR_A DIR_B [--pattern "b2t-*.json"] [--drop key ...]
      Every file of DIR_A matching the pattern: byte-equal to DIR_B, or JSON-equal after --drop.
  python -I check_equal.py decisions A.json B.json
      M4-06 per-trial decision files: every decision field equal except latency_s.
Prints one summary line and exits 1 if anything differs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TIME_KEYS = {"seconds", "wall_s"}


def strip(o, drop: set[str]):
    if isinstance(o, dict):
        return {k: strip(v, drop) for k, v in o.items() if k not in drop}
    if isinstance(o, list):
        return [strip(v, drop) for v in o]
    return o


def json_equal(a: Path, b: Path, drop: set[str]) -> bool:
    ja = json.loads(a.read_text(encoding="utf-8"))
    jb = json.loads(b.read_text(encoding="utf-8"))
    return json.dumps(strip(ja, drop)) == json.dumps(strip(jb, drop))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("json", "dir", "decisions"))
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--pattern", default="*.json")
    ap.add_argument("--drop", nargs="*", default=[])
    x = ap.parse_args()
    drop = TIME_KEYS | set(x.drop)
    a, b = Path(x.a), Path(x.b)
    if x.mode == "json":
        ok = json_equal(a, b, drop)
        print(f"{'EQUAL' if ok else 'DIFFERENT'}: {a} vs {b} (ignored keys {sorted(drop)})")
        return 0 if ok else 1
    if x.mode == "decisions":
        da = json.loads(a.read_text(encoding="utf-8"))
        db = json.loads(b.read_text(encoding="utf-8"))
        assert da["trials"] == db["trials"], "trial order differs"
        n = len(da["decisions"])
        bad = [i for i, (p, q) in enumerate(zip(da["decisions"], db["decisions"]))
               if strip(p, {"latency_s"}) != strip(q, {"latency_s"})]
        print(f"decisions equal (all fields except latency_s): {n - len(bad)}/{n}; differing trials {bad[:10]}")
        return 0 if not bad and len(da["decisions"]) == len(db["decisions"]) else 1
    files = sorted(a.glob(x.pattern))
    n_bytes = n_json = 0
    diff, missing = [], []
    for f in files:
        g = b / f.name
        if not g.exists():
            missing.append(f.name)
        elif f.read_bytes() == g.read_bytes():
            n_bytes += 1
        elif json_equal(f, g, drop):
            n_json += 1
        else:
            diff.append(f.name)
    print(f"{len(files)} files: {n_bytes} byte-equal, {n_json} equal after ignoring {sorted(drop)}, "
          f"{len(diff)} different {diff[:10]}, {len(missing)} missing in {b} {missing[:5]}")
    return 0 if not diff and not missing and files else 1


if __name__ == "__main__":
    sys.exit(main())
