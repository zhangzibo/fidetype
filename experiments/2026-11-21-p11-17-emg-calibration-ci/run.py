"""P11-17: calibration-inclusive safe WPM interval for the EMG P11-14 L-FL guard. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files stay
in C:/Users/zhang/bci-data/derived/p11-17/. The P11-07, P11-09, P11-11, P11-12 and P11-14 files are read only.
The repo gets aggregates and per-draw counts only (no per-user value, no text, no id).

    run.py worker     z0 (X4 code check), then draws k = 1 ... 40 (finished draws are skipped)
    run.py analyse    the combined intervals and verdicts -> results/results.json

The P11-14 runner is imported as a module. Only its pure helpers, ``Analyser.get`` / ``analyse`` and
``GuardFn`` are used; its stages, ``own()``, ``log`` and caches are never called (memo load / save are overridden).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
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
from statistics import NormalDist  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-17"  # the only place this task writes per-prompt files
P1114 = DER / "p11-14"  # READ ONLY (feat.pkl memo, model-L-FL.json, decisions-L-FL.json)
EXP1114 = REPO / "experiments" / "2026-11-20-p11-14-emg-lm-confidence"
OUT = Path(os.environ.get("P1117_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ARM = "L-FL"
K = 40
B = 2000
LEVEL = 0.95
NO_BCI = 3.09
N_NULL = 300
CTL_MAX = 0.05  # V6: evaluation time-shuffled and zero-EMG commit rates
X4_REF = {"threshold": 0.63, "commits": 285, "wrong": 52, "value": 6.8030849745214,
          "ci": [4.486023165888807, 9.630032216474465]}


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


def m14():
    """The P11-14 runner as a module (read-only use)."""
    if "p1114run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1114run", EXP1114 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1114run"] = m
        spec.loader.exec_module(m)
    return sys.modules["p1114run"]


def seed_of(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def jobs() -> list[dict]:
    js = [{"name": "z0", "k": 0, "seed": 0, "boot_seed": None}]
    for k in range(1, K + 1):
        js.append({"name": f"k{k:02d}", "k": k, "seed": seed_of(f"p11-17|emg|cal|{k}"),
                   "boot_seed": seed_of(f"p11-17|emg|boot|{k}")})
    return js


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def draw_order(n: int, seed: int, boot_seed: int | None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Input order L such that calibrate(seed) sees fit / policy / LTT = (bootstrap of) its own split (P15-29).

    Returns (L, desired, info): calibrate's item j is the source prompt desired[j]; L[o[j]] = desired[j].
    """
    from fidetype.trust.dropin import _split

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
    return L, desired, info


def cluster_weights(clusters: list[dict], B_: int = B, seed: int = 0) -> np.ndarray:
    """The B weight vectors of ``bootstrap_ci`` (unit ``group``, the same draws, zero-sum vectors skipped)."""
    from fidetype.benchmark.scoring import bootstrap_weights

    draw = bootstrap_weights(np.random.default_rng(seed), "group", clusters)
    ws = []
    for _ in range(B_):
        w = draw()
        if w.sum() == 0:
            continue
        ws.append(w)
    return np.asarray(ws, float)


def draw_values(committed, correct, nw, nch, ns, W: np.ndarray) -> np.ndarray:
    """safe-wpm/0.1 value of each weight vector (rows of W), as ``safe_wpm._point`` with the default rule."""
    from fidetype.benchmark.safe_wpm import CorrectionRule

    cm = np.asarray(committed, bool)
    ok = cm & np.asarray(correct, bool)
    pen = CorrectionRule().penalty(np.asarray(nch, float))
    credit = W @ np.where(ok, np.asarray(nw, float), 0.0)
    den = W @ np.asarray(ns, float) + W @ np.where(cm & ~ok, pen, 0.0)
    return np.where(den > 0, 60.0 * credit / np.where(den > 0, den, 1.0), np.nan)


def combined_interval(draws: list[dict], nw, nch, ns, W: np.ndarray, *, level: float = LEVEL,
                      reference: float | None = NO_BCI, credit_key: str = "credited") -> dict:
    """Two-level interval: per draw the values of the B weight vectors (0.0 if not credited); pooled percentiles.

    ``draws``: mappings with ``committed``, ``correct``, ``value`` (full-set safe WPM) and the bool ``credit_key``.
    """
    q = [(1.0 - level) / 2.0 * 100.0, (1.0 + level) / 2.0 * 100.0]
    vals, cond = [], []
    for d in draws:
        if d.get(credit_key):
            v = draw_values(d["committed"], d["correct"], nw, nch, ns, W)
            v = v[np.isfinite(v)]
            vals.append(float(d["value"]))
        else:
            v = np.zeros(W.shape[0])
            vals.append(0.0)
        cond.append(v)
    pooled = np.concatenate(cond)
    lo, hi = (float(x) for x in np.percentile(pooled, q))
    va = np.asarray(vals)
    Kd = len(va)
    sd_b = float(va.std(ddof=1)) if Kd > 1 else 0.0
    var_w = float(np.mean([c.var(ddof=1) for c in cond]))
    sd_t = math.sqrt(var_w + sd_b ** 2)
    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    mean = float(va.mean())
    out = {"n_draws": Kd, "n_credited": int(sum(bool(d.get(credit_key)) for d in draws)), "value": mean,
           "median_draw_value": float(np.median(va)), "sd_draw_values": sd_b,
           "draw_value_range": [float(va.min()), float(va.max())], "interval": [lo, hi],
           "zero_fraction_pooled": float(np.mean(pooled == 0.0)),
           "sd_between_draws": sd_b, "sd_within_draw": math.sqrt(var_w), "sd_total": sd_t,
           "between_to_within_sd": (sd_b / math.sqrt(var_w)) if var_w > 0 else None,
           "analytic_interval": [mean - z * sd_t, mean + z * sd_t]}
    if reference is not None:
        out["reference"] = float(reference)
        out["lower_above_reference"] = bool(lo > reference)
        out["fraction_of_draws_above_reference"] = float(np.mean(va > reference))
        out["verdict"] = verdict(mean, lo, reference)
    return out


def verdict(mean: float, lo: float, ref: float) -> str:
    if lo > ref:
        return "clearly above after calibration uncertainty"
    if mean > ref:
        return "above, but inside the combined interval"
    return "not above"


# --- window memo (own copy; the P11-14 memo is read only) ------------------------------------------


def make_analyser():
    M = m14()

    class Memo(M.Analyser):  # type: ignore[misc, name-defined]
        def load(self) -> None:
            f = own("feat.pkl")
            src = f if f.exists() else P1114 / "feat.pkl"
            with open(src, "rb") as fh:
                self.memo.update(pickle.load(fh))

        def save(self) -> None:
            f = own("feat.pkl")
            tmp = f.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump(self.memo, fh, protocol=4)
            os.replace(tmp, f)
            self.dirty = 0

    an = Memo()
    an.load()
    return an


def setup():
    M = m14()
    R, cal, ev = M.setup()
    return M, R, cal, ev


def eval_arrays(R, ev: list[dict]) -> dict:
    truths = [R.intended_truth(r) for r in ev]
    return {"truths": truths, "nw": [len(t.split()) for t in truths], "nch": [len(t) for t in truths],
            "ns": [r["neural_s"] for r in ev], "clusters": [{"group": f"u{r['i']}"} for r in ev]}


# --- one draw -----------------------------------------------------------------------------------------


def fit_model(M, R, an, W, cal: list[dict], tune_src: list[int]):
    ok, right, X = [], [], []
    for i in sorted(tune_src):
        a = an.get(W.get(cal[i]), "FL")
        good = a is not None and a["status"] == "ok"
        if not good:
            continue
        X.append(M.feat_vec(a["sig"]))
        right.append(bool(R.same(a["top"], R.intended_truth(cal[i]))))
    return M.Learned.fit(np.array(X), np.array(right)), len(X)


def run_draw(jb: dict, M, R, an, cal, ev, E: dict) -> dict:
    import fidetype.trust as ft
    from fidetype.benchmark import safe_wpm as SW

    path = own(f"draw-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
    W = R.p1109().Windows()
    n = len(cal)
    L, desired, info = draw_order(n, jb["seed"], jb["boot_seed"])
    n_tune = info["split"][0] + info["split"][1]
    model, n_fit_model = fit_model(M, R, an, W, cal, [int(i) for i in desired[:n_tune]])
    fn = M.GuardFn(an, ARM, model)
    c = M.DECODERS["FL"]
    name = ("fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram+lexicon+intended-text+nosignal-gate+conf-L")
    ver = f"p11-14-w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}-L{model.digest()}"
    xs = [W.get(cal[i]) for i in L]
    texts = [R.intended_truth(cal[i]) for i in L]
    pick = sorted(np.random.default_rng(jb["seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
    nulls = [W.get(cal[i], "shuffled") for i in pick]
    res: dict = {**jb, "draw_info": info, "model": {**model.to_dict(), "digest": model.digest(), "n_fit": n_fit_model,
                                                    "n_kept": int(np.sum(np.asarray(model.coef) != 0))}}
    try:
        g = ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=an.KV, blank=0,
                         input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=fn, null_inputs=nulls,
                         decoder_name=name, decoder_version=ver, modality="emg", name=f"p11-17-{jb['name']}",
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
    dec: dict = {}
    for kind in ("real", "shuffled", "zeros"):
        dec[kind] = []
        for r in ev:
            d = g.decide(W.get(r, kind))
            dec[kind].append({"action": d.action, "text": d.text})
    com = [x["action"] == "commit" for x in dec["real"]]
    cor = [cm and bool(R.same(x["text"], t)) for cm, x, t in zip(com, dec["real"], E["truths"])]
    sw = SW.safe_wpm(com, cor, E["nw"], E["nch"], E["ns"], guarantee=SW.guarantee_from_sheet(sh),
                     controls=SW.controls_from_sheet(sh), gaze_chars_per_min=None, metric_version="0.1")
    ctl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ctl[k] / len(ev) <= CTL_MAX for k in ctl)
    credited = sw["status"] == "certified" and sw["value"] is not None and v6
    res.update(status="guard", config_id=g.config_id, safe_status=sw["status"],
               value=float(sw["value"]) if credited else 0.0,
               raw_value=float(sw["value"]) if sw["value"] is not None else None,
               credited=bool(credited), v6_eval=bool(v6), eval_controls=ctl,
               n_commits=int(sum(com)), n_wrong=int(sum(cm and not k for cm, k in zip(com, cor))),
               threshold=sh.get("commit_threshold"), feasible=sh.get("feasible"),
               cal_controls=[{k: x.get(k) for k in ("name", "n", "n_commit", "allowed", "passed")}
                             for x in sh.get("controls", [])],
               sheet={k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt", "feasible",
                                             "commit_threshold", "confidence")},
               guarantee=SW.guarantee_from_sheet(sh), committed=com, correct=cor, decisions=dec,
               seconds_calibrate=round(t1 - t0, 1),
               seconds=round(time.time() - t0, 1))
    an.save()
    save_json(res, path)
    log(f"draw {jb['name']}: thr {res['threshold']} commits {res['n_commits']} wrong {res['n_wrong']} "
        f"status {sw['status']} raw {res['raw_value']} credited {credited} eval ctl {ctl} "
        f"cal ctl {[x['n_commit'] for x in res['cal_controls']]} model kept {res['model']['n_kept']} "
        f"({res['seconds']} s)")
    return res


def x4_check(d: dict, E: dict) -> dict:
    """z0 must reproduce P11-14 L-FL exactly (plan X4)."""
    M = m14()
    ref_model = M.Learned.from_dict(load_json(P1114 / "model-L-FL.json"))
    ref = load_json(P1114 / "decisions-L-FL.json")
    same = {k: sum(a["action"] == b["action"] and (a["text"] or "") == (b["text"] or "")
                   for a, b in zip(d["decisions"][k], ref[k])) for k in ("real", "shuffled", "zeros")}
    W = cluster_weights(E["clusters"])
    v = draw_values(d["committed"], d["correct"], E["nw"], E["nch"], E["ns"], W)
    ci = [float(x) for x in np.percentile(v[np.isfinite(v)], [2.5, 97.5])]
    n = len(E["truths"])
    out = {"model_digest": d["model"]["digest"], "ref_model_digest": ref_model.digest(),
           "same_decisions": same, "n_eval": n, "threshold": d.get("threshold"), "commits": d.get("n_commits"),
           "wrong": d.get("n_wrong"), "value": d.get("raw_value"), "k1_interval": ci}
    out["pass"] = bool(d["model"]["digest"] == ref_model.digest() and all(s == n for s in same.values())
                       and abs((d.get("threshold") or -1) - X4_REF["threshold"]) < 1e-9
                       and d.get("n_commits") == X4_REF["commits"] and d.get("n_wrong") == X4_REF["wrong"]
                       and abs((d.get("raw_value") or 0) - X4_REF["value"]) < 1e-6
                       and all(abs(a - b) < 1e-9 for a, b in zip(ci, X4_REF["ci"])) and d.get("credited"))
    return out


def worker() -> int:
    keep_awake(True)
    try:
        M, R, cal, ev = setup()
        E = eval_arrays(R, ev)
        an = make_analyser()
        for jb in jobs():
            d = run_draw(jb, M, R, an, cal, ev, E)
            if jb["name"] == "z0":
                x4 = x4_check(d, E)
                save_json(x4, own("x4.json"))
                log(f"X4: {'PASS' if x4['pass'] else 'FAIL'} {x4}")
                if not x4["pass"]:
                    log("X4 failed: stop (plan: no result from code that does not reproduce)")
                    return 2
        return 0
    finally:
        keep_awake(False)


# --- analysis -----------------------------------------------------------------------------------------


def analyse() -> int:
    from fidetype.benchmark import safe_wpm as SW

    M, R, cal, ev = setup()
    E = eval_arrays(R, ev)
    x4 = load_json(own("x4.json"))
    if not x4["pass"]:  # type: ignore[index]
        log("analyse: X4 did not pass; no result")
        return 2
    ds = [load_json(own(f"draw-{jb['name']}.json")) for jb in jobs() if jb["k"] > 0]
    assert len(ds) == K, len(ds)
    W = cluster_weights(E["clusters"])
    prim = combined_interval(ds, E["nw"], E["nch"], E["ns"], W)
    for d in ds:  # exploratory variants (pre-named, descriptive)
        d["keep_above_alpha"] = d.get("status") == "guard" and d.get("v6_eval") and (
            d.get("safe_status") in ("certified", "above-alpha")) and d.get("raw_value") is not None
        if d["keep_above_alpha"] and not d.get("credited"):
            d["value_keep"] = d["raw_value"]
    va = combined_interval([{**d, "value": d.get("value_keep", d["value"])} for d in ds], E["nw"], E["nch"],
                           E["ns"], W, credit_key="keep_above_alpha")
    vb = combined_interval([d for d in ds if d.get("credited")], E["nw"], E["nch"], E["ns"], W) \
        if any(d.get("credited") for d in ds) else None
    lib_draws = []
    for d in ds:
        if d.get("status") != "guard" or not d.get("v6_eval"):
            lib_draws.append({"refused": True})
        else:
            lib_draws.append({"committed": d["committed"], "correct": d["correct"], "guarantee": d["guarantee"]})
    lib = SW.calibration_draw_interval(lib_draws, E["nw"], E["nch"], E["ns"], B=B, seed=0, level=LEVEL,
                                       reference=NO_BCI, metric_version="0.1")
    lib.pop("draws", None)
    per = [{k: d.get(k) for k in ("name", "k", "status", "safe_status", "credited", "value", "raw_value",
                                  "n_commits", "n_wrong", "threshold", "eval_controls", "v6_eval", "seconds")}
           | {"cal_controls": [x["n_commit"] for x in d.get("cal_controls", [])],
              "model_kept": d.get("model", {}).get("n_kept"),
              "distinct_per_part": d.get("draw_info", {}).get("distinct_per_part")} for d in ds]
    statuses: dict[str, int] = {}
    for d in ds:
        s = d["status"] if d["status"] != "guard" else (d["safe_status"] if d.get("v6_eval") else "v6-fail")
        statuses[s] = statuses.get(s, 0) + 1
    gd = [d for d in ds if d.get("status") == "guard"]
    res = {"task": "P11-17", "date": time.strftime("%Y-%m-%d %H:%M"), **m14().p1111().RESEARCH,
           "note": "aggregates and per-draw counts only (no per-user value, no text, no id)",
           "arm": ARM, "K": K, "B": int(W.shape[0]), "level": LEVEL, "reference_no_bci": NO_BCI,
           "x4": x4, "statuses": statuses, "primary_user_cluster": prim,
           "variant_a_keep_above_alpha": va, "variant_b_credited_only": vb, "secondary_library_trial_level": lib,
           "mean_commits": float(np.mean([d["n_commits"] for d in gd])) if gd else None,
           "mean_wrong": float(np.mean([d["n_wrong"] for d in gd])) if gd else None,
           "threshold_range": [min(d["threshold"] for d in gd), max(d["threshold"] for d in gd)] if gd else None,
           "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in gd), default=None),
           "max_eval_control_commits": max((max(d["eval_controls"].values()) for d in gd), default=None),
           "verdict": prim["verdict"], "draws": per}
    save_json(res, OUT / "results.json")
    log(f"analyse: primary {prim['value']:.3f} [{prim['interval'][0]:.2f}, {prim['interval'][1]:.2f}] "
        f"verdict '{prim['verdict']}'; statuses {statuses}; library {lib['value']:.3f} "
        f"[{lib['interval'][0]:.2f}, {lib['interval'][1]:.2f}]")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("worker", "analyse"))
    a = ap.parse_args()
    return worker() if a.stage == "worker" else analyse()


if __name__ == "__main__":
    sys.exit(main())
