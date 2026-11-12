"""Shared code for the Paper 1 round-4 analyses (CPU only).

Re-uses the round-3 module ``common3.py`` (which re-uses the round-1
``common.py``) and adds:

- ``b2t_env``: the B2T '25 context with the per-temperature decode router of
  round 3 (frame temperature snapped to 0.02, decode caches shared with R3).
- ``b2t_tables``: fit the trust pipeline on a fit set (``pipe.fit(F, F)``, the
  paper's fit-A recipe) and build item tables for any number of item sets;
  options: guard off (plain threshold), published-sentence bonus, decoder.
- ``joint_ltt``: LTT with two risks on a fixed grid (marginal wrong-commit
  rate <= alpha AND error among commits <= beta), p(lambda) = max of the two
  exact binomial p-values, Bonferroni over the grid (FWER <= delta for both
  targets at once; the selective risk is not monotone in lambda).
- rule sets (plug-in, CRC / LTT pure and max rule, joint LTT) on one table.
- per-group outcomes and exact Clopper-Pearson intervals.

New caches go to ``C:/Users/zhang/bci-data/cache/paper1-r4`` (outside the repo).
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R3 = HERE.parent / "2026-11-12-paper1-r3-analyses"
sys.path.insert(0, str(R3))
import common3 as K  # noqa: E402

C = K.C
from fidetype.trust.risk_control import _log_binom_cdf  # noqa: E402

REPO = C.REPO
CACHE4 = Path("C:/Users/zhang/bci-data/cache/paper1-r4")
CACHE4.mkdir(parents=True, exist_ok=True)
TAB3 = K.CACHE3 / "splits"
ALPHA, DELTA = C.ALPHA, C.DELTA
BETAS = (0.10, 0.20)
GRID05 = K.LTT_SEL_GRID  # 0.05 .. 1.00, step 0.05 (20 points), fixed before any r4 run
GRID01 = tuple(float(x) for x in np.round(np.arange(0.01, 1.0001, 0.01), 2))  # sensitivity: 100 points
M13 = C.load_module("m213run", REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
SPLITS_B2T = json.loads((R3 / "repeated-splits/results/splits-b2t.json").read_text(encoding="utf-8"))
DAYS_ALL = SPLITS_B2T["days"]  # post-implant day of trial i of (ctx.fit + ctx.test)


# ---------------------------------------------------------------------------
# B2T environment and table builder
# ---------------------------------------------------------------------------

class Router4(K.TRouter):
    """R3 decode router; a decode cache for a temperature that R3 did not decode lives in CACHE4."""

    def get(self, T: float):
        k = f"{T:.2f}"
        if k not in self.d:
            dc = super().get(T)
            if not dc.path.exists():
                dc.path = CACHE4 / dc.path.name
                if dc.path.exists():
                    import pickle
                    try:
                        dc.d = pickle.loads(dc.path.read_bytes())
                    except Exception:  # noqa: BLE001
                        dc.d = {}
            return dc
        return self.d[k]


def b2t_env(snap_step: float = 0.02):
    K.install_snap(snap_step)
    ctx = C.b2t_ctx()
    router = Router4(ctx.cached[0].fn, "b2t-words")
    ctx.dec.words_fn = router
    trials = ctx.fit + ctx.test
    items = ctx.items(trials)
    return ctx, router, trials, items


def decoder_fn(ctx, which: str):
    if which == "ours":
        return ctx.dec.words_fn
    if which == "published":
        return ctx.dec.published_plus_fn
    if which == "published_alone":
        return ctx.dec.published_fn
    raise ValueError(which)


def b2t_tables(ctx, which: str, fit_items, sets: dict, use_guard: bool = True, margin: float | None = None) -> dict:
    """Fit on ``fit_items`` (fit(F, F)); item tables for each named item list in ``sets``."""
    old_margin = ctx.bt.CONFIG["published_margin"]
    if margin is not None:
        ctx.bt.CONFIG["published_margin"] = float(margin)
    try:
        cfg = C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=ALPHA, use_guard=use_guard)
        pipe = C.TrustPipeline(decoder_fn(ctx, which), cfg, {})
        pipe.fit(fit_items, fit_items)
        out = {"T_fitted": K.TState.fitted, "T_used": K.TState.used, "fit_report": C.clean(pipe.fit_report),
               "use_guard": use_guard, "margin": ctx.bt.CONFIG["published_margin"] if which == "published" else None}
        for name, its in sets.items():
            out[name] = M13.item_table(pipe, its)
        return out
    finally:
        ctx.bt.CONFIG["published_margin"] = old_margin


# ---------------------------------------------------------------------------
# Split tables (R3 cache + R4 cache)
# ---------------------------------------------------------------------------

TAB4 = CACHE4 / "splits"
_SP200 = None
_EMG_WHO: dict = {}


def splits200() -> list[dict]:
    global _SP200
    if _SP200 is None:
        _SP200 = json.loads((CACHE4 / "splits-b2t-200.json").read_text(encoding="utf-8"))["splits"]
    return _SP200


def emg_test_who(cname: str) -> list:
    if cname not in _EMG_WHO:
        _EMG_WHO[cname] = json.loads((R3 / f"repeated-splits/results/emg-{cname}-test-participants.json")
                                     .read_text(encoding="utf-8"))["participants_test"]
    return _EMG_WHO[cname]


def split_path(cond: str, r: int, guard: int = 1, margin: float | None = None) -> Path:
    if cond.startswith("b2t-"):
        which = cond[4:]
        if margin is not None and abs(margin - 2.0) > 1e-9:
            return TAB4 / f"b2t-published-m{margin:g}-{r:03d}.json"
        if guard and r < 50:
            return TAB3 / f"b2t-{which}-{r:03d}.json"
        return TAB4 / f"b2t-{which}-g{guard}-{r:03d}.json"
    c = cond[4:]
    return (TAB3 / f"emg-{c}-{r:03d}.json") if guard else (TAB4 / f"emg-{c}-g0-{r:03d}.json")


def load_split(cond: str, r: int, guard: int = 1, margin: float | None = None) -> dict | None:
    """Arrays of one split: reuse / cal / test, plus group labels (day or participant) of the test and cal items."""
    p = split_path(cond, r, guard, margin)
    if not p.exists():
        return None
    tab = json.loads(p.read_text(encoding="utf-8"))
    out = {"r": r, "reuse": K.arr(tab["reuse"]), "cal": K.arr(tab["cal"]), "test": K.arr(tab["test"]),
           "T_used": tab.get("T_used"), "T_fitted": tab.get("T_fitted"),
           "policy_config": (tab.get("fit_report") or {}).get("policy_config")}
    if cond.startswith("b2t-"):
        s = splits200()[r]
        assert list(tab["test_idx"]) == list(s["test"])
        out["test_group"] = np.array([DAYS_ALL[i] for i in s["test"]])
        out["cal_group"] = np.array([DAYS_ALL[i] for i in s["cal"]])
        out["reuse_group"] = np.array([DAYS_ALL[i] for i in s["A"]])
    else:
        out["test_group"] = np.array(emg_test_who(cond[4:]))
    return out


def load_all(cond: str, R: int, guard: int = 1, margin: float | None = None) -> list[dict]:
    rows = [load_split(cond, r, guard, margin) for r in range(R)]
    return [x for x in rows if x is not None]


CONDS = ("b2t-ours", "b2t-published", "emg-calib", "emg-xsession", "emg-xsubject")


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def p_marginal(a: dict, lam: float, alpha: float = ALPHA) -> float:
    on = a["s"] >= lam
    loss = np.where(on, a["c"], a["f"])
    n = loss.size
    k = int(round(loss.sum()))
    return math.exp(_log_binom_cdf(k, n, alpha))


def p_selective(a: dict, lam: float, beta: float) -> float:
    on = a["s"] >= lam
    n = int(on.sum())
    if n == 0:
        return 1.0
    k = int(round(a["c"][on].sum()))
    return math.exp(_log_binom_cdf(k, n, beta))


def joint_ltt(a: dict, alpha: float = ALPHA, beta: float = 0.10, delta: float = DELTA, grid=GRID05) -> dict:
    """Joint LTT: H0(lam): R_marg(lam) > alpha or R_sel(lam) > beta; p = max(p_marg, p_sel);
    Bonferroni over the fixed grid; lambda-hat = the smallest rejected grid point (+inf if none)."""
    rej, ps = [], {}
    for lam in grid:
        pm, pv = p_marginal(a, lam, alpha), p_selective(a, lam, beta)
        ps[f"{lam:.2f}"] = (pm, pv)
        if max(pm, pv) <= delta / len(grid):
            rej.append(float(lam))
    return {"threshold": min(rej) if rej else math.inf, "feasible": bool(rej), "n_rejected": len(rej)}


def rule_lambdas(ca: dict, plug: float, betas=BETAS, grids=(("g05", GRID05),)) -> dict:
    rc, rl = K.crc(ca), K.ltt(ca)
    lam = {"plug-in": plug, "CRC pure": rc.threshold, "CRC max": max(plug, rc.threshold),
           "LTT pure": rl.threshold, "LTT max": max(plug, rl.threshold)}
    for b in betas:
        for gname, g in grids:
            tag = f"joint LTT b{b:.2f}" + ("" if gname == "g05" else f" {gname}")
            lam[tag] = joint_ltt(ca, beta=b, grid=g)["threshold"]
        lam[f"LTT-sel b{b:.2f}"] = K.ltt_selective(ca["s"], ca["c"], b, DELTA)["threshold"]
    return lam


def outcomes(te: dict, lams: dict, rows=None) -> dict:
    return {k: K.outcome(te, v, rows) for k, v in lams.items()}


def cp(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    lo, hi = K.clopper_pearson(int(round(k)), n)
    return [lo, hi]


def wrong_count(o: dict) -> int:
    return int(round(o["wrong_commit"] * o["n"]))


def jsonable(o):
    return C.clean(o)


def fmt(x, nd=4):
    if x is None:
        return "—"
    x = C.fnum(x)
    return "—" if not math.isfinite(x) else f"{x:.{nd}f}"


def fci(c, nd=3):
    if not c or c[0] is None:
        return ""
    return f"[{c[0]:.{nd}f}, {c[1]:.{nd}f}]"


def log_to(path: Path):
    C.Log.path = path


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
