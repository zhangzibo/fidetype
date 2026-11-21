"""P15-40: between-draw SD of the T15 calibration-inclusive safe WPM at n = 361 / 481 / 722; exponent and revised n*.
Pre-registered: plan.md (commit f83397a). CPU only, our own code (Apache-2.0). Data / pipeline / draw helpers copied
from P15-37 run.py (that folder is not changed).

Stages (one process each):
  worker      X1 check draws, then the k-major job list (D2-361, D2-481, D2-722, D1-361, D1-481 per k); one file per
              draw; finished draws are skipped; no new draw after the time limit (launch + 8 h, P1540_DEADLINE)
  analyse     code checks, cell SDs, log-log fit, bootstrap of the exponent, revised n*
  smoke       calibration subsets only (P1540_SMOKE=1); never loads val_eval

Per-trial files (with text) and caches: C:/Users/zhang/bci-data/derived/p15-40/ only. Repo: aggregates.
Read only: derived/p15-22/, derived/p15-26/ (caches); derived/p15-37/t15/draw-k01.json, draw-k02.json (X1);
the committed P15-37 results/results.json (R120 draw values).
Stop file: C:/Users/zhang/bci-data/derived/p15-40/STOP (the worker stops after its current draw).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

import contextlib  # noqa: E402
import datetime as dt  # noqa: E402
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

SMOKE = os.environ.get("P1540_SMOKE", "0") == "1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


P26 = load_module("p1526run_p1540", REPO / "experiments/2026-11-19-p15-26-replication/run.py")
K, F, P22, P524 = P26.K, P26.F, P26.P22, P26.P524
norm = P26.norm

import fidetype.eval.harness as H  # noqa: E402
import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import calibration_draw_interval, format_line, guarantee_from_sheet  # noqa: E402
from fidetype.trust.calibration import TemperatureScaler  # noqa: E402
from fidetype.trust.dropin import _split  # noqa: E402

DER = K.DER
OWN_ROOT = DER / "p15-40"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-40"
ROOT = OWN_ROOT / "smoke" if SMOKE else OWN_ROOT
OUT = ROOT / "results-smoke" if SMOKE else HERE / "results"
LOGF = OUT / "run.log"
STOP = OWN_ROOT / "STOP"
PLAN = "plan.md (pre-registration, commit f83397a)"
P1522 = DER / "p15-22"
P1526 = DER / "p15-26"
P1537_T15 = DER / "p15-37" / "t15"  # read only (X1, C2)
P1537_RESULTS = REPO / "experiments/2026-11-21-p15-37-multi-split/results/results.json"  # read only (R120)

ALPHA, DELTA = 0.05, 0.1
NULL_RATE = 0.05
NULL_TRIALS = 20
B_INNER, SEED_INNER = 2000, 0
B_FIT, SEED_FIT = 2000, 40
NO_BCI = 4.0153
K_TARGET = {"d1": 2, "d2": 3} if SMOKE else {"d1": 40, "d2": 100}  # plan addendum
K_MIN = 2 if SMOKE else 20
N_POOL = 722
SIZES = (361, 481, 722)
CELLS = [("d2", 361), ("d2", 481), ("d2", 722), ("d1", 361), ("d1", 481)]
PINNED = {"frame_temperature": 2.37015800035291, "tau": 0.06996627059278283, "llm_weight": 1.0,
          "fluent": -7.88165954200173}
# P15-37 R120 projection numbers (results.json "projection"; checked at analysis)
R120_SD, R120_SD_NEEDED = 1.0389268195716381, 0.5310194088768984


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
# data + pipeline (pinned values; private caches) -- copied from P15-37
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def pinned_frame_temperature(T: float):
    orig = H.fit_frame_temperature
    H.fit_frame_temperature = lambda streams, truths: TemperatureScaler(temperature=float(T))
    try:
        yield
    finally:
        H.fit_frame_temperature = orig


def load_t15(wdir: Path) -> SimpleNamespace:
    from fidetype.adapters import b2t25 as Bm

    (cx, ct, cph, ckeys), held = K.load_t15("m4-13", norm_text=True, with_keys=True)
    p1405 = load_module("p1405run_p1540", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    if SMOKE:  # calibration subsets only: the evaluation set is never used
        n = int(os.environ.get("P1540_SMOKE_N", "200"))
        hx, ht, hkeys = cx[n:n + 40], ct[n:n + 40], ckeys[n:n + 40]
        cx, ct, cph = cx[:n], ct[:n], cph[:n]
    else:
        hx, ht, _hph, hkeys = held
    durs = p1405.t15_durations(hkeys)
    del held
    gc.collect()
    cache = wdir / "llm-cache-t15.sqlite"
    n_cached = P26.merged_llm_cache(cache, [P1526 / "llm-cache-t15.sqlite", P1522 / "llm-cache.sqlite"])
    dec, _bt = K.word_decoder()
    pipe, lazy = P26.make_pipe("t15", wdir, dec, cache, P1522 / "base-nbest-t15.pkl")
    pv = PINNED
    pipe.grounding.tau, pipe.lam, pipe.frame_T, pipe.fluent_thr = pv["tau"], pv["llm_weight"], \
        pv["frame_temperature"], pv["fluent"]
    u = SimpleNamespace(pipe=pipe, lazy=lazy, base_start=len(pipe.base), B=Bm, cx=cx, ct=ct, cph=cph, hx=hx,
                        ht=[norm(t) for t in ht], durs=durs, T=pv["frame_temperature"])
    log(f"t15: loaded; calibration pool {len(cx)}, evaluation {len(hx)}; llm cache {n_cached}; pinned {pv}")
    return u


def calib_kw(u: SimpleNamespace, name: str, seed: int) -> dict:
    arm = P22.ARM_B1
    pipe = u.pipe

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    return dict(alpha=ALPHA, delta=DELTA, vocab=list(u.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
                frame_period=0.08, decode_fn=fn, decoder_name=name, modality="intracortical", name=name, seed=seed,
                null_trials=NULL_TRIALS, null_max_commit_rate=NULL_RATE, confidence="learned")


def draw_parts(n: int, seed: int, boot_seed: int | None) -> list[np.ndarray]:
    """The P15-29 draw on indices 0..n-1: split by seed, resample with replacement inside each part."""
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
    """Grouped first-fit split of a multiset of source trials into parts of the given sizes (P15-37)."""
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


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------


def cell_name(design: str, n: int, k: int) -> str:
    return f"{design}-n{n}-k{k:02d}"


def job_list(pool: int) -> list[dict]:
    jobs = []
    if not SMOKE:
        for k in (1, 2):  # X1: the P15-37 A0 seeds at n = 722 (D1 rule = the P15-29 draw)
            jobs.append({"name": f"x1-k{k:02d}", "design": "x1", "n": pool, "k": k,
                         "seed": h8(f"p15-37|t15|cal|{k}"), "boot_seed": h8(f"p15-37|t15|boot|{k}")})
    sizes = smoke_sizes(pool) if SMOKE else dict(zip(SIZES, SIZES))
    for k in range(1, max(K_TARGET.values()) + 1):
        for design, n0 in CELLS:
            if k > K_TARGET[design]:
                continue
            n = sizes[n0]
            jobs.append({"name": cell_name(design, n0, k), "design": design, "n": n, "n_label": n0, "k": k,
                         "seed": h8(f"p15-40|{design}|cal|{n0}|{k}"),
                         "boot_seed": h8(f"p15-40|d1|boot|{n0}|{k}") if design == "d1" else None})
    return jobs


def smoke_sizes(pool: int) -> dict:
    return {361: pool // 2, 481: int(round(pool * 481 / 722)), 722: pool}


def parts_for(jb: dict, pool: int) -> tuple[list[np.ndarray], dict]:
    n, n0, k = jb["n"], jb.get("n_label", jb["n"]), jb["k"]
    if jb["design"] == "x1":
        return draw_parts(pool, jb["seed"], jb["boot_seed"]), {}
    if jb["design"] == "d1":
        sub = np.random.default_rng(h8(f"p15-40|d1|sub|{n0}|{k}")).permutation(pool)[:n]
        loc = draw_parts(n, jb["seed"], jb["boot_seed"])
        return [sub[p] for p in loc], {"n_distinct_subsample": int(len(set(sub.tolist())))}
    smp = np.random.default_rng(h8(f"p15-40|d2|boot|{n0}|{k}")).integers(0, pool, n)
    parts, attempt = regroup(smp, _split(n), f"p15-40|d2|split|{n0}|{k}")
    return parts, {"regroup_attempt": attempt, "n_distinct_sample": int(len(set(smp.tolist())))}


def save_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    tmp.replace(path)


def run_draw(u: SimpleNamespace, jb: dict) -> dict:
    out_dir = ROOT / "draws"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{jb['name']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t0 = time.time()
    pool = len(u.cx)
    parts, extra = parts_for(jb, pool)
    disjoint = all(not (set(parts[a].tolist()) & set(parts[b].tolist())) for a, b in ((0, 1), (0, 2), (1, 2)))
    sizes_ok = tuple(len(p) for p in parts) == _split(jb["n"])
    L, sha = order_for(parts, jb["seed"])
    xs, ts, ph = [u.cx[i] for i in L], [u.ct[i] for i in L], [u.cph[i] for i in L]
    nm = f"p15-40-t15-{jb['name']}"
    res = {**jb, **extra, "sha_desired": sha, "disjoint": disjoint, "sizes_ok": sizes_ok, "sizes": _split(jb["n"]),
           "distinct_per_part": [int(len(set(p.tolist()))) for p in parts]}
    try:
        with pinned_frame_temperature(u.T):
            g = ft.calibrate(xs, ts, stream_texts=ph, **calib_kw(u, nm, jb["seed"]))
    except ft.NullControlError as e:
        res.update(status="refused", controls=[x.to_dict() for x in e.report], seconds=round(time.time() - t0, 1))
        save_json(path, res)
        log(f"{jb['name']}: REFUSED {res['controls']}")
        return res
    rows = []
    for i, x in enumerate(u.hx):
        r = g.decide(x, utterance_id=f"{nm}-{i}")
        rows.append({"i": i, "action": r.action, "text": r.text, "complete": r.complete, "truth": u.ht[i],
                     "score": r.commit_score})
        if i % 100 == 99:
            g.audit_log.clear()
    g.audit_log.clear()
    u.pipe.scorer.store.flush()
    u.pipe.save_base()
    sheet = g.sheet.to_dict()
    v = P524.score(rows, sheet, u.durs, "0.1")
    res.update(status="ok", sheet=sheet, rows=rows, frame_temperature=g.config.frame_temperature,
               config_id=g.config_id,
               v0_1={k: v.get(k) for k in ("value", "status", "n_commits", "n_wrong_commits", "measured_wrong_commit",
                                           "unguarded_wpm", "n_cal")},
               seconds=round(time.time() - t0, 1), peak_mb=round(P26.peak_mb(), 1),
               misses_after={"base_nbest_new_decodes": len(u.pipe.base) - u.base_start,
                             "llm_texts_scored_live": u.lazy.texts_scored})
    save_json(path, res)
    log(f"{jb['name']} (n {jb['n']}, seed {jb['seed']}): {format_line(v)}; threshold {sheet.get('commit_threshold')}; "
        f"n_ltt {sheet.get('n_ltt')}; controls {[(c['name'], c['n_commit'], c['allowed']) for c in sheet['controls']]}; "
        f"distinct/part {res['distinct_per_part']}; {res['seconds']:.0f} s")
    return res


def deadline() -> dt.datetime:
    s = os.environ.get("P1540_DEADLINE")
    if s:
        return dt.datetime.fromisoformat(s)
    return dt.datetime.now() + dt.timedelta(hours=8)


def stage_worker() -> dict:
    wdir = ROOT / "w0"
    wdir.mkdir(parents=True, exist_ok=True)
    dl = deadline()
    log(f"worker: time limit {dl.isoformat(timespec='seconds')} (no new draw after it)")
    u = None
    done, stopped, timed_out = [], False, False
    for jb in job_list(N_POOL if not SMOKE else int(os.environ.get("P1540_SMOKE_N", "200"))):
        if (ROOT / "draws" / f"{jb['name']}.json").exists():
            done.append(jb["name"])
            continue
        if STOP.exists():
            stopped = True
            log(f"worker: stop file found; stopping before {jb['name']}")
            break
        if dt.datetime.now() >= dl:
            timed_out = True
            log(f"worker: time limit reached; stopping before {jb['name']}")
            break
        if u is None:
            u = load_t15(wdir)
            assert len(u.cx) == (N_POOL if not SMOKE else len(u.cx))
        run_draw(u, jb)
        done.append(jb["name"])
        gc.collect()
    return {"done": len(done), "stopped": stopped, "timed_out": timed_out, "peak_mb": round(P26.peak_mb(), 1)}


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------


def load_json(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def as_draw(d: dict) -> dict:
    if d.get("status") != "ok":
        return {"refused": True}
    a = P524.trial_arrays(d["rows"], "0.1")
    return {"committed": a["committed"], "correct": a["correct"], "guarantee": guarantee_from_sheet(d["sheet"])}


def same_rows(a: list[dict], b: list[dict]) -> int:
    return sum(x["action"] == y["action"] and norm(x["text"] or "") == norm(y["text"] or "") for x, y in zip(a, b))


def eval_durations() -> list[float]:
    _c, (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
    p1405 = load_module("p1405run_p1540", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    return p1405.t15_durations(hkeys)


def fit(sds: dict) -> tuple[float, float]:
    """OLS of log sd on log n; returns (intercept a, slope)."""
    ns = sorted(sds)
    x = np.log(np.array(ns, float))
    y = np.log(np.array([sds[n] for n in ns], float))
    slope, a = np.polyfit(x, y, 1)
    return float(a), float(slope)


def sd_needed(mu: float, sw: float) -> float | None:
    need = ((mu - NO_BCI) / 1.96) ** 2 - sw ** 2
    return math.sqrt(need) if mu > NO_BCI and need > 0 else None


def n_star_line(a: float, slope: float, sbs: float | None) -> float | None:
    if sbs is None or slope >= 0:
        return None
    ln = (math.log(sbs) - a) / slope
    return float(math.exp(ln)) if ln < 700 else math.inf


def n_star_anchor(sd722: float, b: float, sbs: float | None) -> float | None:
    if sbs is None or b <= 0:
        return None
    ln = math.log(722.0) + math.log(sd722 / sbs) / b
    return float(math.exp(ln)) if ln < 700 else math.inf


def pct(a: list[float]) -> list[float] | None:
    a = [x for x in a if x is not None and math.isfinite(x)]
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if a else None


def boot_fit(vals: dict, rng: np.random.Generator, mu_cell: int | None, sw: float | None) -> dict:
    """Bootstrap over draws inside each cell: exponent b and (if mu_cell) the line-based n*."""
    bs, nss, dropped = [], [], 0
    for _ in range(B_FIT):
        sds, rs = {}, {}
        for n, v in vals.items():
            r = v[rng.integers(0, len(v), len(v))]
            rs[n] = r
            sds[n] = float(r.std(ddof=1))
        if any(s <= 0 for s in sds.values()):
            dropped += 1
            continue
        a, slope = fit(sds)
        bs.append(-slope)
        if mu_cell is not None:
            nss.append(n_star_line(a, slope, sd_needed(float(rs[mu_cell].mean()), sw)))
    out = {"b_interval": pct(bs), "b_boot_median": float(np.median(bs)) if bs else None, "dropped": dropped}
    if mu_cell is not None and nss:
        # not reachable (None) counts as an infinite n*; order-statistic percentiles keep inf without interpolation
        arr = np.array([math.inf if x is None else x for x in nss], float)
        out["n_star_interval"] = [float(np.percentile(arr, 2.5, method="inverted_cdf")),
                                  float(np.percentile(arr, 97.5, method="inverted_cdf"))]
        out["n_star_boot_median"] = float(np.percentile(arr, 50, method="inverted_cdf"))
        out["n_star_not_reachable_fraction"] = float(np.mean([x is None for x in nss]))
        out["n_star_above_1e6_fraction"] = float(np.mean(arr > 1e6))
    return out


def stage_analyse() -> dict:
    out: dict = {"fidetype_version": FT_VERSION, "plan": PLAN, "no_bci_reference": NO_BCI, "B_inner": B_INNER,
                 "B_fit": B_FIT, "null_trials": NULL_TRIALS}
    durs = eval_durations()
    z0 = load_json(P1537_T15 / "draw-z0.json")
    truths0 = [r["truth"] for r in z0["A0"]["rows"]]
    nw = [len(t.split()) for t in truths0]
    nc = [len(t) for t in truths0]
    # X1
    x1 = {}
    for k in (1, 2):
        d = load_json(ROOT / "draws" / f"x1-k{k:02d}.json")
        ref = load_json(P1537_T15 / f"draw-k{k:02d}.json")
        if d is None or d.get("status") != "ok" or ref is None:
            x1[f"k{k:02d}"] = {"pass": False, "reason": "missing or refused"}
            continue
        s = same_rows(d["rows"], ref["A0"]["rows"])
        t_ok = d["sheet"].get("commit_threshold") == ref["A0"]["sheet"].get("commit_threshold")
        x1[f"k{k:02d}"] = {"same_action_and_text": s, "n": len(ref["A0"]["rows"]), "threshold_same": t_ok,
                           "pass": s == len(ref["A0"]["rows"]) == 701 and t_ok}
    x1["pass"] = all(v["pass"] for kk, v in x1.items() if kk.startswith("k"))
    out["X1"] = x1
    log(f"X1: {x1}")
    # draws per cell
    cells: dict = {}
    for design, n in CELLS:
        ds = []
        for k in range(1, K_TARGET[design] + 1):
            d = load_json(ROOT / "draws" / f"{cell_name(design, n, k)}.json")
            if d is None:
                break
            ds.append(d)
        cells[(design, n)] = ds
    kd = {d: min(len(cells[c]) for c in cells if c[0] == d) for d in ("d1", "d2")}
    out["K_used"] = kd
    # C1, C2
    c1, c2, bad = True, True, []
    for (design, n), ds in cells.items():
        for d in ds[:kd[design]]:
            if not (d["disjoint"] and d["sizes_ok"]):
                c1 = False
                bad.append((d["name"], "parts"))
            if d.get("status") == "ok":
                sh = d["sheet"]
                if not (sh["alpha"] == ALPHA and sh["delta"] == DELTA and sh["n_ltt"] == _split(n)[2]
                        and abs(float(d["frame_temperature"]) - PINNED["frame_temperature"]) < 1e-12):
                    c1 = False
                    bad.append((d["name"], "sheet"))
                if [r["truth"] for r in d["rows"]] != truths0:
                    c2 = False
                    bad.append((d["name"], "truths"))
    out["code_checks"] = {"C1": c1, "C2": c2, "failed": bad[:20]}
    log(f"code checks: C1 {c1}, C2 {c2}, failed {bad[:5]}")
    if not (x1["pass"] and c1 and c2):
        out["verdict"] = "not decided: a code check fails"
        (OUT / "results.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
        return out
    # cell summaries
    vals: dict = {"d1": {}, "d2": {}}
    vals_cert: dict = {"d1": {}, "d2": {}}
    summ: dict = {}
    c3 = True
    for (design, n), ds in cells.items():
        ds = ds[:kd[design]]
        if len(ds) < 2:
            continue
        comb = calibration_draw_interval([as_draw(d) for d in ds], nw, nc, durs, B=B_INNER, seed=SEED_INNER,
                                         reference=NO_BCI)
        v = np.array([x["value"] for x in comb["draws"]], float)
        st = [x["status"] for x in comb["draws"]]
        own_sd = float(v.std(ddof=1))
        c3 = c3 and abs(own_sd - comb["sd_between_draws"]) < 1e-9
        cert = np.array([x for x, s in zip(v, st) if s == "certified"], float)
        ok = [d for d in ds if d.get("status") == "ok"]
        vals[design][n] = v
        vals_cert[design][n] = cert
        summ[f"{design}-{n}"] = {
            "design": design, "n": n, "K": len(ds), "statuses": comb["statuses"], "mean": comb["value"],
            "interval": comb["interval"], "sd_between": comb["sd_between_draws"], "sd_within": comb["sd_within_draw"],
            "sd_between_certified_only": float(cert.std(ddof=1)) if len(cert) > 1 else None,
            "median": float(np.median(v)), "range": [float(v.min()), float(v.max())],
            "fraction_above_reference": float(np.mean(v > NO_BCI)),
            "mean_commits": float(np.mean([d["v0_1"]["n_commits"] for d in ok])) if ok else None,
            "mean_wrong_commits": float(np.mean([d["v0_1"]["n_wrong_commits"] for d in ok])) if ok else None,
            "mean_threshold": float(np.mean([d["sheet"]["commit_threshold"] for d in ok
                                             if d["sheet"].get("commit_threshold") is not None
                                             and math.isfinite(d["sheet"]["commit_threshold"])])) if ok else None,
            "max_controls": max((c["n_commit"] for d in ok for c in d["sheet"]["controls"]), default=None),
            "mean_seconds": float(np.mean([d["seconds"] for d in ds])),
            "draw_values": v.tolist(), "draw_statuses": st}
        log(f"cell {design}-{n}: K {len(ds)}; {comb['value']:.3f} [{comb['interval'][0]:.3f}, {comb['interval'][1]:.3f}]; "
            f"SD between {comb['sd_between_draws']:.3f} (certified only {summ[f'{design}-{n}']['sd_between_certified_only']}); "
            f"within {comb['sd_within_draw']:.3f}; statuses {comb['statuses']}")
    # D1 722 cell = R120 (P15-37 results.json)
    r37 = json.loads(P1537_RESULTS.read_text(encoding="utf-8"))
    R = r37["R120"]
    assert abs(R["sd_between_draws"] - R120_SD) < 1e-12 and abs(r37["projection"]["sd_between_needed"] - R120_SD_NEEDED) < 1e-12
    rv = np.array([x if x is not None else 0.0 for x in R["draw_values"]], float)
    rcert = np.array([x for x, s in zip(rv, R["draw_statuses"]) if s == "certified"], float)
    vals["d1"][722] = rv
    vals_cert["d1"][722] = rcert
    summ["d1-722"] = {"design": "d1", "n": 722, "K": len(rv), "source": "P15-37 R120 (results.json)",
                      "statuses": R["statuses"], "mean": R["value"], "interval": R["interval"],
                      "sd_between": R["sd_between_draws"], "sd_within": R["sd_within_draw"],
                      "sd_between_certified_only": float(rcert.std(ddof=1)), "median": float(np.median(rv)),
                      "range": [float(rv.min()), float(rv.max())]}
    out["code_checks"]["C3"] = c3
    out["cells"] = summ
    if not c3:
        out["verdict"] = "not decided: C3 fails"
        (OUT / "results.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
        return out
    rng = np.random.default_rng(SEED_FIT)
    fits: dict = {}
    for design in ("d2", "d1"):
        decided = kd[design] >= K_MIN and len(vals[design]) == 3
        f: dict = {"K": kd[design], "decided": decided}
        if len(vals[design]) == 3:
            sds = {n: float(v.std(ddof=1)) for n, v in vals[design].items()}
            a, slope = fit(sds)
            f.update(sd_between=sds, intercept=a, slope=slope, b=-slope)
            if design == "d2":
                c722 = summ["d2-722"]
                sbs = sd_needed(c722["mean"], c722["sd_within"])
                f["sd_between_needed"] = sbs
                f["n_star_line"] = n_star_line(a, slope, sbs)
                f["n_star_anchor_722"] = n_star_anchor(sds[722], -slope, sbs)
                f["n_star_b_half"] = n_star_anchor(sds[722], 0.5, sbs)
                f.update(boot_fit(vals[design], rng, 722, c722["sd_within"]))
            else:
                f["n_star_A"] = n_star_anchor(R120_SD, -slope, R120_SD_NEEDED)
                f["n_star_A_b_half"] = n_star_anchor(R120_SD, 0.5, R120_SD_NEEDED)
                bf = boot_fit(vals[design], rng, None, None)
                f.update(bf)
                # n*_A interval from the bootstrap exponents is monotone in b: map the b interval
                if bf["b_interval"]:
                    lo, hi = bf["b_interval"]
                    f["n_star_A_interval"] = [n_star_anchor(R120_SD, hi, R120_SD_NEEDED),
                                              n_star_anchor(R120_SD, lo, R120_SD_NEEDED)]
            vc = vals_cert[design]
            if all(len(vc[n]) > 1 for n in vc):
                sdc = {n: float(vc[n].std(ddof=1)) for n in vc}
                ac, sc = fit(sdc)
                f["exploratory_certified_only"] = {"sd": sdc, "b": -sc,
                                                   "b_interval": boot_fit(vc, rng, None, None)["b_interval"]}
            bi = f.get("b_interval")
            if bi:
                f["reading"] = ("consistent with 1/sqrt(n)" if bi[0] <= 0.5 <= bi[1] else
                                "faster than 1/sqrt(n)" if bi[0] > 0.5 else "slower than 1/sqrt(n)")
        fits[design] = f
        log(f"fit {design}: {json.dumps({k: v for k, v in f.items() if k != 'exploratory_certified_only'}, default=str)}")
    out["fits"] = fits
    out["design_effect_722"] = {"sd_R120": R120_SD, "sd_d2_722": summ.get("d2-722", {}).get("sd_between"),
                                "ratio_R120_over_d2": (R120_SD / summ["d2-722"]["sd_between"])
                                if summ.get("d2-722") else None}
    out["headline"] = {"b_d2": fits["d2"].get("b"), "b_d2_interval": fits["d2"].get("b_interval"),
                       "reading_d2": fits["d2"].get("reading"), "n_star_primary": fits["d2"].get("n_star_line"),
                       "n_star_primary_interval": fits["d2"].get("n_star_interval"), "b_d1": fits["d1"].get("b"),
                       "n_star_A": fits["d1"].get("n_star_A"), "decided": fits["d2"]["decided"]}
    from fidetype.benchmark.scoring import to_jsonable

    (OUT / "results.json").write_text(json.dumps(to_jsonable(out), indent=1, default=str) + "\n", encoding="utf-8")
    log(f"analyse: headline {out['headline']}")
    return out


def stage_smoke() -> dict:
    assert SMOKE, "set P1540_SMOKE=1 (calibration subsets only)"
    r = stage_worker()
    pool = int(os.environ.get("P1540_SMOKE_N", "200"))
    res = {"worker": r}
    for jb in job_list(pool):
        d = load_json(ROOT / "draws" / f"{jb['name']}.json")
        res[jb["name"]] = None if d is None else {"status": d["status"], "v": (d.get("v0_1") or {}).get("value"),
                                                   "st": (d.get("v0_1") or {}).get("status"), "sizes": d["sizes"],
                                                   "disjoint": d["disjoint"], "sizes_ok": d["sizes_ok"],
                                                   "n_ltt": (d.get("sheet") or {}).get("n_ltt"),
                                                   "seconds": d.get("seconds")}
    log(f"smoke: {json.dumps(res, default=str)[:1500]}")
    return res


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("worker", "analyse", "smoke"):
        raise SystemExit("usage: run.py worker | analyse | smoke")
    OUT.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    from fidetype.utils.power import keep_awake

    with keep_awake(log=log):
        t0 = time.time()
        log(f"stage {' '.join(args)} start (fidetype {FT_VERSION})")
        if args[0] == "worker":
            r = stage_worker()
        elif args[0] == "analyse":
            r = stage_analyse().get("headline")
        else:
            r = stage_smoke()
        log(f"stage {' '.join(args)} done in {time.time() - t0:.0f} s; peak {P26.peak_mb():.0f} MB; "
            f"{json.dumps(r, default=str)[:600]}")


if __name__ == "__main__":
    main()
