"""P15-29: safe-WPM interval that includes the calibration draw (two-level bootstrap).
Pre-registered: plan.md (commit d7169cf). CPU only, our own code (Apache-2.0).

Stages (one process each):
  worker <w>  run every second job of the fixed job list (w = 0 or 1); each finished draw is saved and skipped later
  analyse     the pre-registered combined intervals, cross-checks X1-X4 and verdicts (no calibration)
  smoke       calibration subsets only (P1529_SMOKE=1); never uses an evaluation set

Run (repo root): launch.py (detached launcher: two workers, then analyse), or one stage in the foreground:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-20-p15-29-calibration-ci/run.py worker 0
Per-trial files (with text) and caches: C:/Users/zhang/bci-data/derived/p15-29/ only. Repo: aggregates.
Read only: derived/p15-22/, derived/p15-26/ (decoder outputs, LLM scores, per-trial decisions).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import contextlib  # noqa: E402
import datetime as dt  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

SMOKE = os.environ.get("P1529_SMOKE", "0") == "1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# P15-26 run.py: data loaders, cache helpers, LazyLLM, the P15-22 / P15-05 / P5-24 modules (read only use)
P26 = load_module("p1526run_p1529", REPO / "experiments/2026-11-19-p15-26-replication/run.py")
K, F, P22, P524 = P26.K, P26.F, P26.P22, P26.P524
norm, _right = P26.norm, P26._right

import fidetype.eval.harness as H  # noqa: E402
import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import calibration_draw_interval, format_line, guarantee_from_sheet  # noqa: E402
from fidetype.trust.calibration import TemperatureScaler  # noqa: E402
from fidetype.trust.dropin import _split  # noqa: E402

DER = K.DER
OWN_ROOT = DER / "p15-29"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-29"
ROOT = OWN_ROOT / "smoke" if SMOKE else OWN_ROOT
OUT = ROOT / "results-smoke" if SMOKE else HERE / "results"
LOGF = OUT / "run.log"
PLAN = "plan.md (pre-registration, commit d7169cf)"

P1522 = DER / "p15-22"
P1526 = DER / "p15-26"

ALPHA, DELTA = 0.05, 0.1
NULL_TRIALS = 20 if SMOKE else 300
B_INNER, SEED_INNER = 2000, 0
NO_BCI = {"t15": 4.0153, "t12": 4.1140}  # P15-26 recomputed values (plan.md)
K_MAX = {"t15": 40, "t12": 20}
K_MIN = {"t15": 20, "t12": 10}
CUTOFF = dt.datetime(2026, 11, 20, 6, 0, 0)  # local time (plan.md)
PINNED = {
    "t15": {"frame_temperature": 2.37015800035291, "tau": 0.06996627059278283, "llm_weight": 1.0,
            "fluent": -7.88165954200173},
    "t12": {"frame_temperature": 2.528091520707864, "tau": 0.47419631304442217, "llm_weight": 0.5,
            "fluent": -8.916451934532247},
}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + f"[{K.private_mb()} MB] " + " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


P26.log = log
F.log = log
P26.OUT = OUT  # P15-26 helpers never write here in this task, but never into the P15-26 folder either


def h8(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# job list (plan.md: order fixed; worker w takes every second job)
# ---------------------------------------------------------------------------


def job(unit: str, name: str) -> dict:
    if name.startswith("z"):
        return {"unit": unit, "name": name, "seed": int(name[1:]), "boot_seed": None, "k": None}
    k = int(name[1:])
    return {"unit": unit, "name": name, "seed": h8(f"p15-29|{unit}|cal|{k}"), "boot_seed": h8(f"p15-29|{unit}|boot|{k}"),
            "k": k}


def kname(k: int) -> str:
    return f"k{k:02d}"


def job_list() -> list[tuple[dict, bool]]:
    """(job, is_minimum) in the pre-registered order."""
    if SMOKE:
        return [(job("t15", "z0"), True), (job("t15", "k01"), True), (job("t12", "z0"), True),
                (job("t12", "k01"), True)]
    out = [(job("t15", f"z{i}"), True) for i in range(4)]
    out += [(job("t15", kname(k)), True) for k in range(1, K_MIN["t15"] + 1)]
    out += [(job("t12", "z0"), True)] + [(job("t12", kname(k)), True) for k in range(1, K_MIN["t12"] + 1)]
    out += [(job("t15", kname(k)), False) for k in range(K_MIN["t15"] + 1, K_MAX["t15"] + 1)]
    out += [(job("t12", kname(k)), False) for k in range(K_MIN["t12"] + 1, K_MAX["t12"] + 1)]
    return out


# ---------------------------------------------------------------------------
# units (data + pipeline with pinned values; caches are private copies per worker)
# ---------------------------------------------------------------------------


def load_unit(unit: str, wdir: Path) -> SimpleNamespace:
    from fidetype.adapters import b2t25 as Bm

    pv = PINNED[unit]
    if unit == "t15":
        (cx, ct, cph, ckeys), (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
        if SMOKE:  # calibration subsets only: the evaluation set is never used
            n = int(os.environ.get("P1529_SMOKE_N", "120"))
            hx, ht, hkeys = cx[n:n + 40], ct[n:n + 40], ckeys[n:n + 40]
            cx, ct, cph = cx[:n], ct[:n], cph[:n]
            durs = [float(x.shape[0]) * 0.08 for x in hx]
        else:
            p1405 = load_module("p1405run_p1529", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
            durs = p1405.t15_durations(hkeys)
        cache = wdir / "llm-cache-t15.sqlite"
        n_cached = P26.merged_llm_cache(cache, [P1526 / "llm-cache-t15.sqlite", P1522 / "llm-cache.sqlite"])
        dec, _bt = K.word_decoder()
        pipe, lazy = P26.make_pipe("t15", wdir, dec, cache, P1522 / "base-nbest-t15.pkl")
    else:
        cal, held, dec = F.data_t12()
        cx, ct, cph = cal
        hx, ht, _hph = held
        if SMOKE:
            n = int(os.environ.get("P1529_SMOKE_N", "120"))
            hx, ht = cx[n:n + 40], ct[n:n + 40]
            cx, ct, cph = cx[:n], ct[:n], cph[:n]
            durs = [float(x.shape[0]) * 0.02 for x in hx]
        else:
            exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
            cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
            d_in = Path(cfg["derived_dir"])
            prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
            texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
            durs = []
            for r in prep["sessions"]:  # as P15-26 t12_unit
                if r["role"] != "test":
                    continue
                z = np.load(d_in / f"{r['session']}.npz")
                for i, _w in enumerate(texts[r["session"]]["pool"]):
                    durs.append(z[f"pool_X{i}"].shape[0] * 0.02)
            assert len(durs) == len(hx) == 400, (len(durs), len(hx))
        cache = wdir / "llm-cache-t12.sqlite"
        n_cached = P26.merged_llm_cache(cache, [P1526 / "llm-cache-t12.sqlite"])
        pipe, lazy = P26.make_pipe("t12", wdir, dec, cache, P1526 / "t12" / "base-nbest-t12.pkl")
    pipe.grounding.tau, pipe.lam, pipe.frame_T, pipe.fluent_thr = pv["tau"], pv["llm_weight"], \
        pv["frame_temperature"], pv["fluent"]
    ht = [norm(t) for t in ht]
    u = SimpleNamespace(unit=unit, pipe=pipe, lazy=lazy, base_start=len(pipe.base), B=Bm, cx=cx, ct=ct, cph=cph,
                        hx=hx, ht=ht, durs=durs, T=pv["frame_temperature"], out=ROOT / unit)
    u.out.mkdir(parents=True, exist_ok=True)
    log(f"{unit}: loaded; calibration {len(cx)}, evaluation {len(hx)}; llm cache {n_cached}; pinned {pv}")
    return u


@contextlib.contextmanager
def pinned_frame_temperature(T: float):
    """Inside calibrate, the frame-temperature fit returns the pinned T (scoped swap, as emg_prepare does)."""
    orig = H.fit_frame_temperature
    H.fit_frame_temperature = lambda streams, truths: TemperatureScaler(temperature=float(T))
    try:
        yield
    finally:
        H.fit_frame_temperature = orig


def draw_order(n: int, seed: int, boot_seed: int | None) -> tuple[np.ndarray, dict]:
    """Input order L such that calibrate(seed) sees parts fit / policy / LTT = (bootstrap of) its own split."""
    o = np.random.default_rng(seed).permutation(n)
    n_fit, n_pol, n_ltt = _split(n)
    parts = [o[:n_fit], o[n_fit:n_fit + n_pol], o[n_fit + n_pol:]]
    if boot_seed is not None:
        rb = np.random.default_rng(boot_seed)
        parts = [rb.choice(p, size=len(p), replace=True) for p in parts]
    desired = np.concatenate(parts)
    L = np.empty(n, dtype=int)
    L[o] = desired  # calibrate's items are inputs[o[j]] = cx[desired[j]]
    info = {"split": [n_fit, n_pol, n_ltt], "distinct_per_part": [int(len(set(p.tolist()))) for p in parts],
            "sha_desired": hashlib.sha256(json.dumps(desired.tolist()).encode()).hexdigest()[:16]}
    return L, info


def run_draw(u: SimpleNamespace, jb: dict) -> dict:
    path = u.out / f"draw-{jb['name']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t0 = time.time()
    pipe = u.pipe
    L, info = draw_order(len(u.cx), jb["seed"], jb["boot_seed"])
    xs, ts, ph = [u.cx[i] for i in L], [u.ct[i] for i in L], [u.cph[i] for i in L]
    arm = P22.ARM_B1

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    nm = f"p15-29-{u.unit}-{jb['name']}"
    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(u.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=0.08, decode_fn=fn, stream_texts=ph, decoder_name=nm, modality="intracortical", name=nm,
              seed=jb["seed"], null_trials=NULL_TRIALS, confidence="learned")
    res = {**jb, "draw_info": info}
    try:
        with pinned_frame_temperature(u.T):
            guard = ft.calibrate(xs, ts, **kw)
    except ft.NullControlError as e:
        res.update({"status": "refused", "controls": [x.to_dict() for x in e.report],
                    "seconds": round(time.time() - t0, 1)})
        log(f"{u.unit} {jb['name']}: REFUSED {res['controls']}")
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(path)
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
    pipe.scorer.store.flush()
    pipe.save_base()
    sheet = guard.sheet.to_dict()
    v01 = P524.score(rows, sheet, u.durs, "0.1")
    res.update({"status": "ok", "config_id": guard.config_id, "sheet": sheet, "frame_temperature": T, "rows": rows,
                "v0_1": {k: v01[k] for k in ("value", "status", "n_commits", "n_wrong_commits", "measured_wrong_commit",
                                             "measured_wrong_commit_cp95", "unguarded_wpm", "n_cal")},
                "seconds_calibrate": round(t_cal, 1), "seconds": round(time.time() - t0, 1),
                "misses_after": {"base_nbest_new_decodes": len(pipe.base) - u.base_start,
                                 "llm_texts_scored_live": u.lazy.texts_scored},
                "peak_mb": round(P26.peak_mb(), 1)})
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(res), encoding="utf-8")
    tmp.replace(path)
    log(f"{u.unit} {jb['name']} (seed {jb['seed']}, boot {jb['boot_seed']}): v0.1 {format_line(v01)}; threshold "
        f"{sheet.get('commit_threshold')}; controls {[(c['name'], c['n_commit'], c['allowed']) for c in sheet['controls']]}; "
        f"{res['seconds']:.0f} s (calibrate {t_cal:.0f} s); misses {res['misses_after']}")
    return res


def stage_worker(w: int) -> dict:
    wdir = ROOT / f"w{w}"
    wdir.mkdir(parents=True, exist_ok=True)
    jobs = [j for i, j in enumerate(job_list()) if i % 2 == w]
    done, skipped = [], []
    u = None
    for jb, is_min in jobs:
        path = ROOT / jb["unit"] / f"draw-{jb['name']}.json"
        if path.exists():
            done.append(jb["name"])
            continue
        if not is_min and not SMOKE and dt.datetime.now() >= CUTOFF:
            skipped.append(f"{jb['unit']}:{jb['name']}")
            continue
        if u is None or u.unit != jb["unit"]:
            if u is not None:
                u.pipe.save_base()
                u.pipe.scorer.store.flush()
                del u
                gc.collect()
            u = load_unit(jb["unit"], wdir)
        run_draw(u, jb)
        done.append(f"{jb['unit']}:{jb['name']}")
    if skipped:
        log(f"worker {w}: cutoff {CUTOFF} passed; not started: {skipped}")
    return {"worker": w, "done": done, "skipped_after_cutoff": skipped}


# ---------------------------------------------------------------------------
# analysis (plan.md decision rule)
# ---------------------------------------------------------------------------


def load_draw(unit: str, name: str) -> dict | None:
    p = ROOT / unit / f"draw-{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def as_draw(d: dict) -> dict:
    if d.get("status") == "refused":
        return {"refused": True}
    rows = d["rows"]
    a = P524.trial_arrays(rows, "0.1")
    return {"committed": a["committed"], "correct": a["correct"], "guarantee": guarantee_from_sheet(d["sheet"])}


def lengths(rows: list[dict]) -> tuple[list[int], list[int]]:
    return [len(r["truth"].split()) for r in rows], [len(r["truth"]) for r in rows]


def same_rows(a: list[dict], b: list[dict]) -> int:
    return sum(x["action"] == y["action"] and norm(x["text"]) == norm(y["text"]) for x, y in zip(a, b))


def summary(d: dict) -> dict:
    keep = ("name", "seed", "boot_seed", "k", "status", "draw_info", "config_id", "frame_temperature", "v0_1",
            "seconds_calibrate", "seconds", "misses_after", "peak_mb")
    s = {k: d.get(k) for k in keep if k in d}
    if d.get("status") == "ok":
        sh = d["sheet"]
        s["commit_threshold"] = sh.get("commit_threshold")
        s["ltt_in_sample"] = [sh.get("ltt_commits"), sh.get("ltt_wrong_commits")]
        s["controls"] = [(c["name"], c["n_commit"], c["n"], c["allowed"]) for c in sh["controls"]]
    else:
        s["controls"] = d.get("controls")
    return s


def verdict(comb: dict, ref: float) -> str:
    lo, mean = comb["interval"][0], comb["value"]
    if lo > ref:
        return "clearly above after calibration uncertainty"
    if mean > ref:
        return "above, but inside the combined interval"
    return "not above"


def analyse_unit(unit: str) -> dict:
    ref = NO_BCI[unit]
    out: dict = {"unit": unit, "no_bci_reference": ref}
    z0 = load_draw(unit, "z0")
    # X4 code check
    p_ref = (P1522 / "arm-llm_learned.json") if unit == "t15" else (P1526 / "t12" / "arm-llm_learned.json")
    ref_rows = json.loads(p_ref.read_text(encoding="utf-8"))["rows"]
    x4: dict = {"reference": str(p_ref.relative_to(DER)).replace("\\", "/")}
    if z0 is None or z0.get("status") != "ok":
        x4["reproduces"] = False
        x4["reason"] = "z0 missing or refused"
    else:
        nw, nc = lengths(z0["rows"])
        x4["same_action_and_text"] = same_rows(z0["rows"], ref_rows)
        x4["n"] = len(ref_rows)
        x4["z0_value"] = z0["v0_1"]["value"]
        one = calibration_draw_interval([as_draw(z0)], nw, nc, z0_durs(unit, z0), B=B_INNER, seed=SEED_INNER)
        x4["k1_interval"] = one["interval"]
        x4["reproduces"] = x4["same_action_and_text"] == x4["n"] == len(z0["rows"])
        if unit == "t15":
            x4["k1_interval_matches_p15_22"] = [round(v, 2) for v in one["interval"]] == [4.25, 5.57]
            x4["reproduces"] = x4["reproduces"] and x4["k1_interval_matches_p15_22"]
    out["X4_code_check"] = x4
    log(f"{unit} X4: {x4}")
    if not x4["reproduces"]:
        out["verdict"] = "not decided: the code check X4 fails"
        return out
    rows0 = z0["rows"]
    nw, nc = lengths(rows0)
    durs = z0_durs(unit, z0)
    # longest finished prefix k01..kK
    Kused = 0
    while Kused < K_MAX[unit] and load_draw(unit, kname(Kused + 1)) is not None:
        Kused += 1
    draws = [load_draw(unit, kname(k)) for k in range(1, Kused + 1)]
    for d in draws:  # same evaluation trials in the same order
        if d.get("status") == "ok":
            assert [r["truth"] for r in d["rows"]] == [r["truth"] for r in rows0]
    out["K_used"] = Kused
    out["K_min_reached"] = Kused >= K_MIN[unit]
    out["draws"] = [summary(d) for d in draws]
    comb = calibration_draw_interval([as_draw(d) for d in draws], nw, nc, durs, B=B_INNER, seed=SEED_INNER,
                                     reference=ref)
    comb_public = {k: v for k, v in comb.items() if k != "draws"}
    comb_public["draw_values"] = [x["value"] for x in comb["draws"]]
    comb_public["draw_conditional_intervals"] = [x["conditional_interval"] for x in comb["draws"]]
    out["combined"] = comb_public
    ok = [d for d in draws if d.get("status") == "ok"]
    out["mean_commits"] = float(np.mean([d["v0_1"]["n_commits"] for d in ok])) if ok else None
    out["mean_wrong_commits"] = float(np.mean([d["v0_1"]["n_wrong_commits"] for d in ok])) if ok else None
    out["X1_analytic"] = {k: comb[k] for k in ("analytic_interval", "sd_between_draws", "sd_within_draw", "sd_total",
                                                "between_to_within_sd")}
    out["verdict"] = verdict(comb, ref) if out["K_min_reached"] else f"not decided: only {Kused} draws (< {K_MIN[unit]})"
    log(f"{unit}: K {Kused}; combined {comb['value']:.3f} [{comb['interval'][0]:.3f}, {comb['interval'][1]:.3f}]; "
        f"analytic {comb['analytic_interval']}; SD between {comb['sd_between_draws']:.3f}, within "
        f"{comb['sd_within_draw']:.3f}; statuses {comb['statuses']}; verdict: {out['verdict']}")
    if unit == "t15":
        # X2: P15-26 full-refit draws c0-c3 (same val_eval)
        cds = []
        for c in ("c0", "c1", "c2", "c3"):
            r = json.loads((P1526 / c / "arm-llm_learned.json").read_text(encoding="utf-8"))
            assert [norm(x["truth"]) for x in r["rows"]] == [x["truth"] for x in rows0]
            cds.append({"committed": P524.trial_arrays(r["rows"], "0.1")["committed"],
                        "correct": P524.trial_arrays(r["rows"], "0.1")["correct"],
                        "guarantee": guarantee_from_sheet(r["sheet"])})
        x2 = calibration_draw_interval(cds, nw, nc, durs, B=B_INNER, seed=SEED_INNER, reference=ref)
        out["X2_p15_26_full_refit"] = {**{k: v for k, v in x2.items() if k != "draws"},
                                       "draw_values": [x["value"] for x in x2["draws"]], "draws_used": "c0 c1 c2 c3"}
        log(f"t15 X2 (P15-26 c0-c3 full refit): {x2['value']:.3f} [{x2['interval'][0]:.3f}, {x2['interval'][1]:.3f}]")
        # X3: pinned vs refit, same partition seeds
        x3 = {}
        for i in (1, 2, 3):
            z = load_draw("t15", f"z{i}")
            c = json.loads((P1526 / f"c{i}" / "unit.json").read_text(encoding="utf-8"))
            cv = c["arms"]["llm_learned"]["v0_1"]["value"]
            zv = z["v0_1"]["value"] if z and z.get("status") == "ok" else None
            x3[f"seed{i}"] = {"pinned_z": zv, "refit_c": cv, "diff_z_minus_c": (zv - cv) if zv is not None else None,
                              "z_commits": z["v0_1"]["n_commits"] if zv is not None else None}
        out["X3_pinned_vs_refit"] = x3
        log(f"t15 X3: {x3}")
    return out


def z0_durs(unit: str, z0: dict) -> list[float]:
    """Evaluation durations (the same for every draw); recomputed from the data loaders."""
    global _DURS
    if unit not in _DURS:
        if unit == "t15":
            _c, (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
            p1405 = load_module("p1405run_p1529", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
            _DURS[unit] = p1405.t15_durations(hkeys)
        else:
            exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
            cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
            d_in = Path(cfg["derived_dir"])
            prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
            texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
            ds = []
            for r in prep["sessions"]:
                if r["role"] != "test":
                    continue
                z = np.load(d_in / f"{r['session']}.npz")
                for i, _w in enumerate(texts[r["session"]]["pool"]):
                    ds.append(z[f"pool_X{i}"].shape[0] * 0.02)
            _DURS[unit] = ds
    assert len(_DURS[unit]) == len(z0["rows"])
    return _DURS[unit]


_DURS: dict = {}


def stage_analyse() -> dict:
    out = {"fidetype_version": FT_VERSION, "plan": PLAN, "cutoff": CUTOFF.isoformat(), "B_inner": B_INNER,
           "units": {}}
    for unit in ("t15", "t12"):
        out["units"][unit] = analyse_unit(unit)
    t15 = out["units"]["t15"]
    out["headline"] = {
        "t15_verdict": t15.get("verdict"),
        "t12_verdict": out["units"]["t12"].get("verdict"),
        "claim": ("above gaze typing on T15; the interval includes the calibration draw"
                  if t15.get("verdict") == "clearly above after calibration uncertainty" else
                  "the README must stop calling the T15 result 'clearly above'"
                  if t15.get("verdict") == "above, but inside the combined interval" else
                  "the T15 headline must change" if t15.get("verdict") == "not above" else "not decided"),
    }
    from fidetype.benchmark.scoring import to_jsonable

    (OUT / "results.json").write_text(json.dumps(to_jsonable(out), indent=1, default=str) + "\n", encoding="utf-8")
    log(f"analyse: headline {out['headline']}")
    return out


def stage_smoke() -> dict:
    assert SMOKE, "set P1529_SMOKE=1 (calibration subsets only)"
    res = {}
    for w in (0, 1):
        res[w] = stage_worker(w)
    for unit in ("t15", "t12"):
        for nm in ("z0", "k01"):
            d = load_draw(unit, nm)
            res[f"{unit}-{nm}"] = summary(d)
    rows = load_draw("t15", "z0")["rows"]
    nw, nc = lengths(rows)
    durs = [float(x.shape[0]) * 0.08 for x in K.load_t15("m4-13", norm_text=True)[0][0][120:160]]
    res["combined_t15"] = {k: v for k, v in calibration_draw_interval(
        [as_draw(load_draw("t15", n)) for n in ("z0", "k01")], nw, nc, durs, B=200).items() if k != "draws"}
    log(f"smoke: {res['combined_t15']}")
    return res


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("worker", "analyse", "smoke"):
        raise SystemExit("usage: run.py worker <0|1> | analyse | smoke")
    OUT.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    from fidetype.utils.power import keep_awake

    with keep_awake(log=log):
        t0 = time.time()
        log(f"stage {' '.join(args)} start (fidetype {FT_VERSION})")
        if args[0] == "worker":
            r = stage_worker(int(args[1]))
        elif args[0] == "analyse":
            r = stage_analyse()
            r = r["headline"]
        else:
            r = stage_smoke()
        log(f"stage {' '.join(args)} done in {time.time() - t0:.0f} s; peak {P26.peak_mb():.0f} MB; {json.dumps(r, default=str)[:600]}")


if __name__ == "__main__":
    main()
