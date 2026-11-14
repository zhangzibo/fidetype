"""Shared code of the P5-07 v5 candidate evaluation (CPU only). See plan.md.

One fitted pipeline per split (``fidetype.trust.recipe_v5.V5Pipeline`` as
a sweep engine: calibration, guard, conformal, the full grid table with
``commit_max_risk`` 0.8 added, per-item outcomes of every grid point and
the fit-time control inputs). Each arm of plan.md section 3 selects a grid
point from that table, then takes lambda = max(grid commit_p, LTT, floor)
and applies the gate.

Re-uses the M3-02 helpers (``abl.py``: item tables, McNemar, CP95, gate
mask) and through them the Paper 1 R1/R3/R4 stack.
No signal, text or participant data is written by this module.
"""

from __future__ import annotations

import copy
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments/2026-11-14-m3-01-02-ablations"))
import abl as A  # noqa: E402

C, K, Q = A.C, A.K, A.Q

from fidetype.trust import recipe_v5 as V  # noqa: E402
from fidetype.trust.content import CommitGate  # noqa: E402
from fidetype.trust.policy import DEFAULT_GRID, DecisionPolicy, PolicyConfig  # noqa: E402

CACHE6 = Path("C:/Users/zhang/bci-data/cache/trust-v5")
CACHE6.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
ALPHA, DELTA, LIMIT = 0.05, 0.1, 0.01
INF = math.inf
GATE = CommitGate(**V.GATE_B)
N_BOOT = 200
BOOT_SEED = 7

#: arm -> (selection key, gate, floor). Selection keys: see ``selections``.
ARMS: dict[str, tuple[str, bool, bool]] = {
    "v4": ("v4", False, False),
    "v5": ("aware_g", True, True),
    "v5 - a (no gate)": ("aware_ng", False, True),
    "v5 - b (v4 grid rule)": ("v4", True, True),
    "v5 - d (no floor)": ("aware_g", True, False),
    "v5 + c (0.8 for 1.0)": ("aware_g_no1", True, True),
    "v4 + a": ("v4", True, False),
    "v4 + b": ("aware_ng", False, False),
    "v4 + c": ("v4_no1", False, False),
    "v4 + d": ("v4", False, True),
}


def log(*a) -> None:
    C.log(*a)


def set_log(path: Path) -> None:
    C.Log.path = path


def dump(obj, path: Path) -> None:
    C.dump(obj, path)


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def grids(base_grid: dict | None) -> tuple[dict, tuple, tuple]:
    """(sweep grid with 0.8 added, v4 commit_max_risk values, values with 1.0 -> 0.8)."""
    g = dict(DEFAULT_GRID if base_grid is None else base_grid)
    v4 = tuple(float(x) for x in g["commit_max_risk"])
    no1 = tuple(sorted({V.NO_ONE_MAX_RISK if x >= 1.0 else x for x in v4}))
    sw = dict(g)
    sw["commit_max_risk"] = tuple(sorted(set(v4) | set(no1)))
    return sw, v4, no1


def fit_sweep(decode_fn, user, fit_args: tuple, base: dict | None = None, cache: dict | None = None,
              control_streams: dict | None = None):
    """Fit one V5Pipeline as the sweep engine (all control inputs computed; selection done later)."""
    base = dict(base or {})
    sw, v4, no1 = grids(base.pop("grid", None))
    o = V.V5Options(commit_gate=False, control_aware_fit=True, no_signal_reference=True)
    kw = dict(seed=C.SEED, user_config=user, max_wrong_commit=ALPHA, use_guard=True, grid=sw)
    kw.update(base)
    cfg = C.HarnessConfig(**kw)
    pipe = V.V5Pipeline(decode_fn, cfg, {} if cache is None else cache, o, control_streams)
    pipe.keep_item_outcomes = True
    t0 = time.time()
    pipe.fit(*fit_args)
    pipe._v4_vals, pipe._no1_vals = v4, no1
    log(f"  sweep: T {pipe.frame_scaler.temperature:.4f}, {len(pipe.fit_table)} grid rows, controls "
        f"{ {k: len(v) for k, v in pipe.control_inputs.items()} } ({time.time() - t0:.0f}s)")
    return pipe


def ctl_arrays(pipe, gate: bool, kinds=V.CONTROL_KINDS) -> dict:
    return {k: V.InputArrays(pipe.control_inputs[k], True, GATE if gate else None) for k in kinds if k in pipe.control_inputs}


def selections(pipe) -> dict:
    """Selection key -> (config dict, metrics, feasible)."""
    tab, v4, no1 = pipe.fit_table, pipe._v4_vals, pipe._no1_vals
    cg, cn = ctl_arrays(pipe, True), ctl_arrays(pipe, False)
    return {
        "v4": V.select_policy(tab, ALPHA, None, LIMIT, v4),
        "aware_g": V.select_policy(tab, ALPHA, cg, LIMIT, v4),
        "aware_ng": V.select_policy(tab, ALPHA, cn, LIMIT, v4),
        "v4_no1": V.select_policy(tab, ALPHA, None, LIMIT, no1),
        "aware_g_no1": V.select_policy(tab, ALPHA, cg, LIMIT, no1),
    }


def with_policy(pipe, cfg: dict):
    p = copy.copy(pipe)
    p.policy = DecisionPolicy(PolicyConfig(**cfg), use_guard=True)
    return p


def item_meta(pipe, items) -> dict:
    """Gate mask and empty-top-1 mask of the first attempt (selection-independent)."""
    blk, emp = [], []
    for it in items:
        x = pipe.analyze(pipe.decode(it, 0)).inputs
        top = x.texts[0] if x.texts else ""
        blk.append(GATE.violation(top, x.guard_risk) is not None)
        emp.append(top.strip() == "")
    return {"block": np.array(blk, bool), "empty": np.array(emp, bool)}


# ---------------------------------------------------------------------------
# Arms on one split
# ---------------------------------------------------------------------------

def evaluate_split(pipe, cal_items, test_items, test_groups=None, nulls: dict | None = None, null_truths=None,
                   null_decode=None, with_tables: bool = True, arms=None) -> dict:
    """All arms on one split: item tables per distinct selection, lambda parts, test outcomes, controls."""
    arms = arms or list(ARMS)
    sel = selections(pipe)
    ref_g, ref_n = ctl_arrays(pipe, True, V.REFERENCE_KINDS), ctl_arrays(pipe, False, V.REFERENCE_KINDS)
    ctl_g, ctl_n = ctl_arrays(pipe, True), ctl_arrays(pipe, False)
    tabs: dict = {}
    for key, (cfg, _, _) in sel.items():
        ck = tuple(sorted(cfg.items(), key=lambda kv: kv[0]))
        hit = next((t for k2, t in tabs.items() if t["ck"] == ck), None)
        if hit is None:
            p = with_policy(pipe, cfg)
            hit = {"ck": ck, "cal": Q.M13.item_table(p, cal_items), "test": Q.M13.item_table(p, test_items)}
        tabs[key] = hit
    meta = item_meta(pipe, test_items)
    out: dict = {"selections": {k: {"policy": C.clean(v[0]), "fit_metrics": {m: v[1][m] for m in ("ewpm", "wrong_commit_rate")},
                                    "feasible": v[2],
                                    "fit_control_rates_gate": V.control_rates(ctl_g, v[0]),
                                    "fit_control_rates_nogate": V.control_rates(ctl_n, v[0])} for k, v in sel.items()},
                 "T": float(pipe.frame_scaler.temperature), "n_test": len(test_items), "n_cal": len(cal_items),
                 "n_fit_controls": {k: len(v) for k, v in pipe.control_inputs.items()},
                 "gate_blockable_test_items": int(meta["block"].sum()), "empty_top1_test_items": int(meta["empty"].sum()),
                 "arms": {}}
    arrs, lam_of = {}, {}
    for arm in arms:
        key, gate, floor = ARMS[arm]
        cfg = sel[key][0]
        tc, tt = tabs[key]["cal"], tabs[key]["test"]
        plug = float(C.fnum(tc["lam_old"]))
        lt = K.ltt(K.arr(tc)).threshold
        fl = V.reference_floor(ref_g if gate else ref_n, cfg, LIMIT) if floor else -INF
        lam = max(plug, lt, fl)
        lam_of[arm] = (cfg, lam, gate)
        a, info = A.arrays(tt, lam, meta["block"] if gate else None)
        arrs[arm] = a
        s = A.summarise(a)
        s["n_empty_commit"] = int(((a["com"] > 0.5) & meta["empty"]).sum())
        out["arms"][arm] = {**s, "lambda": C.clean(lam), "lambda_parts": {"grid": C.clean(plug), "ltt": C.clean(lt),
                                                                          "floor": C.clean(fl)},
                            "selection": key, "gate": gate, "floor_on": floor, **({"gate_info": info} if info else {})}
    # never commit (offer only) reference
    a, _ = A.arrays(tabs["v4"]["test"], INF)
    out["arms"]["never commit"] = {**A.summarise(a), "n_empty_commit": 0}
    base = arrs["v4"]
    ps = {}
    for arm, a in arrs.items():
        if arm == "v4":
            continue
        m = A.mcnemar(a["wc"], base["wc"])
        v = out["arms"][arm]
        v["vs_v4"] = {**m, "d_wrong_commit": v["wrong_commit"] - out["arms"]["v4"]["wrong_commit"],
                      "d_commit_rate": v["commit_rate"] - out["arms"]["v4"]["commit_rate"],
                      "d_ewpm": v["ewpm"] - out["arms"]["v4"]["ewpm"]}
        ps[arm] = m["p"]
    for arm, ph in K.holm(ps).items():
        out["arms"][arm]["vs_v4"]["p_holm"] = ph
    if nulls:
        out["controls"] = control_commits(pipe, lam_of, nulls, null_truths, null_decode)
    out["_lam_of"] = lam_of  # removed before dump
    return out


def control_commits(pipe, lam_of: dict, nulls: dict, truths: list, decode=None) -> dict:
    """Commits per arm on each test-time control set (inputs at the pipeline's frame temperature)."""
    res: dict = {}
    T = pipe.frame_scaler.temperature
    for cname, ss in nulls.items():
        xs, tops = [], []
        for i, s in enumerate(ss):
            s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
            nb = decode(s2, i) if decode is not None else pipe.decode_fn(s2)
            x = pipe.analyze(nb).inputs
            xs.append(x)
            tops.append(x.texts[0] if x.texts else "")
        empty = np.array([t.strip() == "" for t in tops])
        wrong_txt = np.array([t != truths[i] for i, t in enumerate(tops)])
        arr_g, arr_n = V.InputArrays(xs, True, GATE), V.InputArrays(xs, True, None)
        res[cname] = {}
        for arm, (cfg, lam, gate) in lam_of.items():
            c2 = dict(cfg, commit_p=lam)
            com = (arr_g if gate else arr_n).commits(c2)
            k = int(com.sum())
            res[cname][arm] = {"n": len(ss), "n_commit": k, "commit_rate": k / len(ss) if ss else 0.0,
                               "n_wrong": int((com & wrong_txt).sum()), "n_empty_commit": int((com & empty).sum()),
                               "commit_cp95_one_sided_upper": K.upper_one_sided(k, len(ss))}
    return res


# ---------------------------------------------------------------------------
# Stability (bootstrap of the grid-fit set; per-item outcomes from the sweep)
# ---------------------------------------------------------------------------

def stability(pipe, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> dict:
    tab, outs = pipe.fit_table, pipe.fit_outcomes
    assert len(tab) == len(outs) and outs, "sweep without item outcomes"
    WC = np.stack([o["wrong_commit"] for o in outs])  # rows x n
    WO = np.stack([o["words"] for o in outs])
    TI = np.stack([o["time_s"] for o in outs])
    n = WC.shape[1]
    cmr = np.array([float(c["commit_max_risk"]) for c, _ in tab])
    cp = np.array([float(c["commit_p"]) for c, _ in tab])
    v4m = np.isin(np.round(cmr, 9), np.round(pipe._v4_vals, 9))
    cg = ctl_arrays(pipe, True)
    ctl_ok = np.array([all(r <= LIMIT + 1e-12 for r in V.control_rates(cg, c).values()) for c, _ in tab])
    rng = np.random.default_rng(seed)
    W = rng.multinomial(n, np.full(n, 1.0 / n), size=n_boot).astype(float)  # B x n
    wc = W @ WC.T / n
    ew = 60.0 * (W @ WO.T) / np.maximum(W @ TI.T, 1e-12)
    res = {}
    for name, mask in (("v4 rule", v4m), ("v5 rule", v4m & ctl_ok)):
        feas = (wc <= ALPHA + 1e-12) & mask[None, :]
        score = np.where(feas, ew, -np.inf)
        win = np.argmax(score, axis=1)
        none = ~feas.any(axis=1)
        cm_w = cmr[win]
        pts = [f"{cp[w]:g}/{cmr[w]:g}" for w in win]
        vals, cnt = np.unique(pts, return_counts=True)
        res[name] = {"share_commit_max_risk": {f"{v:g}": float(np.mean(cm_w[~none] == v)) for v in sorted(set(cmr[mask]))},
                     "share_top_point": float(cnt.max() / n_boot), "top_point": str(vals[np.argmax(cnt)]),
                     "n_distinct_points": int(len(vals)), "share_infeasible": float(none.mean()),
                     "share_commit_p_gt_1": float(np.mean(cp[win] > 1.0))}
    return res


# ---------------------------------------------------------------------------
# Repeated splits summary
# ---------------------------------------------------------------------------

def split_row(ev: dict) -> dict:
    """Compact per-split record for the repeated-split files."""
    return {"T": ev["T"], "arms": {a: {k: v[k] for k in ("wrong_commit", "commit_rate", "ewpm", "n_commit", "n_wrong_commit",
                                                         "n_empty_commit")} | {"lambda": v.get("lambda")}
                                   for a, v in ev["arms"].items()},
            "selections": {k: {"commit_p": v["policy"]["commit_p"], "commit_max_risk": v["policy"]["commit_max_risk"]}
                           for k, v in ev["selections"].items()}}


def summarise_splits(rows: list[dict]) -> dict:
    from scipy.stats import binom
    arms = list(rows[0]["arms"])
    out = {"R": len(rows)}
    base = np.array([r["arms"]["v4"]["wrong_commit"] for r in rows])
    for arm in arms:
        wc = np.array([r["arms"][arm]["wrong_commit"] for r in rows])
        k = int(np.sum(wc > ALPHA + 1e-12))
        d = wc - base
        npos, nneg = int((d > 1e-12).sum()), int((d < -1e-12).sum())
        sp = 1.0 if npos + nneg == 0 else min(1.0, 2 * float(binom.cdf(min(npos, nneg), npos + nneg, 0.5)))
        out[arm] = {"wrong_commit_mean": float(wc.mean()), "share_gt_alpha": k / len(rows), "share_gt_alpha_cp95": Q.cp(k, len(rows)),
                    "commit_rate_mean": float(np.mean([r["arms"][arm]["commit_rate"] for r in rows])),
                    "ewpm_mean": float(np.mean([r["arms"][arm]["ewpm"] for r in rows])),
                    "n_empty_commit": int(sum(r["arms"][arm]["n_empty_commit"] for r in rows)),
                    "n_up": npos, "n_down": nneg, "sign_test_p": sp}
    sel = {}
    for key in rows[0]["selections"]:
        cm = [r["selections"][key]["commit_max_risk"] for r in rows]
        sel[key] = {f"{v:g}": float(np.mean([c == v for c in cm])) for v in sorted(set(cm))}
    out["selection_commit_max_risk_share"] = sel
    return out


def clean_eval(ev: dict) -> dict:
    ev = dict(ev)
    ev.pop("_lam_of", None)
    return ev
