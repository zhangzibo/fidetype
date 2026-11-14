"""P12-02 evaluation: per-class risk control for discrete intents (FEP-0003).

Two data sources:

A. **Toronto sEMG typing, recast as a 27-way key-choice intent** (Achituve
   et al. 2025, CC BY 4.0). Each key press is one decision unit: "which of
   27 keys did the user mean". We reuse the per-press logits of the M6-07
   CNN decoders (``C:/Users/zhang/bci-data/runs/emg-toronto/<run>/preds.npz``,
   derived data outside the repo). Risk classes are a fixed, arbitrary
   declaration made before any result: ``key.a``-``key.e`` irreversible
   (think "send", "call", "delete"), ``key.space`` safe, the other 21 keys
   undoable. The data has no rest windows, so this vocabulary has no null
   intent.
B. **Synthetic simulator** (``fidetype.trust.intent_sim``, clearly
   artificial): 12 intents with a null ``rest`` intent, rest trials,
   no-signal trials and a signal-quality index.

Protocol (A): per participant and session, R random splits of the presses
into thirds: fit (temperature), calibration (one LTT / CRC threshold per
risk class), test. The configuration fitted on clean data is applied to
the test thirds of the clean input and of the controls:

- ``uniform``: every press gets the uniform distribution (no signal);
- ``zero``: the decoder's output on an all-zero EMG window (no signal);
- ``timeshuffled`` (``calib`` only): the CNN on EMG windows whose time
  samples were permuted (``shuffle_control.py``);
- ``pairshuffled``: decoder outputs permuted across the presses of the
  group (outputs real, pairing with the truth broken: breaks exchangeability).

Settings ``*-nosignalref`` fit with a no-signal reference (the decoder's
zero-input output plus the uniform row; no labels): each class threshold
is raised above the reference's top-1 probability of that class. The
time-shuffled control is never used in a fit (held out).

Plus ``permuted-decoder``: the label-permuted-training decoder of M6-07,
calibrated **and** tested on its own outputs (the full pipeline on a
decoder that learned nothing).

Only aggregate numbers are written (``results/summary.json``,
``results/tables.md``). No per-trial data, no participant text.

CPU only, 2 threads, below-normal priority. Run (repo root)::

    .venv\\Scripts\\python.exe -I experiments/2026-11-13-p12-intent-events/eval_intents.py
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

import numpy as np  # noqa: E402

if sys.platform == "win32":
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from fidetype.trust.intent import (  # noqa: E402
    DEFAULT_ALPHA,
    RISK_CLASSES,
    IntentVocabulary,
    evaluate_policy,
    fit_intent_config,
)
from fidetype.trust.intent_sim import demo_vocabulary, shuffled_control, simulate_trials, uniform_control  # noqa: E402

CACHE = Path("C:/Users/zhang/bci-data/cache/toronto-semg/v1")
RUNS = Path("C:/Users/zhang/bci-data/runs/emg-toronto")
CTRL = Path("C:/Users/zhang/bci-data/runs/p12-intent")
OUT = HERE / "results"
SEED = 20261113
DELTA = 0.1
KEYS = [chr(ord("a") + i) for i in range(26)] + ["space"]
IRREVERSIBLE = {"a", "b", "c", "d", "e"}
SAFE = {"space"}
R = {"calib": 100, "xsession": 50, "xsubject": 50, "permuted-decoder": 50}
SYN_SESSIONS = 200


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with (OUT / "run.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def key_vocabulary() -> IntentVocabulary:
    risk = {f"key.{k}": ("irreversible" if k in IRREVERSIBLE else "safe" if k in SAFE else "undoable") for k in KEYS}
    return IntentVocabulary.simple([f"key.{k}" for k in KEYS], risk=risk, vocab_id="intent.toronto-keys-27")


def softmax(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=np.float64)
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def load_runs(names: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    idx, lg, zl = [], [], []
    for r in names:
        d = np.load(RUNS / r / "preds.npz")
        idx.append(d["idx"])
        lg.append(d["logits"])
        zl.append(np.repeat(d["zero_logits"][None, :], len(d["idx"]), axis=0))
    return np.concatenate(idx), np.concatenate(lg), np.concatenate(zl)


class Agg:
    """Collects per-split metrics; reports means, pooled rates and exceedance."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}

    def add(self, key: str, m: dict, thr: dict | None = None) -> None:
        self.rows.setdefault(key, []).append({**m, **({"thr": thr} if thr else {})})

    def summary(self) -> dict:
        out = {}
        for key, rows in self.rows.items():
            n = np.array([r["n"] for r in rows], dtype=float)
            s: dict = {"splits": len(rows), "n_total": int(n.sum())}
            acted = np.array([r["commit"] + r["armed"] for r in rows])
            s["act_rate_mean"] = float(np.mean(acted / n))
            s["commit_rate_mean"] = float(np.mean([r["commit"] / r["n"] for r in rows]))
            s["armed_rate_mean"] = float(np.mean([r["armed"] / r["n"] for r in rows]))
            s["offer_rate_mean"] = float(np.mean([r["offer"] / r["n"] for r in rows]))
            s["abstain_rate_mean"] = float(np.mean([r["abstain"] / r["n"] for r in rows]))
            tot_c = sum(r["commit"] for r in rows)
            s["commit_precision_pooled"] = (sum(r["commit_correct"] for r in rows) / tot_c) if tot_c else None
            tot_o = sum(r["offer"] for r in rows)
            s["truth_in_offer_pooled"] = (sum(r["truth_in_offer"] for r in rows) / tot_o) if tot_o else None
            for c in RISK_CLASSES:
                w = np.array([r[f"wrong_{c}"] for r in rows], dtype=float)
                s[f"wrong_{c}_mean"] = float(np.mean(w / n))
                s[f"wrong_{c}_pooled"] = float(w.sum() / n.sum())
                s[f"wrong_{c}_exceed"] = float(np.mean(w / n > DEFAULT_ALPHA[c] + 1e-12))
                s[f"wrong_{c}_max"] = float(np.max(w / n))
            s["wrong_any_mean"] = float(np.mean([r["wrong_any"] / r["n"] for r in rows]))
            thr = [r["thr"] for r in rows if "thr" in r]
            if thr:
                for c in RISK_CLASSES:
                    v = np.array([math.inf if t[c] is None else t[c] for t in thr])
                    s[f"thr_{c}_median"] = float(np.median(v)) if np.isfinite(np.median(v)) else None
                    s[f"thr_{c}_never"] = float(np.mean(~np.isfinite(v)))
            out[key] = s
        return out


def thr_dict(cfg) -> dict:
    return {c: (None if not math.isfinite(cfg.thresholds[c]) else float(cfg.thresholds[c])) for c in RISK_CLASSES}


def run_toronto(agg: Agg) -> dict:
    vocab = key_vocabulary()
    d = np.load(CACHE / "windows.npz")
    label_all, fidx_all = d["label"].astype(np.int64), d["file_idx"]
    files = json.loads((CACHE / "files.json").read_text(encoding="utf-8"))
    conds = {
        "calib": ["calib_a", "calib_b"],
        "xsession": ["xsession"],
        "xsubject": [f"xsubject_f{i}" for i in range(4)],
        "permuted-decoder": ["xsession_permuted"],
    }
    info = {}
    rng = np.random.default_rng(SEED)
    for cond, runs in conds.items():
        idx, logits, zero = load_runs(runs)
        y = label_all[idx]
        grp = np.array([files[f]["participant"] + "/" + files[f]["session"] for f in fidx_all[idx]])
        P = softmax(logits)
        Z = softmax(zero)
        TS = None
        if cond == "calib":
            ts_idx, ts = [], []
            for r in runs:
                c = np.load(CTRL / f"{r}_controls.npz")
                ts_idx.append(c["idx"])
                ts.append(c["timeshuffled"])
            ts_idx = np.concatenate(ts_idx)
            assert np.array_equal(ts_idx, idx)
            TS = softmax(np.concatenate(ts))
        acc = float(np.mean(P.argmax(1) == y))
        info[cond] = {"runs": runs, "n_presses": int(len(y)), "groups": int(len(set(grp))), "top1_acc": acc,
                      "splits_per_group": R[cond]}
        log(f"{cond}: {len(y)} presses, {len(set(grp))} groups, top-1 acc {acc:.3f}")
        for g in sorted(set(grp)):
            gi = np.where(grp == g)[0]
            for _ in range(R[cond]):
                perm = rng.permutation(gi)
                k = len(perm) // 3
                f, c, t = perm[:k], perm[k:2 * k], perm[2 * k:]
                ns_ref = np.vstack([np.unique(Z[gi], axis=0), np.full((1, P.shape[1]), 1 / P.shape[1])])
                for meth, floor in (("ltt", 0.5), ("crc", 0.5), ("ltt-nofloor", 0.0), ("ltt-nosignalref", 0.5),
                                    ("crc-nosignalref", 0.5)):
                    if cond == "permuted-decoder" and meth.endswith("nosignalref"):
                        continue
                    cfg = fit_intent_config(vocab, P[f], y[f], P[c], y[c], method=meth.split("-")[0], delta=DELTA,
                                            min_threshold=floor,
                                            no_signal_probs=ns_ref if meth.endswith("nosignalref") else None)
                    key = f"toronto/{cond}/{meth}"
                    agg.add(f"{key}/clean", evaluate_policy(cfg, P[t], y[t]), thr_dict(cfg))
                    if cond == "permuted-decoder" or meth == "ltt-nofloor":
                        continue
                    agg.add(f"{key}/uniform", evaluate_policy(cfg, np.full_like(P[t], 1 / P.shape[1]), y[t]))
                    agg.add(f"{key}/zero", evaluate_policy(cfg, Z[t], y[t]))
                    agg.add(f"{key}/pairshuffled", evaluate_policy(cfg, P[rng.permutation(t)], y[t]))
                    if TS is not None:
                        agg.add(f"{key}/timeshuffled", evaluate_policy(cfg, TS[t], y[t]))
        log(f"{cond}: done")
    return info


def run_synthetic(agg: Agg) -> dict:
    vocab = demo_vocabulary()
    for s in range(SYN_SESSIONS):
        fit = simulate_trials(vocab, 500, seed=10_000 + s)
        cal = simulate_trials(vocab, 500, seed=20_000 + s)
        test = simulate_trials(vocab, 1000, seed=30_000 + s)
        ns = test.kind == "nosignal"
        for meth in ("ltt", "crc"):
            for gate in (None, 0.5):
                cfg = fit_intent_config(vocab, fit.probs, fit.labels, cal.probs, cal.labels, method=meth, delta=DELTA,
                                        min_signal_quality=gate)
                key = f"synthetic/{meth}/{'quality-gate' if gate else 'no-gate'}"
                agg.add(f"{key}/clean", evaluate_policy(cfg, test.probs, test.labels, test.quality), thr_dict(cfg))
                agg.add(f"{key}/nosignal-trials", evaluate_policy(cfg, test.probs[ns], test.labels[ns], test.quality[ns]))
                u = uniform_control(test)
                agg.add(f"{key}/uniform", evaluate_policy(cfg, u.probs, u.labels, u.quality))
                sh = shuffled_control(test, seed=s)
                agg.add(f"{key}/pairshuffled", evaluate_policy(cfg, sh.probs, sh.labels, sh.quality))
    return {"sessions": SYN_SESSIONS, "n_fit": 500, "n_cal": 500, "n_test": 1000, "vocab": vocab.vocab_id,
            "model": "snr 3.0, overconfidence 1.5, rest 10 %, no-signal 10 %"}


def fmt(x, p=3) -> str:
    return "-" if x is None else f"{x:.{p}f}"


def tables(summary: dict) -> str:
    L = ["# P12-02 intent evaluation: tables", "",
         f"alpha: safe {DEFAULT_ALPHA['safe']}, undoable {DEFAULT_ALPHA['undoable']}, irreversible "
         f"{DEFAULT_ALPHA['irreversible']} (per decision unit); LTT delta {DELTA} (Bonferroni over 3 classes). "
         "Rates are means over (group, split) test sets; 'exceed' = share of test sets above alpha; "
         "irreversible wrong = wrong armed intents (execution needs a confirmation too).", "",
         "| setting | input | act rate | commit / armed / offer / abstain | commit precision | truth in offer | "
         "wrong safe (exceed) | wrong undoable (exceed) | wrong irreversible (exceed, max) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for key, s in summary.items():
        setting, inp = key.rsplit("/", 1)
        L.append(f"| {setting} | {inp} | {fmt(s['act_rate_mean'])} | {fmt(s['commit_rate_mean'], 2)} / "
                 f"{fmt(s['armed_rate_mean'], 2)} / {fmt(s['offer_rate_mean'], 2)} / {fmt(s['abstain_rate_mean'], 2)} | "
                 f"{fmt(s['commit_precision_pooled'])} | {fmt(s['truth_in_offer_pooled'])} | "
                 f"{fmt(s['wrong_safe_mean'], 4)} ({fmt(s['wrong_safe_exceed'], 2)}) | "
                 f"{fmt(s['wrong_undoable_mean'], 4)} ({fmt(s['wrong_undoable_exceed'], 2)}) | "
                 f"{fmt(s['wrong_irreversible_mean'], 4)} ({fmt(s['wrong_irreversible_exceed'], 2)}, "
                 f"{fmt(s['wrong_irreversible_max'], 3)}) |")
    L += ["", "Median fitted thresholds (share of fits with 'never commit'):", "",
          "| setting | safe | undoable | irreversible |", "|---|---|---|---|"]
    for key, s in summary.items():
        if key.endswith("/clean") and "thr_safe_never" in s:
            L.append(f"| {key[:-6]} | " + " | ".join(
                f"{fmt(s[f'thr_{c}_median'], 2)} ({fmt(s[f'thr_{c}_never'], 2)})" for c in RISK_CLASSES) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    agg = Agg()
    log("synthetic simulator")
    syn = run_synthetic(agg)
    log("toronto sEMG key-choice recast")
    tor = run_toronto(agg)
    summary = agg.summary()
    res = {"seed": SEED, "alpha": DEFAULT_ALPHA, "delta": DELTA, "toronto": tor, "synthetic": syn,
           "risk_map": {"irreversible": sorted(IRREVERSIBLE), "safe": sorted(SAFE), "undoable": "other 21 keys"},
           "summary": summary, "seconds": round(time.time() - t0, 1)}
    (OUT / "summary.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    (OUT / "tables.md").write_text(tables(summary), encoding="utf-8", newline="\n")
    log(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
