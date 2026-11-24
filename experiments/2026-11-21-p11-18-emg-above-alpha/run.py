"""P11-18: why 22.5 % of the EMG L-FL calibration draws are above alpha. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files stay
in C:/Users/zhang/bci-data/derived/p11-18/. The P11-09, P11-11, P11-12, P11-14 and P11-17 files are read only.
The repo gets aggregates and per-draw counts only (no per-user value, no text, no id).

    run.py worker <w> <n_workers>   jobs z0, P01..P40, E01..E40 (interleaved); worker w takes job i if i % n == w
    run.py analyse                  metrics, decision rule and interval -> results/results.json

Only pure helpers of the P11-17 runner are used (draw_order, fit_model, cluster_weights, draw_values,
combined_interval, verdict, eval_arrays, x4_check, seed_of); its own(), log(), run_draw() and memo are never called.
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
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-18"  # the only place this task writes per-prompt files
P1117D = DER / "p11-17"  # READ ONLY (feat.pkl memo)
P1114D = DER / "p11-14"  # READ ONLY
EXP1117 = REPO / "experiments" / "2026-11-21-p11-17-emg-calibration-ci"
OUT = Path(os.environ.get("P1118_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
K = 40
N_CAL = 1224
N_NULL = 300
ALPHA = 0.05
DELTA = 0.1
NO_BCI = 3.09
CTL_MAX = 0.05
B_BOOT_FAIL = (9, 40)  # P11-17: 9 of 40 bootstrap draws above alpha


def p1117_wrong() -> list[int]:
    """Wrong-commit counts of the 40 P11-17 bootstrap draws (committed results.json; counts only)."""
    d = load_json(EXP1117 / "results" / "results.json")
    return [int(x["n_wrong"]) for x in d["draws"]]  # type: ignore[index]


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


def p17():
    """The P11-17 runner as a module (pure helpers only)."""
    if "p1117run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1117run", EXP1117 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1117run"] = m
        spec.loader.exec_module(m)
    return sys.modules["p1117run"]


def seed_of(tag: str) -> int:
    import hashlib

    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def jobs() -> list[dict]:
    js = [{"name": "z0", "arm": "P", "k": 0, "seed": 0, "pool_seed": None}]
    for k in range(1, K + 1):
        js.append({"name": f"P{k:02d}", "arm": "P", "k": k, "seed": seed_of(f"p11-18|emg|cal|{k}"), "pool_seed": None})
        js.append({"name": f"E{k:02d}", "arm": "E", "k": k, "seed": seed_of(f"p11-18|emg|poolcal|{k}"),
                   "pool_seed": seed_of(f"p11-18|emg|pool|{k}")})
    return js


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def pool_split(n_val: int, n_test: int, pool_seed: int, n_cal: int = N_CAL) -> tuple[np.ndarray, np.ndarray]:
    """Arm E: positions in the pool (val first, then test) of the calibration list and of the held-out set."""
    q = np.random.default_rng(pool_seed).permutation(n_val + n_test)
    return q[:n_cal], q[n_cal:]


def binom_sig_bound(n: int = 1221, alpha: float = ALPHA, level: float = 0.05) -> int:
    """Smallest wrong-commit count w with P(Bin(n, alpha) >= w) < level."""
    from scipy.stats import binom

    w = 0
    while binom.sf(w - 1, n, alpha) >= level:
        w += 1
    return w


def above_alpha(wrong: int, n: int, alpha: float = ALPHA) -> bool:
    return wrong / n > alpha


def fisher_greater(a: int, b: int, n: int = K) -> float:
    """One-sided Fisher exact p-value that a / n > b / n."""
    from scipy.stats import fisher_exact

    return float(fisher_exact([[a, n - a], [b, n - b]], alternative="greater")[1])


def welch_greater(x, y) -> float:
    """One-sided Welch t-test p-value that mean(x) > mean(y)."""
    from scipy.stats import ttest_ind

    return float(ttest_ind(np.asarray(x, float), np.asarray(y, float), equal_var=False, alternative="greater").pvalue)


def decide_cause(x_b: int, x_p: int, x_e: int, gap_p, gap_e, n_sig_p: int, n: int = K) -> dict:
    """The pre-registered decision rule (plan.md, steps 1-3)."""
    p1 = fisher_greater(x_b, x_p, n)
    lim = int(np.floor(DELTA * n + 1e-9))  # 4 of 40
    if x_p <= lim and p1 < 0.05:
        step1 = "duplicates"
    elif x_p <= lim:
        step1 = "partly duplicates"
    else:
        step1 = "noise + shift"
    p_shift = welch_greater(gap_p, gap_e)
    p_fe = fisher_greater(x_p, x_e, n)
    if p_shift < 0.05:
        step2 = "mainly session shift" if x_e <= lim else "shift and noise"
    else:
        step2 = "mainly test-rate noise"
    step3 = ("consistent with test-rate noise around alpha" if n_sig_p <= int(np.floor(0.05 * n + 1e-9))
             else "exceedances larger than test noise explains")
    sentence = f"The excess over delta comes from {step1}"
    if step1 == "noise + shift":
        sentence += f"; sub-cause: {step2}"
    return {"fisher_b_gt_p": p1, "step1": step1, "welch_gap_p_gt_e": p_shift, "fisher_p_gt_e": p_fe,
            "step2": step2, "n_sig_p": int(n_sig_p), "step3": step3, "sentence": sentence + "."}


def rate_stats(x) -> dict:
    a = np.asarray(x, float)
    return {"mean": float(a.mean()), "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "min": float(a.min()), "max": float(a.max())}


# --- window memo (own copy per worker; P11-14 / P11-17 memos are read only) -------------------------


def make_analyser(w: int):
    M = p17().m14()

    class Memo(M.Analyser):  # type: ignore[misc, name-defined]
        def load(self) -> None:
            f = own(f"feat-w{w}.pkl")
            for src in (f, P1117D / "feat.pkl", P1114D / "feat.pkl"):
                if src.exists():
                    with open(src, "rb") as fh:
                        self.memo.update(pickle.load(fh))
                    return

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


def run_draw(jb: dict, M, R, an, cal0: list[dict], ev0: list[dict]) -> dict:
    import fidetype.trust as ft
    from fidetype.benchmark import safe_wpm as SW

    P = p17()
    path = own(f"draw-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
    W = R.p1109().Windows()
    if jb["arm"] == "P":
        cal, ev = cal0, ev0
        pool_info = None
    else:
        pool = cal0 + ev0
        ci, hi = pool_split(len(cal0), len(ev0), jb["pool_seed"])
        cal, ev = [pool[i] for i in ci], [pool[i] for i in hi]
        pool_info = {"cal_from_val": int(np.sum(ci < len(cal0))), "heldout_from_val": int(np.sum(hi < len(cal0)))}
    n = len(cal)
    E = P.eval_arrays(R, ev)
    L, desired, info = P.draw_order(n, jb["seed"], None)
    n_tune = info["split"][0] + info["split"][1]
    model, n_fit_model = P.fit_model(M, R, an, W, cal, [int(i) for i in desired[:n_tune]])
    fn = M.GuardFn(an, "L-FL", model)
    c = M.DECODERS["FL"]
    name = ("fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram+lexicon+intended-text+nosignal-gate+conf-L")
    ver = f"p11-14-w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}-L{model.digest()}"
    xs = [W.get(cal[i]) for i in L]
    texts = [R.intended_truth(cal[i]) for i in L]
    pick = sorted(np.random.default_rng(jb["seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
    nulls = [W.get(cal[i], "shuffled") for i in pick]
    res: dict = {**jb, "draw_info": info, "pool_info": pool_info,
                 "model": {**model.to_dict(), "digest": model.digest(), "n_fit": n_fit_model,
                           "n_kept": int(np.sum(np.asarray(model.coef) != 0))}}
    try:
        g = ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=an.KV, blank=0,
                         input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=fn, null_inputs=nulls,
                         decoder_name=name, decoder_version=ver, modality="emg", name=f"p11-18-{jb['name']}",
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
    t1 = time.time()
    # LTT in-sample risk, counted with the same rule as the test
    ltt_idx = [int(i) for i in desired[n_tune:]]
    ltt_wrong = ltt_com = 0
    for i in ltt_idx:
        d = g.decide(W.get(cal[i]))
        if d.action == "commit":
            ltt_com += 1
            ltt_wrong += int(not R.same(d.text, R.intended_truth(cal[i])))
    kinds = ("real", "shuffled", "zeros") if jb["arm"] == "P" else ("real",)
    dec: dict = {}
    for kind in kinds:
        dec[kind] = []
        for r in ev:
            d = g.decide(W.get(r, kind))
            dec[kind].append({"action": d.action, "text": d.text})
    com = [x["action"] == "commit" for x in dec["real"]]
    cor = [cm and bool(R.same(x["text"], t)) for cm, x, t in zip(com, dec["real"], E["truths"])]
    sw = SW.safe_wpm(com, cor, E["nw"], E["nch"], E["ns"], guarantee=SW.guarantee_from_sheet(sh),
                     controls=SW.controls_from_sheet(sh), gaze_chars_per_min=None, metric_version="0.1")
    if jb["arm"] == "P":
        ctl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
        v6 = all(ctl[k] / len(ev) <= CTL_MAX for k in ctl)
    else:
        ctl, v6 = None, None
    credited = bool(sw["status"] == "certified" and sw["value"] is not None and (v6 is True))
    n_wrong = int(sum(cm and not k for cm, k in zip(com, cor)))
    res.update(status="guard", config_id=g.config_id, safe_status=sw["status"],
               value=float(sw["value"]) if credited else 0.0,
               raw_value=float(sw["value"]) if sw["value"] is not None else None,
               credited=credited, v6_eval=v6, eval_controls=ctl, n_eval=len(ev),
               n_commits=int(sum(com)), n_wrong=n_wrong, test_rate=n_wrong / len(ev),
               above_alpha=above_alpha(n_wrong, len(ev)),
               ltt_n=len(ltt_idx), ltt_commits=ltt_com, ltt_wrong=ltt_wrong, ltt_rate=ltt_wrong / len(ltt_idx),
               sheet_ltt_commits=sh.get("ltt_commits"), sheet_ltt_wrong=sh.get("ltt_wrong_commits"),
               threshold=sh.get("commit_threshold"), feasible=sh.get("feasible"),
               cal_controls=[{k: x.get(k) for k in ("name", "n", "n_commit", "allowed", "passed")}
                             for x in sh.get("controls", [])],
               guarantee=SW.guarantee_from_sheet(sh), committed=com, correct=cor, decisions=dec,
               seconds_calibrate=round(t1 - t0, 1), seconds=round(time.time() - t0, 1))
    an.save()
    save_json(res, path)
    log(f"draw {jb['name']}: thr {res['threshold']} commits {res['n_commits']} wrong {n_wrong} "
        f"rate {res['test_rate']:.4f} ltt {ltt_wrong}/{len(ltt_idx)} (sheet {res['sheet_ltt_wrong']}) "
        f"status {sw['status']} credited {credited} eval ctl {ctl} "
        f"cal ctl {[x['n_commit'] for x in res['cal_controls']]} ({res['seconds']} s)")
    return res


def worker(w: int, nw: int) -> int:
    keep_awake(True)
    try:
        M = p17().m14()
        R, cal, ev = M.setup()
        an = make_analyser(w)
        for i, jb in enumerate(jobs()):
            if i % nw != w:
                continue
            d = run_draw(jb, M, R, an, cal, ev)
            if jb["name"] == "z0":
                x4 = p17().x4_check(d, p17().eval_arrays(R, ev))
                save_json(x4, own("x4.json"))
                log(f"X4: {'PASS' if x4['pass'] else 'FAIL'} {x4}")
                if not x4["pass"]:
                    log("X4 failed: no result will be reported (plan)")
        return 0
    finally:
        keep_awake(False)


# --- analysis -----------------------------------------------------------------------------------------


def analyse() -> int:
    from fidetype.benchmark import safe_wpm as SW

    P = p17()
    M = P.m14()
    R, cal, ev = M.setup()
    E = P.eval_arrays(R, ev)
    x4 = load_json(own("x4.json"))
    if not x4["pass"]:  # type: ignore[index]
        log("analyse: X4 did not pass; no result")
        return 2
    allj = [jb for jb in jobs() if jb["k"] > 0]
    ds = {jb["name"]: load_json(own(f"draw-{jb['name']}.json")) for jb in allj}
    dp = [ds[f"P{k:02d}"] for k in range(1, K + 1)]
    de = [ds[f"E{k:02d}"] for k in range(1, K + 1)]
    sig = binom_sig_bound()
    gp = [d for d in dp if d.get("status") == "guard"]
    ge = [d for d in de if d.get("status") == "guard"]
    x_p = sum(bool(d["above_alpha"]) for d in gp)
    x_e = sum(bool(d["above_alpha"]) for d in ge)
    gap_p = [d["test_rate"] - d["ltt_rate"] for d in gp]
    gap_e = [d["test_rate"] - d["ltt_rate"] for d in ge]
    wb = p1117_wrong()
    assert len(wb) == K and sum(w / 1221 > ALPHA for w in wb) == B_BOOT_FAIL[0]
    n_sig = {"B": sum(w >= sig for w in wb), "P": sum(d["n_wrong"] >= sig for d in gp),
             "E": sum(d["n_wrong"] >= sig for d in ge)}
    rule = decide_cause(B_BOOT_FAIL[0], x_p, x_e, gap_p, gap_e, n_sig["P"])

    def arm_summary(dd: list[dict]) -> dict:
        g = [d for d in dd if d.get("status") == "guard"]
        st: dict[str, int] = {}
        for d in dd:
            s = d["status"] if d["status"] != "guard" else d["safe_status"]
            st[s] = st.get(s, 0) + 1
        return {"n_draws": len(dd), "n_guard": len(g), "statuses": st,
                "above_alpha": sum(bool(d["above_alpha"]) for d in g),
                "test_rate": rate_stats([d["test_rate"] for d in g]),
                "ltt_rate": rate_stats([d["ltt_rate"] for d in g]),
                "gap": rate_stats([d["test_rate"] - d["ltt_rate"] for d in g]),
                "corr_ltt_test": float(np.corrcoef([d["ltt_rate"] for d in g], [d["test_rate"] for d in g])[0, 1]),
                "ltt_recount_equals_sheet": sum(d["ltt_wrong"] == d["sheet_ltt_wrong"] for d in g),
                "commits": rate_stats([d["n_commits"] for d in g]), "wrong": rate_stats([d["n_wrong"] for d in g]),
                "threshold_range": [min(d["threshold"] for d in g), max(d["threshold"] for d in g)],
                "above_alpha_commits_range": ([min(d["n_commits"] for d in g if d["above_alpha"]),
                                               max(d["n_commits"] for d in g if d["above_alpha"])]
                                              if any(d["above_alpha"] for d in g) else None),
                "above_alpha_wrong_range": ([min(d["n_wrong"] for d in g if d["above_alpha"]),
                                             max(d["n_wrong"] for d in g if d["above_alpha"])]
                                            if any(d["above_alpha"] for d in g) else None),
                "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in g),
                                               default=None),
                "model_kept_range": [min(d["model"]["n_kept"] for d in g), max(d["model"]["n_kept"] for d in g)]}

    sp, se = arm_summary(dp), arm_summary(de)
    sp["max_eval_control_commits"] = max((max(d["eval_controls"].values()) for d in gp), default=None)
    sp["v6_fail"] = sum(not d["v6_eval"] for d in gp)
    se["heldout_safe_wpm_raw"] = rate_stats([d["raw_value"] for d in ge if d.get("raw_value") is not None])
    se["heldout_from_val_range"] = [min(d["pool_info"]["heldout_from_val"] for d in de),
                                    max(d["pool_info"]["heldout_from_val"] for d in de)]
    # calibration-inclusive interval, arm P (P11-17 procedure unchanged)
    Wt = P.cluster_weights(E["clusters"])
    prim = P.combined_interval(dp, E["nw"], E["nch"], E["ns"], Wt)
    for d in dp:
        d["keep_above_alpha"] = bool(d.get("status") == "guard" and d.get("v6_eval") and (
            d.get("safe_status") in ("certified", "above-alpha")) and d.get("raw_value") is not None)
    va = P.combined_interval([{**d, "value": d["raw_value"] if d["keep_above_alpha"] else d["value"]} for d in dp],
                             E["nw"], E["nch"], E["ns"], Wt, credit_key="keep_above_alpha")
    vb = (P.combined_interval([d for d in dp if d.get("credited")], E["nw"], E["nch"], E["ns"], Wt)
          if any(d.get("credited") for d in dp) else None)
    lib_draws = [{"refused": True} if d.get("status") != "guard" or not d.get("v6_eval") else
                 {"committed": d["committed"], "correct": d["correct"], "guarantee": d["guarantee"]} for d in dp]
    lib = SW.calibration_draw_interval(lib_draws, E["nw"], E["nch"], E["ns"], B=2000, seed=0, level=0.95,
                                       reference=NO_BCI, metric_version="0.1")
    lib.pop("draws", None)
    per = [{k: d.get(k) for k in ("name", "arm", "k", "status", "safe_status", "credited", "value", "raw_value",
                                  "n_eval", "n_commits", "n_wrong", "test_rate", "above_alpha", "ltt_commits",
                                  "ltt_wrong", "ltt_rate", "sheet_ltt_commits", "sheet_ltt_wrong", "threshold",
                                  "eval_controls", "v6_eval", "seconds")}
           | {"cal_controls": [x["n_commit"] for x in d.get("cal_controls", [])],
              "model_kept": d.get("model", {}).get("n_kept"), "pool_info": d.get("pool_info")} for d in dp + de]
    res = {"task": "P11-18", "date": time.strftime("%Y-%m-%d %H:%M"), **M.p1111().RESEARCH,
           "note": "aggregates and per-draw counts only (no per-user value, no text, no id)",
           "K": K, "alpha": ALPHA, "delta": DELTA, "reference_no_bci": NO_BCI, "x4": x4,
           "binom_sig_bound_wrong": sig, "above_alpha": {"B_p1117": B_BOOT_FAIL[0], "P": x_p, "E": x_e},
           "significant_exceedances": n_sig, "decision": rule, "arm_P": sp, "arm_E": se,
           "interval_P_primary_user_cluster": prim, "interval_P_variant_a_keep_above_alpha": va,
           "interval_P_variant_b_credited_only": vb, "interval_P_secondary_library": lib,
           "verdict_vs_no_bci": prim["verdict"], "draws": per}
    save_json(res, OUT / "results.json")
    log(f"analyse: above-alpha B {B_BOOT_FAIL[0]}/40 P {x_p}/40 E {x_e}/40; sig {n_sig}; {rule['sentence']} "
        f"interval P {prim['value']:.3f} [{prim['interval'][0]:.2f}, {prim['interval'][1]:.2f}] '{prim['verdict']}'")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("worker", "analyse"))
    ap.add_argument("w", nargs="?", type=int, default=0)
    ap.add_argument("nw", nargs="?", type=int, default=1)
    a = ap.parse_args()
    return worker(a.w, a.nw) if a.stage == "worker" else analyse()


if __name__ == "__main__":
    sys.exit(main())
