"""P15-37: multi-split guards (AND / Bonferroni selection) for the T15 calibration-inclusive safe WPM, and R120.
Pre-registered: plan.md; theory: method.md. CPU only, our own code (Apache-2.0). Draw code copied from P15-34 run.py
(that folder is not changed).

Stages (one process each):
  select      stage S: arm selection on val_select only (12 pseudo-calibration / pseudo-evaluation pairs)
  worker <w>  main run: worker 0 = z0 + odd k, worker 1 = even k; one file per draw; finished draws are skipped
  analyse     code checks, combined intervals per arm, R120, projection, verdicts
  smoke       calibration subsets only (P1537_SMOKE=1); never uses an evaluation set

Run (repo root), for example:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 2 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-21-p15-37-multi-split/run.py select
Per-trial files (with text) and caches: C:/Users/zhang/bci-data/derived/p15-37/ only. Repo: aggregates.
Read only: derived/p15-22/, derived/p15-26/ (decoder outputs, LLM scores, P15-22 decisions); derived/p15-29/t15/ and
derived/p15-34/t15/a0.050-d0.100/ (R120 only).
Stop file: C:/Users/zhang/bci-data/derived/p15-37/STOP (a worker stops after its current draw).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

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

SMOKE = os.environ.get("P1537_SMOKE", "0") == "1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


P26 = load_module("p1526run_p1537", REPO / "experiments/2026-11-19-p15-26-replication/run.py")
K, F, P22, P524 = P26.K, P26.F, P26.P22, P26.P524
norm = P26.norm

import fidetype.eval.harness as H  # noqa: E402
import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters.ctc_logits import to_log_probs  # noqa: E402
from fidetype.benchmark.safe_wpm import (CorrectionRule, calibration_draw_interval, format_line,  # noqa: E402
                                         guarantee_from_sheet)
from fidetype.trust.calibration import TemperatureScaler  # noqa: E402
from fidetype.trust.dropin import _norm_text, _split  # noqa: E402
from fidetype.trust.risk_control import DEFAULT_LTT_GRID, ltt_threshold  # noqa: E402

DER = K.DER
OWN_ROOT = DER / "p15-37"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-37"
ROOT = OWN_ROOT / ("smoke" + os.environ.get("P1537_SMOKE_TAG", "")) if SMOKE else OWN_ROOT
OUT = ROOT / "results-smoke" if SMOKE else HERE / "results"
LOGF = OUT / "run.log"
STOP = OWN_ROOT / "STOP"
PLAN = "plan.md (pre-registration)"
P1522 = DER / "p15-22"
P1526 = DER / "p15-26"
P1529_T15 = DER / "p15-29" / "t15"  # read only (R120)
P1534_A0 = DER / "p15-34" / "t15" / "a0.050-d0.100"  # read only (R120)

ALPHA, DELTA = 0.05, 0.1
NULL_RATE = 0.05
NULL_MAIN = 20 if SMOKE else 300
NULL_SIDE = 20
B_INNER, SEED_INNER = 2000, 0
NO_BCI = 4.0153
K_DRAWS = 2 if SMOKE else 40
J_MAX = 4
PINNED = {"frame_temperature": 2.37015800035291, "tau": 0.06996627059278283, "llm_weight": 1.0,
          "fluent": -7.88165954200173}
# arms: (kind, J); kind AND = unanimity at delta, BMAX / BMED = Bonferroni delta / J and selection
ARMS = {"S1": ("S1", 1), "AND-2": ("AND", 2), "AND-3": ("AND", 3), "AND-4": ("AND", 4),
        "BMAX-2": ("BMAX", 2), "BMAX-3": ("BMAX", 3), "BMED-3": ("BMED", 3)}
TIE_ORDER = ["AND-2", "AND-3", "AND-4", "BMAX-2", "BMED-3", "BMAX-3"]
SEL_REPEATS = 2 if SMOKE else 4
SEL_B = 50 if SMOKE else 200


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


# ---------------------------------------------------------------------------
# data + pipeline (pinned values; private caches) -- as P15-34
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def pinned_frame_temperature(T: float):
    orig = H.fit_frame_temperature
    H.fit_frame_temperature = lambda streams, truths: TemperatureScaler(temperature=float(T))
    try:
        yield
    finally:
        H.fit_frame_temperature = orig


def load_t15(wdir: Path, with_eval: bool) -> SimpleNamespace:
    from fidetype.adapters import b2t25 as Bm

    (cx, ct, cph, ckeys), held = K.load_t15("m4-13", norm_text=True, with_keys=True)
    p1405 = load_module("p1405run_p1537", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    if SMOKE:  # calibration subsets only: the evaluation set is never used
        n = int(os.environ.get("P1537_SMOKE_N", "160"))
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


def calib_kw(u: SimpleNamespace, name: str, seed: int, null_trials: int) -> dict:
    arm = P22.ARM_B1
    pipe = u.pipe

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    return dict(alpha=ALPHA, delta=DELTA, vocab=list(u.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
                frame_period=0.08, decode_fn=fn, decoder_name=name, modality="intracortical", name=name, seed=seed,
                null_trials=null_trials, null_max_commit_rate=NULL_RATE, confidence="learned")


def calibrate_guard(u, xs, ts, ph, name: str, seed: int, null_trials: int):
    """One split guard; None + controls if refused."""
    try:
        with pinned_frame_temperature(u.T):
            g = ft.calibrate(xs, ts, stream_texts=ph, **calib_kw(u, name, seed, null_trials))
    except ft.NullControlError as e:
        return None, [x.to_dict() for x in e.report]
    assert abs(g.config.frame_temperature - u.T) < 1e-12
    return g, None


# ---------------------------------------------------------------------------
# offline decision path (exactly as dropin._fit_commit_score / _learned_commit)
# ---------------------------------------------------------------------------


def item_stats(guard, x, input_scale: str | None = None) -> tuple[float, bool, str | None]:
    """(learned score, gate pass and text present, top-1 text) of one input."""
    events, _ = guard._codec.events(x, input_scale)
    sd = guard._run_layer(guard._layer, events)
    f = guard._features(sd, events)
    texts = sd.inputs.texts
    gate = guard.config.gate
    ok = bool(texts) and (gate is None or gate.violation(
        texts[0], float(sd.inputs.guard_risk) if guard.config.use_guard else None) is None)
    return float(guard.commit_score.score(f)), bool(ok), (texts[0] if texts else None)


def stats_many(guard, xs, input_scale: str | None = None) -> dict:
    s, ok, tx = [], [], []
    for x in xs:
        a, b, c = item_stats(guard, x, input_scale)
        s.append(a)
        ok.append(b)
        tx.append(c)
    return {"s": np.array(s, float), "ok": np.array(ok, bool), "text": tx}


def commits(st: dict, thr: float) -> np.ndarray:
    if not math.isfinite(thr):
        return np.zeros(len(st["s"]), bool)
    return st["ok"] & (st["s"] >= thr)


def ltt_part(guard, xs, ts, seed: int, src: np.ndarray) -> dict:
    """LTT items of a split guard: score (-inf if gate blocks), loss, source trial index."""
    n = len(xs)
    order = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, _ = _split(n)
    idx = order[n_fit + n_pol:]
    st = stats_many(guard, [xs[i] for i in idx])
    right = np.array([t is not None and _norm_text(t) == _norm_text(ts[i]) for t, i in zip(st["text"], idx)])
    s = np.where(st["ok"], st["s"], -math.inf)
    return {"s": s, "loss": (~right).astype(float), "src": np.asarray(src)[idx]}


def thr_at(lt: dict, delta: float) -> float:
    r = ltt_threshold(lt["s"], lt["loss"], alpha=ALPHA, delta=delta, grid=DEFAULT_LTT_GRID, pvalue="binomial")
    return float(r.threshold)


def wpm_formula(commit, right, nw, nc, dur) -> float:
    rule = CorrectionRule()
    commit = np.asarray(commit, bool)
    right = np.asarray(right, bool)
    ok = commit & right
    wrong = commit & ~right
    den = float(np.sum(dur) + np.sum(np.where(wrong, rule.penalty(np.asarray(nc, float)), 0.0)))
    return 60.0 * float(np.sum(np.where(ok, nw, 0.0))) / den if den > 0 else 0.0


def in_sample_value(lt: dict, thr: float, u) -> float:
    src = lt["src"]
    cm = (lt["s"] >= thr) if math.isfinite(thr) else np.zeros(len(src), bool)
    truths = [_norm_text(u.ct[i]) for i in src]
    return wpm_formula(cm, lt["loss"] == 0, [len(t.split()) for t in truths], [len(t) for t in truths],
                       [u.cdurs[i] for i in src])


def arm_decisions(kind: str, J: int, comp: list[dict], lts: list[dict], u) -> dict:
    """Commit vector, texts and meta of one arm on the inputs whose per-guard stats are in comp[j]['st'].

    comp[j] = {"st": stats on the target inputs, "thr": threshold at delta} for j = 0..J-1 (None if refused).
    """
    if any(c is None for c in comp[:J]):
        return {"refused_component": True}
    if kind in ("S1", "AND"):
        cms = [commits(c["st"], c["thr"]) for c in comp[:J]]
        n = len(cms[0])
        texts = comp[0]["st"]["text"]
        cm = np.ones(n, bool)
        for j in range(J):
            cm &= cms[j]
        if J > 1:
            same = np.array([all(comp[j]["st"]["text"][i] is not None and
                                 _norm_text(comp[j]["st"]["text"][i]) == _norm_text(texts[i] or "")
                                 for j in range(J)) for i in range(n)])
            cm &= same
        return {"commit": cm, "text": texts, "chosen": None, "thresholds": [c["thr"] for c in comp[:J]]}
    d = DELTA / J
    thr = [thr_at(lts[j], d) for j in range(J)]
    vals = [in_sample_value(lts[j], thr[j], u) for j in range(J)]
    if kind == "BMAX":
        ch = int(np.argmax(vals))  # argmax: first index on ties
    else:
        order = sorted(range(J), key=lambda j: (vals[j], j))
        ch = order[(J - 1) // 2]
    st = comp[ch]["st"]
    return {"commit": commits(st, thr[ch]), "text": st["text"], "chosen": ch, "thresholds": thr,
            "in_sample_values": vals}


# ---------------------------------------------------------------------------
# stage S: arm selection on val_select only
# ---------------------------------------------------------------------------


def stage_select() -> dict:
    wdir = ROOT / "select"
    wdir.mkdir(parents=True, exist_ok=True)
    u = load_t15(wdir, with_eval=False)
    assert u.hx is None or SMOKE
    n = len(u.cx)
    rule = CorrectionRule()
    pooled = {a: [] for a in ARMS}
    pair_vals = {a: [] for a in ARMS}
    pairs_out = []
    for q in range(SEL_REPEATS):
        perm = np.random.default_rng(h8(f"p15-37|sel|perm|{q}")).permutation(n)
        folds = np.array_split(perm, 3)
        for f in range(3):
            t0 = time.time()
            E = folds[f]
            C = np.concatenate([folds[g] for g in range(3) if g != f])
            xs, ts, ph = [u.cx[i] for i in C], [u.ct[i] for i in C], [u.cph[i] for i in C]
            comp, lts, info = [], [], []
            ex = [u.cx[i] for i in E]
            for j in range(1, J_MAX + 1):
                sd = h8(f"p15-37|sel|{q}|{f}|{j}")
                g, ctl = calibrate_guard(u, xs, ts, ph, f"p15-37-sel-{q}-{f}-{j}", sd, NULL_SIDE)
                if g is None:
                    comp.append(None)
                    lts.append(None)
                    info.append({"j": j, "refused": ctl})
                    continue
                lt = ltt_part(g, xs, ts, sd, C)
                thr = float(g.commit_score.threshold)
                chk = thr_at(lt, DELTA)
                same = chk == thr or (not math.isfinite(chk) and not math.isfinite(thr))
                if not same:
                    raise SystemExit(f"stage S check failed (q {q} f {f} j {j}): {chk} != {thr}")
                comp.append({"st": stats_many(g, ex), "thr": thr})
                lts.append(lt)
                info.append({"j": j, "threshold": thr})
                u.pipe.scorer.store.flush()
                u.pipe.save_base()
            truths = [_norm_text(u.ct[i]) for i in E]
            nw = np.array([len(t.split()) for t in truths], float)
            nc = np.array([len(t) for t in truths], float)
            dur = np.array([u.cdurs[i] for i in E], float)
            pen = rule.penalty(nc)
            rng = np.random.default_rng(1)
            W = np.empty((SEL_B, len(E)))
            for b in range(SEL_B):
                W[b] = np.bincount(rng.integers(0, len(E), len(E)), minlength=len(E))
            prow = {"q": q, "f": f, "n_C": int(len(C)), "n_E": int(len(E)), "guards": info, "arms": {}}
            for a, (kind, J) in ARMS.items():
                d = arm_decisions(kind, J, comp, lts, u)
                if d.get("refused_component"):
                    v, rate, ncm = 0.0, None, 0
                    pooled[a].append(np.zeros(SEL_B))
                else:
                    cm = d["commit"]
                    right = np.array([t is not None and _norm_text(t) == y for t, y in zip(d["text"], truths)])
                    wrong = cm & ~right
                    rate = float(wrong.mean())
                    ncm = int(cm.sum())
                    if ncm == 0 or rate > ALPHA:
                        v = 0.0
                        pooled[a].append(np.zeros(SEL_B))
                    else:
                        v = wpm_formula(cm, right, nw, nc, dur)
                        ok = cm & right
                        pooled[a].append(60.0 * (W @ np.where(ok, nw, 0.0)) / (W @ dur + W @ np.where(wrong, pen, 0.0)))
                pair_vals[a].append(v)
                prow["arms"][a] = {"value": v, "rate": rate, "commits": ncm, "chosen": d.get("chosen")}
            pairs_out.append(prow)
            log(f"select pair q{q} f{f}: thresholds {[i.get('threshold') for i in info]}; "
                f"values {{{', '.join(f'{a}: {prow['arms'][a]['value']:.2f}' for a in ARMS)}}}; "
                f"{time.time() - t0:.0f} s")
    rows = []
    for a in ARMS:
        p = np.concatenate(pooled[a])
        v = np.array(pair_vals[a])
        rows.append({"arm": a, "pred_lower": float(np.percentile(p, 2.5)), "pred_upper": float(np.percentile(p, 97.5)),
                     "pred_mean": float(v.mean()), "sd_between_pairs": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                     "zero_fraction": float(np.mean(v == 0.0))})
    cands = [r for r in rows if r["arm"] != "S1"]
    best = max(r["pred_lower"] for r in cands)
    top = [r for r in cands if best - r["pred_lower"] < 0.01]
    top.sort(key=lambda r: (-r["pred_mean"], TIE_ORDER.index(r["arm"])))
    M = top[0]["arm"]
    s1 = next(r for r in rows if r["arm"] == "S1")
    out = {"fidetype_version": FT_VERSION, "plan": PLAN, "stage": "S (val_select only; val_eval not used)",
           "repeats": SEL_REPEATS, "B": SEL_B, "pairs": pairs_out, "grid": rows, "primary": M,
           "S1_higher_than_primary": bool(s1["pred_lower"] > best)}
    from fidetype.benchmark.scoring import to_jsonable

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "selection.json").write_text(json.dumps(to_jsonable(out), indent=1) + "\n", encoding="utf-8")
    for r in rows:
        log(f"select {r['arm']}: predicted {r['pred_mean']:.3f} [{r['pred_lower']:.3f}, {r['pred_upper']:.3f}]; "
            f"SD {r['sd_between_pairs']:.3f}; zero fraction {r['zero_fraction']:.3f}")
    log(f"select: primary M = {M}; S1 higher than M: {out['S1_higher_than_primary']}")
    return {"primary": M}


# ---------------------------------------------------------------------------
# main run
# ---------------------------------------------------------------------------


def kname(k: int) -> str:
    return f"k{k:02d}"


def job(name: str) -> dict:
    if name == "z0":
        return {"name": "z0", "seed": 0, "boot_seed": None, "k": None}
    k = int(name[1:])
    return {"name": name, "seed": h8(f"p15-37|t15|cal|{k}"), "boot_seed": h8(f"p15-37|t15|boot|{k}"), "k": k}


def job_list(w: int) -> list[dict]:
    names = (["z0"] if w == 0 else []) + [kname(k) for k in range(1, K_DRAWS + 1) if k % 2 == (1 if w == 0 else 0)]
    return [job(n) for n in names]


def draw_parts(n: int, seed: int, boot_seed: int | None) -> list[np.ndarray]:
    """The P15-29 draw: split by seed, resample with replacement inside each part (source trial indices)."""
    o = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, _ = _split(n)
    parts = [o[:n_fit], o[n_fit:n_fit + n_pol], o[n_fit + n_pol:]]
    if boot_seed is not None:
        rb = np.random.default_rng(boot_seed)
        parts = [rb.choice(p, size=len(p), replace=True) for p in parts]
    return parts


def order_for(parts: list[np.ndarray], seed: int) -> tuple[np.ndarray, str]:
    """Input order L such that calibrate(seed) sees exactly these parts (P15-29)."""
    desired = np.concatenate(parts)
    n = len(desired)
    o = np.random.default_rng(seed).permutation(n)
    L = np.empty(n, dtype=int)
    L[o] = desired
    return L, hashlib.sha256(json.dumps(desired.tolist()).encode()).hexdigest()[:16]


def regroup(sample: np.ndarray, sizes: tuple[int, int, int], key: str) -> tuple[list[np.ndarray], int]:
    """Grouped first-fit re-split of a (multi)set of source trials into parts of the given sizes (plan.md)."""
    ids, counts = np.unique(sample, return_counts=True)
    for attempt in range(100):
        rng = np.random.default_rng(h8(f"{key}|{attempt}"))
        perm = rng.permutation(len(ids))
        room = list(sizes)
        parts: list[list[int]] = [[], [], []]
        okk = True
        for p in perm:
            c = int(counts[p])
            for b in range(3):
                if room[b] >= c:
                    parts[b].extend([int(ids[p])] * c)
                    room[b] -= c
                    break
            else:
                okk = False
                break
        if okk and room == [0, 0, 0]:
            return [np.array(x, dtype=int) for x in parts], attempt
    raise RuntimeError(f"regroup failed for {key}")


def control_inputs(xs: list, seed: int, n_trials: int, V: int, scale: str):
    """The uniform and shuffled control inputs that calibrate(seed) draws (rebuilt as dropin._run_controls)."""
    rng = np.random.default_rng(seed)
    rng.permutation(len(xs))
    idx = rng.integers(0, len(xs), size=n_trials)
    uni = []
    for i in idx:
        T = to_log_probs(xs[i], scale).shape[0]
        uni.append(np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V)))
    shu = []
    for i in idx:
        lp = to_log_probs(xs[i], scale)
        shu.append(lp[rng.permutation(lp.shape[0])])
    return uni, shu


def save_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    tmp.replace(path)


def run_draw(u: SimpleNamespace, jb: dict) -> dict:
    out_dir = ROOT / "t15"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"draw-{jb['name']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t0 = time.time()
    n = len(u.cx)
    sizes = _split(n)
    parts1 = draw_parts(n, jb["seed"], jb["boot_seed"])
    sample = np.concatenate(parts1)
    res: dict = {**jb, "splits": [], "checks": {}}
    comps, lts, evst, guards = [], [], [], []
    g1 = None
    xs1 = None
    for j in range(1, J_MAX + 1):
        if j == 1:
            parts, attempt, seed_j = parts1, None, jb["seed"]
        else:
            parts, attempt = regroup(sample, sizes, f"p15-37|t15|split|{jb['name']}|{j}")
            seed_j = h8(f"p15-37|t15|cal|{jb['name']}|{j}")
        disjoint = all(not (set(parts[a].tolist()) & set(parts[b].tolist())) for a, b in ((0, 1), (0, 2), (1, 2)))
        sizes_ok = tuple(len(p) for p in parts) == sizes
        L, sha = order_for(parts, seed_j)
        xs, ts, ph = [u.cx[i] for i in L], [u.ct[i] for i in L], [u.cph[i] for i in L]
        nm = f"p15-37-t15-{jb['name']}-s{j}"
        g, ctl = calibrate_guard(u, xs, ts, ph, nm, seed_j, NULL_MAIN if j == 1 else NULL_SIDE)
        sinfo = {"j": j, "seed": seed_j, "attempt": attempt, "sha_desired": sha, "disjoint": disjoint,
                 "sizes_ok": sizes_ok, "distinct_per_part": [int(len(set(p.tolist()))) for p in parts]}
        if g is None:
            sinfo.update(status="refused", controls=ctl)
            res["splits"].append(sinfo)
            comps.append(None)
            lts.append(None)
            evst.append(None)
            guards.append(None)
            log(f"{jb['name']} split {j}: REFUSED {ctl}")
            if j == 1:
                break
            continue
        thr = float(g.commit_score.threshold)
        lt = ltt_part(g, xs, ts, seed_j, L)
        chk = thr_at(lt, DELTA)
        sinfo.update(status="ok", threshold=thr, threshold_recomputed=chk,
                     c3=bool(chk == thr or (not math.isfinite(chk) and not math.isfinite(thr))),
                     sheet_controls=[(c.name, c.n_commit, c.n, c.allowed) for c in g.sheet.controls],
                     ltt_in_sample=[g.sheet.ltt_commits, g.sheet.ltt_wrong_commits], config_id=g.config_id)
        res["splits"].append(sinfo)
        guards.append(g)
        lts.append(lt)
        ev = stats_many(g, u.hx)
        evst.append(ev)
        comps.append({"st": ev, "thr": thr})
        if j == 1:
            g1, xs1 = g, xs
            # A0 = guard.decide (as P15-34), and check C1
            rows = []
            for i, x in enumerate(u.hx):
                r = g.decide(x, utterance_id=f"{nm}-{i}")
                rows.append({"i": i, "action": r.action, "text": r.text, "complete": r.complete, "truth": u.ht[i],
                             "score": r.commit_score})
                if i % 100 == 99:
                    g.audit_log.clear()
            g.audit_log.clear()
            off = commits(ev, thr)
            c1 = sum((rw["action"] == "commit") == bool(c) and (not c or norm(rw["text"] or "") == norm(t or ""))
                     for rw, c, t in zip(rows, off, ev["text"]))
            res["checks"]["C1_same"] = int(c1)
            sheet = g.sheet.to_dict()
            res["A0"] = {"status": "ok", "sheet": sheet, "rows": rows, "frame_temperature": g.config.frame_temperature,
                         "config_id": g.config_id}
        u.pipe.scorer.store.flush()
        u.pipe.save_base()
    if g1 is None:
        res.update(status="refused", seconds=round(time.time() - t0, 1))
        save_json(path, res)
        return res
    # null-control inputs of split 1, decided by every split guard
    V, scale = len(g1._codec.vocab), g1._codec.input_scale
    uni, shu = control_inputs(xs1, jb["seed"], NULL_MAIN, V, scale)
    ctl_st = []
    for j in range(J_MAX):
        if j >= len(comps) or comps[j] is None:
            ctl_st.append(None)
            continue
        ctl_st.append({"uniform": stats_many(guards[j], uni, "logits"),
                       "shuffled": stats_many(guards[j], shu, "log_probs")})
    c_u = int(commits(ctl_st[0]["uniform"], comps[0]["thr"]).sum())
    c_s = int(commits(ctl_st[0]["shuffled"], comps[0]["thr"]).sum())
    sh = {c["name"]: c["n_commit"] for c in res["A0"]["sheet"]["controls"]}
    res["checks"]["C2"] = {"offline": [c_u, c_s], "sheet": [sh.get("uniform"), sh.get("shuffled")],
                           "same": [c_u, c_s] == [sh.get("uniform"), sh.get("shuffled")]}
    allowed = int(math.floor(NULL_RATE * NULL_MAIN + 1e-9))
    base_sheet = res["A0"]["sheet"]
    res["arms"] = {}
    for a, (kind, J) in ARMS.items():
        d = arm_decisions(kind, J, comps, lts, u)
        if d.get("refused_component"):
            res["arms"][a] = {"status": "refused", "reason": "a split guard was refused"}
            continue
        ctl = {}
        for cname in ("uniform", "shuffled"):
            cc = [{"st": ctl_st[j][cname], "thr": comps[j]["thr"]} for j in range(J)]
            if kind in ("BMAX", "BMED"):
                ch = d["chosen"]
                cnt = int(commits(ctl_st[ch][cname], d["thresholds"][ch]).sum())
            else:
                cnt = int(arm_decisions(kind, J, cc, lts, u)["commit"].sum())
            ctl[cname] = cnt
        rows = [{"i": i, "action": "commit" if c else "withhold", "text": (t if c else None), "complete": None,
                 "truth": u.ht[i], "score": None} for i, (c, t) in enumerate(zip(d["commit"], d["text"]))]
        sheet = dict(base_sheet)
        sheet["alpha"], sheet["delta"] = ALPHA, DELTA
        sheet["commit_threshold"] = (d["thresholds"][d["chosen"]] if d.get("chosen") is not None
                                     else d["thresholds"][0])
        sheet["controls"] = [{"name": nmc, "description": f"split-1 control inputs, arm {a}", "n": NULL_MAIN,
                              "n_commit": ctl[nmc], "allowed": allowed, "passed": ctl[nmc] <= allowed}
                             for nmc in ("uniform", "shuffled")]
        sheet["arm_rule"] = a
        refused = any(ctl[c] > allowed for c in ctl)
        v = P524.score(rows, sheet, u.durs, "0.1")
        keys = ("value", "status", "n_commits", "n_wrong_commits", "measured_wrong_commit", "unguarded_wpm")
        res["arms"][a] = {"status": "refused" if refused else "ok", "controls": ctl, "chosen": d.get("chosen"),
                          "thresholds": d["thresholds"], "in_sample_values": d.get("in_sample_values"),
                          "sheet": sheet, "rows": rows, "v0_1": {k: v.get(k) for k in keys}}
    res["status"] = "ok"
    res["seconds"] = round(time.time() - t0, 1)
    res["misses_after"] = {"base_nbest_new_decodes": len(u.pipe.base) - u.base_start,
                           "llm_texts_scored_live": u.lazy.texts_scored}
    res["peak_mb"] = round(P26.peak_mb(), 1)
    save_json(path, res)
    a0v = P524.score(res["A0"]["rows"], res["A0"]["sheet"], u.durs, "0.1")
    log(f"{jb['name']} (seed {jb['seed']}, boot {jb['boot_seed']}): A0 {format_line(a0v)}; thresholds "
        f"{[s.get('threshold') for s in res['splits']]}; C1 {res['checks']['C1_same']}/{len(u.hx)}; C2 "
        f"{res['checks']['C2']['same']}; arms {{{', '.join(f'{a}: {x.get('v0_1', {}).get('value', 0) or 0:.2f} {x.get('v0_1', {}).get('status', x['status'])}' for a, x in res['arms'].items())}}}; "
        f"{res['seconds']:.0f} s; peak {res['peak_mb']} MB")
    return res


def stage_worker(w: int) -> dict:
    wdir = ROOT / f"w{w}"
    wdir.mkdir(parents=True, exist_ok=True)
    u = None
    done, stopped = [], False
    for jb in job_list(w):
        if (ROOT / "t15" / f"draw-{jb['name']}.json").exists():
            done.append(jb["name"])
            continue
        if STOP.exists():
            stopped = True
            log(f"worker {w}: stop file found; stopping before {jb['name']}")
            break
        if u is None:
            u = load_t15(wdir, with_eval=True)
        run_draw(u, jb)
        done.append(jb["name"])
        gc.collect()
    return {"worker": w, "done": done, "stopped": stopped, "peak_mb": round(P26.peak_mb(), 1)}


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------


def load_json(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def as_draw(rows: list[dict] | None, sheet: dict | None, refused: bool) -> dict:
    if refused or rows is None:
        return {"refused": True}
    a = P524.trial_arrays(rows, "0.1")
    return {"committed": a["committed"], "correct": a["correct"], "guarantee": guarantee_from_sheet(sheet)}


def lengths(rows: list[dict]) -> tuple[list[int], list[int]]:
    return [len(r["truth"].split()) for r in rows], [len(r["truth"]) for r in rows]


def same_rows(a: list[dict], b: list[dict]) -> int:
    return sum(x["action"] == y["action"] and norm(x["text"] or "") == norm(y["text"] or "") for x, y in zip(a, b))


def eval_durations() -> list[float]:
    _c, (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
    p1405 = load_module("p1405run_p1537", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    return p1405.t15_durations(hkeys)


def verdict(comb: dict) -> str:
    lo, mean = comb["interval"][0], comb["value"]
    if lo > NO_BCI:
        return "clearly above after calibration uncertainty"
    if mean > NO_BCI:
        return "above, but inside the combined interval"
    return "not above"


def combine(draws: list[dict], nw, nc, durs) -> dict:
    comb = calibration_draw_interval(draws, nw, nc, durs, B=B_INNER, seed=SEED_INNER, reference=NO_BCI, metric_version="0.1")
    pub = {k: v for k, v in comb.items() if k != "draws"}
    vals = [x["value"] for x in comb["draws"]]
    pub["draw_values"] = vals
    pub["draw_statuses"] = [x["status"] for x in comb["draws"]]
    v = np.array([x if x is not None else 0.0 for x in vals], float)
    pub["median"] = float(np.median(v))
    pub["range"] = [float(v.min()), float(v.max())]
    pub["fraction_above_reference"] = float(np.mean(v > NO_BCI))
    pub["verdict"] = verdict(comb)
    return pub


def projection(c: dict) -> dict:
    mu, sb, sw = c["value"], c["sd_between_draws"], c["sd_within_draw"]
    need = ((mu - NO_BCI) / 1.96) ** 2 - sw ** 2
    nz = sum(s != "certified" for s in c["draw_statuses"])
    out = {"mean": mu, "sd_between": sb, "sd_within": sw, "non_credited_draws": nz, "K": len(c["draw_statuses"]),
           "assumption": "sd_between ~ 1/sqrt(n); mean and sd_within fixed (plan.md)"}
    if mu <= NO_BCI or need <= 0:
        out.update(sd_between_needed=None, n_needed=None, note="no positive sd_between reaches the reference")
    else:
        sbs = math.sqrt(need)
        out.update(sd_between_needed=sbs, n_needed=722.0 * (sb / sbs) ** 2)
    return out


def stage_analyse() -> dict:
    sel = load_json(OUT / "selection.json")
    M = sel["primary"]
    out: dict = {"fidetype_version": FT_VERSION, "plan": PLAN, "B_inner": B_INNER, "no_bci_reference": NO_BCI,
                 "primary": M, "results": {}}
    z0 = load_json(ROOT / "t15" / "draw-z0.json")
    ref_rows = json.loads((P1522 / "arm-llm_learned.json").read_text(encoding="utf-8"))["rows"]
    durs = eval_durations()
    x4: dict = {"reference": "p15-22/arm-llm_learned.json"}
    if z0 is None or z0.get("status") != "ok":
        x4.update(reproduces=False, reason="z0 missing or refused")
    else:
        rows0 = z0["A0"]["rows"]
        nw, nc = lengths(rows0)
        v = P524.score(rows0, z0["A0"]["sheet"], durs, "0.1")
        x4["same_action_and_text"] = same_rows(rows0, ref_rows)
        x4["n"] = len(ref_rows)
        x4["z0_value"] = v["value"]
        one = calibration_draw_interval([as_draw(rows0, z0["A0"]["sheet"], False)], nw, nc, durs, B=B_INNER,
                                        seed=SEED_INNER, metric_version="0.1")
        x4["k1_interval"] = one["interval"]
        x4["z0_threshold_commits_wrong"] = [z0["A0"]["sheet"].get("commit_threshold"), v["n_commits"],
                                            v["n_wrong_commits"]]
        x4["reproduces"] = (x4["same_action_and_text"] == x4["n"] == len(rows0)
                            and [round(t, 2) for t in one["interval"]] == [4.25, 5.57]
                            and round(float(x4["z0_threshold_commits_wrong"][0]), 2) == 0.82
                            and x4["z0_threshold_commits_wrong"][1:] == [196, 13] and round(v["value"], 2) == 4.91)
    out["X4_code_check"] = x4
    log(f"X4: {x4}")
    names = [kname(k) for k in range(1, K_DRAWS + 1)]
    draws = [load_json(ROOT / "t15" / f"draw-{n}.json") for n in names]
    # code checks C1-C4 over all draws (and z0)
    chk = {"C1": True, "C2": True, "C3": True, "C4": True, "failed": []}
    for d in [z0] + draws:
        if d is None or d.get("status") != "ok":
            continue
        if d["checks"].get("C1_same") != len(d["A0"]["rows"]):
            chk["C1"] = False
            chk["failed"].append((d["name"], "C1"))
        if not (d["checks"].get("C2") or {}).get("same"):
            chk["C2"] = False
            chk["failed"].append((d["name"], "C2"))
        for s in d["splits"]:
            if s.get("status") == "ok" and not s.get("c3"):
                chk["C3"] = False
                chk["failed"].append((d["name"], f"C3 split {s['j']}"))
            if not (s["disjoint"] and s["sizes_ok"]):
                chk["C4"] = False
                chk["failed"].append((d["name"], f"C4 split {s['j']}"))
    out["code_checks"] = chk
    log(f"code checks: {chk}")
    if not x4.get("reproduces") or not all(chk[c] for c in ("C1", "C2", "C3", "C4")):
        out["verdict"] = "not decided: a code check fails"
        (OUT / "results.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
        return out
    if any(d is None for d in draws):
        out["verdict"] = f"not decided: only {sum(d is not None for d in draws)} of {K_DRAWS} draws"
        (OUT / "results.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
        return out
    rows0 = z0["A0"]["rows"]
    nw, nc = lengths(rows0)
    for d in draws:
        if d.get("status") == "ok":
            assert [r["truth"] for r in d["A0"]["rows"]] == [r["truth"] for r in rows0]

    def arm_draw(d: dict, a: str) -> dict:
        if d.get("status") != "ok":
            return {"refused": True}
        if a == "A0":
            return as_draw(d["A0"]["rows"], d["A0"]["sheet"], False)
        x = d["arms"][a]
        return as_draw(x.get("rows"), x.get("sheet"), x["status"] != "ok")

    arm_list = ["A0"] + list(ARMS)
    for a in arm_list:
        c = combine([arm_draw(d, a) for d in draws], nw, nc, durs)
        if a != "A0":
            ok = [d["arms"][a] for d in draws if d.get("status") == "ok" and d["arms"][a]["status"] == "ok"]
            c["mean_commits"] = float(np.mean([x["v0_1"]["n_commits"] for x in ok])) if ok else None
            c["mean_wrong_commits"] = float(np.mean([x["v0_1"]["n_wrong_commits"] for x in ok])) if ok else None
            c["max_controls"] = {nmc: max(x["controls"][nmc] for x in ok) for nmc in ("uniform", "shuffled")} if ok else None
            if ARMS[a][0] in ("BMAX", "BMED"):
                c["chosen_counts"] = {str(j): sum(x["chosen"] == j for x in ok) for j in range(ARMS[a][1])}
        out["results"][a] = c
        log(f"{a}: {c['value']:.3f} [{c['interval'][0]:.3f}, {c['interval'][1]:.3f}] statuses {c['statuses']}; "
            f"SD between {c['sd_between_draws']:.3f} within {c['sd_within_draw']:.3f}; verdict {c['verdict']}")
    v0 = np.array([x or 0.0 for x in out["results"]["A0"]["draw_values"]])
    s0 = out["results"]["A0"]["draw_statuses"]
    for a in ARMS:
        vj = np.array([x or 0.0 for x in out["results"][a]["draw_values"]])
        sj = out["results"][a]["draw_statuses"]
        both = [y - x for x, y, p, q in zip(v0, vj, s0, sj) if p == "certified" and q == "certified"]
        out["results"][a]["paired_vs_A0"] = {
            "mean_diff_all": float(np.mean(vj - v0)), "mean_diff_both_certified": float(np.mean(both)) if both else None,
            "A0_noncredited_now_certified": sum(p != "certified" and q == "certified" for p, q in zip(s0, sj)),
            "A0_certified_now_not": sum(p == "certified" and q != "certified" for p, q in zip(s0, sj))}
    # R120
    r120: dict = {"sources": ["p15-29/t15 k01-k40", "p15-34/t15/a0.050-d0.100 k01-k40", "p15-37 A0 k01-k40"]}
    try:
        r29 = json.loads((REPO / "experiments/2026-11-20-p15-29-calibration-ci/results/results.json").read_text("utf-8"))
        r34 = json.loads((REPO / "experiments/2026-11-20-p15-34-margin-guard/results/results.json").read_text("utf-8"))
        x4_29 = bool(r29["units"]["t15"]["X4_code_check"]["reproduces"])
        x4_34 = bool(r34["X4_code_check"]["reproduces"])
        d29 = [load_json(P1529_T15 / f"draw-{n}.json") for n in names]
        d34 = [load_json(P1534_A0 / f"draw-{n}.json") for n in names]
        allx = d29 + d34 + [{"status": d["status"], "rows": d["A0"]["rows"], "sheet": d["A0"]["sheet"],
                             "frame_temperature": d["A0"]["frame_temperature"], "seed": d["seed"]}
                            if d.get("status") == "ok" else {"status": d.get("status"), "seed": d["seed"]}
                            for d in draws]
        bad = []
        truths0 = [r["truth"] for r in rows0]
        for i, d in enumerate(allx):
            if d is None:
                bad.append((i, "missing"))
                continue
            if d.get("status") not in ("ok", "refused"):
                bad.append((i, f"status {d.get('status')}"))
            if d.get("status") == "ok":
                sh = d["sheet"]
                if not (sh["alpha"] == 0.05 and sh["delta"] == 0.1 and sh["n_ltt"] == 271):
                    bad.append((i, "sheet"))
                if abs(float(d["frame_temperature"]) - PINNED["frame_temperature"]) > 1e-12:
                    bad.append((i, "T"))
                if [norm(r["truth"]) for r in d["rows"]] != [norm(t) for t in truths0]:
                    bad.append((i, "truths"))
        seeds = [d.get("seed") for d in allx if d]
        overlap = len(seeds) != len(set(seeds))
        r120["compat"] = {"x4_p15_29": x4_29, "x4_p15_34": x4_34, "bad": bad[:20], "n_bad": len(bad),
                          "seed_overlap": overlap}
        if x4_29 and x4_34 and not bad and not overlap:
            dd = [as_draw(d.get("rows"), d.get("sheet"), d.get("status") != "ok") for d in allx]
            c = combine(dd, nw, nc, durs)
            c["K"] = len(dd)
            r120.update(c)
            r120["note"] = "not blind (80 of 120 draws known); cannot close a gap (plan.md)"
            log(f"R120: {c['value']:.3f} [{c['interval'][0]:.3f}, {c['interval'][1]:.3f}] statuses {c['statuses']}; "
                f"SD between {c['sd_between_draws']:.3f}; verdict {c['verdict']}")
        else:
            r120["verdict"] = "not decided: a compatibility check fails"
            log(f"R120 not decided: {r120['compat']}")
    except Exception as e:  # reported, never hidden
        r120["verdict"] = f"not decided: {type(e).__name__}: {e}"
        log(f"R120 error: {e}")
    out["R120"] = {k: v for k, v in r120.items()}
    base = r120 if "sd_between_draws" in r120 else out["results"]["A0"]
    out["projection"] = projection(base)
    out["projection"]["basis"] = "R120" if base is r120 else "A0 (this run)"
    m = out["results"][M]
    out["headline"] = {"primary_arm": M, "verdict": m["verdict"],
                       "criterion_met": m["verdict"] == "clearly above after calibration uncertainty"}
    from fidetype.benchmark.scoring import to_jsonable

    (OUT / "results.json").write_text(json.dumps(to_jsonable(out), indent=1, default=str) + "\n", encoding="utf-8")
    log(f"analyse: headline {out['headline']}; projection {out['projection']}")
    return out


def stage_smoke() -> dict:
    assert SMOKE, "set P1537_SMOKE=1 (calibration subsets only)"
    res = {"select": None if os.environ.get("P1537_SMOKE_SKIP_SELECT") == "1" else stage_select()}
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
