r"""P15-54 runner: F3 at small data, FALCON H2-style protocol, per-session input layers (gap 219).

Our own code, Apache-2.0. Plan: plan.md (pre-registered, 19ec6c5) and amendment-1.md (4d31f8e). Values: config.json.
We do not copy FALCON or NLB code; the NWB files are read with h5py (HDF5) as plain arrays.

Reuses READ-ONLY and UNCHANGED: the E1a causal trunk, augmentation, batch packing, CTC decoding and bootstrap
(P15-08 ``e1.py``), the optimiser, checkpoint and keep-awake helpers (P15-08 ``run.py``), and the T15 trial reader and
GPU clock of P15-50 (``f3.py``).

Model (plan 5.2): per-session input layer A_s = dropout -> softsign(W_s x + b_s) -> dropout (W_s = I, b_s = 0 at the
start), then P_in Linear(C -> 512) (new in every target run), the E1a trunk + LayerNorm, and a head. Fully causal.

Stages (``all`` runs them in order; finished parts are skipped; every training part resumes from its checkpoint):
  prep       stage 0 (CPU): NWB -> caches, session roles, symbol check, T15 norm stats -> session_roles.json
  gate0      results/session_roles.json committed and on origin/main (else exit code 4)
  pretrainI  arm I trunk: 10,000 steps of T15 phoneme CTC with per-session input layers
  s1         stage 1: R, E, I x LR {3e-4, 1e-3} at 12 sentences per val session, tuning seed 10 -> selection.json
  gate1      results/selection.json committed and on origin/main (else exit code 4)
  core       stage 2 core: normal R, E, E0, I; C2 of E, I and R (core cap 9 h)
  ext        M pretraining + M selection (selection-ext.json), P pretraining, gate2, extended runs (total cap 20 h)
  summary    rules, hypotheses, outcome -> summary.json (aggregates only; also results/summary.json)

Run (repo root, GPU venv):  C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments\2026-11-25-f3-small-data-falcon\f3s.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
Exit codes: 0 done / cap / partial, 2 refused, 3 paused, 4 waiting for a commit, 5 data stop (amendment 1, point 4).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P08_DIR = HERE.parent / "2026-11-19-p15-08-e1-cross-body"
F3_DIR = HERE.parent / "2026-11-23-f3-full-data-controls"
sys.path.insert(0, str(P08_DIR))
sys.path.insert(0, str(F3_DIR))
import e1  # noqa: E402
import f3 as F3  # noqa: E402
import run as R8  # noqa: E402

ED = e1.ED
OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-54")
DERIVED = Path(r"C:\Users\zhang\bci-data\derived")
RESULTS = HERE / "results"
OWN = "p15-54"
PAUSED, WAITING, DATA_STOP = 3, 4, 5
CORE_ARMS = ("R", "E", "E0", "I")
ALL_ARMS = ("R", "E", "E0", "I", "M", "T", "P", "X-R", "X-E")


class CapReached(Exception):
    pass


class DataStop(Exception):
    pass


# =====================================================================================================================
# Pure rules (CPU-tested)
# =====================================================================================================================


def map_text(cue: str, symbol_map: dict) -> str:
    """H2 cue -> plain text (amendment 1, 3.2): '>' -> space, '~' -> '.', every other symbol unchanged."""
    return "".join(symbol_map.get(c, c) for c in cue)


def check_symbols(texts: list[str]) -> list[str]:
    """Symbols outside the 98-token vocabulary (plan 5.1: stop if not empty)."""
    return sorted({c for t in texts for c in t if c not in e1.TOK})


def session_roles(counts: dict[str, int], r: dict) -> dict:
    """Plan 4.2 from trial counts only. counts: {date YYYYMMDD: n trials}. Raises DataStop on too few sessions.

    plan.md says "If fewer than 6 sessions are then eligible: use 3 test and 3 val sessions. If fewer than 6: stop".
    The first sentence can only mean "fewer than 8" (3 + 3 needs 6), so: < 8 -> 3 + 3, < 6 -> stop."""
    def elig(th: int) -> list[str]:
        return sorted(d for d, n in counts.items() if n >= th)

    th, core, fallback = int(r["min_trials"]), list(r["core_budgets"]), False
    e = elig(th)
    n_test, n_val = int(r["n_test"]), int(r["n_val"])
    if len(e) < n_test + n_val:
        th, core, fallback = int(r["fallback_min_trials"]), list(r["fallback_core_budgets"]), True
        e = elig(th)
        if len(e) < n_test + n_val:
            n_test = n_val = int(r["n_small"])
        if len(e) < int(r["min_sessions"]):
            raise DataStop(f"only {len(e)} sessions with >= {th} trials: outcome 'not run (data)'")
    ext = [b for b in r["extended_budgets"] if b not in core]
    if max(core + ext) + int(r["test_last"]) > th:
        raise DataStop("a budget does not fit the trial threshold")
    test = e[-n_test:]
    val = e[-(n_test + n_val):-n_test]
    source = sorted(d for d in counts if d not in test and d not in val)
    return {"threshold": th, "fallback": fallback, "eligible": e, "test": test, "val": val, "source": source,
            "core_budgets": core, "extended_budgets": ext, "top_budget": max(core), "test_last": int(r["test_last"]),
            "counts": {d: int(counts[d]) for d in sorted(counts)}}


def select_lr(vals: dict[float, float], c: dict) -> dict:
    """Plan 7.2: lower final-step val CER; > 0.95 excluded; tie (< 0.005) -> smaller LR; all excluded -> 3e-4."""
    ok = {float(lr): float(v) for lr, v in vals.items() if not (v > float(c["exclude_if_val_cer_above"]))}
    if not ok:
        return {"lr": float(c["fallback_lr"]), "why": "all excluded: fallback LR"}
    best = min(ok.values())
    near = sorted(lr for lr, v in ok.items() if v - best < float(c["tie"]))
    return {"lr": near[0], "why": "lowest val CER" + (" (tie: smaller LR)" if len(near) > 1 else "")}


def win(a: str, b: str, budget: int, runs: dict, rules: dict, seeds: list[int]) -> dict:
    """win(A, B, b) (plan 8): d_s = CER_B - CER_A per seed with a paired sentence bootstrap CI95;
    pass if d_s > 0 on all seeds and the CI95 is above 0 on >= 2 of 3 seeds. runs[(arm, budget, seed)] = result."""
    per = []
    for s in seeds:
        if (a, budget, s) not in runs or (b, budget, s) not in runs:
            return {"a": a, "b": b, "budget": budget, "status": "not_run", "pass": None, "per_seed": per}
        ra, rb = runs[(a, budget, s)], runs[(b, budget, s)]
        ref = np.asarray(ra["test_ref"], float)
        if not np.array_equal(ref, np.asarray(rb["test_ref"], float)):
            raise RuntimeError("test references differ")
        bs = e1.bootstrap_delta(np.asarray(rb["test_edits_final"], float), np.asarray(ra["test_edits_final"], float),
                                ref, n=int(rules["bootstrap_n"]), seed=int(rules["bootstrap_seed"]))
        d = float(rb["test_cer_final"]) - float(ra["test_cer_final"])
        per.append({"seed": s, "cer_a": ra["test_cer_final"], "cer_b": rb["test_cer_final"], "d": d,
                    "ci95": [bs["lo"], bs["hi"]], "ci_above_0": bool(bs["lo"] > 0)})
    pa = all(p["d"] > 0 for p in per)
    n_ci = sum(p["ci_above_0"] for p in per)
    pb = n_ci >= int(rules["seed_ci_min"])
    return {"a": a, "b": b, "budget": budget, "status": "done", "per_seed": per, "all_d_positive": bool(pa),
            "n_ci_above_0": n_ci, "pass": bool(pa and pb)}


def c2_need(normal: float, rules: dict) -> float:
    return max(float(rules["c2_min_cer"]), float(normal) + float(rules["c2_min_gap"]))


def c2_triggers_extra(normal: float, deranged: float, rules: dict) -> bool:
    """Plan 7.3: a C2 margin within +-0.03 on a seed -> 2 more deranged runs for that seed."""
    return abs(float(deranged) - c2_need(normal, rules)) <= float(rules["c2_band"]) + 1e-12  # inclusive, float-safe


def c2_seed(normal: float | None, deranged: list[float | None], rules: dict) -> dict:
    """One seed: one deranged run -> it meets the need; three runs -> the mean meets it and >= 2 of 3 meet it.
    A seed whose first run triggered the extra pair needs all 3 (else 'missing')."""
    if normal is None or not deranged or deranged[0] is None:
        return {"status": "missing", "pass": None}
    need = c2_need(normal, rules)
    need_three = c2_triggers_extra(normal, deranged[0], rules)
    if need_three and (len(deranged) < 3 or any(d is None for d in deranged[:3])):
        return {"status": "missing", "pass": None, "normal": normal, "deranged": deranged, "needed": need}
    ds = [float(d) for d in (deranged[:3] if need_three else deranged[:1])]
    ind = [d >= need for d in ds]
    if len(ds) == 1:
        ok = ind[0]
    else:
        ok = float(np.mean(ds)) >= need and sum(ind) >= int(rules["c2_min_individual"])
    return {"status": "done", "normal": float(normal), "deranged": ds, "mean": float(np.mean(ds)), "needed": need,
            "margin": float(np.mean(ds)) - need, "n_runs": len(ds), "pass": bool(ok)}


def c2_rule(arm: str, budget: int, normal: dict, der: dict, rules: dict, seeds: list[int]) -> dict:
    """C2(A, b): passes on every seed. der[(arm, budget, seed, j)] = deranged test CER."""
    rows = {}
    for s in seeds:
        n = normal.get((arm, budget, s))
        rows[str(s)] = c2_seed(None if n is None else float(n["test_cer_final"]),
                               [der.get((arm, budget, s, j)) for j in range(1 + int(rules["c2_extra"]))], rules)
    vals = [r["pass"] for r in rows.values()]
    p = False if any(v is False for v in vals) else (None if any(v is None for v in vals) else True)
    return {"arm": arm, "budget": budget, "seeds": rows, "pass": p}


def c1_rule(arm: str, budget: int, normal: dict, rules: dict, seeds: list[int]) -> dict:
    """C1(A, b): time-shuffled test CER >= 0.85 for each normal run with CER <= 0.70."""
    rows = []
    for s in seeds:
        r = normal.get((arm, budget, s))
        if r is None:
            return {"arm": arm, "budget": budget, "pass": None, "runs": rows}
        if float(r["test_cer_final"]) <= float(rules["c1_applies_if_cer_below"]):
            sh = r.get("c1_shuffled_cer")
            rows.append({"seed": s, "cer": r["test_cer_final"], "shuffled": sh,
                         "pass": sh is not None and float(sh) >= float(rules["c1_min_cer"])})
    return {"arm": arm, "budget": budget, "runs": rows, "pass": bool(all(x["pass"] for x in rows))}


def tri(x) -> bool | None:
    return None if x is None else bool(x)


def verdict(normal: dict, der: dict, roles: dict, rules: dict, seeds: list[int]) -> dict:
    """Plan 8 and 9 with amendment 1 (3.18). normal[(arm, b, s)] = result dict; der[(arm, b, s, j)] = test CER."""
    core = list(roles["core_budgets"])
    top = int(roles["top_budget"])
    budgets = sorted(set(core) | set(roles["extended_budgets"]))
    nb = int(rules["h_min_budgets"])
    W = {(a, b, x): win(a, b, x, normal, rules, seeds) for a in ALL_ARMS for b in ("R",) for x in budgets if a != "R"}
    for a in ("E", "I", "M"):  # negative transfer: R beats A
        for x in core:
            W[("R", a, x)] = win("R", a, x, normal, rules, seeds)
    for x in core:
        W[("E", "T", x)] = win("E", "T", x, normal, rules, seeds)
    C2 = {}
    for a in ("E", "I", "M", "R"):
        for x in budgets:
            if any(k[:2] == (a, x) for k in der):
                C2[(a, x)] = c2_rule(a, x, normal, der, rules, seeds)
    C1 = {(a, x): c1_rule(a, x, normal, rules, seeds) for a in ALL_ARMS for x in budgets}

    def ok(k):
        return bool(k.get("pass")) if k else False

    def valid_win(a, x):
        return ok(W[(a, "R", x)]) and ok(C2.get((a, x))) and ok(C1[(a, x)])

    H = {}
    for hid, a in (("H1", "E"), ("H2", "I"), ("H4", "M")):
        vw = {str(x): valid_win(a, x) for x in core}
        ran = all(W[(a, "R", x)]["status"] == "done" for x in core)
        H[hid] = {"arm": a, "valid_win": vw, "n": sum(vw.values()), "ran": ran,
                  "pass": (sum(vw.values()) >= nb) if ran else None}
    h1_b = [x for x in core if H["H1"]["valid_win"][str(x)]]
    t_ran = all(W[("T", "R", x)]["status"] == "done" for x in core)
    H["H3"] = {"budgets": h1_b, "per": {str(x): ok(W[("E0", "R", x)]) for x in h1_b},
               "pass": (all(ok(W[("E0", "R", x)]) for x in h1_b) if h1_b else None)}
    H["H5"] = {"budgets": h1_b, "ran": t_ran, "per": {str(x): ok(W[("E", "T", x)]) for x in h1_b},
               "pass": (all(ok(W[("E", "T", x)]) for x in h1_b) if (h1_b and t_ran) else None)}
    neg = {}
    for a in ("E", "I", "M"):
        ws = [W[("R", a, x)] for x in core]
        neg[a] = {"n": sum(ok(w) for w in ws), "pass": (sum(ok(w) for w in ws) >= nb)
                  if all(w["status"] == "done" for w in ws) else None}
    reads = {"R_top": tri(C2.get(("R", top), {}).get("pass")), "R_12": tri(C2.get(("R", 12), {}).get("pass"))}
    labels = []
    p = {k: bool(v.get("pass")) for k, v in H.items()}
    if p["H1"]:
        if H["H3"]["pass"] is True and (H["H5"]["pass"] is True or not t_ran):
            labels.append("A-trunk")
        if H["H3"]["pass"] is False:
            labels.append("A-head")
        if t_ran and H["H5"]["pass"] is False:
            labels.append("A-text")
    if p["H2"] and not p["H1"]:
        labels.append("I-only")
    if p["H4"]:
        labels.append("M-only" if not (p["H1"] or p["H2"]) else "M-also")
    if neg["E"]["pass"] or neg["I"]["pass"]:
        labels.append("C")
    tested = [a for a in ("E", "I", "M") if (a, top) in C2]
    would = [a for a in ("E", "I", "M") if sum(ok(W[(a, "R", x)]) for x in core) >= nb]
    n_reason = []
    for a in would:
        fails = sum(C2.get((a, x), {}).get("pass") is False for x in core)
        if fails >= nb:
            n_reason.append(f"C2 fails for would-be winner {a} at {fails} core budgets")
    if [a for a in ("E", "I", "M", "R") if (a, top) in C2] and not any(
            C2[(a, top)]["pass"] is True for a in ("E", "I", "M", "R") if (a, top) in C2):
        n_reason.append(f"no arm passes C2 at {top}")
    if n_reason:
        labels.insert(0, "N")
    if (not any(p[k] for k in ("H1", "H2", "H4")) and not any(neg[a]["pass"] for a in neg) and tested
            and all(C2[(a, top)]["pass"] is True for a in tested)):
        labels.append("D")
    main = labels[0] if labels else "none (C2 partly invalid)"
    table = {}
    for a in ALL_ARMS:
        for x in budgets:
            v = [normal[(a, x, s)]["test_cer_final"] for s in seeds if (a, x, s) in normal]
            if v:
                fw = [normal[(a, x, s)].get("falcon_wer_mean") for s in seeds if (a, x, s) in normal]
                table.setdefault(a, {})[str(x)] = {"mean_cer": float(np.mean(v)), "seeds": v, "n": len(v),
                                                   "falcon_wer_mean": float(np.mean(fw)) if None not in fw else None}
    ratio = {}
    for x in budgets:
        if ok(W[("P", "R", x)]) and "R" in table and str(x) in table["R"] and str(x) in table.get("P", {}):
            dp = table["R"][str(x)]["mean_cer"] - table["P"][str(x)]["mean_cer"]
            ratio[str(x)] = {a: (table["R"][str(x)]["mean_cer"] - table[a][str(x)]["mean_cer"]) / dp
                             for a in ALL_ARMS if a in table and str(x) in table[a] and a not in ("R", "P")}
    key = lambda k: "|".join(map(str, k))  # noqa: E731
    return {"table": table, "win": {key(k): v for k, v in W.items()}, "C2": {key(k): v for k, v in C2.items()},
            "C1": {key(k): v for k, v in C1.items() if v["pass"] is not None}, "H": H, "neg": neg, "reads": reads,
            "transfer_ratio": ratio, "outcome": {"label": main, "labels": labels, "N_reasons": n_reason}}


def run_name(arm: str, budget: int, seed: int, j: int | None = None) -> str:
    return f"{arm}-b{budget}-s{seed}" + ("" if j is None else f"-d{j}")


def stage2_plan(roles: dict, cfg: dict) -> list[dict]:
    """Ordered base runs (amendment 1, 3.14). Conditional C2 pairs (j = 1, 2) are added at run time."""
    s2 = cfg["stage2"]
    seeds = s2["seeds"]
    core = sorted(roles["core_budgets"], reverse=True)
    top = int(roles["top_budget"])
    out = []

    def add(part, arm, b, s, j=None):
        out.append({"part": part, "arm": arm, "budget": int(b), "seed": int(s), "j": j,
                    "dir": f"s2/{run_name(arm, b, s, j)}"})

    for s in seeds:
        for b in core:
            for a in s2["core_normal_arms"]:
                add("core", a, b, s)
    for s in seeds:
        for a in s2["core_c2_arms"]:
            for b in core:
                add("core", a, b, s, 0)
        add("core", "R", top, s, 0)
    ext_b = sorted(roles["extended_budgets"], reverse=True)
    groups = s2["ext_normal_groups"]
    for s in seeds:
        for b in ext_b:
            for a in groups[0]:
                add("ext", a, b, s)
    for grp in groups[1:]:
        for s in seeds:
            for b in core:
                for a in grp:
                    add("ext", a, b, s)
    for s in seeds:
        for b in core:
            add("ext", s2["ext_c2_arm"], b, s, 0)
    if int(s2["ext_c2_r_budget"]) in roles["core_budgets"] + roles["extended_budgets"]:
        for s in seeds:
            add("ext", "R", s2["ext_c2_r_budget"], s, 0)
    return out


def check_out(out: Path, derived: Path = DERIVED) -> bool:
    return F3.check_out(out, derived, own=OWN)


# =====================================================================================================================
# Model
# =====================================================================================================================


class SessionLayers(nn.Module):
    """One A_s per session of one channel space: dropout -> softsign(W_s x + b_s) -> dropout (Levin 2026, eq. 1)."""

    def __init__(self, n_sess: int, c: int, p: float):
        super().__init__()
        self.W = nn.Parameter(torch.eye(c).repeat(n_sess, 1, 1))
        self.b = nn.Parameter(torch.zeros(n_sess, c))
        self.drop = nn.Dropout(p)

    def forward(self, x: torch.Tensor, sess: torch.Tensor) -> torch.Tensor:
        z = torch.einsum("btc,bdc->btd", self.drop(x), self.W[sess]) + self.b[sess][:, None]
        return self.drop(F.softsign(z))


class Net(nn.Module):
    """inputs {dataset: (channels, n_sessions)} -> [A_s] -> P_in[dataset] -> E1a trunk -> LayerNorm -> head / readouts.
    Build order is fixed (adapters, p_in, blocks, out_norm, head, readouts) so that one seed gives one init."""

    def __init__(self, trunk: e1.TrunkCfg, inputs: dict, per_session: bool = True, vocab: int | None = 98,
                 readouts: dict | None = None, p_drop: float = 0.1):
        super().__init__()
        self.per_session = per_session
        if per_session:
            self.adapters = nn.ModuleDict({k: SessionLayers(n, c, p_drop) for k, (c, n) in inputs.items()})
        self.p_in = nn.ModuleDict({k: nn.Linear(c, trunk.d) for k, (c, _) in inputs.items()})
        self.blocks = nn.ModuleList(ED.CausalBlock(trunk.d, trunk.kernel, dl, trunk.ff_mult, trunk.dropout,
                                                   trunk.conv_impl) for dl in trunk.dilations)
        self.out_norm = nn.LayerNorm(trunk.d)
        self.head = nn.Linear(trunk.d, vocab) if vocab else None
        self.readouts = nn.ModuleDict({k: nn.Linear(trunk.d, n) for k, n in (readouts or {}).items()})

    def features(self, x: torch.Tensor, ds: str, sess: torch.Tensor) -> torch.Tensor:
        if self.per_session:
            x = self.adapters[ds](x, sess)
        h = self.p_in[ds](x)
        for b in self.blocks:
            h = b(h)
        return self.out_norm(h)

    def forward(self, x: torch.Tensor, ds: str, sess: torch.Tensor) -> torch.Tensor:
        return F.log_softmax(self.head(self.features(x, ds, sess)).float(), dim=-1)


TRUNK = ("blocks.", "out_norm.")
TRUNK_HEAD = ("blocks.", "out_norm.", "head.")


def copy_parts(model: Net, sd: dict, prefixes: tuple[str, ...]) -> int:
    """Copy the tensors under ``prefixes`` from sd into model (all must exist with the same shape)."""
    own = model.state_dict()
    need = [k for k in own if k.startswith(prefixes)]
    got = {k: v for k, v in sd.items() if k.startswith(prefixes)}
    if sorted(need) != sorted(got):
        raise KeyError(f"keys differ: missing {sorted(set(need) - set(got))[:3]}, extra {sorted(set(got) - set(need))[:3]}")
    for k, v in got.items():
        if own[k].shape != v.shape:
            raise ValueError(f"shape mismatch {k}: {tuple(own[k].shape)} vs {tuple(v.shape)}")
    model.load_state_dict({**own, **got})
    return len(got)


def normalise(x: torch.Tensor, sess: torch.Tensor, mean: torch.Tensor, std: torch.Tensor) -> torch.Tensor:
    return (x.float() - mean[sess][:, None]) / std[sess][:, None]


def norm_stats(arrays: list[tuple[int, np.ndarray]], n_sess: int, c: int, floor: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-session channel mean and SD (floor) from [(session, frames)]. Held frames give the same values."""
    s1 = np.zeros((n_sess, c)); s2 = np.zeros((n_sess, c)); n = np.zeros(n_sess)
    for s, x in arrays:
        xf = np.asarray(x, np.float64)
        s1[s] += xf.sum(0); s2[s] += (xf ** 2).sum(0); n[s] += len(xf)
    n = np.maximum(n, 1)[:, None]
    mean = s1 / n
    std = np.sqrt(np.maximum(s2 / n - mean ** 2, 0.0))
    return mean.astype(np.float32), np.maximum(std, floor).astype(np.float32)


# =====================================================================================================================
# Data: stage 0 (NWB -> caches) and stores
# =====================================================================================================================


def nwb_date(p: Path) -> str:
    return p.name.split("_ses-")[1][:8]


def read_h2_file(path: Path) -> tuple[np.ndarray, np.ndarray, list[dict], int]:
    """One H2 calibration NWB -> (uint8 20 ms counts of all trial bins, offsets, trial rows, n clipped values)."""
    import h5py

    with h5py.File(path, "r") as f:
        d = f["acquisition/binned_spikes/data"][:]
        ts = f["acquisition/binned_spikes/timestamps"][:]
        tr = f["intervals/trials"]
        st, sp = tr["start_time"][:], tr["stop_time"][:]
        cue = list(tr["cue"].asstr()[:])
        blk = tr["block_num"][:]
    order = np.argsort(st, kind="stable")
    xs, off, rows, clip = [], [0], [], 0
    for k, i in enumerate(order):
        a, b = int(np.searchsorted(ts, st[i], "left")), int(np.searchsorted(ts, sp[i], "left"))
        seg = d[a:b]
        clip += int((seg > 255).sum()) + int((seg < 0).sum())
        xs.append(np.clip(np.rint(seg), 0, 255).astype(np.uint8))
        off.append(off[-1] + len(seg))
        rows.append({"trial": k, "nwb_id": int(i), "block": int(blk[i]), "n_bins": int(len(seg)), "cue": str(cue[i])})
    return np.concatenate(xs), np.asarray(off, np.int64), rows, clip


def bin_spikes(f, t0: float, n: int, dt: float) -> np.ndarray:
    """NWB units table -> uint8 counts (n frames, units) in bins [t0 + k dt, t0 + (k + 1) dt)."""
    st = f["units/spike_times"][:]
    idx = f["units/spike_times_index"][:].astype(np.int64)
    lo = np.r_[0, idx[:-1]]
    out = np.zeros((n, len(idx)), np.uint8)
    for u in range(len(idx)):
        k = np.floor((st[lo[u]:idx[u]] - t0) / dt).astype(np.int64)
        k = k[(k >= 0) & (k < n)]
        out[:, u] = np.minimum(np.bincount(k, minlength=n), 255).astype(np.uint8)
    return out


def frame_mean(ts: np.ndarray, v: np.ndarray, t0: float, n: int, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Mean of the samples in each frame (rows with a non-finite value are dropped) and the mask of filled frames."""
    k = np.floor((ts - t0) / dt).astype(np.int64)
    good = (k >= 0) & (k < n) & np.all(np.isfinite(v), axis=1)
    k, v = k[good], v[good]
    cnt = np.bincount(k, minlength=n).astype(np.float64)
    y = np.stack([np.bincount(k, weights=v[:, c], minlength=n) for c in range(v.shape[1])], 1)
    y = y / np.maximum(cnt, 1)[:, None]
    return y.astype(np.float32), cnt > 0


def hold_series(ts: np.ndarray, v: np.ndarray, t0: float, n: int, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Sample-and-hold of a slower series onto the frame grid: frame k takes the last sample at or before its start."""
    tk = t0 + np.arange(n) * dt + 1e-9
    j = np.searchsorted(ts, tk, "right") - 1
    ok = j >= 0
    return v[np.maximum(j, 0)].astype(np.float32), ok


def read_m1_file(path: Path, dt: float) -> dict:
    import h5py

    with h5py.File(path, "r") as f:
        em = f["acquisition/preprocessed_emg"]
        names = sorted(em.keys())
        ts = em[names[0]]["timestamps"][:]
        y20 = np.stack([em[m]["data"][:] for m in names], 1)
        mts = f["acquisition/eval_mask/timestamps"][:]
        m20 = f["acquisition/eval_mask/data"][:].astype(bool)
        t0 = float(ts[0])
        n = int(math.floor((float(ts[-1]) + (ts[1] - ts[0]) - t0) / dt + 1e-6))
        x = bin_spikes(f, t0, n, dt)
    y, ok = hold_series(ts, y20, t0, n, dt)
    mk, ok2 = hold_series(mts, m20[:, None].astype(np.float32), t0, n, dt)
    mask = ok & ok2 & (mk[:, 0] > 0.5) & np.all(np.isfinite(y), axis=1)
    return {"x": x, "y": y, "mask": mask, "targets": names}


def read_nlb_file(path: Path, key: str, dt: float) -> dict:
    import h5py

    with h5py.File(path, "r") as f:
        g = f[f"processing/behavior/{key}"]
        v = g["data"][:]
        if "timestamps" in g:
            ts = g["timestamps"][:]
        else:
            ts = float(g["starting_time"][()]) + np.arange(len(v)) / float(g["starting_time"].attrs["rate"])
        t0 = float(ts[0])
        n = int(math.floor((float(ts[-1]) - t0) / dt)) + 1
        x = bin_spikes(f, t0, n, dt)
    y, mask = frame_mean(ts, v, t0, n, dt)
    return {"x": x, "y": y, "mask": mask, "targets": [f"{key}[{i}]" for i in range(v.shape[1])]}


class H2Store:
    """H2 calibration trials at 20 ms (uint8); ``frames(i)`` holds each bin twice (10 ms). meta rows: date, trial,
    block, n_bins, text. ``crop`` (smoke test only) keeps the first ``crop`` frames of each trial."""

    def __init__(self, meta: list[dict], arrays: dict[str, tuple[np.ndarray, np.ndarray]], hold: int = 2,
                 crop: int | None = None):
        self.meta, self.hold, self.crop = meta, hold, crop
        self.x20 = {}
        for i, r in enumerate(meta):
            xa, off = arrays[r["date"]]
            self.x20[i] = xa[off[r["row"]]:off[r["row"] + 1]]
        self.tgt = {i: e1.encode(r["text"]) for i, r in enumerate(meta)}
        self.length = {i: self._len(len(v)) for i, v in self.x20.items()}
        self.by_date: dict[str, list[int]] = {}
        for i, r in enumerate(meta):
            self.by_date.setdefault(r["date"], []).append(i)
        for d in self.by_date:
            self.by_date[d].sort(key=lambda i: meta[i]["trial"])

    def _len(self, nb: int) -> int:
        L = nb * self.hold
        return min(L, self.crop) if self.crop else L

    def frames(self, i: int, perm: np.ndarray | None = None) -> np.ndarray:
        x = np.repeat(self.x20[i], self.hold, axis=0)
        if self.crop:
            x = x[:self.crop]
        return x if perm is None else x[:, perm]

    @staticmethod
    def load(cache: Path, crop: int | None = None) -> "H2Store":
        meta = json.loads((cache / "meta.json").read_text(encoding="utf-8"))
        arrays = {}
        for d in sorted({r["date"] for r in meta}):
            z = np.load(cache / f"{d}.npz")
            arrays[d] = (z["x"], z["off"])
        return H2Store(meta, arrays, crop=crop)

    def split(self, dates: list[str], budget: int, test_last: int) -> tuple[list[int], list[int]]:
        """Train pool = first ``budget`` trials of each session; eval = last ``test_last`` trials (plan 4.3)."""
        pool, ev = [], []
        for d in dates:
            t = self.by_date[d]
            if budget + test_last > len(t):
                raise DataStop(f"session {d} has {len(t)} trials < {budget} + {test_last}")
            pool += t[:budget]
            ev += t[-test_last:]
        return pool, ev


def overlap_counts(store: H2Store, roles: dict) -> dict:
    """Plan 4.3: per budget, the number of test sentences whose text occurs in the run's train pool (counts only)."""
    out = {}
    for b in sorted(roles["core_budgets"] + roles["extended_budgets"]):
        pool, ev = store.split(roles["test"], b, roles["test_last"])
        texts = {store.meta[i]["text"] for i in pool}
        out[str(b)] = int(sum(store.meta[i]["text"] in texts for i in ev))
    return out


def p_trials(store: H2Store, roles: dict) -> tuple[list[int], int]:
    """Arm P pretraining trials: all trials of the source sessions minus texts equal to a val or test sentence."""
    held = set()
    for d in roles["val"] + roles["test"]:
        held |= {store.meta[i]["text"] for i in store.by_date[d][-roles["test_last"]:]}
    idx = [i for d in roles["source"] for i in store.by_date[d]]
    keep = [i for i in idx if store.meta[i]["text"] not in held]
    return keep, len(idx) - len(keep)


class MStore:
    """Arm M windows. data[ds] = list of sessions {x uint8 (T, C), y z-scored (T, k), mask (T,)}."""

    def __init__(self, data: dict[str, list[dict]], floor: float):
        self.data = data
        self.norm = {}
        for ds, ss in data.items():
            mean, std = norm_stats([(k, s["x"]) for k, s in enumerate(ss)], len(ss), ss[0]["x"].shape[1], floor)
            self.norm[ds] = (mean, std)
            for s in ss:
                yv = s["y"][s["mask"]]
                mu, sd = yv.mean(0), np.maximum(yv.std(0), 1e-6)
                s["yz"] = ((s["y"] - mu) / sd).astype(np.float32)

    @staticmethod
    def load(cache: Path, datasets: list[str], floor: float) -> "MStore":
        data = {}
        for ds in datasets:
            data[ds] = []
            for p in sorted(cache.glob(f"{ds}-*.npz")):
                z = np.load(p)
                data[ds].append({"x": z["x"], "y": z["y"], "mask": z["mask"]})
        return MStore(data, floor)

    def batch(self, ds: str, n: int, window: int, rng: np.random.Generator) -> dict:
        ss = self.data[ds]
        xs, ys, ms, sess = [], [], [], []
        for _ in range(n):
            k = int(rng.integers(len(ss)))
            T = len(ss[k]["x"])
            a = int(rng.integers(0, max(1, T - window)))
            xs.append(ss[k]["x"][a:a + window]); ys.append(ss[k]["yz"][a:a + window]); ms.append(ss[k]["mask"][a:a + window])
            sess.append(k)
        L = min(len(x) for x in xs)
        return {"x": np.stack([x[:L] for x in xs]).astype(np.float32), "y": np.stack([y[:L] for y in ys]),
                "mask": np.stack([m[:L] for m in ms]), "sess": np.asarray(sess, np.int64),
                "lengths": np.full(n, L, np.int64)}


def t15_norm(t15, floor: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-session mean and SD over the T15 train trials that arm I uses (amendment 1, 3.3)."""
    n = max(si for si, _, _ in t15.items) + 1 if t15.items else 0
    arrays = ((t15.items[k][0], t15.get(k)[0]) for k in range(len(t15.items)))
    return norm_stats(arrays, n, 512, floor)


def stage_prep(cfg: dict, out: Path, log, t15_sessions: int | None = None) -> dict:
    """Stage 0 (CPU). Writes caches, session_roles.json (dates, counts, roles; no neural or text values)."""
    c = out / "cache"
    if (c / "DONE.json").exists():
        return json.loads((out / "session_roles.json").read_text(encoding="utf-8"))
    (c / "h2").mkdir(parents=True, exist_ok=True)
    (c / "m").mkdir(parents=True, exist_ok=True)
    dt = float(cfg["pretrain"]["M"]["dt"])
    files = sorted(Path(cfg["raw"]["h2"]).glob("*.nwb"))
    meta, counts, clip = [], {}, 0
    for p in files:
        d = nwb_date(p)
        x, off, rows, cl = read_h2_file(p)
        clip += cl
        np.savez(c / "h2" / f"{d}.npz", x=x, off=off)
        counts[d] = len(rows)
        for k, r in enumerate(rows):
            meta.append({"date": d, "trial": r["trial"], "block": r["block"], "n_bins": r["n_bins"], "row": k,
                         "text": map_text(r["cue"], cfg["roles"]["symbol_map"])})
        log(f"[prep] H2 {d}: {len(rows)} trials")
    bad = check_symbols([r["text"] for r in meta])
    if bad:
        raise DataStop(f"{len(bad)} H2 symbols are not in the 98-token vocabulary")
    e1.save_json(meta, c / "h2" / "meta.json")
    roles = session_roles(counts, cfg["roles"])
    store = H2Store.load(c / "h2")
    keep, removed = p_trials(store, roles)
    for k, p in enumerate(sorted(Path(cfg["raw"]["m1"]).glob("*.nwb"))):
        r = read_m1_file(p, dt)
        np.savez(c / "m" / f"m1-{k}.npz", x=r["x"], y=r["y"], mask=r["mask"])
        log(f"[prep] M1-A {nwb_date(p)}: {r['x'].shape} frames x units, {int(r['mask'].sum())} masked-in frames")
    for ds, key in (("maze", "hand_vel"), ("rtt", "finger_vel")):
        r = read_nlb_file(Path(cfg["raw"][ds]), key, dt)
        np.savez(c / "m" / f"{ds}-0.npz", x=r["x"], y=r["y"], mask=r["mask"])
        log(f"[prep] {ds}: {r['x'].shape} frames x units, {int(r['mask'].sum())} frames with behaviour")
    t15 = F3.T15Store(Path(cfg["sources"]["t15_derived"]), cfg["pretrain"]["I"]["part"], max_sessions=t15_sessions)
    mean, std = t15_norm(t15, float(cfg["model"]["std_floor"]))
    np.savez(c / "t15_norm.npz", mean=mean, std=std)
    log(f"[prep] T15 norm stats: {len(mean)} sessions, {len(t15.items)} train trials")
    man = Path(cfg["raw"]["manifest"])
    data = None
    if man.exists():
        m = json.loads(man.read_text(encoding="utf-8"))
        data = {ds: {"files": sum(1 for x in m if x["dandiset"] == ds), "bytes": sum(x["size"] for x in m if x["dandiset"] == ds),
                     "sha256_ok": all(x["ok"] for x in m if x["dandiset"] == ds), "version": next(x["version"] for x in m if x["dandiset"] == ds)}
                for ds in sorted({x["dandiset"] for x in m})}
    rec = {"note": "P15-54 stage 0 (plan 4.2, amendment 1 point 1): session roles from trial counts only. No neural "
                   "value, no text. 'overlap' = test sentences whose text also occurs in the run's train pool "
                   "(counts only, not removed). 'p_removed' = arm-P source trials removed because their text equals a "
                   "val or test sentence.",
           **roles, "overlap": overlap_counts(store, roles), "p_trials": len(keep), "p_removed": removed,
           "h2_clipped_values": clip, "symbols_ok": True, "data": data,
           "t15_sessions": int(len(mean)), "t15_train_trials": int(len(t15.items))}
    e1.save_json(rec, out / "session_roles.json")
    e1.save_json({"time": time.strftime("%Y-%m-%dT%H:%M:%S")}, c / "DONE.json")
    log(f"[prep] DONE roles test {roles['test']} val {roles['val']} core {roles['core_budgets']} "
        f"ext {roles['extended_budgets']} fallback {roles['fallback']}")
    return rec


# =====================================================================================================================
# Training
# =====================================================================================================================


@dataclass
class Env:
    cfg: dict
    out: Path
    device: str
    trunk: e1.TrunkCfg
    roles: dict
    h2: H2Store | None = None
    clock: object | None = None
    max_frames_override: int | None = None
    gates: bool = True
    extra: dict = field(default_factory=dict)

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(self.out / "run.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def stop_requested(self) -> bool:
        return (self.out / "pause").exists() or (self.out / "stop").exists()

    def max_frames(self, key: str = "target") -> int:
        return self.max_frames_override or int(self.cfg[key]["max_frames"])


def aug_cfg(cfg: dict) -> e1.FTCfg:
    t = cfg["target"]
    return e1.FTCfg(noise_sd=t["noise_sd"], offset_sd=t["offset_sd"], time_masks=t["time_masks"],
                    time_mask_max=t["time_mask_max"])


def train_loop(env: Env, d: Path, tag: str, model: nn.Module, opt, total: int, lr: float, lr_min: float, warmup: int,
               clip: float, ckpt_minutes: float, step_fn, max_steps: int | None = None) -> dict:
    """Shared loop: resume from latest.pt, LR schedule, clip, checkpoint every ckpt_minutes, pause / stop file."""
    step, skipped = 0, 0
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=env.device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        step, skipped = int(ck["step"]), int(ck.get("skipped", 0))
        env.log(f"[{tag}] resume at step {step}")

    def save_latest():
        R8.atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step, "skipped": skipped},
                       d / "latest.pt")

    end = total if max_steps is None else min(total, step + max_steps)
    t_ck = t_log = time.time(); s_log = step; losses: list[float] = []
    while step < end:
        model.train()
        for g in opt.param_groups:
            g["lr"] = e1.lr_at(step, total, lr, lr_min, warmup)
        loss = step_fn(step)
        opt.zero_grad(set_to_none=True)
        if loss is not None and torch.isfinite(loss):
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), clip); opt.step()
            losses.append(float(loss.detach()))
        else:
            skipped += 1
        step += 1
        if step % 100 == 0 or step == end:
            dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
            env.log(f"[{tag}] step {step}/{total} loss {np.mean(losses) if losses else float('nan'):.4f} "
                    f"{dt:.3f} s/step skipped {skipped}")
            losses = []
        if time.time() - t_ck > 60 * ckpt_minutes:
            save_latest(); t_ck = time.time()
            if env.clock is not None:
                env.clock.save()
        if env.stop_requested():
            save_latest()
            env.log(f"[{tag}] pause/stop file: saved latest.pt at step {step}, exit")
            raise R8.Paused()
    if step < total:
        save_latest()
        return {"partial": True, "step": step}
    return {"steps": step, "skipped": skipped}


def licence(arm: str, cfg: dict, deranged: bool = False) -> dict:
    L = cfg["licences"]
    base = arm[2:] if arm.startswith("X-") else arm
    data = [L["h2"]] + {"R": [], "E": [L["emg"]], "E0": [L["emg"]], "T": [L["text"]], "I": [L["t15"]],
                        "M": [L["m1"], L["maze"], L["rtt"]], "P": []}[base]
    return {"arm": arm, "data": data, "research_only": base in ("E", "E0", "T"), "label_deranged": deranged}


def init_target(env: Env, arm: str, seed: int, n_sess: int) -> Net:
    """Amendment 1, 3.8: seed -> build every layer in one order -> copy the pretrained parts."""
    torch.manual_seed(seed)
    base = arm[2:] if arm.startswith("X-") else arm
    model = Net(env.trunk, {"h2": (int(env.cfg["model"]["n_h2"]), n_sess)}, per_session=not arm.startswith("X-"),
                vocab=98, p_drop=float(env.cfg["model"]["adapter_dropout"]))
    src = env.cfg["sources"]
    if base == "R":
        pass
    elif base in ("E", "E0"):
        sd = torch.load(src["e_checkpoint"], map_location="cpu", weights_only=True)["model"]
        copy_parts(model, sd, TRUNK_HEAD if base == "E" else TRUNK)
    elif base == "T":
        copy_parts(model, torch.load(src["t_checkpoint"], map_location="cpu", weights_only=True)["model"], TRUNK_HEAD)
    elif base in ("I", "M", "P"):
        sd = torch.load(env.out / f"pretrain-{base}" / "final.pt", map_location="cpu", weights_only=True)["model"]
        copy_parts(model, sd, TRUNK_HEAD if base == "P" else TRUNK)
    else:
        raise ValueError(arm)
    return model.to(env.device)


@torch.no_grad()
def evaluate(env: Env, model: Net, idx: list[int], sess_of: dict, mean, std, shuffle_seed: int | None = None) -> dict:
    """Greedy CTC on whole trials (batched; post-padding does not change earlier causal outputs)."""
    model.eval()
    h2 = env.h2
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    xs = {}
    for i in idx:
        x = h2.frames(i)
        xs[i] = x[rng.permutation(len(x))] if rng is not None else x
    order = sorted(idx, key=lambda i: h2.length[i])
    res = {}
    k = 0
    while k < len(order):
        grp = [order[k]]; k += 1
        while k < len(order) and h2.length[order[k]] * (len(grp) + 1) <= env.max_frames():
            grp.append(order[k]); k += 1
        b = e1.collate([(xs[i], h2.tgt[i], sess_of[i]) for i in grp])
        sess = torch.from_numpy(b["sess"]).to(env.device)
        lp = model(normalise(torch.from_numpy(b["x"]).to(env.device), sess, mean, std), "h2", sess).cpu().numpy()
        for j, i in enumerate(grp):
            hyp = ED.greedy(lp[j, :h2.length[i]])
            ref = h2.tgt[i]
            rw, hw = e1.decode(ref).split(), e1.decode(hyp).split()
            vocab = {w: n for n, w in enumerate(sorted(set(rw) | set(hw)))}
            res[i] = (ED.levenshtein(ref, hyp), len(ref), ED.levenshtein([vocab[w] for w in rw], [vocab[w] for w in hw]),
                      len(rw))
    ed = [res[i][0] for i in idx]; ref = [res[i][1] for i in idx]
    per = {}
    for i in idx:
        p = per.setdefault(h2.meta[i]["date"], [0, 0, 0, 0])
        for q in range(4):
            p[q] += res[i][q]
    ps = {d: {"cer": v[0] / max(1, v[1]), "wer": v[2] / max(1, v[3])} for d, v in per.items()}
    return {"cer": e1.pooled_cer(ed, ref), "edits": ed, "ref": ref, "per_session": ps,
            "falcon_cer_mean": float(np.mean([v["cer"] for v in ps.values()])),
            "falcon_wer_mean": float(np.mean([v["wer"] for v in ps.values()]))}


def target_run(env: Env, spec: dict, max_steps: int | None = None) -> dict:
    """One target run. spec: stage ('s1' / 's2'), arm, budget, seed, j (None = normal), lr, dir, sessions."""
    d = env.out / spec["dir"]
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    cfg, t = env.cfg, env.cfg["target"]
    arm, budget, seed, j, lr = spec["arm"], int(spec["budget"]), int(spec["seed"]), spec["j"], float(spec["lr"])
    dates = list(spec["sessions"])
    pool, ev = env.h2.split(dates, budget, int(env.roles["test_last"]))
    sidx = {dd: k for k, dd in enumerate(dates)}
    sess_of = {i: sidx[env.h2.meta[i]["date"]] for i in pool + ev}
    mean, std = norm_stats([(sess_of[i], env.h2.x20[i]) for i in pool], len(dates), int(cfg["model"]["n_h2"]),
                           float(cfg["model"]["std_floor"]))
    mean_t, std_t = torch.from_numpy(mean).to(env.device), torch.from_numpy(std).to(env.device)
    tgt = {i: env.h2.tgt[i] for i in pool}
    if j is not None:
        perm = e1.derangement(len(pool), np.random.default_rng([seed, int(cfg["rules"]["c2_rng"]) + int(j)]))
        tgt = {pool[k]: env.h2.tgt[pool[int(perm[k])]] for k in range(len(pool))}
    model = init_target(env, arm, seed, len(dates))
    opt = R8.make_optim(model, float(t["weight_decay"]), lr)
    total = int(t["steps"][str(budget)])
    aug = aug_cfg(cfg)
    e1.save_json(licence(arm, cfg, j is not None), d / "licence.json")
    jcode = 0 if j is None else int(j) + 1
    stage_code = 1 if spec["stage"] == "s1" else 2

    def step_fn(step):
        rng = np.random.default_rng([seed, budget, jcode, stage_code, step])
        gen = torch.Generator().manual_seed(int(rng.integers(2 ** 62)))
        torch.manual_seed(int(rng.integers(2 ** 62)))
        bi = e1.pack_batch(pool, env.h2.length, env.max_frames(), rng)
        b = e1.collate([(env.h2.frames(i), tgt[i], sess_of[i]) for i in bi])
        sess = torch.from_numpy(b["sess"]).to(env.device)
        x = normalise(torch.from_numpy(b["x"]).to(env.device), sess, mean_t, std_t)
        x = e1.augment_w(x, torch.from_numpy(b["lengths"]), aug, gen)
        lp = model(x, "h2", sess)
        return F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(env.device),
                          torch.from_numpy(b["lengths"]), torch.from_numpy(b["target_lengths"]),
                          blank=e1.BLANK, reduction="mean", zero_infinity=True)

    name = spec["dir"]
    env.log(f"[{name}] start, lr {lr:g}, steps {total}, {len(pool)} train trials, {len(dates)} sessions"
            + (f", GPU clock {env.clock.hours():.2f} h" if env.clock is not None else ""))
    r = train_loop(env, d, name, model, opt, total, lr, float(t["lr_min"]), int(t["warmup"]), float(t["clip"]),
                   float(t["ckpt_minutes"]), step_fn, max_steps)
    if r.get("partial"):
        return r
    R8.atomic_save({"model": model.state_dict(), "step": total}, d / "final.pt")
    res = {"run": name, "stage": spec["stage"], "arm": arm, "budget": budget, "seed": seed, "j": j,
           "label_deranged": j is not None, "lr": lr, "steps": r["steps"], "skipped": r["skipped"],
           "n_train": len(pool), "sessions": dates}
    fin = evaluate(env, model, ev, sess_of, mean_t, std_t)
    if spec["stage"] == "s1":  # val sessions only (plan 7.2): no test session is read in stage 1
        res.update({"val_cer_final": fin["cer"], "val_falcon_cer_mean": fin["falcon_cer_mean"]})
        msg = f"val CER {fin['cer']:.4f}"
    else:
        res.update({"test_cer_final": fin["cer"], "test_edits_final": fin["edits"], "test_ref": fin["ref"],
                    "per_session": fin["per_session"], "falcon_cer_mean": fin["falcon_cer_mean"],
                    "falcon_wer_mean": fin["falcon_wer_mean"]})
        if j is None:
            res["c1_shuffled_cer"] = evaluate(env, model, ev, sess_of, mean_t, std_t,
                                              shuffle_seed=int(cfg["rules"]["c1_seed"]))["cer"]
        msg = f"test CER {fin['cer']:.4f}" + (f" C1 {res['c1_shuffled_cer']:.4f}" if "c1_shuffled_cer" in res else "")
    e1.save_json(res, d / "result.json")
    e1.save_json({"done": time.strftime("%Y-%m-%dT%H:%M:%S")}, d / "DONE.json")
    (d / "latest.pt").unlink(missing_ok=True)
    env.log(f"[{name}] DONE {msg}")
    if env.clock is not None:
        env.clock.save()
    return res


# --- pretraining ------------------------------------------------------------------------------------------------------


def pretrain(env: Env, arm: str, model: Net, batch_at, loss_fn, meta: dict, max_steps: int | None = None) -> dict:
    """Arms I, M, P pretraining (plan 6): AdamW, LR 1e-3, warmup 1,000, cosine to 1e-6, last step kept."""
    pc = env.cfg["pretrain"]
    d = env.out / f"pretrain-{arm}"
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "DONE.json").read_text(encoding="utf-8"))
    total = int(env.extra.get("pretrain_steps", pc["steps"]))
    warm = min(int(pc["warmup"]), max(1, total // 4))
    model = model.to(env.device)
    opt = R8.make_optim(model, float(pc["weight_decay"]), float(pc["lr"]))
    e1.save_json({"pretrain": pc, "trunk": e1.cfg_json(env.trunk), "steps": total, **meta}, d / "config.json")
    e1.save_json(licence(arm, env.cfg) | {"data": licence(arm, env.cfg)["data"][1:] or licence(arm, env.cfg)["data"]},
                 d / "licence.json")
    pool = ThreadPoolExecutor(1)
    futs: dict = {}

    def step_fn(step):
        for k in range(step, min(total, step + 3)):
            if k not in futs:
                futs[k] = pool.submit(batch_at, k)
        b = futs.pop(step).result()
        torch.manual_seed(int(b["torch_seed"]))
        return loss_fn(b)

    env.log(f"[pretrain-{arm}] start, {total} steps" + (f", GPU clock {env.clock.hours():.2f} h" if env.clock else ""))
    try:
        r = train_loop(env, d, f"pretrain-{arm}", model, opt, total, float(pc["lr"]), float(pc["lr_min"]), warm,
                       float(pc["clip"]), float(pc["ckpt_minutes"]), step_fn, max_steps)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if r.get("partial"):
        return r
    R8.atomic_save({"model": model.state_dict(), "step": total}, d / "final.pt")
    rec = {"steps": r["steps"], "skipped": r["skipped"], **meta, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    e1.save_json(rec, d / "DONE.json")
    (d / "latest.pt").unlink(missing_ok=True)
    env.log(f"[pretrain-{arm}] DONE {rec}")
    if env.clock is not None:
        env.clock.save()
    return rec


def pretrain_i(env: Env, t15=None, max_steps: int | None = None) -> dict:
    pc, ic = env.cfg["pretrain"], env.cfg["pretrain"]["I"]
    if (env.out / "pretrain-I" / "DONE.json").exists():
        return json.loads((env.out / "pretrain-I" / "DONE.json").read_text(encoding="utf-8"))
    t15 = t15 or F3.T15Store(Path(env.cfg["sources"]["t15_derived"]), ic["part"])
    z = np.load(env.out / "cache" / "t15_norm.npz")
    n_sess = len(z["mean"])
    mean_t, std_t = torch.from_numpy(z["mean"]).to(env.device), torch.from_numpy(z["std"]).to(env.device)
    hold = int(ic["hold"])
    idx = [k for k in range(len(t15.items)) if t15.items[k][0] < n_sess]
    length = {k: t15.length[k] * hold for k in idx}
    aug = aug_cfg(env.cfg)
    torch.manual_seed(int(pc["seed"]))
    model = Net(env.trunk, {"t15": (int(ic["n_in"]), n_sess)}, vocab=int(ic["vocab"]),
                p_drop=float(env.cfg["model"]["adapter_dropout"]))

    def batch_at(k):
        rng = np.random.default_rng([int(pc["seed"]), 41, k])
        gs, ts = int(rng.integers(2 ** 62)), int(rng.integers(2 ** 62))
        bi = e1.pack_batch(idx, length, env.max_frames("pretrain"), rng)
        items = []
        for q in bi:
            x, ph = t15.get(q)
            items.append((np.repeat(np.asarray(x, np.float32), hold, axis=0), ph, t15.items[q][0]))
        return {"gen_seed": gs, "torch_seed": ts, **e1.collate(items)}

    def loss_fn(b):
        gen = torch.Generator().manual_seed(int(b["gen_seed"]))
        sess = torch.from_numpy(b["sess"]).to(env.device)
        x = e1.augment_w(normalise(torch.from_numpy(b["x"]).to(env.device), sess, mean_t, std_t),
                         torch.from_numpy(b["lengths"]), aug, gen)
        lp = model(x, "t15", sess)
        return F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(env.device),
                          torch.from_numpy(b["lengths"]), torch.from_numpy(b["target_lengths"]),
                          blank=0, reduction="mean", zero_infinity=True)

    return pretrain(env, "I", model, batch_at, loss_fn, {"n_trials": len(idx), "n_sessions": n_sess}, max_steps)


def pretrain_p(env: Env, max_steps: int | None = None) -> dict:
    pc = env.cfg["pretrain"]
    if (env.out / "pretrain-P" / "DONE.json").exists():
        return json.loads((env.out / "pretrain-P" / "DONE.json").read_text(encoding="utf-8"))
    h2, roles = env.h2, env.roles
    idx, removed = p_trials(h2, roles)
    sidx = {dd: k for k, dd in enumerate(roles["source"])}
    sess_of = {i: sidx[h2.meta[i]["date"]] for i in idx}
    perm = np.random.default_rng(int(pc["P"]["perm_seed"])).permutation(int(env.cfg["model"]["n_h2"]))
    mean, std = norm_stats([(sess_of[i], h2.x20[i][:, perm]) for i in idx], len(sidx), len(perm),
                           float(env.cfg["model"]["std_floor"]))
    mean_t, std_t = torch.from_numpy(mean).to(env.device), torch.from_numpy(std).to(env.device)
    aug = aug_cfg(env.cfg)
    torch.manual_seed(int(pc["seed"]))
    model = Net(env.trunk, {"h2": (len(perm), len(sidx))}, vocab=98, p_drop=float(env.cfg["model"]["adapter_dropout"]))

    def batch_at(k):
        rng = np.random.default_rng([int(pc["seed"]), 61, k])
        gs, ts = int(rng.integers(2 ** 62)), int(rng.integers(2 ** 62))
        bi = e1.pack_batch(idx, h2.length, env.max_frames("pretrain"), rng)
        return {"gen_seed": gs, "torch_seed": ts, **e1.collate([(h2.frames(i, perm), h2.tgt[i], sess_of[i]) for i in bi])}

    def loss_fn(b):
        gen = torch.Generator().manual_seed(int(b["gen_seed"]))
        sess = torch.from_numpy(b["sess"]).to(env.device)
        x = e1.augment_w(normalise(torch.from_numpy(b["x"]).to(env.device), sess, mean_t, std_t),
                         torch.from_numpy(b["lengths"]), aug, gen)
        lp = model(x, "h2", sess)
        return F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(env.device),
                          torch.from_numpy(b["lengths"]), torch.from_numpy(b["target_lengths"]),
                          blank=e1.BLANK, reduction="mean", zero_infinity=True)

    return pretrain(env, "P", model, batch_at, loss_fn,
                    {"n_trials": len(idx), "n_removed": removed, "n_sessions": len(sidx)}, max_steps)


def pretrain_m(env: Env, mstore: MStore | None = None, max_steps: int | None = None) -> dict:
    pc, mc = env.cfg["pretrain"], env.cfg["pretrain"]["M"]
    if (env.out / "pretrain-M" / "DONE.json").exists():
        return json.loads((env.out / "pretrain-M" / "DONE.json").read_text(encoding="utf-8"))
    ms = mstore or MStore.load(env.out / "cache" / "m", mc["datasets"], float(env.cfg["model"]["std_floor"]))
    dss = list(mc["datasets"])
    norm = {ds: tuple(torch.from_numpy(a).to(env.device) for a in ms.norm[ds]) for ds in dss}
    aug = aug_cfg(env.cfg)
    torch.manual_seed(int(pc["seed"]))
    inputs = {ds: (ms.data[ds][0]["x"].shape[1], len(ms.data[ds])) for ds in dss}
    model = Net(env.trunk, inputs, vocab=None, readouts={ds: ms.data[ds][0]["y"].shape[1] for ds in dss},
                p_drop=float(env.cfg["model"]["adapter_dropout"]))
    window = int(env.extra.get("m_window", mc["window"]))
    n_win = max(1, env.max_frames("pretrain") // window) if env.max_frames_override else int(mc["n_windows"])

    def batch_at(k):
        rng = np.random.default_rng([int(pc["seed"]), 51, k])
        gs, ts = int(rng.integers(2 ** 62)), int(rng.integers(2 ** 62))
        ds = dss[k % len(dss)]
        return {"gen_seed": gs, "torch_seed": ts, "ds": ds, **ms.batch(ds, n_win, window, rng)}

    def loss_fn(b):
        ds = b["ds"]
        gen = torch.Generator().manual_seed(int(b["gen_seed"]))
        sess = torch.from_numpy(b["sess"]).to(env.device)
        x = e1.augment_w(normalise(torch.from_numpy(b["x"]).to(env.device), sess, *norm[ds]),
                         torch.from_numpy(b["lengths"]), aug, gen)
        pred = model.readouts[ds](model.features(x, ds, sess)).float()
        m = torch.from_numpy(b["mask"]).to(env.device)
        if not bool(m.any()):
            return None
        y = torch.from_numpy(b["y"]).to(env.device)
        return ((pred - y) ** 2).mean(-1)[m].mean()

    meta = {"datasets": {ds: {"sessions": len(ms.data[ds]), "channels": inputs[ds][0],
                              "targets": ms.data[ds][0]["y"].shape[1],
                              "frames": int(sum(len(s["x"]) for s in ms.data[ds]))} for ds in dss}}
    return pretrain(env, "M", model, batch_at, loss_fn, meta, max_steps)


# =====================================================================================================================
# Stages
# =====================================================================================================================


def committed(repo_file: Path, derived_file: Path, root: Path = ROOT) -> tuple[bool, str]:
    """The repo copy equals the derived file, is in HEAD, and its last commit is on origin/main."""
    try:
        rel = repo_file.resolve().relative_to(root.resolve()).as_posix()
        mine = json.loads(derived_file.read_text(encoding="utf-8"))
        if json.loads(repo_file.read_text(encoding="utf-8")) != mine:
            return False, f"{rel} differs from {derived_file}"
        git = ["git", "-C", str(root)]
        head = subprocess.run(git + ["show", f"HEAD:{rel}"], capture_output=True, text=True, encoding="utf-8")
        if head.returncode != 0 or json.loads(head.stdout) != mine:
            return False, f"{rel} is not committed in HEAD"
        c = subprocess.run(git + ["log", "-1", "--format=%H", "--", rel], capture_output=True, text=True).stdout.strip()
        anc = subprocess.run(git + ["merge-base", "--is-ancestor", c, "refs/remotes/origin/main"], capture_output=True)
        if not c or anc.returncode != 0:
            return False, f"{rel}: commit not on origin/main yet"
        return True, c
    except Exception as ex:  # noqa: BLE001
        return False, repr(ex)


def publish(env: Env, name: str) -> None:
    """Copy an aggregate file (no text, no neural values) from --out to results/ (real run only)."""
    if env.out.resolve() == OUT.resolve():
        RESULTS.mkdir(parents=True, exist_ok=True)
        src = json.loads((env.out / name).read_text(encoding="utf-8"))
        if not (RESULTS / name).exists() or json.loads((RESULTS / name).read_text(encoding="utf-8")) != src:
            e1.save_json(src, RESULTS / name)


def gate(env: Env, name: str) -> bool:
    if not env.gates:
        return True
    publish(env, name)
    ok, why = committed(RESULTS / name, env.out / name)
    env.log(f"[gate] {name}: " + (f"committed in {why}" if ok else f"waits: {why} (commit + push it, then re-launch)"))
    return ok


def cap_check(env: Env, part: str) -> None:
    caps = env.cfg["caps"]
    h = env.clock.hours() if env.clock is not None else 0.0
    if h >= float(caps["total_hours"]):
        raise CapReached("total")
    if part == "core" and h >= float(caps["core_hours"]):
        raise CapReached("core")


def lr_for(sel: dict, cfg: dict, arm: str) -> float:
    src = cfg["stage1"]["lr_of"][arm]
    return float(sel["arms"][src]["chosen"]["lr"])


def stage1(env: Env, arms: list[str], fname: str, max_steps: int | None = None) -> dict | None:
    c = env.cfg["stage1"]
    for arm in arms:
        for lr in c["lrs"]:
            cap_check(env, "core" if fname == "selection.json" else "ext")
            r = target_run(env, {"stage": "s1", "arm": arm, "budget": c["budget"], "seed": c["seed"], "j": None,
                                 "lr": lr, "sessions": env.roles["val"],
                                 "dir": f"s1/{arm}-lr{lr:g}-b{c['budget']}-s{c['seed']}"}, max_steps)
            if r.get("partial"):
                return None
    sel = {"note": "P15-54 stage 1 (plan 7.2): per arm the LR with the lower final-step val CER (30 val sentences, "
                   "3 val sessions, 12 train sentences each, tuning seed 10); > 0.95 excluded; tie (< 0.005) -> smaller "
                   "LR; both excluded -> 3e-4. Val only; no test session is read in stage 1.",
           "arms": {}, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    for arm in arms:
        vals = {}
        for lr in c["lrs"]:
            rr = json.loads((env.out / f"s1/{arm}-lr{lr:g}-b{c['budget']}-s{c['seed']}" / "result.json")
                            .read_text(encoding="utf-8"))
            vals[float(lr)] = float(rr["val_cer_final"])
        sel["arms"][arm] = {"val_cer": {f"{k:g}": v for k, v in vals.items()}, "chosen": select_lr(vals, c)}
    if (env.out / fname).exists():  # never overwrite a written selection
        return json.loads((env.out / fname).read_text(encoding="utf-8"))
    e1.save_json(sel, env.out / fname)
    env.log(f"[select] {fname}: " + json.dumps({a: v["chosen"]["lr"] for a, v in sel["arms"].items()}))
    return sel


def load_runs(env: Env, plan: list[dict]) -> tuple[dict, dict, list[dict]]:
    normal, der, rows = {}, {}, []
    seen = set()
    for r in plan:
        for j in ([None] if r["j"] is None else range(1 + int(env.cfg["rules"]["c2_extra"]))):
            name = run_name(r["arm"], r["budget"], r["seed"], j)
            if name in seen:
                continue
            seen.add(name)
            p = env.out / "s2" / name / "result.json"
            row = {"run": name, "part": r["part"], "arm": r["arm"], "budget": r["budget"], "seed": r["seed"], "j": j}
            if not p.exists():
                if j is None or j == 0:
                    rows.append({**row, "status": "not_run"})
                continue
            res = json.loads(p.read_text(encoding="utf-8"))
            if res["arm"] != r["arm"] or int(res["budget"]) != r["budget"] or res["j"] != j:
                raise RuntimeError(f"{p.parent} does not match its plan row")
            if j is None:
                normal[(r["arm"], r["budget"], r["seed"])] = res
            else:
                der[(r["arm"], r["budget"], r["seed"], j)] = float(res["test_cer_final"])
            rows.append({**row, "status": "done", "lr": res["lr"], "steps": res["steps"], "skipped": res["skipped"],
                         "test_cer_final": res["test_cer_final"], "falcon_cer_mean": res.get("falcon_cer_mean"),
                         "falcon_wer_mean": res.get("falcon_wer_mean"), "c1_shuffled_cer": res.get("c1_shuffled_cer")})
    return normal, der, rows


def stage2(env: Env, plan: list[dict], part: str, sel: dict, max_steps: int | None = None) -> bool:
    rules = env.cfg["rules"]
    for r in [x for x in plan if x["part"] == part]:
        js = [r["j"]]
        k = 0
        while k < len(js):
            j = js[k]; k += 1
            cap_check(env, part)
            spec = {**r, "stage": "s2", "j": j, "lr": lr_for(sel, env.cfg, r["arm"]), "sessions": env.roles["test"],
                    "dir": f"s2/{run_name(r['arm'], r['budget'], r['seed'], j)}"}
            res = target_run(env, spec, max_steps)
            if res.get("partial"):
                return False
            if j == 0:
                nd = env.out / "s2" / run_name(r["arm"], r["budget"], r["seed"]) / "result.json"
                if nd.exists():
                    normal = json.loads(nd.read_text(encoding="utf-8"))["test_cer_final"]
                    if c2_triggers_extra(normal, res["test_cer_final"], rules):
                        env.log(f"[{spec['dir']}] C2 margin within +-{rules['c2_band']}: 2 more deranged runs")
                        js += list(range(1, 1 + int(rules["c2_extra"])))
    return True


def stage_summary(env: Env, status: str, sel: dict | None, sel_ext: dict | None) -> dict:
    plan = stage2_plan(env.roles, env.cfg)
    normal, der, rows = load_runs(env, plan)
    v = verdict(normal, der, env.roles, env.cfg["rules"], env.cfg["stage2"]["seeds"])
    pre = {a: json.loads((env.out / f"pretrain-{a}" / "DONE.json").read_text(encoding="utf-8"))
           for a in ("I", "M", "P") if (env.out / f"pretrain-{a}" / "DONE.json").exists()}
    agg = {"note": "P15-54 aggregate only (plan 19ec6c5, amendment 1 4d31f8e): pooled test CER over the 50 test sentences "
                   "(last 10 trials of 5 H2 held-in sessions), greedy CTC, no LM, final step. Not comparable with the "
                   "FALCON leaderboard. Every pretrained arm except P differs from T5 in person (E: person and signal; "
                   "I: person and task; M: species and task); E, E0, T and X-E are research only.",
           "status": status, "gpu_hours": round(env.clock.hours(), 3) if env.clock is not None else None,
           "roles": {k: env.roles[k] for k in ("test", "val", "core_budgets", "extended_budgets", "fallback")},
           "selection": {a: x["chosen"] for a, x in (sel or {}).get("arms", {}).items()},
           "selection_ext": {a: x["chosen"] for a, x in (sel_ext or {}).get("arms", {}).items()},
           "pretrain": pre, **v, "runs": rows, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    agg = json.loads(json.dumps(agg, default=float))
    e1.save_json(agg, env.out / "summary.json")
    if env.out.resolve() == OUT.resolve():
        RESULTS.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, RESULTS / "summary.json")
    env.log(f"[summary] outcome {agg['outcome']}")
    return agg


def make_env(cfg: dict, out: Path, device: str, roles: dict, crop: int | None = None) -> Env:
    t = dict(cfg["trunk"]); t["dilations"] = tuple(t["dilations"])
    env = Env(cfg=cfg, out=out, device=device, trunk=e1.TrunkCfg(**t), roles=roles)
    env.h2 = H2Store.load(out / "cache" / "h2", crop=crop)
    return env


def run_all(env: Env, max_steps: int | None = None, t15=None) -> int:
    """Stages after prep and gate0. Returns an exit code."""
    cap_check(env, "core")
    if pretrain_i(env, t15=t15, max_steps=max_steps).get("partial"):
        return 0
    sel = stage1(env, env.cfg["stage1"]["arms"], "selection.json", max_steps)
    if sel is None:
        return 0
    if not gate(env, "selection.json"):
        return WAITING
    plan = stage2_plan(env.roles, env.cfg)
    try:
        if not stage2(env, plan, "core", sel, max_steps):
            return 0
    except CapReached as ex:
        if str(ex) != "core":
            raise
        env.log(f"[cap] core cap {env.cfg['caps']['core_hours']} h reached: remaining core runs 'not run (cap)'")
    cap_check(env, "ext")
    if pretrain_m(env, mstore=env.extra.get("mstore"), max_steps=max_steps).get("partial"):
        return 0
    sel_ext = stage1(env, env.cfg["stage1"]["ext_arms"], "selection-ext.json", max_steps)
    if sel_ext is None:
        return 0
    cap_check(env, "ext")
    if pretrain_p(env, max_steps=max_steps).get("partial"):
        return 0
    if not gate(env, "selection-ext.json"):
        return WAITING
    if not stage2(env, plan, "ext", {"arms": {**sel["arms"], **sel_ext["arms"]}}, max_steps):
        return 0
    stage_summary(env, "done", sel, sel_ext)
    (env.out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
    env.log("ALL DONE")
    return 0


def read_opt(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-54 F3 small-data runner")
    ap.add_argument("stage", choices=("all", "prep", "gate", "summary", "smoke"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--smoke-steps", type=int, default=3)
    ap.add_argument("--smoke-crop", type=int, default=300)
    ap.add_argument("--smoke-max-frames", type=int, default=1500)
    ap.add_argument("--smoke-t15-sessions", type=int, default=2)
    ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if not check_out(out):
        print(f"never write into {out}", file=sys.stderr)
        return 2
    smoke = a.stage == "smoke"
    if smoke and out == OUT.resolve():
        print("smoke needs another --out (not the result folder)", file=sys.stderr)
        return 2
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(a.threads)
    logenv = Env(cfg=cfg, out=out, device=a.device, trunk=e1.TrunkCfg(), roles={})
    logenv.log(f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    if a.stage in ("all", "smoke") and (out / "DONE").exists():
        logenv.log("DONE exists: the run is finished")
        return 0
    try:
        roles = stage_prep(cfg, out, logenv.log, t15_sessions=a.smoke_t15_sessions if smoke else None)
    except DataStop as ex:
        logenv.log(f"DATA STOP: {ex}")
        (out / "STOPPED").write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {ex}", encoding="utf-8")
        return DATA_STOP
    if a.stage == "prep":
        if out == OUT.resolve():
            publish(Env(cfg=cfg, out=out, device=a.device, trunk=e1.TrunkCfg(), roles=roles), "session_roles.json")
        return 0
    env = make_env(cfg, out, a.device, roles, crop=a.smoke_crop if smoke else None)
    if a.stage == "gate":
        oks = [gate(env, n) for n in ("session_roles.json", "selection.json", "selection-ext.json")
               if (out / n).exists()]
        return 0 if all(oks) else WAITING
    if a.stage == "summary":
        stage_summary(env, "summary", read_opt(out / "selection.json"), read_opt(out / "selection-ext.json"))
        return 0
    if smoke:
        env.gates = False
        env.max_frames_override = a.smoke_max_frames
        n = a.smoke_steps
        cfg["target"]["steps"] = {k: n for k in cfg["target"]["steps"]}
        cfg["target"]["warmup"] = 1
        env.extra["pretrain_steps"] = n
        env.extra["m_window"] = 300
        cfg["stage2"]["seeds"] = [0]
    elif not gate(env, "session_roles.json"):
        return WAITING
    env.clock = F3.Clock(out / "gpu_clock.json")
    R8.keep_awake(True)
    t15 = F3.T15Store(Path(cfg["sources"]["t15_derived"]), "train", max_sessions=a.smoke_t15_sessions) if smoke else None
    try:
        return run_all(env, t15=t15)
    except R8.Paused:
        return PAUSED
    except CapReached:
        env.log(f"GPU cap {cfg['caps']['total_hours']} h reached: stop (plan 11); remaining runs 'not run (cap)'")
        stage_summary(env, "cap", read_opt(out / "selection.json"), read_opt(out / "selection-ext.json"))
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    except DataStop as ex:
        env.log(f"DATA STOP: {ex}")
        (out / "STOPPED").write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {ex}", encoding="utf-8")
        return DATA_STOP
    except Exception as ex:  # noqa: BLE001
        env.log(f"FAILED: {ex!r}")
        (out / "FAILED").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + f" {ex!r}", encoding="utf-8")
        raise
    finally:
        env.clock.save()
        R8.keep_awake(False)


if __name__ == "__main__":
    sys.exit(main())
