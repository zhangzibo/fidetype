"""Shared code of the M3-01 / M3-02 ablations (CPU only). See plan.md.

Re-uses the Paper 1 analysis stack (R4 ``common4`` -> R3 ``common3`` -> R1
``common``): item tables (``M13.item_table``), the CRC / LTT thresholds and
the exact Clopper-Pearson helpers. This module adds:

- the arm definitions of plan.md section 2;
- ``fit_four``: the four pipelines {calibration on, off} x {guard on, off}
  of one split, plus the "conformal off" and "declaration mismatch"
  variants of the v4 pipeline;
- ``arm_rows``: per-arm outcomes on a test table (gate and monitor
  applied after the threshold), with CP95 and exact McNemar vs v4;
- ``control_rows``: per-arm commit counts on control streams;
- ``zero_standin``: the zero-input stand-in (every frame = the first frame).

No signal, text or participant data is written by this module.
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
R4 = REPO / "experiments/2026-11-12-paper1-r4-analyses"
sys.path.insert(0, str(R4))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
CACHE5 = Path("C:/Users/zhang/bci-data/cache/m3-02-ablations")
CACHE5.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
ALPHA, DELTA = 0.05, 0.1
INF = math.inf

# Monitor settings (plan.md, arm 12; same as experiments/2026-11-13-a2-per-session-risk).
MON = dict(alpha=0.05, gamma=0.1, alternatives=(0.075, 0.1, 0.15, 0.2, 0.3), max_bet_fraction=0.5)
GATE_B = dict(min_chars=1, min_words=0, max_guard_risk=1.0)

#: arm -> (pipeline key, rule, extra)
ARMS: dict[str, tuple[str, str, str | None]] = {
    "v4 (baseline)": ("c1g1", "LTT max", None),
    "no risk control": ("c1g1", "plug-in", None),
    "CRC instead of LTT": ("c1g1", "CRC max", None),
    "LTT without max": ("c1g1", "LTT pure", None),
    "guard off": ("c1g0", "LTT max", None),
    "calibration alone": ("c1g0", "plug-in", None),
    "calibration off": ("c0g1", "LTT max", None),
    "guard alone": ("c0g1", "plug-in", None),
    "LTT alone": ("c0g0", "LTT max", None),
    "nothing (bare grid)": ("c0g0", "plug-in", None),
    "conformal off": ("conf0", "LTT max", None),
    "+ commit gate B": ("c1g1", "LTT max", "gate"),
    "+ session monitor": ("c1g1", "LTT max", "monitor"),
    "always commit": ("c1g0", "always", None),
    "never commit": ("c1g1", "never", None),
}
#: Arms computable from the cached repeated-split tables (guard on / off only).
SPLIT_ARMS = ("v4 (baseline)", "no risk control", "CRC instead of LTT", "LTT without max", "guard off",
              "calibration alone", "+ session monitor", "always commit", "never commit")
PIPES = {"c1g1": (True, True), "c1g0": (True, False), "c0g1": (False, True), "c0g0": (False, False)}


def log(*a) -> None:
    C.log(*a)


def set_log(path: Path) -> None:
    C.Log.path = path


def dump(obj, path: Path) -> None:
    C.dump(obj, path)


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

def make_pipe(decode_fn, user, cal_on: bool, guard_on: bool, cache: dict | None = None, **base):
    cfg = C.HarnessConfig(seed=C.SEED, user_config=user, max_wrong_commit=ALPHA, use_guard=guard_on,
                          use_calibration=cal_on, **base)
    return C.TrustPipeline(decode_fn, cfg, {} if cache is None else cache)


def conformal_off(pipe):
    p2 = copy.copy(pipe)
    p2.conformal = copy.deepcopy(pipe.conformal)
    p2.conformal.q = math.nan
    return p2


def mismatch(pipe):
    """The v4 pipeline fed by a producer that decodes the raw stream (frame temperature 1.0)."""
    from fidetype.trust.calibration import TemperatureScaler
    p2 = copy.copy(pipe)
    p2.frame_scaler = TemperatureScaler()
    return p2


def fit_four(decode_fn, user, fit_args: tuple, cal_items, test_items, base: dict | None = None,
             extra_tables: bool = True) -> dict:
    """Fit the four pipelines; item tables on calibration and test. Returns pipes + tables."""
    base = base or {}
    cache: dict = {}
    pipes, tabs = {}, {}
    for key, (c, g) in PIPES.items():
        t0 = time.time()
        p = make_pipe(decode_fn, user, c, g, cache, **base)
        p.fit(*fit_args)
        pipes[key] = p
        tabs[key] = {"cal": Q.M13.item_table(p, cal_items), "test": Q.M13.item_table(p, test_items),
                     "T": float(p.frame_scaler.temperature), "policy": C.clean(p.policy.config.__dict__)}
        log(f"  pipe {key}: T {p.frame_scaler.temperature:.4f} grid commit_p {p.policy.config.commit_p} "
            f"max_risk {p.policy.config.commit_max_risk} ({time.time() - t0:.0f}s)")
    if extra_tables:
        p = conformal_off(pipes["c1g1"])
        pipes["conf0"] = p
        tabs["conf0"] = {"cal": Q.M13.item_table(p, cal_items), "test": Q.M13.item_table(p, test_items),
                         "T": float(p.frame_scaler.temperature), "policy": tabs["c1g1"]["policy"]}
    return {"pipes": pipes, "tabs": tabs}


def lambdas(tab_cal: dict) -> dict:
    ca = K.arr(tab_cal)
    plug = float(C.fnum(tab_cal["lam_old"]))
    rc, rl = K.crc(ca), K.ltt(ca)
    return {"plug-in": plug, "CRC max": max(plug, rc.threshold), "LTT pure": rl.threshold,
            "LTT max": max(plug, rl.threshold), "CRC pure": rc.threshold, "always": -INF, "never": INF}


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

def gate_block(pipe, items) -> np.ndarray:
    """True where commit gate B would block a COMMIT (empty top-1 or guard risk >= 1.0)."""
    from fidetype.trust.content import CommitGate
    gate = CommitGate(**GATE_B)
    out = []
    for it in items:
        an = pipe.analyze(pipe.decode(it, 0))
        top = an.inputs.texts[0] if an.inputs.texts else ""
        out.append(gate.violation(top, an.inputs.guard_risk if pipe.policy.use_guard else None) is not None)
    return np.array(out, bool)


def monitor_mask(on: np.ndarray, loss_c: np.ndarray, loss_f: np.ndarray, groups) -> tuple[np.ndarray, dict]:
    """Apply the per-session monitor: after an alarm, the rest of that session is offer-only."""
    from fidetype.trust.session_risk import SessionRiskMonitor
    on = on.copy()
    groups = np.asarray(groups)
    alarms, n_sess = {}, 0
    for gval in dict.fromkeys(groups.tolist()):
        idx = np.flatnonzero(groups == gval)
        n_sess += 1
        mon = SessionRiskMonitor(MON["alpha"], MON["gamma"], MON["alternatives"], MON["max_bet_fraction"])
        for j, i in enumerate(idx):
            loss = loss_c[i] if on[i] else loss_f[i]
            if mon.update(float(loss)):
                on[idx[j + 1:]] = False
                alarms[str(gval)] = j + 1
                break
    return on, {"n_sessions": n_sess, "n_alarms": len(alarms), "alarm_at": alarms}


def arrays(tab: dict, lam: float, block: np.ndarray | None = None, groups=None) -> tuple[dict, dict]:
    g = lambda k: np.asarray(tab[k], float)  # noqa: E731
    s = np.array([C.fnum(x) for x in tab["score"]])
    on = (s >= lam) if lam != -INF else np.ones(s.size, bool)
    info: dict = {}
    if block is not None:
        info["n_blocked"] = int((on & block).sum())
        on = on & ~block
    if groups is not None:
        on, info = monitor_mask(on, g("loss_c"), g("loss_f"), groups)
    wc = np.where(on, g("wc_c"), g("wc_f"))
    a = {"w": np.where(on, g("words_c"), g("words_f")), "t": np.where(on, g("time_c"), g("time_f")), "wc": wc,
         "com": on.astype(float), "wcc": wc * on}
    return a, info


def summarise(a: dict) -> dict:
    n = int(a["wc"].size)
    k = int(round(a["wc"].sum()))
    nc = int(a["com"].sum())
    lo, hi = K.clopper_pearson(k, n)
    return {"n": n, "n_wrong_commit": k, "wrong_commit": k / n, "wrong_commit_cp95": [lo, hi],
            "wrong_commit_cp95_one_sided_upper": K.upper_one_sided(k, n), "n_commit": nc, "commit_rate": nc / n,
            "eac": (float(a["wcc"].sum()) / nc) if nc else None, "ewpm": 60.0 * float(a["w"].sum() / a["t"].sum())}


def mcnemar(x: np.ndarray, y: np.ndarray) -> dict:
    from scipy.stats import binom
    b = int(((x > 0.5) & (y < 0.5)).sum())
    c = int(((x < 0.5) & (y > 0.5)).sum())
    p = 1.0 if b + c == 0 else min(1.0, 2.0 * float(binom.cdf(min(b, c), b + c, 0.5)))
    return {"arm_only": b, "v4_only": c, "p": p}


def arm_rows(tabs: dict, test_groups=None, gate_blk: np.ndarray | None = None, arms=None) -> dict:
    """All arms on one split. ``tabs[key] = {"cal": table, "test": table}``."""
    arms = arms or list(ARMS)
    out, arrs = {}, {}
    for arm in arms:
        key, rule, extra = ARMS[arm]
        if key not in tabs:
            continue
        lam = lambdas(tabs[key]["cal"])[rule]
        blk = gate_blk if extra == "gate" else None
        grp = test_groups if extra == "monitor" else None
        if extra == "gate" and gate_blk is None:
            continue
        if extra == "monitor" and test_groups is None:
            continue
        a, info = arrays(tabs[key]["test"], lam, blk, grp)
        arrs[arm] = a
        out[arm] = {**summarise(a), "lambda": C.clean(lam), "pipe": key, "rule": rule, **({"info": info} if info else {})}
    base = arrs.get("v4 (baseline)")
    if base is not None:
        ps = {}
        for arm, a in arrs.items():
            if arm == "v4 (baseline)":
                continue
            m = mcnemar(a["wc"], base["wc"])
            out[arm]["vs_v4"] = {**m, "d_wrong_commit": out[arm]["wrong_commit"] - out["v4 (baseline)"]["wrong_commit"],
                                 "d_commit_rate": out[arm]["commit_rate"] - out["v4 (baseline)"]["commit_rate"],
                                 "d_ewpm": out[arm]["ewpm"] - out["v4 (baseline)"]["ewpm"]}
            ps[arm] = m["p"]
        if ps:
            for arm, ph in K.holm(ps).items():
                out[arm]["vs_v4"]["p_holm"] = ph
    return out


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

def zero_standin(s):
    """Zero-input stand-in: every frame = the stream's first frame (pre-signal silence)."""
    lp = np.repeat(np.asarray(s.log_probs)[:1], s.log_probs.shape[0], axis=0)
    return replace(s, log_probs=lp, source=s.source + "+zero_standin", meta={**s.meta, "audit": "zero_standin"})


def control_inputs(pipe, streams: list, decode) -> list[tuple]:
    """(PolicyInputs, top text) per control stream under ``pipe`` (its frame temperature)."""
    T = pipe.frame_scaler.temperature
    out = []
    for i, s in enumerate(streams):
        s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
        nb = decode(s2, i)
        an = pipe.analyze(nb)
        out.append((an.inputs, nb.top.text if nb.top is not None else ""))
    return out


def control_rows(pipes: dict, lams: dict, nulls: dict, decode, truths: list[str], groups=None,
                 arms=None, extra_pipes: dict | None = None) -> dict:
    """Commits per arm on each control set. ``lams[key]`` = lambdas() of that pipeline's calibration table.

    ``extra_pipes`` maps an extra row name to (pipe, lambda) (for example the declaration mismatch).
    """
    from fidetype.trust.content import CommitGate, gate_decision
    from fidetype.trust.policy import Action, DecisionPolicy
    from fidetype.trust.session_risk import SessionRiskMonitor
    arms = arms or list(ARMS)
    gate = CommitGate(**GATE_B)
    rows = {}
    jobs = []
    for arm in arms:
        key, rule, extra = ARMS[arm]
        if key in pipes:
            jobs.append((arm, pipes[key], lams[key][rule], extra))
    for name, (p, lam) in (extra_pipes or {}).items():
        jobs.append((name, p, lam, None))
    inputs_cache: dict = {}
    for arm, pipe, lam, extra in jobs:
        rows[arm] = {}
        pol = DecisionPolicy(replace(pipe.policy.config, commit_p=lam), use_guard=pipe.policy.use_guard)
        for cname, ss in nulls.items():
            ck = (id(pipe.frame_scaler), id(pipe.calibrator), id(pipe.conformal), id(pipe.guard), cname)
            if ck not in inputs_cache:
                inputs_cache[ck] = control_inputs(pipe, ss, decode)
            com, wr = [], []
            for i, (x, top) in enumerate(inputs_cache[ck]):
                if lam == -INF:
                    c = bool(x.texts)
                else:
                    d = pol.decide(x, final_attempt=True)
                    if extra == "gate":
                        d = gate_decision(d, x, gate, pol, True)
                    c = d.action == Action.COMMIT
                com.append(c)
                wr.append(c and top != truths[i])
            com = np.array(com, bool)
            wr = np.array(wr, bool)
            info = {}
            if extra == "monitor" and groups is not None:
                g = np.asarray(groups)
                n_al = 0
                for gv in dict.fromkeys(g.tolist()):
                    idx = np.flatnonzero(g == gv)
                    mon = SessionRiskMonitor(MON["alpha"], MON["gamma"], MON["alternatives"], MON["max_bet_fraction"])
                    for j, i in enumerate(idx):
                        if mon.update(float(wr[i])):
                            com[idx[j + 1:]] = False
                            wr[idx[j + 1:]] = False
                            n_al += 1
                            break
                info["n_alarms"] = n_al
            k = int(com.sum())
            rows[arm][cname] = {"n": len(ss), "n_commit": k, "commit_rate": k / len(ss), "n_wrong": int(wr.sum()),
                                "commit_cp95_one_sided_upper": K.upper_one_sided(k, len(ss)), **info}
    return rows


# ---------------------------------------------------------------------------
# Repeated splits (cached tables)
# ---------------------------------------------------------------------------

def split_arm_outcomes(cond: str, R: int) -> dict:
    """Arms of SPLIT_ARMS on the cached repeated-split tables (guard on: g1, guard off: g0)."""
    on = {sp["r"]: sp for sp in Q.load_all(cond, R, 1)}
    off = {sp["r"]: sp for sp in Q.load_all(cond, R, 0)}
    rs = sorted(set(on) & set(off))
    per: dict = {a: [] for a in SPLIT_ARMS}
    alarms = []
    for r in rs:
        for arm in SPLIT_ARMS:
            key, rule, extra = ARMS[arm]
            sp = on[r] if key == "c1g1" else off[r]
            ca, te = sp["cal"], sp["test"]
            plug = float(ca["lam_old"])
            rc, rl = K.crc(ca), K.ltt(ca)
            lam = {"plug-in": plug, "CRC max": max(plug, rc.threshold), "LTT pure": rl.threshold,
                   "LTT max": max(plug, rl.threshold), "always": -INF, "never": INF}[rule]
            s = te["s"]
            o = (s >= lam) if lam != -INF else np.ones(s.size, bool)
            if extra == "monitor":
                o, inf = monitor_mask(o, te["loss_c"], te["loss_f"], sp["test_group"])
                alarms.append(inf["n_alarms"])
            wc = np.where(o, te["wc_c"], te["wc_f"])
            w = np.where(o, te["words_c"], te["words_f"])
            t = np.where(o, te["time_c"], te["time_f"])
            per[arm].append({"wrong_commit": float(wc.mean()), "commit_rate": float(o.mean()),
                             "ewpm": 60.0 * float(w.sum() / t.sum()), "n_commit": int(o.sum()),
                             "n_commit_wrong": float((wc * o).sum())})
    out = {"R": len(rs)}
    base = np.array([x["wrong_commit"] for x in per["v4 (baseline)"]])
    for arm, v in per.items():
        wc = np.array([x["wrong_commit"] for x in v])
        nk = int(np.sum(wc > ALPHA + 1e-12))
        nc = sum(x["n_commit"] for x in v)
        d = wc - base
        from scipy.stats import binom
        npos, nneg = int((d > 1e-12).sum()), int((d < -1e-12).sum())
        sign_p = 1.0 if npos + nneg == 0 else min(1.0, 2 * float(binom.cdf(min(npos, nneg), npos + nneg, 0.5)))
        out[arm] = {"wrong_commit_mean": float(wc.mean()), "p05": float(np.quantile(wc, 0.05)),
                    "p95": float(np.quantile(wc, 0.95)), "share_gt_alpha": nk / len(v), "share_gt_alpha_cp95": Q.cp(nk, len(v)),
                    "commit_rate_mean": float(np.mean([x["commit_rate"] for x in v])),
                    "ewpm_mean": float(np.mean([x["ewpm"] for x in v])),
                    "eac_pooled": (sum(x["n_commit_wrong"] for x in v) / nc) if nc else None,
                    "d_wrong_commit_mean": float(d.mean()), "sign_test_p": sign_p, "n_up": npos, "n_down": nneg}
    out["+ session monitor"]["alarms_per_split_mean"] = float(np.mean(alarms)) if alarms else None
    return out


def env_note() -> dict:
    return {"threads": os.environ.get("OMP_NUM_THREADS"), "python": sys.version.split()[0],
            "time": time.strftime("%Y-%m-%dT%H:%M:%S")}


def load_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Streaming layer (end to end): frozen config -> StreamingTrustLayer
# ---------------------------------------------------------------------------

def frozen_v4(pipe, lam: float, name: str, gate: bool = False):
    """FrozenTrustConfig of a fitted pipeline with the final commit threshold ``lam``."""
    from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig
    from fidetype.trust.policy import DecisionPolicy
    p = copy.copy(pipe)
    p.policy = DecisionPolicy(replace(pipe.policy.config, commit_p=lam), use_guard=pipe.policy.use_guard)
    fz = FrozenTrustConfig.from_pipeline(p, name=name, recipe=PAPER1_V4_RECIPE)
    return fz.with_commit_gate(**GATE_B) if gate else fz


def _f(v) -> float | None:
    v = float(v)
    return None if v == -INF else v


def header_event(stream, decl: dict | None = None) -> dict:
    h = {"type": "header", "spec_version": stream.version, "vocab": list(stream.vocab), "vocab_type": stream.vocab_type,
         "blank_id": stream.blank_id, "source": stream.source, "meta": stream.meta}
    if stream.frame_period is not None:
        h["frame_period"] = stream.frame_period
    if decl is not None:
        h["decode_declaration"] = decl
    return h


def frame_events(stream) -> list[dict]:
    return [{"type": "frame", "t": float(t), "log_probs": [_f(v) for v in row]}
            for t, row in zip(stream.frame_times, stream.log_probs)]


def hypothesis_event(nb) -> dict:
    items = []
    for c in nb.candidates:
        it = {"text": c.text, "score": float(c.score)}
        for k in ("logp_acoustic", "logp_lm"):
            v = float(getattr(c, k))
            if math.isfinite(v):
                it[k] = v
        cc = list(c.char_confidences)
        if cc:
            it["char_confidences"] = [float(x) for x in cc]
        items.append(it)
    return {"type": "hypothesis", "id": "final", "is_final": True, "score_semantics": "log", "nbest": items}


def replay(fz, jobs: list[tuple], route: str, decode_fn=None, **streaming_kw) -> list:
    """jobs = [(session_id, stream, nbest or None, declaration or None)]. Returns the final decisions in order."""
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer
    layer = StreamingTrustLayer(fz, decode_fn=decode_fn if route == "frames" else None,
                                streaming=StreamingConfig(route=route, max_attempts=1, **streaming_kw))
    decs = []
    for sid, s, nb, decl in jobs:
        evs = [header_event(s, decl)]
        evs += frame_events(s) if route == "frames" else [hypothesis_event(nb)]
        evs.append({"type": "end"})
        got = []
        for ev in evs:
            got += layer.push(ev, sid)
        got += layer.end_of_utterance(sid)
        fin = [d for d in got if d.final]
        assert len(fin) == 1, f"{len(fin)} final decisions"
        decs.append(fin[0])
    return decs


class ReplayPolicy:
    """Feeds streaming decisions, in order, into the harness user simulation (for eWPM)."""

    def __init__(self, decs) -> None:
        self.it = iter(decs)

    def decide(self, inputs, final_attempt=False):
        d = next(self.it)
        assert tuple(d.inputs.texts) == tuple(inputs.texts), "replayed decision belongs to another n-best"
        return d.decision


def stream_metrics(pipe, items, decs, batch_tab: dict, lam: float) -> dict:
    """Metrics of streaming decisions (user simulation) + agreement with the batch item table at ``lam``."""
    from fidetype.trust.policy import Action
    recs = pipe.run_items(items, ReplayPolicy(decs))
    m = C.metrics(C.rec_arrays(recs))
    com = np.array([d.action == Action.COMMIT for d in decs])
    s = np.array([C.fnum(x) for x in batch_tab["score"]])
    m.update({"n": len(decs), "n_commit": int(com.sum()), "n_wrong_commit": int(sum(bool(r.wrong_commit) for r in recs)),
              "commit_equal_to_batch": int((com == (s >= lam)).sum())})
    return m
