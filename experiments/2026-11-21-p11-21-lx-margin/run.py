"""P11-21: calibration-inclusive lower end above 3.09 for the EMG LX-FL prefix guard. CPU only.

Pre-registration: plan.md (this folder, commit 95b1a91). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0.
Per-prompt and per-user files stay in C:/Users/zhang/bci-data/derived/p11-21/. Every other derived folder is read
only. The repo gets aggregates, per-draw pooled counts and unlabelled spread statistics only.

    run.py worker 1 <w> <n>  X1 reproduction draws (P11-16 k01, k07) + stage 1: A01..A40 (a -> b), B01..B40 (b -> a)
    run.py margin            X1, X2, X3, X4 checks; LX step sizes, m_LX, alpha_LX; the arm list
    run.py worker 2 <w> <n>  arms LX-M (primary), LX-P, LX-T: 40 partition-only draws each
    run.py analyse           metrics, decision rules and intervals -> results/results.json

The P11-16 runner is imported for its pure helpers and its A16 analyser class. Its module constants OWN and OUT are
redirected to this item's folders before any call, so nothing is written into derived/p11-16/. The P11-23 runner is
imported for pure helpers (seed_of, user_counts, draw_gaps, direction_steps, Windows, spread, rules).
A worker stops after its current draw if derived/p11-21/STOP exists.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-21"  # the only place this task writes per-prompt files
P1116D = DER / "p11-16"  # READ ONLY (feat.pkl, draw-k01.json, draw-k07.json)
P1120D = DER / "p11-20"  # READ ONLY (prompts-ab.json, lp/)
P1123D = DER / "p11-23"  # READ ONLY (feat-w*.pkl for X2)
EXP1116 = REPO / "experiments" / "2026-11-21-p11-16-emg-prefix-confidence"
EXP1123 = REPO / "experiments" / "2026-11-21-p11-23-shift-margin-steps"
OUT = Path(os.environ.get("P1121_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA = 0.05  # the claim
DELTA = 0.1
K = 40
J = 40
N_NULL = 300
CTL_MAX = 0.05
NO_BCI = 3.09
MIN_GUARD_DRAWS = 30
ALPHA_T = 0.0314  # P11-23 alpha'' (m2 = 0.0185)
M2_LFL = 0.0185
DIRS = {"A": ("a", "b"), "B": ("b", "a")}
X1_DRAWS = (1, 7)  # P11-16 k01 (certified) and k07 (above alpha)
ARMS = {"M": "LX-M", "P": "LX-P", "T": "LX-T"}
X2P_TAGS = ("run", "p1120")  # plan amendment 1: x2_fresh.py under the run code and the P11-20 code snapshot


def log(*a: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents or p == OWN
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=_js) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _js(o: object) -> object:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def _load(name: str, path: Path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    return sys.modules[name]


def p16():
    """The P11-16 runner, with its write locations redirected to this item (never derived/p11-16)."""
    m = _load("p1116run", EXP1116 / "run.py")
    m.OWN = OWN
    m.OUT = OUT
    return m


def p23():
    return _load("p1123run", EXP1123 / "run.py")


def seed_of(tag: str) -> int:
    return p23().seed_of(tag)


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def jobs(phase: int, mg: dict | None = None) -> list[dict]:
    """Phase 1: X1 reproduction draws + stage-1 steps. Phase 2: the arm draws (``mg``: margin.json)."""
    if phase == 1:
        js = [{"name": f"X{k:02d}", "arm": "X", "k": k, "seed": seed_of(f"p11-17|emg|cal|{k}"),
               "boot_seed": seed_of(f"p11-17|emg|boot|{k}"), "ltt_alpha": ALPHA} for k in X1_DRAWS]
        for j in range(1, J + 1):
            js.append({"name": f"A{j:02d}", "arm": "A", "k": j, "seed": seed_of(f"p11-20|emg|m|{j}"),
                       "boot_seed": None, "ltt_alpha": ALPHA})
            js.append({"name": f"B{j:02d}", "arm": "B", "k": j, "seed": seed_of(f"p11-23|emg|ba|{j}"),
                       "boot_seed": None, "ltt_alpha": ALPHA})
        return js
    assert mg is not None
    js = []
    for arm in arm_plan(mg)["run"]:
        a = arm_alpha(arm, mg)
        js += [{"name": f"{arm}{k:02d}", "arm": arm, "k": k, "seed": seed_of(f"p11-18|emg|cal|{k}"),
                "boot_seed": None, "ltt_alpha": a} for k in range(1, K + 1)]
    return js


def arm_alpha(arm: str, mg: dict) -> float:
    return {"M": mg.get("alpha_lx"), "P": ALPHA, "T": ALPHA_T}[arm]


def arm_plan(mg: dict) -> dict:
    """Which arms run, and which arm reuses which (plan: LX-M = LX-T if alpha_LX = 0.0314; = LX-P if 0.05)."""
    run, reuse = [], {}
    if mg.get("run_arm_m"):
        run.append("M")
        a = mg["alpha_lx"]
        for arm in ("P", "T"):
            if abs(arm_alpha(arm, mg) - a) < 1e-12:
                reuse[arm] = "M"
            else:
                run.append(arm)
    else:
        run += ["P", "T"]
    return {"run": run, "reuse": reuse}


def margin_rule_lx(dirs: dict[str, dict], alpha: float = ALPHA) -> dict:
    """Plan: m_LX = max(0, max_d U_d); alpha_LX = floor((alpha - m_LX) * 1e4) / 1e4; >= 30 guards per direction."""
    out: dict = {"n_guard": {d: v["n_guard"] for d, v in dirs.items()}, "U": {d: v.get("U") for d, v in dirs.items()}}
    low = [d for d, v in dirs.items() if v["n_guard"] < MIN_GUARD_DRAWS]
    if low:
        return {**out, "run_arm_m": False, "reason": f"fewer than {MIN_GUARD_DRAWS} guards in direction(s) {low}"}
    m = max(0.0, max(v["U"] for v in dirs.values()))
    out["m_lx"] = m
    if m >= alpha:
        return {**out, "run_arm_m": False, "reason": f"m_LX = {m:.4f} >= alpha"}
    return {**out, "alpha_lx": math.floor((alpha - m) * 1e4 + 1e-9) / 1e4, "run_arm_m": True}


def h1_verdict(mean: float, lo: float, c_null: bool, ref: float = NO_BCI) -> str:
    if lo > ref and c_null:
        return "clearly above after calibration uncertainty"
    if mean > ref:
        return "above, but inside the combined interval"
    return "not above"


def h2_conclusion(f: int) -> str:
    if f <= 1:
        return "margin removes the excess"
    if f <= int(math.floor(DELTA * K + 1e-9)):
        return "within delta, excess not removed"
    return "margin not enough"


def a2_check(mean_rate: float, f: int) -> str:
    ok = mean_rate <= ALPHA and f <= int(math.floor(DELTA * K + 1e-9))
    return "(A2) not contradicted on test" if ok else "(A2) fails on test"


def fisher_less(a: int, b: int, n: int = K) -> float:
    """One-sided Fisher p of 'arm count b / n is lower than reference count a / n'."""
    from scipy.stats import fisher_exact

    return float(fisher_exact([[b, n - b], [a, n - a]], alternative="less")[1])


def commit_flags(decs: list[dict], truths: list[str]) -> list[tuple[bool, bool]]:
    """(committed, wrong) per decision with the safe-wpm/0.2 prefix rule."""
    from fidetype.benchmark.safe_wpm import prefix_outcome

    out = []
    for d, t in zip(decs, truths):
        c = d["action"] == "commit"
        out.append((c, bool(c and not prefix_outcome(d["text"], t, bool(d["complete"]))["correct"])))
    return out


def prompt_weights(n: int, B: int = 2000, seed: int = 0) -> np.ndarray:
    """Multinomial trial-resample weights as in safe_wpm.calibration_draw_interval (prompt-level inner level)."""
    rng = np.random.default_rng(seed)
    W = np.empty((B, n))
    for b in range(B):
        W[b] = np.bincount(rng.integers(0, n, n), minlength=n)
    return W


def certify_at(scorer, items: list, alpha: float) -> dict:
    """``ltt_prefix_threshold`` on (analysis, truth) items at level ``alpha`` (P11-16 ``certify`` with alpha free)."""
    from fidetype.trust.commit_score import ltt_prefix_threshold, prefix_right
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    sc, rt = [], []
    for a, truth in items:
        mono = scorer.mono(a)
        if mono is None:
            sc.append(np.zeros(0))
            rt.append(np.zeros(0, bool))
        else:
            sc.append(mono)
            rt.append(prefix_right(a["top"].split(), truth.split()))
    return ltt_prefix_threshold(sc, rt, alpha=alpha, delta=DELTA, grid=DEFAULT_LTT_GRID)


# --- analyser with this item's memo ------------------------------------------------------------------


def make_analyser(w: int):
    P = p16()
    base = P.make_analyser()  # P.OWN is redirected: loads derived/p11-21/feat.pkl (absent) -> empty memo
    cls = type(base)
    del base

    class Mine(cls):  # type: ignore[misc, valid-type]
        def load(self) -> None:
            f = own(f"feat-w{w}.pkl")
            src = f if f.exists() else P1116D / "feat.pkl"  # P11-16 memo: read only
            with open(src, "rb") as fh:
                self.memo.update(pickle.load(fh))

        def save(self) -> None:
            f = own(f"feat-w{w}.pkl")
            tmp = f.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump(self.memo, fh, protocol=4)
            os.replace(tmp, f)
            self.dirty = 0

    an = Mine()
    an.load()
    return an


# --- one draw -----------------------------------------------------------------------------------------


def run_draw(jb: dict, R, an, W, cal0: list[dict], ev0: list[dict], ab: list[dict], E: dict) -> dict:
    from fidetype.benchmark import safe_wpm as SW

    P = p16()
    S17 = P.m17()
    path = own(f"draw-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
    step = jb["arm"] in DIRS
    if step:
        cs, es = DIRS[jb["arm"]]
        cal = [r for r in ab if r["j"] == cs]
        ev = [r for r in ab if r["j"] == es]
    else:
        cal, ev = cal0, ev0
    n = len(cal)
    L, desired, info = S17.draw_order(n, jb["seed"], jb["boot_seed"])
    n_tune = info["split"][0] + info["split"][1]
    items = lambda idx: [(an.get(W.get(cal[int(i)]), P.DEC), R.intended_truth(cal[int(i)])) for i in idx]  # noqa: E731
    model, n_items, n_rows = P.fit_lx(an, items(sorted(int(i) for i in desired[:n_tune])))
    sc = P.Scorer(P.PRIMARY, an, model)
    ltt_idx = [int(i) for i in desired[n_tune:]]
    ltt = certify_at(sc, items(ltt_idx), jb["ltt_alpha"])
    thr = float(ltt["threshold"])
    xs = [W.get(cal[int(i)]) for i in L]
    if step:
        nulls = None
    else:
        pick = sorted(np.random.default_rng(jb["seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
        nulls = [W.get(cal[i], "shuffled") for i in pick]
    ctl = P.run_controls(an, sc, thr, xs, jb["seed"], nulls) if math.isfinite(thr) else []
    del xs, nulls
    cal_ok = bool(ctl) and all(c.passed for c in ctl)
    md = model.to_dict()
    sh = P.ext_sheet(P.PRIMARY, md, ltt, ctl, n)
    # LTT recount with the safe-wpm/0.2 prefix rule (check X4)
    ltt_rows = [cal[i] for i in ltt_idx]
    ltt_dec = [P.decision(sc, thr, an.get(W.get(r), P.DEC)) for r in ltt_rows]
    fl = commit_flags(ltt_dec, [R.intended_truth(r) for r in ltt_rows])
    ltt_com, ltt_wrong = sum(x[0] for x in fl), sum(x[1] for x in fl)
    emp = ltt.get("empirical_risk")
    x4 = (not math.isfinite(thr)) or (emp is not None and abs(emp * len(ltt_rows) - ltt_wrong) < 1e-6)
    res: dict = {**jb, "n_cal": n, "n_eval": len(ev), "draw_info": info,
                 "model": {**md, "digest": model.digest(), "n_fit_items": n_items, "n_fit_rows": n_rows,
                           "n_kept": int(np.sum(model.coef != 0))},
                 "threshold": thr if math.isfinite(thr) else None, "feasible": bool(ltt["feasible"]), "ltt": ltt,
                 "cal_controls": [c.to_dict() for c in ctl], "cal_controls_pass": cal_ok,
                 "status": "guard" if (math.isfinite(thr) and cal_ok) else ("no-threshold" if not math.isfinite(thr)
                                                                            else "control-fail"),
                 "ltt_n": len(ltt_rows), "ltt_commits": ltt_com, "ltt_wrong": ltt_wrong,
                 "ltt_rate": ltt_wrong / len(ltt_rows), "x4": bool(x4)}
    if step:
        truths_y = [R.intended_truth(r) for r in ev]
        dy = [P.decision(sc, thr, an.get(W.get(r), P.DEC)) for r in ev]
        fy = commit_flags(dy, truths_y)
        com_y, wrong_y = sum(x[0] for x in fy), sum(x[1] for x in fy)
        U = p23().user_counts
        ul, uy = U(ltt_rows, fl), U(ev, fy)
        res.update(n_commits=com_y, n_wrong=wrong_y, test_rate=wrong_y / len(ev),
                   gap=wrong_y / len(ev) - ltt_wrong / len(ltt_rows),
                   per_user={str(u): {"L": ul.get(u, [0, 0, 0]), "Y": uy[u]} for u in sorted(uy)},
                   seconds=round(time.time() - t0, 1))
        an.save()
        save_json(res, path)
        log(f"draw {jb['name']}: thr {res['threshold']} ltt {ltt_wrong}/{len(ltt_rows)} eval {wrong_y}/{len(ev)} "
            f"(commits {com_y}) gap {res['gap']:+.4f} status {res['status']} x4 {x4} "
            f"cal ctl {[c['n_commit'] for c in res['cal_controls']]} ({res['seconds']} s)")
        return res
    dec = {kind: [P.decision(sc, thr, an.get(W.get(r, kind), P.DEC)) for r in ev] for kind in ("real", "shuffled",
                                                                                               "zeros")}
    oc = P.outcomes(dec["real"], E["truths"])
    gu = SW.guarantee_from_sheet(sh)
    gu["ltt_alpha"] = jb["ltt_alpha"]
    sw = SW.safe_wpm(oc["committed"], oc["correct"], E["nw"], E["nch"], E["ns"], guarantee=gu,
                     controls=SW.controls_from_sheet(sh), gaze_chars_per_min=None, metric_version="0.2",
                     committed_words=oc["committed_words"], complete=oc["complete"], penalty_chars=oc["penalty_chars"])
    ectl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ectl[k] / len(ev) <= CTL_MAX for k in ectl)
    credited = bool(cal_ok and sw["status"] == "certified" and sw["value"] is not None and v6)
    n_wrong = int(sum(c and not k for c, k in zip(oc["committed"], oc["correct"])))
    res.update(safe_status=sw["status"], raw_value=float(sw["value"]) if sw["value"] is not None else None,
               value=float(sw["value"]) if credited else 0.0, credited=credited, v6_eval=bool(v6),
               eval_controls=ectl, c_null=bool(ectl["shuffled"] == 0 and ectl["zeros"] == 0),
               n_commits=int(sum(oc["committed"])),
               n_prefix_commits=int(sum(c and not f for c, f in zip(oc["committed"], oc["complete"]))),
               n_wrong=n_wrong, test_rate=n_wrong / len(ev), above_alpha=bool(n_wrong / len(ev) > ALPHA),
               above_ltt_alpha=bool(n_wrong / len(ev) > jb["ltt_alpha"]),
               **{k: oc[k] for k in ("committed", "correct", "credit_words", "penalty_chars")},
               actions={kind: [x["action"] for x in dec[kind]] for kind in dec},
               n_words={kind: [x["n_words_committed"] for x in dec[kind]] for kind in dec},
               seconds=round(time.time() - t0, 1))
    an.save()
    save_json(res, path)
    log(f"draw {jb['name']}: ltt_alpha {jb['ltt_alpha']} thr {res['threshold']} commits {res['n_commits']} "
        f"({res['n_prefix_commits']} prefix) wrong {n_wrong} status {sw['status']} raw {res['raw_value']} "
        f"credited {credited} eval ctl {ectl} cal ctl {[c['n_commit'] for c in res['cal_controls']]} x4 {x4} "
        f"({res['seconds']} s)")
    return res


def worker(phase: int, w: int, nw: int) -> int:
    keep_awake(True)
    try:
        P = p16()
        M14, R, cal, ev = P.setup()
        E = P.eval_arrays(R, ev)
        ab = load_json(P1120D / "prompts-ab.json")
        W = p23().Windows(R)
        an = make_analyser(w)
        if phase == 1:
            js = jobs(1)
        else:
            mg = load_json(own("margin.json"))
            if not mg.get("checks_pass"):  # type: ignore[union-attr]
                log("worker phase 2: must-pass checks failed; no arm is run (plan)")
                return 0
            js = jobs(2, mg)  # type: ignore[arg-type]
        for i, jb in enumerate(js):
            if i % nw != w:
                continue
            if own("STOP").exists():
                log(f"worker {phase}-{w}: STOP file found; stopping")
                return 3
            run_draw(jb, R, an, W, cal, ev, ab, E)  # type: ignore[arg-type]
        an.save()
        return 0
    finally:
        keep_awake(False)


# --- margin (checks + LX steps) ---------------------------------------------------------------------


def x1_check() -> dict:
    out = {}
    keys = ("threshold", "n_commits", "n_prefix_commits", "n_wrong", "raw_value", "actions", "n_words")
    for k in X1_DRAWS:
        a = load_json(own(f"draw-X{k:02d}.json"))
        b = load_json(P1116D / f"draw-k{k:02d}.json")
        same = {key: a.get(key) == b.get(key) for key in keys}  # type: ignore[union-attr]
        same["model_digest"] = a["model"]["digest"] == b["model"]["digest"]  # type: ignore[index]
        out[f"k{k:02d}"] = {"same": same, "pass": all(same.values()),
                            "threshold": a.get("threshold"), "n_commits": a.get("n_commits"),  # type: ignore[union-attr]
                            "n_wrong": a.get("n_wrong"), "raw_value": a.get("raw_value")}  # type: ignore[union-attr]
    out["pass"] = all(v["pass"] for v in out.values())
    return out


def x2_x3_check(R, ab: list[dict]) -> tuple[dict, dict]:
    """X2: a / b analyses equal the P11-23 memo (P11-14 analyser). X3: a / b prompt counts = P11-20 file."""
    P = p16()
    M = P.m14()
    W = p23().Windows(R)
    keys = {R.window_key(W.get(r)) + "|" + P.DEC for r in ab}
    mine: dict = {}
    for w in range(2):
        f = own(f"feat-w{w}.pkl")
        if f.exists():
            with open(f, "rb") as fh:
                d = pickle.load(fh)
            mine.update({k: d[k] for k in keys if k in d})
            del d
    ref: dict = {}
    for w in range(2):
        f = P1123D / f"feat-w{w}.pkl"
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        ref.update({k: d[k] for k in keys if k in d})
        del d
    n_bad = n_missing = 0
    for k in keys:
        a, b = mine.get(k, "missing"), ref.get(k, "missing")
        if isinstance(a, str) or isinstance(b, str):
            n_missing += 1
            continue
        if a is None or b is None:
            ok = a is None and b is None
        elif a["status"] != b["status"]:
            ok = False
        elif a["status"] == "ok":
            ok = (a["top"] == b["top"] and len(a["native"]) == len(b["native"])
                  and all(t1 == t2 and abs(s1 - s2) <= 1e-9 for (t1, s1), (t2, s2) in zip(a["native"], b["native"]))
                  and all(abs(float(a["sig"][s]) - float(b["sig"][s])) <= 1e-9 for s in M.SIGNALS))
            if ok and a.get("fU"):
                ok = abs(P.prefix_mass(a["fU"], a["top"].split(), len(a["top"].split())) - a["sig"]["p_fU"]) <= 1e-9
        else:
            ok = True
        n_bad += int(not ok)
    x2 = {"windows": len(keys), "missing": n_missing, "mismatch": n_bad, "pass": n_missing == 0 and n_bad == 0}
    na = sum(r["j"] == "a" for r in ab)
    nb = sum(r["j"] == "b" for r in ab)
    users_a = {r["i"] for r in ab if r["j"] == "a"}
    users_b = {r["i"] for r in ab if r["j"] == "b"}
    x3 = {"n_a": na, "n_b": nb, "n_rows": len(ab), "users": len(users_a | users_b),
          "pass": na + nb == len(ab) and users_a == users_b and len(users_a) == 8}
    return x2, x3


def margin() -> int:
    P = p16()
    M14, R, cal, ev = P.setup()
    ab = load_json(P1120D / "prompts-ab.json")
    x1 = x1_check()
    log(f"X1: {'PASS' if x1['pass'] else 'FAIL'} {x1}")
    x2, x3 = x2_x3_check(R, ab)  # type: ignore[arg-type]
    log(f"X2: {'PASS' if x2['pass'] else 'FAIL'} {x2}; X3: {'PASS' if x3['pass'] else 'FAIL'} {x3}")
    dd = {arm: [load_json(own(f"draw-{arm}{j:02d}.json")) for j in range(1, J + 1)] for arm in DIRS}
    x4 = {"n": sum(len(v) for v in dd.values()), "n_pass": sum(bool(d["x4"]) for v in dd.values() for d in v)}
    x4["pass"] = x4["n"] == x4["n_pass"]
    log(f"X4 (stage 1): {x4}")
    # Plan amendment 1: X2 (vs the P11-23 memo) is descriptive; X2' (fresh analyses, run code and P11-20 code)
    # is the must-pass check.
    x2p: dict = {}
    for tag in X2P_TAGS:
        f = own(f"x2-fresh-{tag}.json")
        x2p[tag] = load_json(f) if f.exists() else {"pass": False, "reason": "missing"}
    x2p["pass"] = all(bool(x2p[t].get("pass")) for t in X2P_TAGS)
    log(f"X2' (amendment 1): {'PASS' if x2p['pass'] else 'FAIL'} {x2p}")
    checks = bool(x1["pass"] and x2p["pass"] and x3["pass"] and x4["pass"])
    mg: dict = {"x1": x1, "x2_descriptive": x2, "x2_prime": x2p, "x3": x3, "x4_stage1": x4, "checks_pass": checks}
    if checks:
        T = p23()
        dirs = {}
        for arm in DIRS:
            gl = [T.draw_gaps(d["per_user"]) for d in dd[arm] if d["status"] == "guard"]
            dirs[arm] = T.direction_steps(gl) if gl else {"n_guard": 0, "U": float("nan")}
        mg.update(margin_rule_lx(dirs))
        mg["steps"] = {a: {k: v for k, v in d.items() if k in ("n_guard", "s", "se_jack", "U")} for a, d in dirs.items()}
        mg["arm_plan"] = arm_plan(mg)
        save_json(dirs, own("steps-local.json"))  # per-user values: local only
    else:
        mg.update(run_arm_m=False, reason="a must-pass check failed (plan)")
    save_json(mg, own("margin.json"))
    log(f"margin: { {k: v for k, v in mg.items() if k not in ('x1', 'x2_descriptive', 'x2_prime', 'x3', 'x4_stage1')} }")
    return 0


# --- analysis -----------------------------------------------------------------------------------------


def analyse() -> int:
    P = p16()
    T = p23()
    S17 = P.m17()
    P18 = T.p18()
    M14, R, cal, ev = P.setup()
    E = P.eval_arrays(R, ev)
    mg = load_json(own("margin.json"))
    rs = lambda xs: P18.rate_stats(xs) if len(xs) else None  # noqa: E731
    res: dict = {"task": "P11-21", "date": time.strftime("%Y-%m-%d %H:%M"), **R.RESEARCH,
                 "note": "aggregates, per-draw pooled counts and unlabelled spread statistics only (no per-user value, "
                         "no text, no id); safe-wpm/0.2 is PROPOSED, not adopted",
                 "alpha_claim": ALPHA, "delta": DELTA, "reference_no_bci": NO_BCI, "alpha_T": ALPHA_T,
                 "m2_lfl_p1123": M2_LFL,
                 "checks": {k: mg.get(k) for k in ("x1", "x2_descriptive", "x2_prime", "x3", "x4_stage1", "checks_pass")},  # type: ignore[union-attr]
                 "margin": {k: mg.get(k) for k in ("n_guard", "U", "m_lx", "alpha_lx", "run_arm_m", "reason",  # type: ignore[union-attr]
                                                   "steps", "arm_plan")}}
    if not mg.get("checks_pass"):  # type: ignore[union-attr]
        save_json(res, OUT / "results.json")
        log("analyse: must-pass checks failed; no result (plan)")
        return 0
    dirs = load_json(own("steps-local.json"))
    stage1: dict = {}
    allg: list[float] = []
    for arm, (cs, es) in DIRS.items():
        dd = [load_json(own(f"draw-{arm}{j:02d}.json")) for j in range(1, J + 1)]
        gd = [d for d in dd if d["status"] == "guard"]  # type: ignore[index]
        st: dict[str, int] = {}
        for d in dd:
            st[d["status"]] = st.get(d["status"], 0) + 1  # type: ignore[index]
        s = dirs[arm]  # type: ignore[index]
        allg += s.get("g", [])
        stage1[arm] = {"direction": f"{cs} -> {es}", "statuses": st, "n_cal": dd[0]["n_cal"],  # type: ignore[index]
                       "n_eval": dd[0]["n_eval"], "s": s.get("s"), "se_jack": s.get("se_jack"),  # type: ignore[index]
                       "U": s.get("U"), "gap_per_draw": T.spread(s.get("g", [])),
                       "louo_step_sizes": T.spread(s.get("louo", [])),
                       "per_user_step_sizes": T.spread(s.get("per_user", [])),
                       "ltt_rate": rs([d["ltt_rate"] for d in gd]), "eval_rate": rs([d["test_rate"] for d in gd]),  # type: ignore[index]
                       "eval_commits": rs([d["n_commits"] for d in gd]),  # type: ignore[index]
                       "threshold_range": [min(d["threshold"] for d in gd), max(d["threshold"] for d in gd)]  # type: ignore[index]
                       if gd else None,
                       "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in gd),  # type: ignore[index]
                                                      default=None)}
    stage1["gap_per_draw_both_directions"] = T.spread(allg)
    res["stage1"] = stage1
    sig = P18.binom_sig_bound()
    res["binom_sig_bound_wrong"] = sig
    Wt = S17.cluster_weights(E["clusters"])
    Wp = prompt_weights(len(ev))
    p16draws = [load_json(P1116D / f"draw-k{k:02d}.json") for k in range(1, K + 1)]
    plan = mg["arm_plan"]  # type: ignore[index]

    def load_arm(arm: str) -> list[dict]:
        src = plan["reuse"].get(arm, arm)
        return [load_json(own(f"draw-{src}{k:02d}.json")) for k in range(1, K + 1)]  # type: ignore[misc]

    def summary(dd: list[dict]) -> dict:
        st: dict[str, int] = {}
        for d in dd:
            s = d["status"] if d["status"] != "guard" else (d["safe_status"] if d["v6_eval"] else "v6-fail")
            st[s] = st.get(s, 0) + 1
        g = [d for d in dd if d["threshold"] is not None]
        cred = sorted((d["value"], d["n_commits"]) for d in dd if d["credited"])
        return {"n_draws": len(dd), "statuses": st, "n_credited": sum(bool(d["credited"]) for d in dd),
                "above_alpha": sum(bool(d["above_alpha"]) for d in dd),
                "above_ltt_alpha": sum(bool(d["above_ltt_alpha"]) for d in dd),
                "significant_exceedances": sum(d["n_wrong"] >= sig for d in dd),
                "test_rate": rs([d["test_rate"] for d in dd]), "ltt_rate": rs([d["ltt_rate"] for d in dd]),
                "optimism_gap": rs([d["test_rate"] - d["ltt_rate"] for d in dd]),
                "commits": rs([d["n_commits"] for d in dd]), "prefix_commits": rs([d["n_prefix_commits"] for d in dd]),
                "wrong": rs([d["n_wrong"] for d in dd]),
                "threshold_range": [min(d["threshold"] for d in g), max(d["threshold"] for d in g)] if g else None,
                "above_alpha_wrong": sorted(d["n_wrong"] for d in dd if d["above_alpha"]),
                "c_null_all": all(bool(d["c_null"]) for d in dd),
                "max_eval_control_commits": max(max(d["eval_controls"].values()) for d in dd),
                "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in dd
                                                if d["cal_controls"]), default=None),
                "cal_control_fail": sum(not d["cal_controls_pass"] for d in dd),
                "x4_pass": sum(bool(d["x4"]) for d in dd), "lowest_credited": cred[:3]}

    def paired(a: list[dict], b: list[dict]) -> dict:
        pr = [(x["n_wrong"], y["n_wrong"]) for x, y in zip(a, b)]
        return {"n_pairs": len(pr), "wrong_down": sum(x < y for x, y in pr), "wrong_same": sum(x == y for x, y in pr),
                "wrong_up": sum(x > y for x, y in pr),
                "mcnemar_above_alpha": T.p20().mcnemar_exact([x["n_wrong"] / 1221 > ALPHA for x in a],
                                                             [y["n_wrong"] / 1221 > ALPHA for y in b]),
                "value_higher": sum(x["value"] > y["value"] for x, y in zip(a, b)),
                "mean_value_difference": float(np.mean([x["value"] - y["value"] for x, y in zip(a, b)]))}

    arms_out: dict = {}
    for arm in ("M", "P", "T"):
        if arm == "M" and not mg.get("run_arm_m"):  # type: ignore[union-attr]
            continue
        dd = load_arm(arm)
        sm = summary(dd)
        prim = P.combined_interval(dd, E["ns"], Wt)
        sec = P.combined_interval(dd, E["ns"], Wp)
        keep = [{**d, "value": d["raw_value"] if d["raw_value"] is not None else 0.0,
                 "keep": d["raw_value"] is not None and d["cal_controls_pass"] and d["v6_eval"]} for d in dd]
        va = P.combined_interval(keep, E["ns"], Wt, credit_key="keep")
        blk = {"arm": ARMS[arm], "ltt_alpha": arm_alpha(arm, mg), "reused_from": plan["reuse"].get(arm),  # type: ignore[arg-type]
               "summary": sm, "interval_user_cluster": prim, "interval_prompt_level_secondary": sec,
               "variant_zero_draws_at_raw_value": va,
               "verdict": h1_verdict(prim["value"], prim["interval"][0], sm["c_null_all"]),
               "h2": h2_conclusion(sm["above_alpha"]), "a2": a2_check(sm["test_rate"]["mean"], sm["above_alpha"]),
               "fisher_vs_p11_16_bootstrap_7": fisher_less(7, sm["above_alpha"]),
               "paired_vs_p11_16": paired(dd, p16draws),
               "draws": [{k: d.get(k) for k in ("name", "k", "ltt_alpha", "status", "safe_status", "credited", "value",
                                                 "raw_value", "n_commits", "n_prefix_commits", "n_wrong", "test_rate",
                                                 "above_alpha", "ltt_wrong", "ltt_rate", "threshold", "eval_controls",
                                                 "seconds")}
                         | {"cal_controls": [c["n_commit"] for c in d["cal_controls"]]} for d in dd]}
        arms_out[ARMS[arm]] = blk
        log(f"analyse {ARMS[arm]}: {prim['value']:.3f} [{prim['interval'][0]:.2f}, {prim['interval'][1]:.2f}] "
            f"'{blk['verdict']}'; above alpha {sm['above_alpha']}/40 '{blk['h2']}'; statuses {sm['statuses']}")
    if "LX-M" in arms_out:
        m = load_arm("M")
        for other in ("P", "T"):
            arms_out["LX-M"][f"paired_vs_{ARMS[other]}"] = paired(m, load_arm(other))
        res["H1"] = {"verdict": arms_out["LX-M"]["verdict"],
                     "interval": arms_out["LX-M"]["interval_user_cluster"]["interval"],
                     "value": arms_out["LX-M"]["interval_user_cluster"]["value"],
                     "target_met": arms_out["LX-M"]["verdict"] == "clearly above after calibration uncertainty"}
        res["H2"] = {"f": arms_out["LX-M"]["summary"]["above_alpha"], "conclusion": arms_out["LX-M"]["h2"],
                     "a2": arms_out["LX-M"]["a2"]}
        lxt = arms_out.get("LX-T", {}).get("verdict")
        res["robustness_LX-T"] = lxt
        res["robustness_note"] = ("met with the LX-specific margin; not robust to the larger L-FL margin"
                                  if res["H1"]["target_met"] and lxt != "clearly above after calibration uncertainty"
                                  else None)
    if "LX-P" in arms_out:
        res["H3"] = {"f_LXP": arms_out["LX-P"]["summary"]["above_alpha"], "lt_7": arms_out["LX-P"]["summary"]
                     ["above_alpha"] < 7, "fisher_p": arms_out["LX-P"]["fisher_vs_p11_16_bootstrap_7"]}
    res["arms"] = arms_out
    stage_draws = {}
    for arm in DIRS:
        stage_draws[arm] = [{k: d.get(k) for k in ("name", "status", "threshold", "ltt_n", "ltt_wrong", "ltt_rate",
                                                   "n_commits", "n_wrong", "test_rate", "gap", "seconds")}
                            for d in (load_json(own(f"draw-{arm}{j:02d}.json")) for j in range(1, J + 1))]  # type: ignore[union-attr]
    res["stage1_draws"] = stage_draws
    save_json(res, OUT / "results.json")
    log(f"analyse: H1 {res.get('H1')}; H2 {res.get('H2')}; H3 {res.get('H3')}; LX-T {res.get('robustness_LX-T')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("worker", "margin", "analyse"))
    ap.add_argument("args", nargs="*", type=int)
    a = ap.parse_args()
    if a.stage == "worker":
        phase, w, nw = (list(a.args) + [1, 0, 1][len(a.args):])[:3]
        return worker(phase, w, nw)
    if a.stage == "margin":
        return margin()
    return analyse()


if __name__ == "__main__":
    sys.exit(main())
