"""P11-23: robustness of the EMG shift margin across session steps (a -> b, b -> a, leave-one-user-out). CPU only.

Pre-registration: plan.md (this folder, commit a03b20c). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0.
Per-prompt and per-user files stay in C:/Users/zhang/bci-data/derived/p11-23/. The P11-01, P11-09, P11-11, P11-14,
P11-17, P11-18 and P11-20 files are read only. The repo gets aggregates, per-draw pooled counts and unlabelled spread
statistics only (no per-user value, no text, no id).

    run.py worker 1 <w> <n> stage 1: A01..A40 (a -> b, reruns of P11-20 M01..M40) and B01..B40 (b -> a), interleaved
    run.py margin           X6 check, step sizes, m2 and alpha''
    run.py worker 2 <w> <n> arm S2: S01..S40 at alpha'' (only S01 if alpha'' = P11-20 alpha')
    run.py analyse          metrics, decision rules and intervals -> results/results.json

Only pure helpers of the P11-20 / P11-18 / P11-17 runners are used; their own(), log(), run_draw() and memos are
never called. No inference: the session a / b log-probs and prompt rows of P11-20 are read only.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import hashlib  # noqa: E402
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
OWN = DER / "p11-23"  # the only place this task writes per-prompt files
P1120D = DER / "p11-20"  # READ ONLY (lp/, prompts-ab.json, feat-w*.pkl, draw-M*.json, draw-S*.json, margin.json)
P1118D = DER / "p11-18"  # READ ONLY (draw-P*.json)
EXP1120 = REPO / "experiments" / "2026-11-21-p11-20-emg-shift-robust"
OUT = Path(os.environ.get("P1123_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA = 0.05  # the claim
DELTA = 0.1
K = 40
J = 40
N_NULL = 300
CTL_MAX = 0.05
NO_BCI = 3.09
MIN_GUARD_DRAWS = 30
T_95_7 = 1.8946  # t_{0.95, 7}
N_USERS = 8
P1120_ALPHA_PRIME = 0.0455
DIRS = {"A": ("a", "b"), "B": ("b", "a")}  # arm -> (calibration session, evaluation session)


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def seed_of(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def p20():
    """The P11-20 runner as a module (pure helpers only)."""
    if "p1120run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1120run", EXP1120 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1120run"] = m
        spec.loader.exec_module(m)
    return sys.modules["p1120run"]


def p18():
    return p20().p18()


def p17():
    return p20().p17()


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def jobs(phase: int, reuse_s: bool = False) -> list[dict]:
    if phase == 1:
        js = []
        for j in range(1, J + 1):
            js.append({"name": f"A{j:02d}", "arm": "A", "k": j, "seed": seed_of(f"p11-20|emg|m|{j}"),
                       "ltt_alpha": ALPHA})
            js.append({"name": f"B{j:02d}", "arm": "B", "k": j, "seed": seed_of(f"p11-23|emg|ba|{j}"),
                       "ltt_alpha": ALPHA})
        return js
    n = 1 if reuse_s else K
    return [{"name": f"S{k:02d}", "arm": "S", "k": k, "seed": seed_of(f"p11-18|emg|cal|{k}"), "ltt_alpha": None}
            for k in range(1, n + 1)]


def user_counts(rows: list[dict], flags: list[tuple[bool, bool]]) -> dict[int, list[int]]:
    """Per user: [n, commits, wrong] from per-row (committed, wrong) flags."""
    out: dict[int, list[int]] = {}
    for r, (c, w) in zip(rows, flags):
        v = out.setdefault(int(r["i"]), [0, 0, 0])
        v[0] += 1
        v[1] += int(c)
        v[2] += int(w)
    return out


def draw_gaps(pu: dict) -> dict:
    """Pooled gap and the leave-one-user-out gaps of one draw.

    pu: {user: {"L": [n, commits, wrong], "Y": [n, commits, wrong]}} (L = LTT part, Y = evaluation session).
    """
    users = sorted(pu, key=int)

    def gap(us: list) -> float:
        nl = sum(pu[u]["L"][0] for u in us)
        wl = sum(pu[u]["L"][2] for u in us)
        ny = sum(pu[u]["Y"][0] for u in us)
        wy = sum(pu[u]["Y"][2] for u in us)
        return wy / ny - wl / nl

    out = {"pooled": gap(users), "louo": {str(u): gap([v for v in users if v != u]) for u in users},
           "per_user": {}}
    for u in users:
        nl, _, wl = pu[u]["L"]
        ny, _, wy = pu[u]["Y"]
        out["per_user"][str(u)] = (wy / ny - wl / nl) if nl and ny else None
    return out


def direction_steps(gap_list: list[dict], t: float = T_95_7) -> dict:
    """Step sizes of one direction from the draws with a guard (plan: s_d, s_{d,-u}, SE_d, U_d, p_{d,u})."""
    g = np.array([x["pooled"] for x in gap_list], float)
    users = sorted(gap_list[0]["louo"], key=int)
    louo = np.array([np.mean([x["louo"][u] for x in gap_list]) for u in users], float)
    n = len(users)
    se = float(math.sqrt((n - 1) / n * float(np.sum((louo - louo.mean()) ** 2))))
    pu = [float(np.mean([x["per_user"][u] for x in gap_list if x["per_user"][u] is not None])) for u in users]
    s = float(g.mean())
    return {"n_guard": int(len(g)), "s": s, "se_jack": se, "U": s + t * se, "louo": louo.tolist(), "per_user": pu,
            "g": g.tolist()}


def margin_rule2(dirs: dict[str, dict], n_draws: int = J, alpha: float = ALPHA) -> dict:
    """Plan: m2 = max(0, max_d U_d); alpha'' = floor((alpha - m2) * 1e4) / 1e4; run arm S2 or not."""
    out: dict = {"n_guard": {d: v["n_guard"] for d, v in dirs.items()}, "n_draws": n_draws,
                 "U": {d: v["U"] for d, v in dirs.items()}}
    low = [d for d, v in dirs.items() if v["n_guard"] < MIN_GUARD_DRAWS]
    if low:
        return {**out, "run_arm_s2": False, "reason": f"fewer than {MIN_GUARD_DRAWS} guards in direction(s) {low}"}
    m2 = max(0.0, max(v["U"] for v in dirs.values()))
    out["m2"] = m2
    if m2 >= alpha:
        return {**out, "run_arm_s2": False, "reason": f"m2 = {m2:.4f} >= alpha"}
    ap = math.floor((alpha - m2) * 1e4 + 1e-9) / 1e4
    return {**out, "alpha_pp": ap, "reuse_p1120_s": ap == P1120_ALPHA_PRIME, "run_arm_s2": True}


def spread_verdict(alpha_pp: float | None) -> str | None:
    if alpha_pp is None:
        return None
    if alpha_pp >= P1120_ALPHA_PRIME - 1e-12:
        return "the one-step margin of P11-20 covers the spread"
    return "the one-step margin of P11-20 under-states the spread"


def primary_conclusion(f_s: int) -> str:
    if f_s <= 1:
        return "margin removes the excess"
    if f_s <= int(np.floor(DELTA * K + 1e-9)):
        return "within delta, excess not removed"
    return "margin not enough"


def assumption_check(mean_test_rate: float, f_s: int) -> str:
    ok = mean_test_rate <= ALPHA and f_s <= int(np.floor(DELTA * K + 1e-9))
    return "(A2) not contradicted on test" if ok else "(A2) fails on test"


def spread(x) -> dict | None:
    x = np.asarray([v for v in x if v is not None], float)
    if not len(x):
        return None
    return {"n": int(len(x)), "mean": float(x.mean()), "sd": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
            "min": float(x.min()), "q10": float(np.quantile(x, 0.1)), "q25": float(np.quantile(x, 0.25)),
            "median": float(np.median(x)), "q75": float(np.quantile(x, 0.75)), "q90": float(np.quantile(x, 0.9)),
            "max": float(x.max())}


def x6_check(mine: list[dict], ref: list[dict]) -> dict:
    keys = ("status", "threshold", "ltt_wrong", "n_commits", "n_wrong")
    same = [all(a.get(k) == b.get(k) for k in keys) for a, b in zip(mine, ref)]
    return {"n": len(ref), "n_same": int(sum(same)), "fields": list(keys),
            "pass": bool(len(mine) == len(ref) == J and all(same))}


# --- windows and memo -------------------------------------------------------------------------------------


class Windows:
    """Track windows from P11-09 (read only); session a / b windows from the P11-20 log-probs (read only)."""

    def __init__(self, R) -> None:
        self.base = R.p1109().Windows()
        self._mm: dict[str, np.ndarray] = {}

    def get(self, r: dict, kind: str = "real") -> np.ndarray:
        if r["j"] in ("a", "b"):
            from fidetype.adapters import emg2qwerty as A

            if kind != "real":
                raise ValueError("sessions a / b: real windows only")
            name = f"u{r['i']}-{r['j']}-real.npy"
            if name not in self._mm:
                self._mm[name] = np.load(P1120D / "lp" / name, mmap_mode="r", allow_pickle=False)
            return A.merge_to_key_ctc(np.asarray(self._mm[name][r["lo"]:r["end"]]), self.base.vocab)
        return self.base.get(r, kind)


def make_analyser(w: int):
    M = p17().m14()

    class Memo(M.Analyser):  # type: ignore[misc, name-defined]
        def load(self) -> None:
            f = own(f"feat-w{w}.pkl")
            if f.exists():
                with open(f, "rb") as fh:
                    self.memo.update(pickle.load(fh))
                return
            for k in range(4):  # union of the P11-20 memos (read only; window-content keys)
                src = P1120D / f"feat-w{k}.pkl"
                if src.exists():
                    with open(src, "rb") as fh:
                        self.memo.update(pickle.load(fh))

        def save(self) -> None:
            f = own(f"feat-w{w}.pkl")
            tmp = f.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump(self.memo, fh, protocol=4)
            os.replace(tmp, f)
            self.dirty = 0

    an = Memo()
    an.load()
    return an


# --- one draw -----------------------------------------------------------------------------------------


def flags_on(g, W, R, rows: list[dict]) -> list[tuple[bool, bool]]:
    out = []
    for r in rows:
        d = g.decide(W.get(r))
        c = d.action == "commit"
        out.append((c, bool(c and not R.same(d.text, R.intended_truth(r)))))
    return out


def run_draw(jb: dict, M, R, an, W, cal0: list[dict], ev0: list[dict], ab: list[dict], E: dict) -> dict:
    import fidetype.trust as ft
    from fidetype.benchmark import safe_wpm as SW

    P = p17()
    path = own(f"draw-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
    if jb["arm"] in DIRS:
        cs, es = DIRS[jb["arm"]]
        cal = [r for r in ab if r["j"] == cs]
        ev = [r for r in ab if r["j"] == es]
    else:
        cal, ev = cal0, ev0
    n = len(cal)
    L, desired, info = P.draw_order(n, jb["seed"], None)
    n_tune = info["split"][0] + info["split"][1]
    model, n_fit_model = P.fit_model(M, R, an, W, cal, [int(i) for i in desired[:n_tune]])
    fn = M.GuardFn(an, "L-FL", model)
    c = M.DECODERS["FL"]
    name = ("fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram+lexicon+intended-text+nosignal-gate+conf-L")
    ver = f"p11-14-w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}-L{model.digest()}"
    xs = [W.get(cal[i]) for i in L]
    texts = [R.intended_truth(cal[i]) for i in L]
    if jb["arm"] in DIRS:
        nulls = None
    else:
        pick = sorted(np.random.default_rng(jb["seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
        nulls = [W.get(cal[i], "shuffled") for i in pick]
    # A draws keep the P11-20 guard name (reruns of M01..M40, check X6); B and S draws use this item's name.
    gname = f"p11-20-M{jb['k']:02d}" if jb["arm"] == "A" else f"p11-23-{jb['name']}"
    res: dict = {**jb, "n_cal": n, "n_eval": len(ev), "draw_info": info,
                 "model": {**model.to_dict(), "digest": model.digest(), "n_fit": n_fit_model,
                           "n_kept": int(np.sum(np.asarray(model.coef) != 0))}}
    try:
        g = ft.calibrate(xs, texts, alpha=jb["ltt_alpha"], delta=DELTA, input_kind="logits", vocab=an.KV, blank=0,
                         input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=fn, null_inputs=nulls,
                         decoder_name=name, decoder_version=ver, modality="emg", name=gname,
                         seed=jb["seed"], audit_text=False)
    except ft.NullControlError as e:
        res.update(status="refused", reason=str(e)[:2000], credited=False, value=0.0,
                   seconds=round(time.time() - t0, 1))
        an.save()
        save_json(res, path)
        log(f"draw {jb['name']}: REFUSED ({res['seconds']} s): {str(e)[:300]}")
        return res
    del xs, nulls
    sh = g.sheet.to_dict()
    ltt_rows = [cal[int(i)] for i in desired[n_tune:]]
    fl = flags_on(g, W, R, ltt_rows)
    ltt_com, ltt_wrong = sum(x[0] for x in fl), sum(x[1] for x in fl)
    common = dict(status="guard", config_id=g.config_id, threshold=sh.get("commit_threshold"),
                  feasible=sh.get("feasible"), sheet_alpha=sh.get("alpha"),
                  ltt_n=len(ltt_rows), ltt_commits=ltt_com, ltt_wrong=ltt_wrong, ltt_rate=ltt_wrong / len(ltt_rows),
                  sheet_ltt_commits=sh.get("ltt_commits"), sheet_ltt_wrong=sh.get("ltt_wrong_commits"),
                  cal_controls=[{k: x.get(k) for k in ("name", "n", "n_commit", "allowed", "passed")}
                                for x in sh.get("controls", [])])
    if jb["arm"] in DIRS:
        fy = flags_on(g, W, R, ev)
        com_y, wrong_y = sum(x[0] for x in fy), sum(x[1] for x in fy)
        ul, uy = user_counts(ltt_rows, fl), user_counts(ev, fy)
        pu = {str(u): {"L": ul.get(u, [0, 0, 0]), "Y": uy[u]} for u in sorted(uy)}
        res.update(**common, n_commits=com_y, n_wrong=wrong_y, test_rate=wrong_y / len(ev),
                   gap=wrong_y / len(ev) - ltt_wrong / len(ltt_rows), per_user=pu)
        if jb["arm"] == "B":  # descriptive only (two-step b -> track val); enters no rule
            fv = flags_on(g, W, R, cal0)
            res.update(val_commits=sum(x[0] for x in fv), val_wrong=sum(x[1] for x in fv))
            res["val_rate"] = res["val_wrong"] / len(cal0)
        res["seconds"] = round(time.time() - t0, 1)
        an.save()
        save_json(res, path)
        log(f"draw {jb['name']}: n_cal {n} thr {res['threshold']} ltt {ltt_wrong}/{len(ltt_rows)} "
            f"eval {wrong_y}/{len(ev)} (commits {com_y}) gap {res['gap']:+.4f} "
            f"cal ctl {[x['n_commit'] for x in res['cal_controls']]} ({res['seconds']} s)")
        return res
    dec: dict = {}
    for kind in ("real", "shuffled", "zeros"):
        dec[kind] = []
        for r in ev:
            d = g.decide(W.get(r, kind))
            dec[kind].append({"action": d.action, "text": d.text})
    com = [x["action"] == "commit" for x in dec["real"]]
    cor = [cm and bool(R.same(x["text"], t)) for cm, x, t in zip(com, dec["real"], E["truths"])]
    gu = SW.guarantee_from_sheet(sh)
    gu["alpha"] = ALPHA  # the claim (plan: the margin is part of the method)
    gu["ltt_alpha"] = jb["ltt_alpha"]
    sw = SW.safe_wpm(com, cor, E["nw"], E["nch"], E["ns"], guarantee=gu, controls=SW.controls_from_sheet(sh),
                     gaze_chars_per_min=None, metric_version="0.1")
    ctl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ctl[k] / len(ev) <= CTL_MAX for k in ctl)
    credited = bool(sw["status"] == "certified" and sw["value"] is not None and v6)
    n_wrong = int(sum(cm and not k for cm, k in zip(com, cor)))
    res.update(**common, safe_status=sw["status"], value=float(sw["value"]) if credited else 0.0,
               raw_value=float(sw["value"]) if sw["value"] is not None else None, credited=credited, v6_eval=v6,
               eval_controls=ctl, n_commits=int(sum(com)), n_wrong=n_wrong, test_rate=n_wrong / len(ev),
               above_alpha=bool(n_wrong / len(ev) > ALPHA),
               above_ltt_alpha=bool(n_wrong / len(ev) > jb["ltt_alpha"]), guarantee=gu, committed=com,
               correct=cor, decisions=dec, seconds=round(time.time() - t0, 1))
    an.save()
    save_json(res, path)
    log(f"draw {jb['name']}: alpha'' {jb['ltt_alpha']} thr {res['threshold']} commits {res['n_commits']} "
        f"wrong {n_wrong} rate {res['test_rate']:.4f} ltt {ltt_wrong}/{len(ltt_rows)} (sheet {res['sheet_ltt_wrong']}) "
        f"status {sw['status']} credited {credited} eval ctl {ctl} "
        f"cal ctl {[x['n_commit'] for x in res['cal_controls']]} ({res['seconds']} s)")
    return res


def worker(phase: int, w: int, nw: int) -> int:
    keep_awake(True)
    try:
        if not load_json(P1120D / "checks.json")["pass"]:  # type: ignore[index]
            log("worker: P11-20 checks C1 / C2 not passed; stop")
            return 2
        M = p17().m14()
        R, cal, ev = M.setup()
        E = p17().eval_arrays(R, ev)
        ab = load_json(P1120D / "prompts-ab.json")
        W = Windows(R)
        an = make_analyser(w)
        if phase == 1:
            js = jobs(1)
        else:
            mg = load_json(own("margin.json"))
            if not mg.get("run_arm_s2"):  # type: ignore[union-attr]
                log(f"worker phase 2: arm S2 not run ({mg.get('reason')})")  # type: ignore[union-attr]
                return 0
            js = [{**jb, "ltt_alpha": mg["alpha_pp"]} for jb in jobs(2, mg["reuse_p1120_s"])]  # type: ignore[index]
        for i, jb in enumerate(js):
            if i % nw != w:
                continue
            run_draw(jb, M, R, an, W, cal, ev, ab, E)  # type: ignore[arg-type]
        return 0
    finally:
        keep_awake(False)


def load_dir(arm: str) -> list[dict]:
    return [load_json(own(f"draw-{arm}{j:02d}.json")) for j in range(1, J + 1)]  # type: ignore[misc]


def margin() -> int:
    da = load_dir("A")
    ref = [load_json(P1120D / f"draw-M{j:02d}.json") for j in range(1, J + 1)]
    x6 = x6_check(da, ref)  # type: ignore[arg-type]
    save_json(x6, own("x6.json"))
    log(f"X6: {'PASS' if x6['pass'] else 'FAIL'} {x6}")
    if not x6["pass"]:
        save_json({"run_arm_s2": False, "reason": "X6 failed (plan)"}, own("margin.json"))
        return 0
    dirs = {}
    for arm in DIRS:
        gl = [draw_gaps(d["per_user"]) for d in load_dir(arm) if d.get("status") == "guard"]
        dirs[arm] = direction_steps(gl) if gl else {"n_guard": 0, "U": float("nan")}
    mg = margin_rule2(dirs)
    mg["steps"] = {a: {k: v for k, v in d.items() if k in ("n_guard", "s", "se_jack", "U")} for a, d in dirs.items()}
    save_json(mg, own("margin.json"))
    save_json(dirs, own("steps-local.json"))  # per-user values: local only
    log(f"margin: {mg}")
    return 0


# --- analysis -----------------------------------------------------------------------------------------


def analyse() -> int:
    from fidetype.benchmark import safe_wpm as SW

    P18, P = p18(), p17()
    M = P.m14()
    R, cal, ev = M.setup()
    E = P.eval_arrays(R, ev)
    x6 = load_json(own("x6.json"))
    mg = load_json(own("margin.json"))
    rs = lambda xs: P18.rate_stats(xs) if len(xs) else None  # noqa: E731
    res: dict = {"task": "P11-23", "date": time.strftime("%Y-%m-%d %H:%M"), **M.p1111().RESEARCH,
                 "note": "aggregates, per-draw pooled counts and unlabelled spread statistics only "
                         "(no per-user value, no text, no id)",
                 "alpha_claim": ALPHA, "delta": DELTA, "reference_no_bci": NO_BCI, "x6": x6, "margin": mg,
                 "p1120_m": float(load_json(P1120D / "margin.json")["m"]),  # type: ignore[index]
                 "p1120_alpha_prime": P1120_ALPHA_PRIME}
    stage1: dict = {}
    if x6["pass"]:  # type: ignore[index]
        dirs = load_json(own("steps-local.json"))
        allg: list[float] = []
        all18: list[float] = []
        for arm, (cs, es) in DIRS.items():
            dd = load_dir(arm)
            gd = [d for d in dd if d.get("status") == "guard"]
            st: dict[str, int] = {}
            for d in dd:
                st[d["status"]] = st.get(d["status"], 0) + 1
            s = dirs[arm]  # type: ignore[index]
            allg += s["g"]
            all18 += [s["s"]] + s["louo"]
            blk = {"direction": f"{cs} -> {es}", "statuses": st, "n_cal": dd[0]["n_cal"], "n_eval": dd[0]["n_eval"],
                   "s": s["s"], "se_jack": s["se_jack"], "U": s["U"],
                   "gap_per_draw": spread(s["g"]), "louo_step_sizes": spread(s["louo"]),
                   "per_user_step_sizes": spread(s["per_user"]),
                   "ltt_rate": rs([d["ltt_rate"] for d in gd]), "eval_rate": rs([d["test_rate"] for d in gd]),
                   "eval_commits": rs([d["n_commits"] for d in gd]),
                   "threshold_range": [min(d["threshold"] for d in gd), max(d["threshold"] for d in gd)],
                   "ltt_recount_equals_sheet": sum(d["ltt_wrong"] == d["sheet_ltt_wrong"] for d in gd),
                   "max_cal_control_commits": max(max(x["n_commit"] for x in d["cal_controls"]) for d in gd)}
            if arm == "B":
                blk["descriptive_two_step_gap_b_to_val"] = rs([d["val_rate"] - d["ltt_rate"] for d in gd])
                blk["descriptive_val_rate"] = rs([d["val_rate"] for d in gd])
            stage1[arm] = blk
        stage1["gap_per_draw_both_directions"] = spread(allg)
        stage1["max_of_18_step_estimates"] = float(max(all18))
        stage1["s_ab_minus_s_ba"] = stage1["A"]["s"] - stage1["B"]["s"]
    res["stage1"] = stage1
    res["spread_verdict"] = spread_verdict(mg.get("alpha_pp")) if x6["pass"] else None  # type: ignore[union-attr]
    sig = P18.binom_sig_bound()
    res["binom_sig_bound_wrong"] = sig
    dp18 = [load_json(P1118D / f"draw-P{k:02d}.json") for k in range(1, K + 1)]
    ds20 = [load_json(P1120D / f"draw-S{k:02d}.json") for k in range(1, K + 1)]
    Wt = P.cluster_weights(E["clusters"])

    def interval_block(dd: list[dict]) -> dict:
        prim = P.combined_interval(dd, E["nw"], E["nch"], E["ns"], Wt)
        lib_draws = [{"refused": True} if d.get("status") != "guard" or not d.get("v6_eval") else
                     {"committed": d["committed"], "correct": d["correct"], "guarantee": d["guarantee"]} for d in dd]
        lib = SW.calibration_draw_interval(lib_draws, E["nw"], E["nch"], E["ns"], B=2000, seed=0, level=0.95,
                                           reference=NO_BCI, metric_version="0.1")
        lib.pop("draws", None)
        return {"primary": prim, "secondary_library": lib}

    def arm_summary(dd: list[dict]) -> dict:
        g = [d for d in dd if d.get("status") == "guard"]
        st: dict[str, int] = {}
        for d in dd:
            s = d["status"] if d["status"] != "guard" else d["safe_status"]
            st[s] = st.get(s, 0) + 1
        return {"n_draws": len(dd), "n_guard": len(g), "statuses": st,
                "above_alpha": sum(bool(d["above_alpha"]) for d in g),
                "above_ltt_alpha": sum(bool(d.get("above_ltt_alpha", d.get("above_alpha"))) for d in g),
                "significant_exceedances": sum(d["n_wrong"] >= sig for d in g),
                "test_rate": rs([d["test_rate"] for d in g]), "ltt_rate": rs([d["ltt_rate"] for d in g]),
                "gap": rs([d["test_rate"] - d["ltt_rate"] for d in g]),
                "commits": rs([d["n_commits"] for d in g]), "wrong": rs([d["n_wrong"] for d in g]),
                "threshold_range": [min(d["threshold"] for d in g), max(d["threshold"] for d in g)] if g else None,
                "above_alpha_wrong": sorted(d["n_wrong"] for d in g if d["above_alpha"]),
                "max_eval_control_commits": max((max(d["eval_controls"].values()) for d in g), default=None),
                "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in g),
                                               default=None),
                "v6_fail": sum(not d["v6_eval"] for d in g),
                "ltt_recount_equals_sheet": sum(d["ltt_wrong"] == d["sheet_ltt_wrong"] for d in g)}

    def paired(ds: list[dict], ref: list[dict]) -> dict:
        pair = [(d["n_wrong"], o["n_wrong"]) for d, o in zip(ds, ref)
                if d.get("status") == "guard" and o.get("status") == "guard"]
        return {"n_pairs": len(pair), "wrong_down": sum(a < b for a, b in pair),
                "wrong_same": sum(a == b for a, b in pair), "wrong_up": sum(a > b for a, b in pair),
                "mcnemar_above_alpha": p20().mcnemar_exact([bool(d.get("above_alpha")) for d in ds],
                                                           [bool(o.get("above_alpha")) for o in ref])}

    if x6["pass"] and mg.get("run_arm_s2"):  # type: ignore[index, union-attr]
        if mg["reuse_p1120_s"]:  # type: ignore[index]
            s1 = load_json(own("draw-S01.json"))
            res["arm_S2_identity_check_S01_equals_P1120_S01"] = bool(s1["decisions"] == ds20[0]["decisions"])  # type: ignore[index]
            ds = ds20
        else:
            ds = [load_json(own(f"draw-S{k:02d}.json")) for k in range(1, K + 1)]
        ss = arm_summary(ds)  # type: ignore[arg-type]
        ss["paired_vs_p11_20_S"] = paired(ds, ds20)  # type: ignore[arg-type]
        ss["paired_vs_p11_18_P"] = paired(ds, dp18)  # type: ignore[arg-type]
        f_s = ss["above_alpha"]
        res["arm_S2"] = ss
        iv = interval_block(ds)  # type: ignore[arg-type]
        res["interval_S2"] = iv
        res["primary_conclusion"] = primary_conclusion(f_s)
        res["assumption_check"] = assumption_check(ss["test_rate"]["mean"], f_s)
        res["verdict_vs_no_bci"] = iv["primary"]["verdict"]
        res["draws_S2"] = [{k: d.get(k) for k in ("name", "k", "ltt_alpha", "status", "safe_status", "credited",
                                                  "value", "raw_value", "n_commits", "n_wrong", "test_rate",
                                                  "above_alpha", "above_ltt_alpha", "ltt_wrong", "ltt_rate",
                                                  "threshold", "eval_controls", "seconds")} for d in ds]  # type: ignore[union-attr]
    elif not x6["pass"]:  # type: ignore[index]
        log("analyse: X6 failed; no margin and no arm S2 result (plan)")
    for arm in DIRS:
        try:
            dd = load_dir(arm)
        except FileNotFoundError:
            continue
        res[f"draws_{arm}"] = [{k: d.get(k) for k in ("name", "k", "status", "n_cal", "n_eval", "threshold", "ltt_n",
                                                      "ltt_wrong", "ltt_rate", "n_commits", "n_wrong", "test_rate",
                                                      "gap", "val_wrong", "val_rate", "seconds")}
                               | {"cal_controls": [x["n_commit"] for x in d.get("cal_controls", [])]} for d in dd]
    save_json(res, OUT / "results.json")
    log(f"analyse: m2 {mg.get('m2')} alpha'' {mg.get('alpha_pp')} '{res.get('spread_verdict')}'; "  # type: ignore[union-attr]
        f"f_S2 {res.get('arm_S2', {}).get('above_alpha')}/40 '{res.get('primary_conclusion')}' "
        f"'{res.get('assumption_check')}' verdict '{res.get('verdict_vs_no_bci')}'")
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
