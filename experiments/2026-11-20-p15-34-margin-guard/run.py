"""P15-34: T15 safe-WPM interval over calibration draws for guards with a safety margin.
Pre-registered: plan.md. CPU only, our own code (Apache-2.0). Draw code copied from P15-29 run.py (that folder is
not changed).

Stages (one process each):
  select      stage S: lever selection on val_select only (bootstrap world over 4 seeds); writes results/selection.json
  worker <w>  main run: worker 0 = z0 + odd k, worker 1 = even k; all arms per draw; finished files are skipped
  analyse     combined intervals per arm, X4 code check, verdicts
  smoke       calibration subsets only (P1534_SMOKE=1); never uses an evaluation set

Run (repo root), for example:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-20-p15-34-margin-guard/run.py select
Per-trial files (with text) and caches: C:/Users/zhang/bci-data/derived/p15-34/ only. Repo: aggregates.
Read only: derived/p15-22/, derived/p15-26/ (decoder outputs, LLM scores, P15-22 decisions).
Stop file: C:/Users/zhang/bci-data/derived/p15-34/STOP (a worker stops after its current draw).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import contextlib  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

SMOKE = os.environ.get("P1534_SMOKE", "0") == "1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# P15-26 run.py: data loaders, cache helpers, the P15-22 / P5-24 modules (read only use, as P15-29)
P26 = load_module("p1526run_p1534", REPO / "experiments/2026-11-19-p15-26-replication/run.py")
K, F, P22, P524 = P26.K, P26.F, P26.P22, P26.P524
norm = P26.norm

import fidetype.eval.harness as H  # noqa: E402
import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import (CorrectionRule, calibration_draw_interval, format_line,  # noqa: E402
                                         guarantee_from_sheet)
from fidetype.trust.calibration import TemperatureScaler  # noqa: E402
from fidetype.trust.dropin import _norm_text, _split  # noqa: E402
from fidetype.trust.risk_control import DEFAULT_LTT_GRID, ltt_threshold  # noqa: E402

DER = K.DER
OWN_ROOT = DER / "p15-34"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-34"
ROOT = OWN_ROOT / "smoke" if SMOKE else OWN_ROOT
OUT = ROOT / "results-smoke" if SMOKE else HERE / "results"
LOGF = OUT / "run.log"
STOP = OWN_ROOT / "STOP"
PLAN = "plan.md (pre-registration)"
P1522 = DER / "p15-22"
P1526 = DER / "p15-26"

CLAIM_ALPHA = 0.05  # the safe-WPM alpha of the headline (P15-29)
NULL_RATE = 0.05  # null controls as in P15-29 (allowed 15 of 300)
NULL_TRIALS = 20 if SMOKE else 300
B_INNER, SEED_INNER = 2000, 0
NO_BCI = 4.0153
K_DRAWS = 2 if SMOKE else 40
PINNED = {"frame_temperature": 2.37015800035291, "tau": 0.06996627059278283, "llm_weight": 1.0,
          "fluent": -7.88165954200173}
# stage S
SEL_SEEDS = (0, 1) if SMOKE else (0, 1, 2, 3)
SEL_R, SEL_B, SEL_N_EVAL = (50, 50, 701) if SMOKE else (500, 200, 701)
SEL_ALPHAS = (0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02)
SEL_DELTAS = (0.1, 0.05, 0.025, 0.01)


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + f"[{K.private_mb()} MB] " + " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


P26.log = log
F.log = log
P26.OUT = OUT


def h8(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def arm_name(alpha: float, delta: float) -> str:
    return f"a{alpha:.3f}-d{delta:.3f}"


# ---------------------------------------------------------------------------
# data + pipeline (pinned values; private caches)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def pinned_frame_temperature(T: float):
    """Inside calibrate, the frame-temperature fit returns the pinned T (scoped swap, as P15-29)."""
    orig = H.fit_frame_temperature
    H.fit_frame_temperature = lambda streams, truths: TemperatureScaler(temperature=float(T))
    try:
        yield
    finally:
        H.fit_frame_temperature = orig


def load_t15(wdir: Path, with_eval: bool) -> SimpleNamespace:
    from fidetype.adapters import b2t25 as Bm

    (cx, ct, cph, ckeys), held = K.load_t15("m4-13", norm_text=True, with_keys=True)
    p1405 = load_module("p1405run_p1534", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    if SMOKE:  # calibration subsets only: the evaluation set is never used
        n = int(os.environ.get("P1534_SMOKE_N", "160"))
        hx, ht, hkeys = cx[n:n + 40], ct[n:n + 40], ckeys[n:n + 40]
        cx, ct, cph, ckeys = cx[:n], ct[:n], cph[:n], ckeys[:n]
        durs = p1405.t15_durations(hkeys) if with_eval else None
    elif with_eval:
        hx, ht, _hph, hkeys = held
        durs = p1405.t15_durations(hkeys)
    else:
        hx = ht = durs = None
    del held
    gc.collect()
    cdurs = p1405.t15_durations(ckeys)
    cache = wdir / "llm-cache-t15.sqlite"
    n_cached = P26.merged_llm_cache(cache, [P1526 / "llm-cache-t15.sqlite", P1522 / "llm-cache.sqlite"])
    dec, _bt = K.word_decoder()
    pipe, lazy = P26.make_pipe("t15", wdir, dec, cache, P1522 / "base-nbest-t15.pkl")
    pv = PINNED
    pipe.grounding.tau, pipe.lam, pipe.frame_T, pipe.fluent_thr = pv["tau"], pv["llm_weight"], \
        pv["frame_temperature"], pv["fluent"]
    u = SimpleNamespace(pipe=pipe, lazy=lazy, base_start=len(pipe.base), B=Bm, cx=cx, ct=ct, cph=cph,
                        cdurs=cdurs, hx=hx, ht=[norm(t) for t in ht] if ht is not None else None, durs=durs,
                        T=pv["frame_temperature"])
    log(f"t15: loaded; calibration {len(cx)}, evaluation {len(hx) if hx is not None else 'not loaded'}; "
        f"llm cache {n_cached}; pinned {pv}")
    return u


def calib_kw(u: SimpleNamespace, name: str, seed: int, alpha: float, delta: float, null_trials: int) -> dict:
    arm = P22.ARM_B1
    pipe = u.pipe

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    return dict(alpha=alpha, delta=delta, vocab=list(u.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
                frame_period=0.08, decode_fn=fn, decoder_name=name, modality="intracortical", name=name, seed=seed,
                null_trials=null_trials, null_max_commit_rate=NULL_RATE, confidence="learned")


# ---------------------------------------------------------------------------
# stage S: lever selection on val_select only
# ---------------------------------------------------------------------------


def ltt_items(guard, inputs, texts, seed: int) -> dict:
    """Learned score, loss and gate of the LTT items of this seed, exactly as dropin._fit_commit_score."""
    n = len(inputs)
    order = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, _n_ltt = _split(n)
    idx = order[n_fit + n_pol:]
    codec = guard._codec
    gate = guard.config.gate
    s, loss = [], []
    for i in idx:
        events, _ = codec.events(inputs[i])
        sd = guard._run_layer(guard._layer, events)
        f = guard._features(sd, events)
        top = _norm_text(sd.inputs.texts[0]) if sd.inputs.texts else ""
        right = bool(sd.inputs.texts) and top == _norm_text(texts[i])
        ok = bool(sd.inputs.texts) and (gate is None or gate.violation(
            sd.inputs.texts[0], float(sd.inputs.guard_risk) if guard.config.use_guard else None) is None)
        s.append(guard.commit_score.score(f) if ok else -math.inf)
        loss.append(0.0 if right else 1.0)
    return {"idx": idx, "s": np.array(s, float), "loss": np.array(loss, float)}


def sim_arm(pops: list[dict], alpha: float, delta: float, W: np.ndarray) -> dict:
    """Bootstrap world: pooled values over seeds x R outer draws x B inner resamples (plan.md stage S)."""
    rule = CorrectionRule()
    pooled, values, fails, vac, thrs = [], [], 0, 0, []
    for p in pops:
        n = len(p["s"])
        pen = rule.penalty(p["nc"])
        t_neural = W @ p["dur"]
        for r in range(SEL_R):
            rb = np.random.default_rng(h8(f"p15-34|sel|{p['seed']}|{r}"))
            j = rb.integers(0, n, n)
            res = ltt_threshold(p["s"][j], p["loss"][j], alpha=alpha, delta=delta, grid=DEFAULT_LTT_GRID,
                                pvalue="binomial")
            thr = res.threshold
            thrs.append(thr if math.isfinite(thr) else None)
            cm = p["s"] >= thr if math.isfinite(thr) else np.zeros(n, bool)
            wrong = cm & (p["loss"] > 0)
            rate = float(wrong.mean())
            if not cm.any():
                vac += 1
                values.append(0.0)
                pooled.append(np.zeros(W.shape[0]))
                continue
            if rate > CLAIM_ALPHA:
                fails += 1
                values.append(0.0)
                pooled.append(np.zeros(W.shape[0]))
                continue
            ok = cm & ~wrong
            credit = np.where(ok, p["nw"], 0.0)
            pent = np.where(wrong, pen, 0.0)
            values.append(float(60.0 * credit.sum() / (p["dur"].sum() + pent.sum())))
            pooled.append(60.0 * (W @ credit) / (t_neural + W @ pent))
    pooled = np.concatenate(pooled)
    v = np.array(values)
    t = [x for x in thrs if x is not None]
    return {"alpha": alpha, "delta": delta, "arm": arm_name(alpha, delta),
            "pred_lower": float(np.percentile(pooled, 2.5)), "pred_upper": float(np.percentile(pooled, 97.5)),
            "pred_mean": float(v.mean()), "fail_fraction": fails / len(v), "vacuous_fraction": vac / len(v),
            "mean_threshold": float(np.mean(t)) if t else None}


def choose_arms(rows: list[dict]) -> dict:
    """Arm rule of plan.md (A1 primary, A0 reference, A2 alpha-only, A3 delta-only)."""
    best = max(r["pred_lower"] for r in rows)
    top = [r for r in rows if best - r["pred_lower"] < 0.01]
    a1 = max(top, key=lambda r: (r["alpha"], r["delta"]))
    ranking = sorted(rows, key=lambda r: (-r["pred_lower"], -r["alpha"], -r["delta"]))
    chosen = {a1["arm"], arm_name(0.05, 0.1)}

    def best_of(cands):
        for r in sorted(cands, key=lambda r: (-r["pred_lower"], -r["alpha"], -r["delta"])):
            if r["arm"] not in chosen:
                return r
        return None

    def next_any():
        for r in ranking:
            if r["arm"] not in chosen:
                return r
        return None

    a2 = best_of([r for r in rows if r["delta"] == 0.1 and r["alpha"] < 0.05]) or next_any()
    chosen.add(a2["arm"])
    a3 = best_of([r for r in rows if r["alpha"] == 0.05 and r["delta"] < 0.1]) or next_any()
    chosen.add(a3["arm"])
    out = {"A0": {"alpha": 0.05, "delta": 0.1, "role": "reference (P15-29 settings)"},
           "A1": {"alpha": a1["alpha"], "delta": a1["delta"], "role": "primary"},
           "A2": {"alpha": a2["alpha"], "delta": a2["delta"], "role": "secondary (alpha margin)"},
           "A3": {"alpha": a3["alpha"], "delta": a3["delta"], "role": "secondary (delta margin)"}}
    if a1["arm"] == arm_name(0.05, 0.1):
        out["note"] = "A1 equals the reference settings"
    for v in out.values():
        if isinstance(v, dict):
            v["name"] = arm_name(v["alpha"], v["delta"])
    return out


def stage_select() -> dict:
    wdir = ROOT / "select"
    wdir.mkdir(parents=True, exist_ok=True)
    u = load_t15(wdir, with_eval=False)
    assert u.hx is None or SMOKE
    pops = []
    for s in SEL_SEEDS:
        t0 = time.time()
        nm = f"p15-34-select-s{s}"
        with pinned_frame_temperature(u.T):
            guard = ft.calibrate(u.cx, u.ct, stream_texts=u.cph,
                                 **calib_kw(u, nm, s, 0.05, 0.1, 20))
        it = ltt_items(guard, u.cx, u.ct, s)
        chk = ltt_threshold(it["s"], it["loss"], alpha=0.05, delta=0.1, grid=DEFAULT_LTT_GRID, pvalue="binomial")
        thr = float(guard.commit_score.threshold)
        same = (chk.threshold == thr) or (not math.isfinite(chk.threshold) and not math.isfinite(thr))
        log(f"select seed {s}: guard threshold {thr}, recomputed {chk.threshold}; same {same}; "
            f"{time.time() - t0:.0f} s")
        if not same:
            raise SystemExit(f"stage S check failed for seed {s}: {chk.threshold} != {thr}")
        idx = it["idx"]
        truths = [_norm_text(u.ct[i]) for i in idx]
        pops.append({"seed": s, "s": it["s"], "loss": it["loss"], "nw": np.array([len(t.split()) for t in truths], float),
                     "nc": np.array([len(t) for t in truths], float),
                     "dur": np.array([u.cdurs[i] for i in idx], float), "threshold": thr})
        u.pipe.scorer.store.flush()
        u.pipe.save_base()
    n = len(pops[0]["s"])
    rng = np.random.default_rng(1)
    W = np.empty((SEL_B, n))
    for b in range(SEL_B):
        W[b] = np.bincount(rng.integers(0, n, SEL_N_EVAL), minlength=n)
    rows = []
    for a in SEL_ALPHAS:
        for d in SEL_DELTAS:
            r = sim_arm(pops, a, d, W)
            rows.append(r)
            log(f"select {r['arm']}: predicted {r['pred_mean']:.3f} [{r['pred_lower']:.3f}, {r['pred_upper']:.3f}]; "
                f"fail {r['fail_fraction']:.3f}; vacuous {r['vacuous_fraction']:.3f}; mean threshold "
                f"{r['mean_threshold']}")
    arms = choose_arms(rows)
    out = {"fidetype_version": FT_VERSION, "plan": PLAN, "stage": "S (calibration data only; val_eval not used)",
           "seeds": list(SEL_SEEDS), "R": SEL_R, "B": SEL_B, "n_eval_inner": SEL_N_EVAL,
           "populations": [{"seed": p["seed"], "n_ltt": int(len(p["s"])), "threshold_0.05_0.1": p["threshold"],
                            "n_wrong_top1": int(p["loss"].sum()), "n_gate_blocked": int(np.isinf(p["s"]).sum())}
                           for p in pops],
           "grid": rows, "arms": arms}
    from fidetype.benchmark.scoring import to_jsonable

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "selection.json").write_text(json.dumps(to_jsonable(out), indent=1) + "\n", encoding="utf-8")
    log(f"select: arms {json.dumps(arms)}")
    return arms


# ---------------------------------------------------------------------------
# main run (draw procedure copied from P15-29)
# ---------------------------------------------------------------------------


def load_arms() -> dict:
    sel = json.loads((OUT / "selection.json").read_text(encoding="utf-8"))
    return {k: v for k, v in sel["arms"].items() if k in ("A0", "A1", "A2", "A3")}


def kname(k: int) -> str:
    return f"k{k:02d}"


def job(name: str) -> dict:
    if name == "z0":
        return {"name": "z0", "seed": 0, "boot_seed": None, "k": None}
    k = int(name[1:])
    return {"name": name, "seed": h8(f"p15-34|t15|cal|{k}"), "boot_seed": h8(f"p15-34|t15|boot|{k}"), "k": k}


def job_list(w: int) -> list[dict]:
    names = (["z0"] if w == 0 else []) + [kname(k) for k in range(1, K_DRAWS + 1) if k % 2 == (1 if w == 0 else 0)]
    return [job(n) for n in names]


def draw_order(n: int, seed: int, boot_seed: int | None) -> tuple[np.ndarray, dict]:
    """Input order L such that calibrate(seed) sees parts fit / policy / LTT = (bootstrap of) its own split (P15-29)."""
    o = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, n_ltt = _split(n)
    parts = [o[:n_fit], o[n_fit:n_fit + n_pol], o[n_fit + n_pol:]]
    if boot_seed is not None:
        rb = np.random.default_rng(boot_seed)
        parts = [rb.choice(p, size=len(p), replace=True) for p in parts]
    desired = np.concatenate(parts)
    L = np.empty(n, dtype=int)
    L[o] = desired
    info = {"split": [n_fit, n_pol, n_ltt], "distinct_per_part": [int(len(set(p.tolist()))) for p in parts],
            "sha_desired": hashlib.sha256(json.dumps(desired.tolist()).encode()).hexdigest()[:16]}
    return L, info


def claimed(sheet: dict) -> dict:
    """The sheet with alpha = 0.05: P(R <= alpha') >= 1 - delta' implies P(R <= 0.05) >= 1 - delta' (plan.md)."""
    s = dict(sheet)
    assert float(s["alpha"]) <= CLAIM_ALPHA + 1e-12
    s["alpha"] = CLAIM_ALPHA
    return s


def save_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    tmp.replace(path)


def run_draw_arm(u: SimpleNamespace, jb: dict, arm_key: str, arm: dict) -> dict:
    out_dir = ROOT / "t15" / arm["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"draw-{jb['name']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t0 = time.time()
    L, info = draw_order(len(u.cx), jb["seed"], jb["boot_seed"])
    xs, ts, ph = [u.cx[i] for i in L], [u.ct[i] for i in L], [u.cph[i] for i in L]
    nm = f"p15-34-t15-{jb['name']}-{arm['name']}"
    res = {**jb, "arm": arm_key, "arm_name": arm["name"], "alpha_cal": arm["alpha"], "delta_cal": arm["delta"],
           "draw_info": info}
    try:
        with pinned_frame_temperature(u.T):
            guard = ft.calibrate(xs, ts, stream_texts=ph,
                                 **calib_kw(u, nm, jb["seed"], arm["alpha"], arm["delta"], NULL_TRIALS))
    except ft.NullControlError as e:
        res.update({"status": "refused", "controls": [x.to_dict() for x in e.report],
                    "seconds": round(time.time() - t0, 1)})
        log(f"{jb['name']} {arm_key} {arm['name']}: REFUSED {res['controls']}")
        save_json(path, res)
        return res
    T = guard.config.frame_temperature
    assert abs(T - u.T) < 1e-12, f"frame temperature {T} differs from the pinned {u.T}"
    t_cal = time.time() - t0
    rows = []
    for i, x in enumerate(u.hx):
        r = guard.decide(x, utterance_id=f"{nm}-{i}")
        rows.append({"i": i, "action": r.action, "text": r.text, "complete": r.complete, "truth": u.ht[i],
                     "score": r.commit_score})
        if i % 100 == 99:
            guard.audit_log.clear()
    guard.audit_log.clear()
    u.pipe.scorer.store.flush()
    u.pipe.save_base()
    sheet = guard.sheet.to_dict()
    keys = ("value", "status", "n_commits", "n_wrong_commits", "measured_wrong_commit", "measured_wrong_commit_cp95",
            "unguarded_wpm", "n_cal", "alpha", "delta")
    v_cl = P524.score(rows, claimed(sheet), u.durs, "0.1")
    v_st = P524.score(rows, sheet, u.durs, "0.1")
    res.update({"status": "ok", "config_id": guard.config_id, "sheet": sheet, "frame_temperature": T, "rows": rows,
                "v0_1_claimed": {k: v_cl.get(k) for k in keys}, "v0_1_strict": {k: v_st.get(k) for k in keys},
                "seconds_calibrate": round(t_cal, 1), "seconds": round(time.time() - t0, 1),
                "misses_after": {"base_nbest_new_decodes": len(u.pipe.base) - u.base_start,
                                 "llm_texts_scored_live": u.lazy.texts_scored},
                "peak_mb": round(P26.peak_mb(), 1)})
    save_json(path, res)
    log(f"{jb['name']} {arm_key} {arm['name']} (seed {jb['seed']}, boot {jb['boot_seed']}): claimed {format_line(v_cl)}; "
        f"strict status {v_st['status']}; threshold {sheet.get('commit_threshold')}; controls "
        f"{[(c['name'], c['n_commit'], c['allowed']) for c in sheet['controls']]}; {res['seconds']:.0f} s "
        f"(calibrate {t_cal:.0f} s); misses {res['misses_after']}; peak {res['peak_mb']} MB")
    return res


def stage_worker(w: int) -> dict:
    arms = load_arms()
    wdir = ROOT / f"w{w}"
    wdir.mkdir(parents=True, exist_ok=True)
    u = None
    done, stopped = [], False
    for jb in job_list(w):
        todo = [(k, a) for k, a in arms.items() if not (ROOT / "t15" / a["name"] / f"draw-{jb['name']}.json").exists()]
        if not todo:
            done.append(jb["name"])
            continue
        if STOP.exists():
            stopped = True
            log(f"worker {w}: stop file found; stopping before {jb['name']}")
            break
        if u is None:
            u = load_t15(wdir, with_eval=True)
        for k, a in todo:
            run_draw_arm(u, jb, k, a)
        done.append(jb["name"])
        gc.collect()
    return {"worker": w, "done": done, "stopped": stopped, "peak_mb": round(P26.peak_mb(), 1)}


# ---------------------------------------------------------------------------
# analysis (plan.md decision rule)
# ---------------------------------------------------------------------------


def load_draw(arm_name_: str, name: str) -> dict | None:
    p = ROOT / "t15" / arm_name_ / f"draw-{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def as_draw(d: dict, strict: bool = False) -> dict:
    if d.get("status") == "refused":
        return {"refused": True}
    a = P524.trial_arrays(d["rows"], "0.1")
    sheet = d["sheet"] if strict else claimed(d["sheet"])
    return {"committed": a["committed"], "correct": a["correct"], "guarantee": guarantee_from_sheet(sheet)}


def lengths(rows: list[dict]) -> tuple[list[int], list[int]]:
    return [len(r["truth"].split()) for r in rows], [len(r["truth"]) for r in rows]


def same_rows(a: list[dict], b: list[dict]) -> int:
    return sum(x["action"] == y["action"] and norm(x["text"] or "") == norm(y["text"] or "") for x, y in zip(a, b))


def eval_durations() -> list[float]:
    _c, (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
    p1405 = load_module("p1405run_p1534", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    return p1405.t15_durations(hkeys)


def summary(d: dict) -> dict:
    keep = ("name", "seed", "boot_seed", "k", "arm", "arm_name", "status", "draw_info", "config_id",
            "v0_1_claimed", "v0_1_strict", "seconds_calibrate", "seconds", "misses_after", "peak_mb")
    s = {k: d.get(k) for k in keep if k in d}
    if d.get("status") == "ok":
        sh = d["sheet"]
        s["commit_threshold"] = sh.get("commit_threshold")
        s["ltt_in_sample"] = [sh.get("ltt_commits"), sh.get("ltt_wrong_commits")]
        s["controls"] = [(c["name"], c["n_commit"], c["n"], c["allowed"]) for c in sh["controls"]]
    else:
        s["controls"] = d.get("controls")
    return s


def verdict(comb: dict) -> str:
    lo, mean = comb["interval"][0], comb["value"]
    if lo > NO_BCI:
        return "clearly above after calibration uncertainty"
    if mean > NO_BCI:
        return "above, but inside the combined interval"
    return "not above"


def stage_analyse() -> dict:
    arms = load_arms()
    out: dict = {"fidetype_version": FT_VERSION, "plan": PLAN, "B_inner": B_INNER, "no_bci_reference": NO_BCI,
                 "arms": arms, "results": {}}
    a0 = arms["A0"]["name"]
    z0 = load_draw(a0, "z0")
    ref_rows = json.loads((P1522 / "arm-llm_learned.json").read_text(encoding="utf-8"))["rows"]
    x4: dict = {"reference": "p15-22/arm-llm_learned.json"}
    durs = eval_durations()
    if z0 is None or z0.get("status") != "ok":
        x4.update(reproduces=False, reason="z0 missing or refused")
    else:
        nw, nc = lengths(z0["rows"])
        x4["same_action_and_text"] = same_rows(z0["rows"], ref_rows)
        x4["n"] = len(ref_rows)
        x4["z0_value"] = z0["v0_1_claimed"]["value"]
        one = calibration_draw_interval([as_draw(z0)], nw, nc, durs, B=B_INNER, seed=SEED_INNER, metric_version="0.1")
        x4["k1_interval"] = one["interval"]
        x4["k1_interval_matches_p15_22"] = [round(v, 2) for v in one["interval"]] == [4.25, 5.57]
        x4["z0_threshold_commits_wrong"] = [z0["sheet"].get("commit_threshold"), z0["v0_1_claimed"]["n_commits"],
                                            z0["v0_1_claimed"]["n_wrong_commits"]]
        x4["matches_p15_29_z0"] = (round(float(z0["sheet"].get("commit_threshold")), 2) == 0.82
                                   and x4["z0_threshold_commits_wrong"][1:] == [196, 13])
        x4["reproduces"] = (x4["same_action_and_text"] == x4["n"] == len(z0["rows"])
                            and x4["k1_interval_matches_p15_22"] and x4["matches_p15_29_z0"]
                            and round(x4["z0_value"], 2) == 4.91)
    out["X4_code_check"] = x4
    log(f"X4: {x4}")
    if not x4["reproduces"]:
        out["verdict"] = "not decided: the code check X4 fails"
        (OUT / "results.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
        return out
    rows0 = z0["rows"]
    nw, nc = lengths(rows0)
    names = [kname(k) for k in range(1, K_DRAWS + 1)]
    per_arm_draws = {}
    for key, arm in arms.items():
        draws = [load_draw(arm["name"], n) for n in names]
        res: dict = {"name": arm["name"], "alpha_cal": arm["alpha"], "delta_cal": arm["delta"], "role": arm["role"]}
        if any(d is None for d in draws):
            res["K_done"] = sum(d is not None for d in draws)
            res["verdict"] = f"not decided: only {res['K_done']} of {K_DRAWS} draws"
            out["results"][key] = res
            continue
        for d in draws:
            if d.get("status") == "ok":
                assert [r["truth"] for r in d["rows"]] == [r["truth"] for r in rows0]
        per_arm_draws[key] = draws
        res["K"] = len(draws)
        for mode in ("claimed", "strict"):
            comb = calibration_draw_interval([as_draw(d, strict=(mode == "strict")) for d in draws], nw, nc, durs,
                                             B=B_INNER, seed=SEED_INNER, reference=NO_BCI, metric_version="0.1")
            pub = {k: v for k, v in comb.items() if k != "draws"}
            pub["draw_values"] = [x["value"] for x in comb["draws"]]
            pub["draw_statuses"] = [x["status"] for x in comb["draws"]]
            if mode == "claimed":
                # pooled percentiles again, for the Bonferroni level of the secondary arms
                pooled = _pooled(draws, nw, nc, durs)
                pub["p1_25"] = float(np.percentile(pooled, 1.25))
            res[mode] = pub
        ok = [d for d in draws if d.get("status") == "ok"]
        res["mean_commits"] = float(np.mean([d["v0_1_claimed"]["n_commits"] for d in ok])) if ok else None
        res["mean_wrong_commits"] = float(np.mean([d["v0_1_claimed"]["n_wrong_commits"] for d in ok])) if ok else None
        res["thresholds"] = [d["sheet"].get("commit_threshold") if d.get("status") == "ok" else None for d in draws]
        res["draws"] = [summary(d) for d in draws]
        c = res["claimed"]
        res["verdict"] = verdict(c)
        if key in ("A2", "A3"):
            res["bonferroni_above"] = bool(c["p1_25"] > NO_BCI)
        out["results"][key] = res
        log(f"{key} {arm['name']}: claimed {c['value']:.3f} [{c['interval'][0]:.3f}, {c['interval'][1]:.3f}] "
            f"statuses {c['statuses']}; strict {res['strict']['value']:.3f} [{res['strict']['interval'][0]:.3f}, "
            f"{res['strict']['interval'][1]:.3f}] {res['strict']['statuses']}; mean commits {res['mean_commits']}; "
            f"verdict {res['verdict']}")
    # paired comparison to A0
    if "A0" in per_arm_draws:
        v0 = out["results"]["A0"]["claimed"]["draw_values"]
        s0 = out["results"]["A0"]["claimed"]["draw_statuses"]
        for key in ("A1", "A2", "A3"):
            if key not in per_arm_draws:
                continue
            vj = out["results"][key]["claimed"]["draw_values"]
            sj = out["results"][key]["claimed"]["draw_statuses"]
            both = [b - a for a, b, x, y in zip(v0, vj, s0, sj) if x == "certified" and y == "certified"]
            out["results"][key]["paired_vs_A0"] = {
                "mean_diff_all": float(np.mean(np.array(vj) - np.array(v0))),
                "mean_diff_both_certified": float(np.mean(both)) if both else None,
                "n_both_certified": len(both),
                "A0_above_alpha_now_certified": sum(x == "above-alpha" and y == "certified" for x, y in zip(s0, sj)),
                "A0_certified_now_not": sum(x == "certified" and y != "certified" for x, y in zip(s0, sj)),
            }
    a1 = out["results"].get("A1", {})
    out["headline"] = {"primary_arm": arms["A1"]["name"], "A1_verdict": a1.get("verdict"),
                       "criterion_met": a1.get("verdict") == "clearly above after calibration uncertainty",
                       "gap_132": "close" if a1.get("verdict") == "clearly above after calibration uncertainty"
                       else "stays open"}
    from fidetype.benchmark.scoring import to_jsonable

    (OUT / "results.json").write_text(json.dumps(to_jsonable(out), indent=1, default=str) + "\n", encoding="utf-8")
    log(f"analyse: headline {out['headline']}")
    return out


def _pooled(draws: list[dict], nw, nc, durs) -> np.ndarray:
    """Pooled K x B values of the claimed scoring (same construction as calibration_draw_interval)."""
    from fidetype.benchmark.safe_wpm import safe_wpm

    rule = CorrectionRule()
    ns, nw_, nc_ = np.asarray(durs, float), np.asarray(nw, float), np.asarray(nc, float)
    n = len(ns)
    pen = rule.penalty(nc_)
    rng = np.random.default_rng(SEED_INNER)
    W = np.empty((B_INNER, n))
    for b in range(B_INNER):
        W[b] = np.bincount(rng.integers(0, n, n), minlength=n)
    t_neural = W @ ns
    vals = []
    for d in draws:
        dd = as_draw(d)
        if dd.get("refused"):
            vals.append(np.zeros(B_INNER))
            continue
        r = safe_wpm(dd["committed"], dd["correct"], nw_, nc_, ns, guarantee=dd["guarantee"], rule=rule,
                     gaze_chars_per_min=None, metric_version="0.1")
        if r["status"] != "certified" or r["value"] is None:
            vals.append(np.zeros(B_INNER))
            continue
        cm = np.asarray(dd["committed"], bool)
        ok = cm & np.asarray(dd["correct"], bool)
        den = t_neural + W @ np.where(cm & ~ok, pen, 0.0)
        vals.append(np.where(den > 0, 60.0 * (W @ np.where(ok, nw_, 0.0)) / np.where(den > 0, den, 1.0), 0.0))
    return np.concatenate(vals)


def stage_smoke() -> dict:
    assert SMOKE, "set P1534_SMOKE=1 (calibration subsets only)"
    arms = stage_select()
    res = {"arms": arms}
    for w in (0, 1):
        res[w] = stage_worker(w)
    log(f"smoke: {json.dumps(res, default=str)[:800]}")
    return res


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("select", "worker", "analyse", "smoke"):
        raise SystemExit("usage: run.py select | worker <0|1> | analyse | smoke")
    OUT.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    from fidetype.utils.power import keep_awake

    with keep_awake(log=log):
        t0 = time.time()
        log(f"stage {' '.join(args)} start (fidetype {FT_VERSION})")
        if args[0] == "select":
            r = stage_select()
        elif args[0] == "worker":
            r = stage_worker(int(args[1]))
        elif args[0] == "analyse":
            r = stage_analyse().get("headline")
        else:
            r = stage_smoke()
        log(f"stage {' '.join(args)} done in {time.time() - t0:.0f} s; peak {P26.peak_mb():.0f} MB; "
            f"{json.dumps(r, default=str)[:600]}")


if __name__ == "__main__":
    main()
