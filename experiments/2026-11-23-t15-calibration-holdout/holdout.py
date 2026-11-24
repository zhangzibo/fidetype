"""Calibration hold-out split for the T15 decoder retrain (pre-registered in plan.md). Our own code.

Rule (fixed in plan.md before any decoder output exists):

1. Items: the labelled trials of the B2T '25 ``train`` partition (phonemes known), key
   ``"<session>|train|<index>"`` (the M4-13 loader key).
2. Group: the normalised sentence text. All trials of one sentence go to the same side, so no
   held-out sentence is also a training sentence of the new decoder.
3. Hold-out: a group is held out iff ``u(text) < Q``, with ``u`` = the first 16 hex digits of
   SHA-256(``SALT | "group" | text``) / 16**16.
4. Pipeline-tune set: the ``N_TUNE`` held-out items with the smallest SHA-256(``SALT | "tune" | key``).
   The other held-out items join the calibration pool (with ``val_select``).

The module reads the M4-01/02 derived folder (read only) and never writes there.
Usage:
  python holdout.py audit [--derived DIR]            # print counts only
  python holdout.py write --out DIR [--derived DIR]  # also write split.json (keys only, no text) to DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

SALT = "fidetype-t15-calho-2026-11-23"
Q = 0.2727  # target share of train trials held out: about 2,200 of 8,065
N_TUNE = 250
DEFAULT_DERIVED = Path("C:/Users/zhang/bci-data/derived/m4-01-02-lookahead")
FORBIDDEN_OUT = ("m4-01-02-lookahead", "m4-13")  # other experiments' derived folders


def normalize_text(s: str) -> str:
    """Lower case, keep letters, apostrophes and spaces, collapse whitespace."""
    return " ".join(re.sub(r"[^a-z' ]", " ", s.lower()).split())


def _u(*parts: str) -> float:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16) / float(16 ** 16)


def group_u(text: str, salt: str = SALT) -> float:
    return _u(salt, "group", normalize_text(text))


def assign(items: list[tuple[str, str, str]], q: float = Q, salt: str = SALT) -> set[str]:
    """Keys of the held-out items. ``items``: (key, session, text)."""
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")
    return {k for k, _s, t in items if group_u(t, salt) < q}


def split_tune(holdout: set[str], n_tune: int = N_TUNE, salt: str = SALT) -> tuple[list[str], list[str]]:
    """(tune keys, calibration keys), both sorted by their tune hash."""
    order = sorted(holdout, key=lambda k: (_u(salt, "tune", k), k))
    if n_tune > len(order):
        raise ValueError("n_tune is larger than the hold-out")
    return order[:n_tune], order[n_tune:]


def load_items(derived: Path) -> tuple[list[tuple[str, str, str]], dict[str, int]]:
    """Labelled train items (key, session, text) and the labelled val_select / val_eval counts."""
    import numpy as np  # local import: the pure rules above need no numpy

    sessions = json.loads((derived / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((derived / "texts.json").read_text(encoding="utf-8"))
    items: list[tuple[str, str, str]] = []
    other = Counter()
    for s in sessions:
        z = np.load(derived / f"{s}.npz")
        for part in ("train", "val_select", "val_eval"):
            kn = z[f"{part}_known"] if f"{part}_known" in z else []
            for i, ok in enumerate(kn):
                if not bool(ok):
                    continue
                if part == "train":
                    items.append((f"{s}|train|{i}", s, texts[s]["train"][i]))
                else:
                    other[part] += 1
    return items, dict(other)


def audit(items: list[tuple[str, str, str]], q: float = Q, n_tune: int = N_TUNE, salt: str = SALT) -> dict:
    ho = assign(items, q, salt)
    tune, cal = split_tune(ho, n_tune, salt)
    train_texts = Counter(normalize_text(t) for k, _s, t in items if k not in ho)
    ho_texts = {normalize_text(t) for k, _s, t in items if k in ho}
    per_sess = Counter(s for k, s, _t in items if k in ho)
    n_sess = Counter(s for _k, s, _t in items)
    shares = [per_sess[s] / n_sess[s] for s in n_sess]
    return {
        "salt": salt, "q": q, "n_tune": n_tune,
        "train_labelled": len(items), "holdout": len(ho), "train_kept": len(items) - len(ho),
        "tune": len(tune), "holdout_to_calibration": len(cal),
        "holdout_sentences_also_in_kept_train": sum(1 for t in ho_texts if t in train_texts),
        "sessions": len(n_sess), "session_share_min": min(shares), "session_share_max": max(shares),
        "sessions_with_zero_holdout": sum(1 for s in n_sess if per_sess[s] == 0),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["audit", "write"])
    ap.add_argument("--derived", type=Path, default=DEFAULT_DERIVED)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    items, other = load_items(a.derived)
    r = audit(items)
    r.update({f"{k}_labelled": v for k, v in other.items()})
    r["calibration_pool"] = r["holdout_to_calibration"] + other.get("val_select", 0)
    print(json.dumps(r, indent=1))
    if a.cmd == "write":
        if a.out is None or any(p in a.out.parts for p in FORBIDDEN_OUT):
            print("refused: --out must be this task's own folder", file=sys.stderr)
            return 2
        ho = assign(items)
        tune, cal = split_tune(ho)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "split.json").write_text(json.dumps({"rule": r, "tune": tune, "calibration_holdout": cal,
                                                      "holdout": sorted(ho)}, indent=0), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
