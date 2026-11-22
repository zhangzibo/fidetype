"""P11-19: multi-split (Bonferroni + selection, J = 3) EMG L-FL sentence guard on top of the P11-23 margin. CPU only.

Pre-registration: plan.md (this folder, commit c71c9bc). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0.
Per-prompt files stay in C:/Users/zhang/bci-data/derived/p11-19/. All other derived folders are read only. The repo
gets aggregates and per-draw pooled counts only (no per-user value, no text, no id).

    run.py worker 1 <w> <n>  X1' draws XF01 (= P11-23 S01) and XF13 (= P11-23 S13), fresh memo (amendment 1)
    run.py checks            X1 (first run, P11-23 memo copy), X1' (fresh), X2f (second empty memo = run memo)
    run.py worker 2 <w> <n>  the 120 split guards (k = 1..40, j = 1..3) at (alpha'' 0.0314, delta / 3)
    run.py analyse           X3, X4, arms BX3 / BD3 / AN3 / J1, intervals, why-not analysis -> results/results.json

Only pure helpers of the P11-23 / P11-20 / P11-18 / P11-17 / P11-14 runners are used; their own(), log(),
run_draw(), make_analyser() and memo files are never called or written.
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
OWN = Path(os.environ.get("P1119_OWN", str(DER / "p11-19")))  # the only place this task writes per-prompt files
P1123D = DER / "p11-23"  # READ ONLY (margin.json, feat-w*.pkl, draw-S*.json)
EXP1123 = REPO / "experiments" / "2026-11-21-p11-23-shift-margin-steps"
OUT = Path(os.environ.get("P1119_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA = 0.05  # the claim
DELTA = 0.1
J = 3
SPLIT_DELTA = DELTA / J
ALPHA_PP = 0.0314  # P11-23 alpha'' (m2 0.0185); checked against derived/p11-23/margin.json
K = 40
N_NULL = 300
CTL_MAX = 0.05
NO_BCI = 3.09
GRID_FLOOR = 0.30
X1_DRAWS = (1, 13)
Z95 = 1.959963984540054
N_USERS = 8
N_CAL = 1224


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


def p23():
    """The P11-23 runner as a module (pure helpers and the Windows class only)."""
    if "p1123run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1123run", EXP1123 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1123run"] = m
        spec.loader.exec_module(m)
    return sys.modules["p1123run"]


def p17():
    return p23().p17()


def p18():
    return p23().p18()


def p20():
    return p23().p20()


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def split_seed(k: int, j: int) -> int:
    return seed_of(f"p11-18|emg|cal|{k}") if j == 1 else seed_of(f"p11-19|emg|split|{k}|{j}")


def jobs(phase: int) -> list[dict]:
    if phase == 1:  # X1: reruns of P11-23 S01 / S13 at (alpha'', delta)
        return [{"name": f"XF{k:02d}", "k": k, "j": 1, "seed": split_seed(k, 1), "null_seed": split_seed(k, 1),
                 "ltt_alpha": ALPHA_PP, "delta": DELTA, "gname": f"p11-23-S{k:02d}"} for k in X1_DRAWS]
    return [{"name": f"k{k:02d}-j{j}", "k": k, "j": j, "seed": split_seed(k, j), "null_seed": split_seed(k, 1),
             "ltt_alpha": ALPHA_PP, "delta": SPLIT_DELTA, "gname": f"p11-19-k{k:02d}-j{j}"}
            for k in range(1, K + 1) for j in range(1, J + 1)]


def select(cands: list[dict], rule: str) -> dict | None:
    """Deployed split guard of one draw. cands: non-refused split guards with ``j`` and in-sample value ``v``.

    BX3: highest v (ties: lowest j). BD3: median v (2 guards: the lower; 1: that one; ties broken by j).
    """
    c = [x for x in cands if x is not None and x.get("v") is not None]
    if not c:
        return None
    if rule == "BX3":
        return sorted(c, key=lambda x: (-x["v"], x["j"]))[0]
    if rule == "BD3":
        s = sorted(c, key=lambda x: (x["v"], x["j"]))
        return s[(len(s) - 1) // 2]
    raise ValueError(rule)


def and_actions(decs: list[list[dict]], same) -> list[dict]:
    """AND of split guards: commit only if all commit the same text (``same`` compares two texts)."""
    out = []
    for row in zip(*decs):
        ok = all(d["action"] == "commit" for d in row) and all(same(row[0]["text"], d["text"]) for d in row[1:])
        out.append({"action": "commit", "text": row[0]["text"]} if ok else {"action": "abstain", "text": None})
    return out


def floor_w(mean: float, sd_w: float) -> float:
    return mean - Z95 * sd_w


def data_needed(mean: float, sd_b: float, sd_w: float, ref: float = NO_BCI, n_users: int = N_USERS,
                n_cal: int = N_CAL) -> dict:
    """Plan why-not item 3: users n_u* and calibration prompts n_cal* (normal approximation)."""
    h = (mean - ref) / Z95
    out: dict = {"h": h}
    if h <= 0:
        return {**out, "n_users": None, "n_cal": None, "note": "mean <= reference: not reachable by more data"}
    out["n_users"] = (n_users * sd_w ** 2 / (h ** 2 - sd_b ** 2)) if h > sd_b else None
    out["n_cal"] = (n_cal * sd_b ** 2 / (h ** 2 - sd_w ** 2)) if h > sd_w else None
    out["n_users_note"] = None if out["n_users"] is not None else "not reachable by more users alone"
    out["n_cal_note"] = None if out["n_cal"] is not None else "not reachable by more calibration data alone"
    return out


def h2_conclusion(f: int) -> str:
    if f <= 1:
        return "multi-split keeps the excess removed"
    if f <= int(np.floor(DELTA * K + 1e-9)):
        return "within delta"
    return "selection raises the risk"


def same_analysis(a: dict | None, b: dict | None, signals, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if a["status"] != b["status"]:
        return False
    if a["status"] != "ok":
        return True
    if a["top"] != b["top"] or len(a["native"]) != len(b["native"]):
        return False
    if any(t1 != t2 or abs(s1 - s2) > tol for (t1, s1), (t2, s2) in zip(a["native"], b["native"])):
        return False
    return all(abs(float(a["sig"][s]) - float(b["sig"][s])) <= tol for s in signals)


def x1_compare(mine: dict, ref: dict) -> dict:
    keys = ("threshold", "n_commits", "n_wrong", "value", "status", "safe_status")
    fields = {k: mine.get(k) == ref.get(k) for k in keys}
    fields["model_digest"] = mine["model"]["digest"] == ref["model"]["digest"]
    fields["decisions"] = all(mine["decisions"][kd] == ref["decisions"][kd] for kd in ("real", "shuffled", "zeros"))
    return {"name": mine["name"], "fields": fields, "pass": all(fields.values())}


# --- windows and memo -------------------------------------------------------------------------------


def make_analyser(w: int, empty: bool = False):
    M = p17().m14()

    class Memo(M.Analyser):  # type: ignore[misc, name-defined]
        def load(self) -> None:
            if empty:
                return
            f = own(f"feat-w{w}.pkl")  # amendment 1: fresh decodes only; the memo starts empty
            if f.exists():
                with open(f, "rb") as fh:
                    self.memo.update(pickle.load(fh))

        def save(self) -> None:
            if empty:
                self.dirty = 0
                return
            f = own(f"feat-w{w}.pkl")
            tmp = f.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump(self.memo, fh, protocol=4)
            os.replace(tmp, f)
            self.dirty = 0

    an = Memo()
    an.load()
    return an


# --- one split guard --------------------------------------------------------------------------------


def run_guard(jb: dict, M, R, an, W, cal: list[dict], ev: list[dict], E: dict, Ec: dict) -> dict:
    import fidetype.trust as ft
    from fidetype.benchmark import safe_wpm as SW

    P = p17()
    path = own(f"split-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
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
    pick = sorted(np.random.default_rng(jb["null_seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
    nulls = [W.get(cal[i], "shuffled") for i in pick]
    res: dict = {**jb, "n_cal": n, "n_eval": len(ev), "draw_info": info,
                 "model": {**model.to_dict(), "digest": model.digest(), "n_fit": n_fit_model,
                           "n_kept": int(np.sum(np.asarray(model.coef) != 0))}}
    try:
        g = ft.calibrate(xs, texts, alpha=jb["ltt_alpha"], delta=jb["delta"], input_kind="logits", vocab=an.KV,
                         blank=0, input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=fn, null_inputs=nulls,
                         decoder_name=name, decoder_version=ver, modality="emg", name=jb["gname"],
                         seed=jb["seed"], audit_text=False)
    except ft.NullControlError as e:
        res.update(status="refused", reason=str(e)[:2000], seconds=round(time.time() - t0, 1))
        an.save()
        save_json(res, path)
        log(f"split {jb['name']}: REFUSED ({res['seconds']} s): {str(e)[:300]}")
        return res
    del xs, nulls
    sh = g.sheet.to_dict()
    ltt_rows = [cal[int(i)] for i in desired[n_tune:]]
    fl = p23().flags_on(g, W, R, ltt_rows)
    ltt_wrong = sum(x[1] for x in fl)
    cal_dec = [g.decide(W.get(r)) for r in cal]
    cal_com = [d.action == "commit" for d in cal_dec]
    cal_cor = [cm and bool(R.same(d.text, t)) for cm, d, t in zip(cal_com, cal_dec, Ec["truths"])]
    v_in = float(P.draw_values(cal_com, cal_cor, Ec["nw"], Ec["nch"], Ec["ns"], np.ones((1, n)))[0])
    dec: dict = {}
    for kind in ("real", "shuffled", "zeros"):
        dec[kind] = []
        for r in ev:
            d = g.decide(W.get(r, kind))
            dec[kind].append({"action": d.action, "text": d.text})
    com = [x["action"] == "commit" for x in dec["real"]]
    cor = [cm and bool(R.same(x["text"], t)) for cm, x, t in zip(com, dec["real"], E["truths"])]
    gu = SW.guarantee_from_sheet(sh)
    gu.update(alpha=ALPHA, delta=DELTA, ltt_alpha=jb["ltt_alpha"], split_delta=jb["delta"])  # the claim
    sw = SW.safe_wpm(com, cor, E["nw"], E["nch"], E["ns"], guarantee=gu, controls=SW.controls_from_sheet(sh),
                     gaze_chars_per_min=None)
    ctl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ctl[k] / len(ev) <= CTL_MAX for k in ctl)
    credited = bool(sw["status"] == "certified" and sw["value"] is not None and v6)
    n_wrong = int(sum(cm and not k for cm, k in zip(com, cor)))
    res.update(status="guard", config_id=g.config_id, threshold=sh.get("commit_threshold"),
               feasible=sh.get("feasible"), sheet_alpha=sh.get("alpha"), sheet_delta=sh.get("delta"),
               ltt_n=len(ltt_rows), ltt_commits=sum(x[0] for x in fl), ltt_wrong=ltt_wrong,
               ltt_rate=ltt_wrong / len(ltt_rows), sheet_ltt_wrong=sh.get("ltt_wrong_commits"),
               cal_controls=[{k: x.get(k) for k in ("name", "n", "n_commit", "allowed", "passed")}
                             for x in sh.get("controls", [])],
               v_in=v_in, cal_commits=int(sum(cal_com)), safe_status=sw["status"],
               value=float(sw["value"]) if credited else 0.0,
               raw_value=float(sw["value"]) if sw["value"] is not None else None, credited=credited, v6_eval=v6,
               eval_controls=ctl, n_commits=int(sum(com)), n_wrong=n_wrong, test_rate=n_wrong / len(ev),
               above_alpha=bool(n_wrong / len(ev) > ALPHA), above_ltt_alpha=bool(n_wrong / len(ev) > jb["ltt_alpha"]),
               guarantee=gu, sheet=sh, committed=com, correct=cor, decisions=dec, seconds=round(time.time() - t0, 1))
    an.save()
    save_json(res, path)
    log(f"split {jb['name']}: done ({res['seconds']} s); ltt recount = sheet: {ltt_wrong == res['sheet_ltt_wrong']}")
    return res


def worker(phase: int, w: int, nw: int) -> int:
    keep_awake(True)
    try:
        mg = load_json(P1123D / "margin.json")
        if not (mg.get("run_arm_s2") and abs(mg["alpha_pp"] - ALPHA_PP) < 1e-12):  # type: ignore[union-attr, index]
            log("worker: P11-23 margin.json does not give alpha'' 0.0314; stop")
            return 2
        M = p17().m14()
        R, cal, ev = M.setup()
        E = p17().eval_arrays(R, ev)
        Ec = p17().eval_arrays(R, cal)
        W = p23().Windows(R)
        an = make_analyser(w)
        for i, jb in enumerate(jobs(phase)):
            if i % nw != w:
                continue
            if own("STOP").exists():
                log(f"worker {phase}-{w}: STOP file found; stop")
                return 3
            run_guard(jb, M, R, an, W, cal, ev, E, Ec)
        return 0
    finally:
        keep_awake(False)


# --- checks X1, X2'' ---------------------------------------------------------------------------------


def checks() -> int:
    M = p17().m14()
    R, cal, ev = M.setup()
    W = p23().Windows(R)
    first = own("memo-p1123-copy")
    x1 = [x1_compare(load_json(first / f"split-X{k:02d}.json"), load_json(P1123D / f"draw-S{k:02d}.json"))  # type: ignore[arg-type]
          for k in X1_DRAWS]
    log(f"X1 (first run, P11-23 memo copy): {'PASS' if all(x['pass'] for x in x1) else 'FAIL'} {x1}")
    x1f = []
    for k in X1_DRAWS:  # X1' (descriptive): fresh memo vs P11-23
        a, b = load_json(own(f"split-XF{k:02d}.json")), load_json(P1123D / f"draw-S{k:02d}.json")
        c = x1_compare(a, b)  # type: ignore[arg-type]
        c["n_actions_differ"] = int(sum(x != y for kd in ("real", "shuffled", "zeros")
                                        for x, y in zip(a["decisions"][kd], b["decisions"][kd])))  # type: ignore[index]
        x1f.append(c)
    log(f"X1' (fresh memo, descriptive): {x1f}")
    # X2f: a second empty-memo analyser vs this item's fresh run memo (worker-0 memo after phase 1)
    rv = sorted(np.random.default_rng(1919).choice(len(cal), 100, replace=False).tolist())
    rt = sorted(np.random.default_rng(1919).choice(len(ev), 100, replace=False).tolist())
    rs = sorted(np.random.default_rng(1920).choice(len(ev), 50, replace=False).tolist())
    wins = [W.get(cal[i]) for i in rv] + [W.get(ev[i]) for i in rt] + [W.get(ev[i], "shuffled") for i in rs]
    used = make_analyser(0)
    fresh = make_analyser(0, empty=True)
    assert not fresh.memo
    t0 = time.time()
    miss, bad = 0, 0
    for x in wins:
        k = M.p1111().window_key(x) + "|FL"
        if k not in used.memo:
            miss += 1
            continue
        if not same_analysis(fresh.analyse(np.asarray(x, np.float64), "FL"), used.memo[k], M.SIGNALS):
            bad += 1
    x2 = {"windows": len(wins), "val_real": len(rv), "test_real": len(rt), "test_shuffled": len(rs),
          "not_in_memo": miss, "mismatch": bad, "seconds": round(time.time() - t0, 1)}
    x2["pass"] = bool(bad == 0 and miss == 0)
    log(f"X2f: {'PASS' if x2['pass'] else 'FAIL'} {x2}")
    old = {}
    for kk in range(2):  # descriptive: the original X2'' count against the P11-23 memo
        with open(P1123D / f"feat-w{kk}.pkl", "rb") as fh:
            d = pickle.load(fh)
        old.update({M.p1111().window_key(x) + "|FL": d.get(M.p1111().window_key(x) + "|FL") for x in wins
                    if M.p1111().window_key(x) + "|FL" in d})
        del d
    x2["descriptive_vs_p11_23_memo_mismatch"] = int(sum(
        not same_analysis(used.memo[M.p1111().window_key(x) + "|FL"], old.get(M.p1111().window_key(x) + "|FL"),
                          M.SIGNALS) for x in wins))
    log(f"X2'' (descriptive): fresh run memo vs P11-23 memo: {x2['descriptive_vs_p11_23_memo_mismatch']} / {len(wins)}")
    out = {"x1": x1, "x1_pass": all(x["pass"] for x in x1), "x1_fresh": x1f, "x2f": x2}
    out["pass"] = bool(out["x1_pass"] and x2["pass"])
    save_json(out, own("checks.json"))
    return 0 if out["pass"] else 4


# --- analysis -----------------------------------------------------------------------------------------


def score_actions(dec: dict, sheets: list[dict], E: dict, R, rule: str) -> dict:
    from fidetype.benchmark import safe_wpm as SW

    com = [x["action"] == "commit" for x in dec["real"]]
    cor = [cm and bool(R.same(x["text"], t)) for cm, x, t in zip(com, dec["real"], E["truths"])]
    gu = SW.guarantee_from_sheet(sheets[0])
    gu.update(alpha=ALPHA, delta=DELTA, ltt_alpha=ALPHA_PP, split_delta=SPLIT_DELTA, rule=rule, J=J,
              feasible=all(s.get("feasible", True) for s in sheets))
    sw = SW.safe_wpm(com, cor, E["nw"], E["nch"], E["ns"], guarantee=gu, controls=SW.controls_from_sheet(sheets[0]),
                     gaze_chars_per_min=None)
    ctl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ctl[k] / len(com) <= CTL_MAX for k in ctl)
    credited = bool(sw["status"] == "certified" and sw["value"] is not None and v6)
    n_wrong = int(sum(cm and not k for cm, k in zip(com, cor)))
    return {"safe_status": sw["status"], "credited": credited, "value": float(sw["value"]) if credited else 0.0,
            "raw_value": float(sw["value"]) if sw["value"] is not None else None, "v6_eval": v6,
            "eval_controls": ctl, "n_commits": int(sum(com)), "n_wrong": n_wrong, "test_rate": n_wrong / len(com),
            "above_alpha": bool(n_wrong / len(com) > ALPHA), "above_ltt_alpha": bool(n_wrong / len(com) > ALPHA_PP),
            "committed": com, "correct": cor, "guarantee": gu}


def build_arm(rule: str, splits: dict[int, list[dict]], E: dict, R) -> list[dict]:
    out = []
    for k in range(1, K + 1):
        ss = splits[k]
        ok = [s for s in ss if s.get("status") == "guard"]
        base = {"k": k, "rule": rule, "n_split_guards": len(ok)}
        if rule == "AN3":
            if len(ok) < J:
                out.append({**base, "status": "refused", "credited": False, "value": 0.0})
                continue
            dec = {kd: and_actions([s["decisions"][kd] for s in ok], R.same) for kd in ("real", "shuffled", "zeros")}
            d = score_actions(dec, [s["sheet"] for s in ok], E, R, rule)
            ltt_rate = max(s["ltt_rate"] for s in ok)  # descriptive (AND risk <= each split's risk)
            out.append({**base, "status": "guard", "j_hat": None, "threshold": None, "ltt_rate": ltt_rate, **d})
            continue
        if rule == "J1":
            pick = next((s for s in ss if s["j"] == 1 and s.get("status") == "guard"), None)
        else:
            pick = select([{"j": s["j"], "v": s["v_in"], "s": s} for s in ok], rule)
            pick = pick["s"] if pick else None
        if pick is None:
            out.append({**base, "status": "refused", "credited": False, "value": 0.0})
            continue
        d = score_actions(pick["decisions"], [pick["sheet"]], E, R, rule)
        out.append({**base, "status": "guard", "j_hat": pick["j"], "threshold": pick["threshold"],
                    "ltt_rate": pick["ltt_rate"], "v_in": pick["v_in"], **d})
    return out


def analyse() -> int:
    from fidetype.benchmark import safe_wpm as SW

    P18, P = p18(), p17()
    M = P.m14()
    R, cal, ev = M.setup()
    E = P.eval_arrays(R, ev)
    ck = load_json(own("checks.json"))
    res: dict = {"task": "P11-19", "date": time.strftime("%Y-%m-%d %H:%M"), **M.p1111().RESEARCH,
                 "note": "aggregates and per-draw pooled counts only (no per-user value, no text, no id)",
                 "metric_version": "safe-wpm/0.1 (adopted; equal to the proposed v0.2 for sentence commits)",
                 "alpha_claim": ALPHA, "delta": DELTA, "J": J, "split_delta": SPLIT_DELTA, "ltt_alpha": ALPHA_PP,
                 "reference_no_bci": NO_BCI, "checks": ck}
    splits: dict[int, list[dict]] = {k: [] for k in range(1, K + 1)}
    missing = []
    for jb in jobs(2):
        p = own(f"split-{jb['name']}.json")
        if p.exists():
            splits[jb["k"]].append(load_json(p))  # type: ignore[arg-type]
        else:
            missing.append(jb["name"])
    res["missing_split_guards"] = missing
    allg = [s for k in splits for s in splits[k] if s.get("status") == "guard"]
    ds2 = [load_json(P1123D / f"draw-S{k:02d}.json") for k in range(1, K + 1)]
    x3 = [next(s for s in splits[k] if s["j"] == 1)["draw_info"]["sha_desired"] == ds2[k - 1]["draw_info"]["sha_desired"]  # type: ignore[index]
          for k in range(1, K + 1) if any(s["j"] == 1 for s in splits[k])]
    x4 = [s["ltt_wrong"] == s["sheet_ltt_wrong"] for s in allg]
    res["x3"] = {"n": len(x3), "n_same": int(sum(x3)), "pass": bool(len(x3) == K and all(x3))}
    res["x4"] = {"n": len(x4), "n_same": int(sum(x4)), "pass": bool(len(x4) > 0 and all(x4))}
    must = bool(ck["pass"] and res["x3"]["pass"] and res["x4"]["pass"] and not missing)  # type: ignore[index]
    res["must_pass_all"] = must
    rs = lambda xs: P18.rate_stats(xs) if len(xs) else None  # noqa: E731
    res["split_guards"] = {
        "n": sum(len(v) for v in splits.values()), "n_guard": len(allg),
        "refused": sum(s.get("status") == "refused" for k in splits for s in splits[k]),
        "infeasible": sum(s.get("feasible") is False for s in allg),
        "at_grid_floor": sum(s["threshold"] is not None and abs(s["threshold"] - GRID_FLOOR) < 1e-9 for s in allg),
        "per_split_test_value_mean": {j: (float(np.mean([s["raw_value"] or 0.0 for s in allg if s["j"] == j]))
                                          if any(s["j"] == j for s in allg) else None) for j in range(1, J + 1)},
        "v_in": rs([s["v_in"] for s in allg]), "threshold": rs([s["threshold"] for s in allg]),
        "max_cal_control_commits": max((max(x["n_commit"] for x in s["cal_controls"]) for s in allg), default=None),
        "seconds": rs([s["seconds"] for s in allg])}
    if not must:
        log(f"analyse: a must-pass check failed or split guards are missing ({len(missing)}); no arm result (plan)")
        res["arms"] = None
        save_json(res, OUT / "results.json")
        return 0
    sig = P18.binom_sig_bound()
    Wt = P.cluster_weights(E["clusters"])
    s2 = [{**d, "k": d["k"], "status": "guard" if d.get("status") == "guard" else d.get("status"), "j_hat": 1}
          for d in ds2]  # type: ignore[union-attr]
    arms = {r: build_arm(r, splits, E, R) for r in ("BX3", "BD3", "AN3", "J1")}
    arms["S2"] = s2  # type: ignore[assignment]

    def summary(dd: list[dict]) -> dict:
        g = [d for d in dd if d.get("status") == "guard"]
        st: dict[str, int] = {}
        for d in dd:
            s = d["safe_status"] if d.get("status") == "guard" else d.get("status")
            st[s] = st.get(s, 0) + 1
        thr = [d["threshold"] for d in g if d.get("threshold") is not None]
        return {"n_draws": len(dd), "n_guard": len(g), "statuses": st,
                "above_alpha": sum(bool(d["above_alpha"]) for d in g),
                "above_ltt_alpha": sum(bool(d.get("above_ltt_alpha")) for d in g),
                "significant_exceedances": sum(d["n_wrong"] >= sig for d in g),
                "test_rate": rs([d["test_rate"] for d in g]), "ltt_rate": rs([d["ltt_rate"] for d in g]),
                "gap": rs([d["test_rate"] - d["ltt_rate"] for d in g]),
                "commits": rs([d["n_commits"] for d in g]), "wrong": rs([d["n_wrong"] for d in g]),
                "threshold": rs(thr) if thr else None,
                "at_grid_floor": sum(abs(t - GRID_FLOOR) < 1e-9 for t in thr),
                "j_hat": {str(j): sum(d.get("j_hat") == j for d in g) for j in range(1, J + 1)},
                "max_eval_control_commits": max((max(d["eval_controls"].values()) for d in g), default=None),
                "c_null_all_zero": all(max(d["eval_controls"].values()) == 0 for d in g),
                "v6_fail": sum(not d["v6_eval"] for d in g)}

    def interval_block(dd: list[dict]) -> dict:
        prim = P.combined_interval(dd, E["nw"], E["nch"], E["ns"], Wt)
        lib_draws = [{"refused": True} if d.get("status") != "guard" or not d.get("v6_eval") else
                     {"committed": d["committed"], "correct": d["correct"], "guarantee": d["guarantee"]} for d in dd]
        lib = SW.calibration_draw_interval(lib_draws, E["nw"], E["nch"], E["ns"], B=2000, seed=0, level=0.95,
                                           reference=NO_BCI)
        lib.pop("draws", None)
        va = np.asarray([d["value"] for d in dd])
        low = sorted(range(len(dd)), key=lambda i: va[i])[:3]
        why = {"floor_w": floor_w(prim["value"], prim["sd_within_draw"]),
               "floor_w_above_reference": bool(floor_w(prim["value"], prim["sd_within_draw"]) > NO_BCI),
               "data_needed": data_needed(prim["value"], prim["sd_between_draws"], prim["sd_within_draw"]),
               "zero_draws": int(sum(v == 0.0 for v in va)),
               "lowest_draws": [{"value": float(va[i]), "n_commits": dd[i].get("n_commits"),
                                 "threshold": dd[i].get("threshold"), "j_hat": dd[i].get("j_hat")} for i in low]}
        return {"primary": prim, "secondary_library": lib, "why_not": why}

    def paired(a: list[dict], b: list[dict]) -> dict:
        da = np.asarray([x["value"] for x in a]) - np.asarray([x["value"] for x in b])
        return {"value_up": int(np.sum(da > 1e-12)), "value_same": int(np.sum(np.abs(da) <= 1e-12)),
                "value_down": int(np.sum(da < -1e-12)), "mean_diff": float(da.mean()),
                "mcnemar_above_alpha": p20().mcnemar_exact([bool(x.get("above_alpha")) for x in a],
                                                           [bool(x.get("above_alpha")) for x in b])}

    out: dict = {}
    for r, dd in arms.items():
        out[r] = {"summary": summary(dd), "interval": interval_block(dd)}
        if r != "S2":
            out[r]["paired_vs_S2"] = paired(dd, s2)
        out[r]["draws"] = [{k: d.get(k) for k in ("k", "status", "safe_status", "credited", "value", "raw_value",
                                                  "n_commits", "n_wrong", "test_rate", "above_alpha", "ltt_rate",
                                                  "threshold", "j_hat", "v_in", "eval_controls")} for d in dd]
    res["arms"] = out
    res["s2_pairing"] = ("exact (X1' equal)" if all(x["n_actions_differ"] == 0 for x in ck["x1_fresh"])  # type: ignore[index]
                         else "approximate (memo world vs fresh world)")
    bx = out["BX3"]
    prim = bx["interval"]["primary"]
    c_null = bx["summary"]["c_null_all_zero"]
    verdict = prim["verdict"]
    if verdict == "clearly above after calibration uncertainty" and not c_null:
        verdict = "above, but inside the combined interval"
    res["H1_verdict"] = verdict
    res["H1_met"] = verdict == "clearly above after calibration uncertainty"
    res["H2"] = h2_conclusion(bx["summary"]["above_alpha"])
    res["A2_check"] = ("(A2) not contradicted on test" if bx["summary"]["test_rate"]["mean"] <= ALPHA
                       and bx["summary"]["above_alpha"] <= int(DELTA * K + 1e-9) else "(A2) fails on test")
    res["H3_BD3_verdict"] = out["BD3"]["interval"]["primary"]["verdict"]
    save_json(res, OUT / "results.json")
    log(f"analyse: BX3 {prim['value']:.2f} [{prim['interval'][0]:.2f}, {prim['interval'][1]:.2f}] "
        f"'{res['H1_verdict']}'; f {bx['summary']['above_alpha']}/40 '{res['H2']}'; BD3 '{res['H3_BD3_verdict']}'")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("worker", "checks", "analyse"))
    ap.add_argument("args", nargs="*", type=int)
    a = ap.parse_args()
    if a.stage == "worker":
        phase, w, nw = (list(a.args) + [1, 0, 1][len(a.args):])[:3]
        return worker(phase, w, nw)
    if a.stage == "checks":
        return checks()
    return analyse()


if __name__ == "__main__":
    sys.exit(main())
