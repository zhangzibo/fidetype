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

Amendment 1 (amendment-1.md, 2026-11-24, before any run) makes every calibration part sentence-group-aware:

5. Pipeline-tune set (replaces rule 4): whole sentence groups of the hold-out, in the order of
   SHA-256(``SALT | "tune-group" | text``), skipping a group that also has a ``val_select`` trial, until the set has
   at least ``N_TUNE`` items. The rest of the hold-out joins the calibration pool (with ``val_select``).
6. Every calibration draw passes ``groups=pool_groups(pool)`` (the normalised sentence text) to
   ``fidetype.trust.calibrate``, so all repeats of a sentence fall in one part (fit, policy grid or LTT).

The module reads the M4-01/02 derived folder (read only) and never writes there.
Usage:
  python holdout.py audit [--derived DIR]               # print counts only
  python holdout.py write --out DIR [--derived DIR]     # also write split.json (keys only, no text) to DIR
  python holdout.py crossing [--derived DIR] [--json F] # amendment 1: groups that cross parts (counts only)
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


# --- amendment 1: sentence-group-aware calibration parts ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
N_DRAWS = 120
ARM_POOLS = {"A": "holdout_to_calibration + val_select", "B": "val_select", "R": "val_select"}


def split_tune_groups(holdout_items: list[tuple[str, str, str]], n_tune: int = N_TUNE, salt: str = SALT,
                      exclude: frozenset = frozenset()) -> tuple[list[str], list[str]]:
    """Rule 5 (amendment 1): (tune keys, calibration keys). The tune set takes whole sentence groups, in the order of
    SHA-256(``salt | "tune-group" | text``); a group whose text is in ``exclude`` (texts that also have a val_select
    trial) is skipped. Groups are added until the tune set has at least ``n_tune`` items. Both lists are sorted by
    the rule-4 tune hash of the key."""
    by: dict[str, list[str]] = {}
    for k, _s, t in holdout_items:
        by.setdefault(normalize_text(t), []).append(k)
    tune: list[str] = []
    for g in sorted(by, key=lambda g: (_u(salt, "tune-group", g), g)):
        if len(tune) >= n_tune:
            break
        if g in exclude:
            continue
        tune.extend(by[g])
    if len(tune) < n_tune:
        raise ValueError("not enough held-out groups for the tune set")
    ts = set(tune)
    key = lambda k: (_u(salt, "tune", k), k)  # noqa: E731
    return sorted(tune, key=key), sorted((k for k, _s, _t in holdout_items if k not in ts), key=key)


def pool_groups(pool: list[tuple[str, str, str]]) -> list[str]:
    """Rule 6 (amendment 1): the group id of each pool item for ``calibrate(groups=...)``."""
    return [normalize_text(t) for _k, _s, t in pool]


def draw_seed(arm: str, k: int) -> int:
    """plan.md: calibrate seed of draw k = first 8 hex digits of SHA-256(``t15-calho|<arm>|cal|<k>``)."""
    return int(hashlib.sha256(f"t15-calho|{arm}|cal|{k}".encode("utf-8")).hexdigest()[:8], 16)


def _src():
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    import numpy as np
    from fidetype.trust import dropin as D

    return np, D


def part_crossing(groups: list[str], seed: int, group_aware: bool = False) -> dict:
    """Counts of the groups with items in two or more calibrate parts (fit, policy grid, LTT) for one draw. The split
    is the one ``calibrate(seed=seed)`` makes from this pool order: plain = ``default_rng(seed).permutation`` and
    ``_split``; group-aware = ``_group_split`` (the ``groups=`` option)."""
    np, D = _src()
    n = len(groups)
    perm = np.random.default_rng(seed).permutation(n)
    if group_aware:
        order, n_fit, n_pol, n_ltt = D._group_split(perm, groups, seed)
    else:
        order, (n_fit, n_pol, n_ltt) = perm, D._split(n)
    part = [0] * n
    for k, i in enumerate(order.tolist()):
        part[i] = 0 if k < n_fit else 1 if k < n_fit + n_pol else 2
    seen: dict[str, set] = {}
    for g, pt in zip(groups, part):
        seen.setdefault(g, set()).add(pt)
    cross = {g for g, v in seen.items() if len(v) > 1}
    size = Counter(groups)
    return {"n": n, "sizes": [int(n_fit), int(n_pol), int(n_ltt)], "groups": len(seen),
            "repeated_groups": sum(1 for c in size.values() if c > 1), "crossing_groups": len(cross),
            "crossing_items": sum(size[g] for g in cross),
            "groups_in_all_3": sum(1 for v in seen.values() if len(v) == 3),
            "ltt_groups": len({g for g, pt in zip(groups, part) if pt == 2}),
            "ltt_items_sharing_a_group_with_fit_or_policy": sum(1 for g, pt in zip(groups, part)
                                                                 if pt == 2 and g in cross)}


def _summ(rows: list[dict]) -> dict:
    out = {}
    for k in ("crossing_groups", "crossing_items", "groups_in_all_3", "ltt_groups",
              "ltt_items_sharing_a_group_with_fit_or_policy"):
        v = [r[k] for r in rows]
        out[k] = {"mean": round(sum(v) / len(v), 2), "min": min(v), "max": max(v)}
    return out


def crossing_audit(parts: dict[str, list[tuple[str, str, str]]], n_draws: int = N_DRAWS, n_tune: int = N_TUNE) -> dict:
    """Amendment 1 report (counts only, no text): sentence groups that cross calibration parts under the plan's old
    rules, and the same counts under rules 5 and 6. ``parts``: {"train", "val_select", "val_eval"} -> items."""
    train, vs, ve = parts["train"], parts["val_select"], parts["val_eval"]
    ho = assign(train)
    ho_items = [x for x in train if x[0] in ho]
    vs_texts = {normalize_text(t) for _k, _s, t in vs}
    ve_texts = {normalize_text(t) for _k, _s, t in ve}
    key2 = {k: (k, s, t) for k, s, t in train}
    rep: dict = {"n_draws": n_draws,
                 "draw_seed": "first 8 hex digits of SHA-256(t15-calho|<arm>|cal|<k>), k = 1 .. n_draws",
                 "pool_order": "hold-out calibration keys in tune-hash order, then val_select in session file order "
                               "(calibrate permutes the pool with the draw seed)"}
    rules = {"old (rule 4, plain split)": split_tune(ho, n_tune),
             "amendment 1 (rule 5 tune set)": split_tune_groups(ho_items, n_tune, exclude=frozenset(vs_texts))}
    for rule, (tune, cal) in rules.items():
        tune_texts = {normalize_text(key2[k][2]) for k in tune}
        pool_a = [key2[k] for k in cal] + list(vs)
        pool_texts = {normalize_text(t) for _k, _s, t in pool_a}
        r = {"tune_items": len(tune), "tune_groups": len(tune_texts), "pool_A_items": len(pool_a),
             "pool_A_groups": len(pool_texts), "tune_groups_also_in_pool_A": len(tune_texts & pool_texts),
             "pool_A_items_sharing_a_group_with_tune": sum(1 for _k, _s, t in pool_a
                                                           if normalize_text(t) in tune_texts),
             "val_select_groups_also_in_holdout_pool": len(vs_texts & {normalize_text(key2[k][2]) for k in cal}),
             "pool_A_groups_also_in_val_eval": len(pool_texts & ve_texts),
             "val_eval_items_sharing_a_group_with_pool_A": sum(1 for _k, _s, t in ve
                                                               if normalize_text(t) in pool_texts)}
        pools = {"A": pool_groups(pool_a), "B": pool_groups(list(vs)), "R": pool_groups(list(vs))}
        for arm, g in pools.items():
            for ga in ((False, True) if rule.startswith("amendment") else (False,)):
                rows = [part_crossing(g, draw_seed(arm, k), ga) for k in range(1, n_draws + 1)]
                r[f"arm_{arm}_{'group_aware' if ga else 'plain'}_split"] = {
                    "pool": ARM_POOLS[arm], "n": rows[0]["n"], "groups": rows[0]["groups"],
                    "repeated_groups": rows[0]["repeated_groups"], "sizes_draw_1": rows[0]["sizes"], **_summ(rows)}
        rep[rule] = r
    return rep


def load_parts(derived: Path) -> dict[str, list[tuple[str, str, str]]]:
    """Labelled items (key, session, text) of train, val_select and val_eval (keys ``<session>|<part>|<index>``)."""
    import numpy as np

    sessions = json.loads((derived / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((derived / "texts.json").read_text(encoding="utf-8"))
    out: dict[str, list[tuple[str, str, str]]] = {"train": [], "val_select": [], "val_eval": []}
    for s in sessions:
        z = np.load(derived / f"{s}.npz")
        for part in out:
            kn = z[f"{part}_known"] if f"{part}_known" in z else []
            for i, ok in enumerate(kn):
                if bool(ok):
                    out[part].append((f"{s}|{part}|{i}", s, texts[s][part][i]))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["audit", "write", "crossing"])
    ap.add_argument("--derived", type=Path, default=DEFAULT_DERIVED)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None, help="crossing: also write the counts to this file")
    a = ap.parse_args(argv)
    if a.cmd == "crossing":
        rep = crossing_audit(load_parts(a.derived))
        print(json.dumps(rep, indent=1))
        if a.json is not None:
            a.json.parent.mkdir(parents=True, exist_ok=True)
            a.json.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
        return 0
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
