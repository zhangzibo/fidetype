"""P11-28: safety headroom of the EMG BX3 guard (40 new draws + the 40 P11-19 draws). CPU only.

Pre-registration: plan.md (this folder, commit 84d465f). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0.
Per-prompt files stay in C:/Users/zhang/bci-data/derived/p11-28/. derived/p11-19 and derived/p11-23 are read only.
The repo gets aggregates and per-draw pooled counts only (no per-user value, no text, no id).

    run.py worker 1 <w> <n>  X1' (XF01, XF13 = P11-23 S01 / S13) and X5 (R-k01-j2, R-k13-j3 = P11-19 split guards)
    run.py checks            X1' and X5 comparisons (must pass)
    run.py worker 2 <w> <n>  the 120 new split guards (k = 41..80, j = 1..3) at (alpha'' 0.0314, delta / 3)
    run.py analyse           X4, X6, rules BX3 / BXS / BX2 / BD3 / J1 / AN3, tail and headroom -> results/results.json

The split guard code is the P11-19 run.py (imported read only; its OWN / OUT are redirected to this item by the
environment variables P1119_OWN / P1119_OUT before the import). The window memo starts empty (fresh decodes only).
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
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = Path(os.environ.get("P1128_OWN", str(DER / "p11-28")))  # the only place this task writes per-prompt files
P1119D = DER / "p11-19"  # READ ONLY (split-k*-j*.json, split-XF*.json)
P1123D = DER / "p11-23"  # READ ONLY (draw-S*.json)
EXP1119 = REPO / "experiments" / "2026-11-21-p11-19-multi-split"
OUT = Path(os.environ.get("P1128_OUT", str(HERE / "results")))
os.environ["P1119_OWN"] = str(OWN)  # redirect the imported P11-19 runner (plan "Fixed parts")
os.environ["P1119_OUT"] = str(OUT)

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA = 0.05
DELTA = 0.1
ALPHA_PP = 0.0314
J = 3
K_OLD = range(1, 41)
K_NEW = range(41, 81)
X1_DRAWS = (1, 13)
X5_GUARDS = ((1, 2), (13, 3))
LEVEL = 0.95
Q_LEVEL = 0.9  # the delta-quantile
CLEAR_H = 0.005
CAP_S = 4.6 * 3600  # no new split guard after 4.6 h from the chain start
NO_BCI = 3.09
X6_REF = {"test_rate_mean": 0.028112203112203117, "value": 5.898744142080952}
RULES = ("BX3", "BXS", "BX2", "BD3", "J1", "AN3")


def p19():
    """The P11-19 runner as a module (read only)."""
    if "p1119run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1119run", EXP1119 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1119run"] = m
        spec.loader.exec_module(m)
        assert m.OWN == OWN and m.OUT == OUT, "P11-19 runner not redirected"
    return sys.modules["p1119run"]


def log(*a: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(obj: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def split_seed(k: int, j: int) -> int:
    """P11-19 split_seed (same formula; tested against it)."""
    import hashlib

    tag = f"p11-18|emg|cal|{k}" if j == 1 else f"p11-19|emg|split|{k}|{j}"
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def jobs(phase: int) -> list[dict]:
    if phase == 1:
        x1 = [{"name": f"XF{k:02d}", "k": k, "j": 1, "seed": split_seed(k, 1), "null_seed": split_seed(k, 1),
               "ltt_alpha": ALPHA_PP, "delta": DELTA, "gname": f"p11-23-S{k:02d}"} for k in X1_DRAWS]
        x5 = [{"name": f"R-k{k:02d}-j{j}", "k": k, "j": j, "seed": split_seed(k, j), "null_seed": split_seed(k, 1),
               "ltt_alpha": ALPHA_PP, "delta": DELTA / J, "gname": f"p11-19-k{k:02d}-j{j}"} for k, j in X5_GUARDS]
        return x1 + x5
    return [{"name": f"k{k:02d}-j{j}", "k": k, "j": j, "seed": split_seed(k, j), "null_seed": split_seed(k, 1),
             "ltt_alpha": ALPHA_PP, "delta": DELTA / J, "gname": f"p11-28-k{k:02d}-j{j}"}
            for k in K_NEW for j in range(1, J + 1)]


def _max_v(c: list[dict]) -> dict | None:
    return sorted(c, key=lambda x: (-x["v_in"], x["j"]))[0] if c else None


def pick(rule: str, ok: list[dict]) -> dict | None:
    """Deployed split guard of one draw (ok: non-refused split guards with j, v_in, ltt_rate). Not for AN3."""
    if rule == "BX3":
        return _max_v(ok)
    if rule == "BXS":  # safety tie-break: keep ltt_rate <= the draw median, then the highest v_in
        if not ok:
            return None
        med = float(np.median([s["ltt_rate"] for s in ok]))
        return _max_v([s for s in ok if s["ltt_rate"] <= med + 1e-15])
    if rule == "BX2":
        return _max_v([s for s in ok if s["j"] in (1, 2)])
    if rule == "BD3":
        if not ok:
            return None
        s = sorted(ok, key=lambda x: (x["v_in"], x["j"]))
        return s[(len(s) - 1) // 2]
    if rule == "J1":
        return next((s for s in ok if s["j"] == 1), None)
    raise ValueError(rule)


def cp_upper(f: int, n: int, level: float = LEVEL) -> float:
    """One-sided Clopper-Pearson upper bound on a binomial proportion."""
    from scipy.stats import beta

    return 1.0 if f >= n else float(beta.ppf(level, f + 1, n - f))


def quantile_rank(n: int, q: float = Q_LEVEL, level: float = LEVEL) -> int | None:
    """Smallest m with P(Bin(n, q) <= m - 1) >= level: r_(m) is a distribution-free upper bound on the q-quantile."""
    from scipy.stats import binom

    return next((m for m in range(1, n + 1) if binom.cdf(m - 1, n, q) >= level), None)


def headroom_label(h: float | None) -> str:
    if h is None:
        return "not computable"
    if h >= CLEAR_H:
        return "clear headroom"
    if h > 0:
        return "thin headroom"
    return "no headroom"


def tail_stats(rates: list[float]) -> dict:
    from statistics import NormalDist

    r = np.sort(np.asarray(rates, float))
    n = len(r)
    f = int(np.sum(r > ALPHA))
    m = quantile_rank(n)
    Q = float(r[m - 1]) if m is not None else None
    h = (ALPHA - Q) if Q is not None else None
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    tail = float(1.0 - NormalDist(float(r.mean()), sd).cdf(ALPHA)) if sd > 0 else None
    return {"n": n, "f_above_alpha": f, "cp_upper": cp_upper(f, n), "cp_upper_le_delta": bool(cp_upper(f, n) <= DELTA),
            "above_ltt_alpha": int(np.sum(r > ALPHA_PP)), "q_rank": m, "Q": Q, "headroom": h,
            "headroom_label": headroom_label(h), "mean": float(r.mean()), "sd": sd,
            "quantiles": {str(p): float(np.quantile(r, p)) for p in (0.5, 0.75, 0.9, 0.95)},
            "max": float(r.max()), "top5": [float(x) for x in r[::-1][:5]], "normal_tail_p_above_alpha": tail}


def cluster_fraction(wrong: np.ndarray, W: np.ndarray) -> dict:
    """Test-set uncertainty: per weight vector (rows of W), the fraction of draws (rows of wrong) above alpha."""
    rates = (W @ wrong.T.astype(float)) / W.sum(axis=1, keepdims=True)  # (B, N)
    frac = np.mean(rates > ALPHA, axis=1)
    return {"B": int(W.shape[0]), "fraction_median": float(np.median(frac)),
            "fraction_p95": float(np.quantile(frac, 0.95)), "p_fraction_gt_delta": float(np.mean(frac > DELTA)),
            "max_rate_median": float(np.median(rates.max(axis=1))),
            "max_rate_p95": float(np.quantile(rates.max(axis=1), 0.95))}


def overall_verdict(cp_ok: bool, label: str) -> str:
    if not cp_ok:
        return "BX3 does not keep the claim with margin"
    if label == "clear headroom":
        return "BX3 safety holds with headroom"
    return "the claim holds, but the headroom is thin"


# --- workers and checks -------------------------------------------------------------------------------


def worker(phase: int, w: int, nw: int) -> int:
    P19 = p19()
    P19.keep_awake(True)
    try:
        st = OWN / "CHAIN_START"
        t_start = float(st.read_text(encoding="utf-8").strip()) if st.exists() else time.time()
        M = P19.p17().m14()
        R, cal, ev = M.setup()
        E = P19.p17().eval_arrays(R, ev)
        Ec = P19.p17().eval_arrays(R, cal)
        W = P19.p23().Windows(R)
        an = P19.make_analyser(w)  # derived/p11-28/feat-w<w>.pkl: empty at the first phase-1 start
        if phase == 1 and not any((OWN / f"split-{jb['name']}.json").exists() for jb in jobs(1)) and an.memo:
            log(f"worker 1-{w}: memo not empty before phase 1 (plan: fresh decodes only); stop")
            return 6
        for i, jb in enumerate(jobs(phase)):
            if i % nw != w:
                continue
            if (OWN / "STOP").exists():
                log(f"worker {phase}-{w}: STOP file found; stop")
                return 3
            if not (OWN / f"split-{jb['name']}.json").exists() and time.time() - t_start > CAP_S:
                log(f"worker {phase}-{w}: compute cap (4.6 h from chain start) reached; stop")
                return 5
            P19.run_guard(jb, M, R, an, W, cal, ev, E, Ec)
        return 0
    finally:
        P19.keep_awake(False)


def n_actions_differ(a: dict, b: dict) -> int:
    return int(sum(x != y for kd in ("real", "shuffled", "zeros") for x, y in zip(a["decisions"][kd], b["decisions"][kd])))


def checks() -> int:
    P19 = p19()
    out: dict = {"x1_fresh": [], "x5": []}
    for k in X1_DRAWS:
        a = load_json(OWN / f"split-XF{k:02d}.json")
        for ref_name, ref in (("p11-23", load_json(P1123D / f"draw-S{k:02d}.json")),
                              ("p11-19", load_json(P1119D / f"split-XF{k:02d}.json"))):
            c = P19.x1_compare(a, ref)
            c.update(ref=ref_name, n_actions_differ=n_actions_differ(a, ref))  # type: ignore[arg-type]
            out["x1_fresh"].append(c)
    for k, j in X5_GUARDS:
        a = load_json(OWN / f"split-R-k{k:02d}-j{j}.json")
        ref = load_json(P1119D / f"split-k{k:02d}-j{j}.json")
        c = P19.x1_compare(a, ref)
        c["fields"]["v_in"] = a.get("v_in") == ref.get("v_in")  # type: ignore[union-attr]
        c["pass"] = all(c["fields"].values())
        c.update(name=f"R-k{k:02d}-j{j}", n_actions_differ=n_actions_differ(a, ref),  # type: ignore[arg-type]
                 config_id_equal=a.get("config_id") == ref.get("config_id"))  # type: ignore[union-attr]
        out["x5"].append(c)
    out["x1_fresh_pass"] = all(c["pass"] and c["n_actions_differ"] == 0 for c in out["x1_fresh"])
    out["x5_pass"] = all(c["pass"] and c["n_actions_differ"] == 0 for c in out["x5"])
    out["pass"] = bool(out["x1_fresh_pass"] and out["x5_pass"])
    save_json(out, OWN / "checks.json")
    log(f"checks: X1' {'PASS' if out['x1_fresh_pass'] else 'FAIL'}; X5 {'PASS' if out['x5_pass'] else 'FAIL'}; "
        f"{[(c['name'], c.get('ref'), c['pass'], c['n_actions_differ']) for c in out['x1_fresh'] + out['x5']]}")
    return 0 if out["pass"] else 4


# --- analysis -----------------------------------------------------------------------------------------


def load_splits() -> tuple[dict, list[str]]:
    splits: dict[int, list[dict]] = {}
    missing = []
    for k in list(K_OLD) + list(K_NEW):
        src = P1119D if k in K_OLD else OWN
        ss = []
        for j in range(1, J + 1):
            p = src / f"split-k{k:02d}-j{j}.json"
            if p.exists():
                ss.append(load_json(p))
            else:
                missing.append(f"k{k:02d}-j{j}")
        if len(ss) == J:
            splits[k] = ss
    return splits, missing


def build(rule: str, ss: list[dict], E: dict, R) -> dict:
    P19 = p19()
    ok = [s for s in ss if s.get("status") == "guard"]
    base = {"rule": rule, "n_split_guards": len(ok)}
    if rule == "AN3":
        if len(ok) < J:
            return {**base, "status": "refused", "credited": False, "value": 0.0}
        dec = {kd: P19.and_actions([s["decisions"][kd] for s in ok], R.same) for kd in ("real", "shuffled", "zeros")}
        d = P19.score_actions(dec, [s["sheet"] for s in ok], E, R, rule)
        return {**base, "status": "guard", "j_hat": None, "threshold": None,
                "ltt_rate": max(s["ltt_rate"] for s in ok), **d}
    g = pick(rule, ok)
    if g is None:
        return {**base, "status": "refused", "credited": False, "value": 0.0}
    d = P19.score_actions(g["decisions"], [g["sheet"]], E, R, rule)
    d["guarantee"]["J"] = 2 if rule == "BX2" else (1 if rule == "J1" else J)
    return {**base, "status": "guard", "j_hat": g["j"], "threshold": g["threshold"], "ltt_rate": g["ltt_rate"],
            "v_in": g["v_in"], **d}


def analyse() -> int:
    P19 = p19()
    P = P19.p17()
    M = P.m14()
    R, cal, ev = M.setup()
    E = P.eval_arrays(R, ev)
    ck = load_json(OWN / "checks.json")
    res: dict = {"task": "P11-28", "date": time.strftime("%Y-%m-%d %H:%M"), **M.p1111().RESEARCH,
                 "note": "aggregates and per-draw pooled counts only (no per-user value, no text, no id)",
                 "metric_version": "safe-wpm/0.1 (adopted; equal to the proposed v0.2 for sentence commits)",
                 "alpha_claim": ALPHA, "delta": DELTA, "ltt_alpha": ALPHA_PP, "J": J, "split_delta": DELTA / J,
                 "reference_no_bci": NO_BCI, "checks": ck}
    splits, missing = load_splits()
    new_k = [k for k in K_NEW if k in splits]
    old_k = [k for k in K_OLD if k in splits]
    res["draws_complete"] = {"old": len(old_k), "new": len(new_k)}
    res["missing_split_guards"] = missing
    newg = [s for k in new_k for s in splits[k] if s.get("status") == "guard"]
    x4 = [s["ltt_wrong"] == s["sheet_ltt_wrong"] for s in newg]
    res["x4"] = {"n": len(x4), "n_same": int(sum(x4)), "pass": bool(len(x4) > 0 and all(x4))}
    rs = P19.p18().rate_stats
    res["new_split_guards"] = {
        "n": 3 * len(new_k), "n_guard": len(newg),
        "refused": sum(s.get("status") == "refused" for k in new_k for s in splits[k]),
        "infeasible": sum(s.get("feasible") is False for s in newg),
        "at_grid_floor": sum(s["threshold"] is not None and abs(s["threshold"] - 0.30) < 1e-9 for s in newg),
        "v_in": rs([s["v_in"] for s in newg]) if newg else None,
        "threshold": rs([s["threshold"] for s in newg]) if newg else None,
        "max_cal_control_commits": max((max(x["n_commit"] for x in s["cal_controls"]) for s in newg), default=None),
        "seconds": rs([s["seconds"] for s in newg]) if newg else None}
    Wt = P.cluster_weights(E["clusters"])
    arms = {r: {k: build(r, splits[k], E, R) for k in old_k + new_k} for r in RULES}
    # X6: the 40 old BX3 draws rebuild the committed P11-19 BX3 numbers
    bx_old = [arms["BX3"][k] for k in old_k]
    x6_rate = float(np.mean([d["test_rate"] for d in bx_old])) if bx_old else None
    x6_val = P.combined_interval(bx_old, E["nw"], E["nch"], E["ns"], Wt)["value"] if bx_old else None
    res["x6"] = {"test_rate_mean": x6_rate, "value": x6_val, "ref": X6_REF,
                 "pass": bool(len(old_k) == 40 and abs(x6_rate - X6_REF["test_rate_mean"]) < 1e-9
                              and abs(x6_val - X6_REF["value"]) < 1e-9)}
    must = bool(ck["pass"] and res["x4"]["pass"] and res["x6"]["pass"])  # type: ignore[index]
    res["must_pass_all"] = must
    res["complete"] = bool(len(new_k) == 40 and not [m for m in missing if int(m[1:3]) in K_NEW])
    log(f"analyse: checks {ck['pass']}, X4 {res['x4']['pass']}, X6 {res['x6']['pass']}; "  # type: ignore[index]
        f"draws old {len(old_k)} new {len(new_k)}")
    if not must:
        log("analyse: a must-pass check failed; no arm result (plan)")
        res["arms"] = None
        save_json(res, OUT / "results.json")
        return 0
    sets = {"new": new_k, "old": old_k, "pooled": old_k + new_k}
    out: dict = {}
    for r in RULES:
        out[r] = {}
        for sname, ks in sets.items():
            dd = [arms[r][k] for k in ks]
            g = [d for d in dd if d.get("status") == "guard"]
            if not g:
                continue
            ts = tail_stats([d["test_rate"] for d in g])
            wrong = np.asarray([np.asarray(d["committed"], bool) & ~np.asarray(d["correct"], bool) for d in g])
            iv = P.combined_interval(dd, E["nw"], E["nch"], E["ns"], Wt)
            out[r][sname] = {
                "tail": ts, "test_set_uncertainty": cluster_fraction(wrong, Wt),
                "ltt_rate": rs([d["ltt_rate"] for d in g]), "gap": rs([d["test_rate"] - d["ltt_rate"] for d in g]),
                "commits": rs([d["n_commits"] for d in g]), "wrong": rs([d["n_wrong"] for d in g]),
                "refused": len(dd) - len(g), "credited": int(sum(bool(d.get("credited")) for d in dd)),
                "statuses": {s: sum((d.get("safe_status") if d.get("status") == "guard" else d.get("status")) == s
                                    for d in dd) for s in {(d.get("safe_status") if d.get("status") == "guard"
                                                            else d.get("status")) for d in dd}},
                "c_null_all_zero": all(max(d["eval_controls"].values()) == 0 for d in g),
                "j_hat": {str(j): sum(d.get("j_hat") == j for d in g) for j in range(1, J + 1)},
                "interval": {kk: iv[kk] for kk in ("value", "interval", "median_draw_value", "draw_value_range",
                                                   "sd_between_draws", "sd_within_draw", "analytic_interval",
                                                   "lower_above_reference", "verdict", "n_credited")}}
        out[r]["draws_new"] = [{"k": k, **{kk: arms[r][k].get(kk) for kk in (
            "status", "j_hat", "n_commits", "n_wrong", "test_rate", "ltt_rate", "threshold", "value", "credited",
            "eval_controls")}} for k in new_k]
    res["arms"] = out
    bxp, bxn = out["BX3"]["pooled"], out["BX3"]["new"]
    res["H1"] = {"f80": bxp["tail"]["f_above_alpha"], "cp_upper": bxp["tail"]["cp_upper"],
                 "pass": bxp["tail"]["cp_upper_le_delta"], "n": bxp["tail"]["n"]}
    res["H2"] = {"Q": bxp["tail"]["Q"], "q_rank": bxp["tail"]["q_rank"], "headroom": bxp["tail"]["headroom"],
                 "label": bxp["tail"]["headroom_label"]}
    res["H2_rep"] = {"f40": bxn["tail"]["f_above_alpha"], "cp_upper": bxn["tail"]["cp_upper"], "Q": bxn["tail"]["Q"],
                     "headroom": bxn["tail"]["headroom"], "label": bxn["tail"]["headroom_label"],
                     "replicated": bool(bxn["tail"]["f_above_alpha"] <= 1)}
    res["H3"] = {"new": bxn["interval"]["verdict"], "new_interval": [bxn["interval"]["value"], *bxn["interval"]["interval"]],
                 "pooled": bxp["interval"]["verdict"],
                 "pooled_interval": [bxp["interval"]["value"], *bxp["interval"]["interval"]],
                 "replicated": bool(bxn["interval"]["lower_above_reference"])}
    res["overall_verdict"] = overall_verdict(res["H1"]["pass"], res["H2"]["label"])
    res["secondary_more_margin"] = {
        r: bool(out[r]["pooled"]["tail"]["Q"] < bxp["tail"]["Q"] and out[r]["pooled"]["interval"]["lower_above_reference"])
        for r in RULES if r != "BX3" and "pooled" in out[r]}
    res["complete"] = res["complete"]
    save_json(res, OUT / "results.json")
    log(f"analyse: BX3 pooled f {res['H1']['f80']}/{res['H1']['n']} CP95 {res['H1']['cp_upper']:.4f} "
        f"(H1 {'pass' if res['H1']['pass'] else 'fail'}); Q {res['H2']['Q']:.4f} headroom {res['H2']['headroom']:.4f} "
        f"'{res['H2']['label']}'; new f {res['H2_rep']['f40']}/40; H3 new '{res['H3']['new']}'; "
        f"verdict '{res['overall_verdict']}'")
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
