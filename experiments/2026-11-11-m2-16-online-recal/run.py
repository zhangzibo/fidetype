"""M2-16: online re-calibration of the COMMIT threshold under drift (CPU, < 1 min).

Uses the per-trial item files of M2-13 (B2T '25 our decoder and the
published-sentence gate; MEG M1-15 full-r1) and of ``emg_items.py``
(Toronto sEMG composed sentences). Each item has the commit score, the
commit / fallback loss and the eWPM terms of both outcomes, so a
threshold sequence gives the exact per-trial outcome of the simulated user
(the M2-13 mix, checked there against the full harness).

Protocols:

- ``drift`` (the M2-13 failure case): warm start on the fit half (earlier
  trials of each day), then run the test half (later trials) in
  chronological order, day by day. Feedback after each trial (delay 0) or
  10 trials late.
- ``fullday`` (B2T only): all trials of all days in chronological order
  (per day: earlier half, then later half), **cold start** (no
  calibration; the online gate starts at "never commit"). Note: the
  upstream parts (temperatures, conformal sets, guard, policy grid) were
  fit on the earlier halves, so the earlier-half scores are in-sample.
- ``shuffled``: as ``drift``, but the test half in random order (20
  shuffles): an exchangeable control for the eWPM cost.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-11-m2-16-online-recal/run.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.trust.online_risk import OnlineCommitRiskControl  # noqa: E402
from fidetype.trust.risk_control import crc_threshold, ltt_threshold  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
ALPHA, DELTA, RW = CONFIG["alpha"], CONFIG["delta"], CONFIG["rolling_window"]
OUT = HERE / "results"
M213 = REPO / CONFIG["m213_items"]
KEYS = ("loss_c", "loss_f", "wc_c", "wc_f", "time_c", "time_f", "words_c", "words_f", "silent_c", "silent_f")


class Arr:
    def __init__(self, d: dict):
        self.s = np.array([float(x) for x in d["score"]])
        for k in KEYS:
            setattr(self, k, np.asarray(d[k], dtype=np.float64))
        self.lam_old = float(d["lam_old"])

    @staticmethod
    def concat(a: "Arr", b: "Arr", order: np.ndarray) -> "Arr":
        out = object.__new__(Arr)
        out.s = np.r_[a.s, b.s][order]
        for k in KEYS:
            setattr(out, k, np.r_[getattr(a, k), getattr(b, k)][order])
        out.lam_old = a.lam_old
        return out

    def take(self, idx: np.ndarray) -> "Arr":
        out = object.__new__(Arr)
        out.s = self.s[idx]
        for k in KEYS:
            setattr(out, k, getattr(self, k)[idx])
        out.lam_old = self.lam_old
        return out


def outcome(a: Arr, on: np.ndarray, rows: np.ndarray | None = None) -> dict:
    sel = slice(None) if rows is None else rows
    wc = np.where(on, a.wc_c, a.wc_f)[sel]
    t = np.where(on, a.time_c, a.time_f)[sel]
    w = np.where(on, a.words_c, a.words_f)[sel]
    se = np.where(on, a.silent_c, a.silent_f)[sel]
    out = {"n": int(wc.size), "wrong_commit": float(wc.mean()), "commit_rate": float(np.mean(on[sel])),
           "ewpm": float(60 * w.sum() / t.sum()), "silent_error": float(se.mean())}
    if wc.size >= RW:
        roll = np.convolve(wc, np.ones(RW), "valid") / RW
        out["roll_max"] = float(roll.max())
        out["roll_share_gt_alpha"] = float(np.mean(roll > ALPHA + 1e-12))
    return out


def run_online(kw: dict, a: Arr, warm: Arr | None, delay: int, noticed: bool = False) -> tuple[np.ndarray, dict, np.ndarray]:
    """Run one controller over ``a`` in order. ``noticed``: the feedback is what the simulated
    user noticed: a silent wrong commit looks right (loss 0), and a non-commit item whose final
    text is wrong gives no truth (None)."""
    o = OnlineCommitRiskControl(alpha=ALPHA, **kw)
    if warm is not None:
        o.fit(warm.s, warm.loss_c, warm.loss_f)
    on, lam, queue = np.zeros(a.s.size, bool), np.zeros(a.s.size), []
    for i in range(a.s.size):
        tk = o.decide(a.s[i])
        on[i], lam[i] = tk.commit, tk.threshold
        queue.append((tk, i))
        if len(queue) > delay:
            tk, j = queue.pop(0)
            c = a.loss_c[j]
            if noticed and tk.commit and a.silent_c[j]:
                c = 0.0
            elif noticed and not tk.commit and a.silent_f[j]:
                c = None
            o.observe(tk, c, a.loss_f[j])
    rep = o.report()
    if kw["method"] == "aci":
        rep["prior_bound"] = o.prior_bound(max(rep["n_observed"], 1), delay)
    return on, rep, lam


def offline(a_test: Arr, warm: Arr) -> dict[str, float]:
    return {"old": a_test.lam_old,
            "crc": crc_threshold(warm.s, warm.loss_c, ALPHA, warm.loss_f).threshold,
            "ltt": ltt_threshold(warm.s, warm.loss_c, ALPHA, DELTA, warm.loss_f).threshold}


def fnum(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None if math.isnan(x) else ("inf" if x > 0 else "-inf")
    return x


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return fnum(float(o))
    if isinstance(o, np.integer):
        return int(o)
    return o


def protocol_drift(fit: Arr, test: Arr, eta_grid: bool = False) -> dict:
    res: dict = {"offline": {}, "online": {}}
    for k, lam in offline(test, fit).items():
        res["offline"][k] = {"threshold": lam, **outcome(test, test.s >= lam)}
    for d in CONFIG["delays"]:
        for name, kw in CONFIG["methods"].items():
            on, rep, lam = run_online(kw, test, fit, d)
            res["online"][f"{name}@d{d}"] = {**outcome(test, on), "report": rep,
                                            "threshold_mean": float(np.mean(np.where(np.isfinite(lam), lam, 1.0)))}
    for name in ("aci", "aci_window"):
        on, rep, _ = run_online(CONFIG["methods"][name], test, fit, max(CONFIG["delays"]), noticed=True)
        res["online"][f"{name}@d{max(CONFIG['delays'])}-noticed"] = {**outcome(test, on), "report": rep}
    if eta_grid:
        res["eta"] = {}
        for eta in CONFIG["eta_sensitivity"]:
            on, rep, _ = run_online({"method": "aci", "eta": eta}, test, fit, 0)
            res["eta"][str(eta)] = {**outcome(test, on), "certificate": rep["certificate"], "prior_bound": rep["prior_bound"]}
    return res


def protocol_shuffled(fit: Arr, test: Arr, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    rows: dict[str, list[dict]] = {}
    for _ in range(reps):
        a = test.take(rng.permutation(test.s.size))
        for k, lam in offline(a, fit).items():
            rows.setdefault(k, []).append(outcome(a, a.s >= lam))
        for name, kw in CONFIG["methods"].items():
            on, _, _ = run_online(kw, a, fit, 0)
            rows.setdefault(name, []).append(outcome(a, on))
    return {k: {m: float(np.mean([r[m] for r in v])) for m in v[0]} for k, v in rows.items()}


def protocol_fullday(fit: Arr, test: Arr, days_fit: list[int], days_test: list[int]) -> dict:
    n_f = fit.s.size
    order = []
    for d in sorted(set(days_fit)):
        order += [i for i, x in enumerate(days_fit) if x == d]
        order += [n_f + i for i, x in enumerate(days_test) if x == d]
    order = np.array(order)
    a = Arr.concat(fit, test, order)
    is_test = order >= n_f
    res: dict = {"n": int(order.size), "offline": {}, "online": {}}
    for k, lam in {"old": fit.lam_old}.items():
        on = a.s >= lam
        res["offline"][k] = {"all": outcome(a, on), "later_halves": outcome(a, on, np.where(is_test)[0])}
    for d in CONFIG["delays"]:
        for name, kw in CONFIG["methods"].items():
            on, rep, _ = run_online(kw, a, None, d)
            res["online"][f"{name}@d{d}"] = {"all": outcome(a, on), "later_halves": outcome(a, on, np.where(is_test)[0]),
                                            "report": rep}
    return res


def iid_reference(n: int, reps: int = 2000, seed: int = 1) -> dict:
    """Max rolling-window rate of an i.i.d. Bernoulli(alpha) sequence of length n."""
    rng = np.random.default_rng(seed)
    x = (rng.uniform(size=(reps, n)) < ALPHA).astype(float)
    c = np.cumsum(np.pad(x, ((0, 0), (1, 0))), axis=1)
    m = ((c[:, RW:] - c[:, :-RW]) / RW).max(axis=1)
    return {"n": n, "median": float(np.median(m)), "p95": float(np.quantile(m, 0.95))}


def main() -> None:
    t0 = time.time()
    out: dict = {"config": CONFIG, "datasets": {}}
    for name in ("b2t-ours", "b2t-published"):
        d = json.loads((M213 / f"items-{name}.json").read_text(encoding="utf-8"))
        fit, test = Arr(d["fit"]), Arr(d["test"])
        out["datasets"][name] = {
            "n_fit": int(fit.s.size), "n_test": int(test.s.size),
            "drift": protocol_drift(fit, test, eta_grid=True),
            "shuffled": protocol_shuffled(fit, test, CONFIG["shuffles"], CONFIG["seed"]),
            "fullday": protocol_fullday(fit, test, d["days_fit"], d["days_test"]),
            "iid_reference": iid_reference(test.s.size),
            "iid_reference_fullday": iid_reference(fit.s.size + test.s.size),
        }
        print(f"{name} done ({time.time() - t0:.0f}s)", flush=True)
    d = json.loads((M213 / "items-meg-full-r1.json").read_text(encoding="utf-8"))
    fit, test = Arr(d["fit"]), Arr(d["test"])
    out["datasets"]["meg-full-r1"] = {"n_fit": int(fit.s.size), "n_test": int(test.s.size),
                                      "drift": protocol_drift(fit, test), "iid_reference": iid_reference(test.s.size)}
    for cond in ("xsession", "calib", "xsubject"):
        p = OUT / f"items-emg-{cond}.json"
        if not p.exists():
            print(f"skip EMG {cond}: run emg_items.py first")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        fit, test = Arr(d["fit"]), Arr(d["test"])
        out["datasets"][f"emg-{cond}"] = {"n_fit": int(fit.s.size), "n_test": int(test.s.size),
                                          "drift": protocol_drift(fit, test), "iid_reference": iid_reference(test.s.size)}
    out["seconds"] = round(time.time() - t0, 1)
    (OUT / "online.json").write_text(json.dumps(clean(out), indent=1), encoding="utf-8")
    tables(out)
    print(f"done ({out['seconds']}s)")


def f4(x) -> str:
    if isinstance(x, str):
        return x
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4f}"


def row(name: str, m: dict, extra: str = "") -> str:
    return (f"| {name} | {f4(m['wrong_commit'])} | {f4(m.get('roll_max'))} | {f4(m.get('roll_share_gt_alpha'))} | "
            f"{m['commit_rate']:.3f} | {m['ewpm']:.3f} | {f4(m['silent_error'])} | {extra} |")


HEAD = ["| method | wrong-commit | max rolling-50 | share of 50-windows > α | commit rate | eWPM | silent error | certificate / note |",
        "|---|---|---|---|---|---|---|---|"]


def tables(out: dict) -> None:
    L = ["# M2-16 tables (generated by run.py)", "",
         f"α = {ALPHA}. Rolling window = {RW} trials. Certificate = the deterministic long-run bound of the "
         "method on the observed losses (aci / aci_window); — = no such bound.", ""]
    for name, ds in out["datasets"].items():
        L += [f"## {name} (fit {ds['n_fit']}, test {ds['n_test']})", "", "### drift: warm start on the earlier data, test in order", ""] + HEAD
        dr = ds["drift"]
        for k, m in dr["offline"].items():
            L.append(row(f"offline {k}", m, f"λ = {f4(fnum(float(m['threshold'])))}"))
        for k, m in dr["online"].items():
            r = m["report"]
            note = f"cert {f4(r['certificate'])}" + (f", prior {f4(r.get('prior_bound'))}" if "prior_bound" in r else "")
            L.append(row(k, m, note))
        ref = ds["iid_reference"]
        L += ["", f"Reference: i.i.d. Bernoulli(α), n = {ref['n']}: max rolling-50 median {ref['median']:.3f}, p95 {ref['p95']:.3f}.", ""]
        if "eta" in dr:
            L += ["### aci step size (drift, delay 0)", "", "| η | wrong-commit | max rolling-50 | commit rate | eWPM | certificate | prior bound |",
                  "|---|---|---|---|---|---|---|"]
            for e, m in dr["eta"].items():
                L.append(f"| {e} | {f4(m['wrong_commit'])} | {f4(m.get('roll_max'))} | {m['commit_rate']:.3f} | {m['ewpm']:.3f} | "
                         f"{f4(m['certificate'])} | {f4(m['prior_bound'])} |")
            L.append("")
        if "shuffled" in ds:
            L += [f"### shuffled test order (exchangeable control, mean of {CONFIG['shuffles']})", ""] + HEAD
            for k, m in ds["shuffled"].items():
                L.append(row(k, m))
            L.append("")
        if "fullday" in ds:
            fd = ds["fullday"]
            ref = ds["iid_reference_fullday"]
            L += [f"### fullday: all {fd['n']} trials in order, cold start (no calibration)", "",
                  "Columns as above, over all trials; the last column gives wrong-commit / eWPM on the later halves only.", ""] + HEAD
            for k, m in fd["offline"].items():
                lh = m["later_halves"]
                L.append(row(f"offline {k} (in-sample fit)", m["all"], f"later halves {f4(lh['wrong_commit'])} / {lh['ewpm']:.3f}"))
            for k, m in fd["online"].items():
                lh = m["later_halves"]
                L.append(row(k, m["all"], f"cert {f4(m['report']['certificate'])}; later halves {f4(lh['wrong_commit'])} / {lh['ewpm']:.3f}"))
            L += ["", f"Reference: i.i.d. Bernoulli(α), n = {ref['n']}: max rolling-50 median {ref['median']:.3f}, p95 {ref['p95']:.3f}.", ""]
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
