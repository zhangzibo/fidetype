"""P14-28: reading cost per commit and minimum prefix length in the proposed safe-wpm/0.2 (plan.md). CPU only.

A SENSITIVITY analysis: it re-scores the fixed P5-24 per-trial decisions (no fitting, no new decisions, no new
calibration). It is not a new test of the guard.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-18-p14-28-reading-cost/run.py

Reads (read only): C:/Users/zhang/bci-data/derived/p5-24/decisions-p5-24-*-{sentence,prefix}.json and the trial
durations (npy headers only: number of 20 ms bins) from the P5-24 data folders. Writes per-cell tables (no text) to
C:/Users/zhang/bci-data/derived/p14-28/ and the aggregates to results/ here.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import zipfile  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import (  # noqa: E402
    CorrectionRule,
    controls_from_sheet,
    guarantee_from_sheet,
    prefix_outcome,
    safe_wpm,
)

DER = Path("C:/Users/zhang/bci-data/derived")
SRC = DER / "p5-24"  # read only
OWN = DER / "p14-28"  # the only place this task writes per-cell files
assert OWN.name == "p14-28" and SRC.name == "p5-24"
P524 = REPO / "experiments/2026-11-18-p5-24-prefix-commits"
OUT = HERE / "results"
BIN_S = 0.02
B, SEED = 2000, 0
NO_BCI = {"t15": 4.02, "t12": 4.11}
SETS = {"t15": "t15-m4-13", "t12": "t12-v2"}
ARMS = ("sentence", "prefix")
# pre-registered grid (plan.md)
FIXED_S = (0.0, 0.5, 1.0, 2.0, 3.0)
MIN_WORDS = (1, 2, 3)
NAMED = {  # name: (s per commit, s per committed word)
    "aac-gaze-v1 verify (0.5 s + 0.3 s/word)": (0.5, 0.3),
    "KLM M (1.35 s)": (1.35, 0.0),
    "KLM M + silent reading 238 wpm (1.35 s + 0.252 s/word)": (1.35, 60.0 / 238.0),
}
EXPECTED = {("t15", "sentence"): 2.6444020156977244, ("t15", "prefix"): 4.866011441941262,
            ("t12", "sentence"): 1.867605321866411, ("t12", "prefix"): 4.7613478791118835}


def npy_rows(zf: zipfile.ZipFile, key: str) -> int:
    """First dimension of one array in an .npz, from its .npy header only (no array data is read)."""
    with zf.open(key + ".npy") as f:
        v = np.lib.format.read_magic(f)
        shape = (np.lib.format.read_array_header_1_0(f) if v == (1, 0) else np.lib.format.read_array_header_2_0(f))[0]
    return int(shape[0])


def durations_t15() -> list[float]:
    """As P14-05 ``t15_durations`` on the ``t15_keys`` order of val_eval (M4-13 log-prob file keys)."""
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    order = {s: j for j, s in enumerate(sessions)}
    with zipfile.ZipFile(DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz") as z:
        files = [n[:-4] for n in z.namelist() if n.endswith(".npy")]
    keys = sorted((k for k in files if "|val_eval|" in k), key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
    out, cache = [], {}
    for k in keys:
        s, p, i, _ = k.split("|")
        if s not in cache:
            cache[s] = zipfile.ZipFile(d_in / f"{s}.npz")
        out.append(npy_rows(cache[s], f"{p}_X{int(i)}") * BIN_S)
    for z in cache.values():
        z.close()
    return out


def durations_t12() -> list[float]:
    """As P5-23 ``data_t12``: test sessions of the T12 v2 prep, pool trials in order."""
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    d_in = Path(json.loads((exp / "config.json").read_text(encoding="utf-8"))["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    out = []
    for r in prep["sessions"]:
        if r["role"] != "test":
            continue
        with zipfile.ZipFile(d_in / f"{r['session']}.npz") as z:
            for i, _w in enumerate(texts[r["session"]]["pool"]):
                out.append(npy_rows(z, f"pool_X{i}") * BIN_S)
    return out


def arrays(rows: list[dict]) -> dict:
    """v0.2 per-trial arrays exactly as P5-24 ``trial_arrays(rows, "0.2")``."""
    cm, ok, kw, comp, pc = [], [], [], [], []
    for r in rows:
        y = r["truth"]
        c = r["action"] == "commit"
        full = True if r.get("complete") is None else bool(r["complete"])
        cm.append(c)
        if not c:
            ok.append(False)
            kw.append(math.nan)
            comp.append(True)
            pc.append(math.nan)
            continue
        po = prefix_outcome(r["text"], y, full)
        ok.append(po["correct"])
        kw.append(po["committed_words"])
        comp.append(po["complete"])
        pc.append(po["penalty_chars"])
    t = [r["truth"] for r in rows]
    return {"committed": cm, "correct": ok, "n_words": [len(y.split()) for y in t], "n_chars": [len(y) for y in t],
            "committed_words": kw, "complete": comp, "penalty_chars": pc}


def per_trial(a: dict, rs: float, rw: float, m: int):
    """(credit, time) per trial under one cell; matches safe_wpm(metric_version="0.2", ...) (checked)."""
    cm = np.array(a["committed"], bool)
    comp = np.array(a["complete"], bool)
    kw = np.array(a["committed_words"], float)
    partial = cm & ~comp
    cm = cm & ~(partial & (np.nan_to_num(kw) < m))
    partial = cm & ~comp
    ok = cm & np.array(a["correct"], bool)
    nw = np.array(a["n_words"], float)
    nc = np.array(a["n_chars"], float)
    pc = np.nan_to_num(np.array(a["penalty_chars"], float))
    credit = np.where(ok, np.where(partial, np.nan_to_num(kw), nw), 0.0)
    pen = CorrectionRule().penalty(np.where(partial, pc, nc))
    read = np.where(cm, rs + rw * np.where(np.isfinite(kw), kw, nw), 0.0)
    extra = np.where(cm & ~ok, pen, 0.0) + read
    return credit, extra, int(cm.sum()), int((cm & ~ok).sum())


def boot_idx(n: int) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    return np.stack([np.bincount(rng.integers(0, n, n), minlength=n) for _ in range(B)]).astype(float)


def pct(v) -> list[float]:
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def break_even(a: dict, ns: np.ndarray, target: float, m: int, per_word: bool) -> float | None:
    """Reading cost x (s per commit, or s per committed word if per_word) where safe WPM = target (closed form)."""
    credit, extra, _, _ = per_trial(a, 0.0, 0.0, m)
    cm = np.array(a["committed"], bool)
    comp = np.array(a["complete"], bool)
    kw = np.array(a["committed_words"], float)
    keep = cm & ~((cm & ~comp) & (np.nan_to_num(kw) < m))
    unit = np.where(keep, np.where(np.isfinite(kw), kw, np.array(a["n_words"], float)) if per_word else 1.0, 0.0)
    t0 = ns.sum() + extra.sum()
    need = 60.0 * credit.sum() / target - t0
    return None if need < 0 else float(need / unit.sum())


def run_set(name: str) -> dict:
    t0 = time.time()
    tag = SETS[name]
    ns = np.asarray(durations_t15() if name == "t15" else durations_t12(), float)
    rows = {arm: json.loads((SRC / f"decisions-p5-24-{tag}-{arm}.json").read_text(encoding="utf-8")) for arm in ARMS}
    sheets = {arm: json.loads((P524 / "results" / f"guard-p5-24-{tag}-{arm}.json").read_text(encoding="utf-8"))["sheet"]
              for arm in ARMS}
    arr = {arm: arrays(rows[arm]) for arm in ARMS}
    n = len(ns)
    assert all(len(rows[a]) == n for a in ARMS), (n, [len(rows[a]) for a in ARMS])
    W = boot_idx(n)
    cells = [("grid", f"{c:g} s/commit", c, 0.0) for c in FIXED_S] + [("named", k, v[0], v[1]) for k, v in NAMED.items()]
    table = []
    for kind, label, rs, rw in cells:
        for m in MIN_WORDS:
            row = {"kind": kind, "reading": label, "read_s_per_commit": rs, "read_s_per_word": rw, "min_prefix_words": m}
            boots = {}
            for arm in ARMS:
                lib = safe_wpm(**arr[arm], neural_s=ns, guarantee=guarantee_from_sheet(sheets[arm]),
                               controls=controls_from_sheet(sheets[arm]), metric_version="0.2",
                               timing="measured trial duration (20 ms neural bins)", read_s_per_commit=rs,
                               read_s_per_word=rw, min_prefix_words=m)
                credit, extra, k, kwr = per_trial(arr[arm], rs, rw, m)
                own = 60.0 * credit.sum() / (ns.sum() + extra.sum())
                assert abs(own - lib["unguarded_wpm"]) < 1e-9, (name, arm, rs, rw, m, own, lib["unguarded_wpm"])
                if rs == 0 and rw == 0 and m == 1:
                    assert abs(lib["value"] - EXPECTED[(name, arm)]) < 1e-9, (name, arm, lib["value"])
                boots[arm] = 60.0 * (W @ credit) / (W @ ns + W @ extra)
                row[arm] = {"value": lib["value"], "status": lib["status"], "ci95": pct(boots[arm]),
                            "n_commits": k, "n_wrong": kwr, "wrong_rate": kwr / n,
                            "committed_correct_words": lib["committed_correct_words"],
                            "minutes_reading": (lib.get("reading_cost") or {}).get("minutes_reading", 0.0),
                            "n_prefix_commits_dropped": (lib.get("reading_cost") or {}).get("n_prefix_commits_dropped", 0)}
            d = boots["prefix"] - boots["sentence"]
            row["delta_prefix_minus_sentence"] = row["prefix"]["value"] - row["sentence"]["value"]
            row["delta_ci95"] = pct(d)
            row["prefix_above_no_bci"] = row["prefix"]["value"] > NO_BCI[name]
            row["prefix_ci_low_above_no_bci"] = row["prefix"]["ci95"][0] > NO_BCI[name]
            table.append(row)
    be = {}
    for m in MIN_WORDS:
        be[f"m{m}"] = {
            "prefix_s_per_commit_to_no_bci": break_even(arr["prefix"], ns, NO_BCI[name], m, False),
            "prefix_s_per_word_to_no_bci": break_even(arr["prefix"], ns, NO_BCI[name], m, True),
        }
    # break-even where prefix = sentence (both pay the same fixed cost per commit), m = 1: bisection
    def gap(c: float) -> float:
        v = []
        for arm in ARMS:
            cr, ex, _, _ = per_trial(arr[arm], c, 0.0, 1)
            v.append(60.0 * cr.sum() / (ns.sum() + ex.sum()))
        return v[1] - v[0]
    lo, hi = 0.0, 1000.0
    be_eq = None
    if gap(hi) < 0:
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if gap(mid) > 0 else (lo, mid)
        be_eq = (lo + hi) / 2
    be["prefix_equals_sentence_s_per_commit_m1"] = be_eq
    # words per commit (prefix arm), as a check of the P5-24 histogram
    kw = [r["n_words_committed"] for r in rows["prefix"] if r["action"] == "commit"]
    hist = {int(k): int(v) for k, v in zip(*np.unique(kw, return_counts=True))}
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / f"cells-p14-28-{tag}.json").write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    return {"n_trials": n, "minutes_neural": float(ns.sum()) / 60.0, "no_bci": NO_BCI[name], "table": table,
            "break_even": be, "prefix_words_per_commit": hist, "seconds": round(time.time() - t0, 1)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    res = {"fidetype_version": FT_VERSION, "plan": "experiments/2026-11-18-p14-28-reading-cost/plan.md",
           "label": "SENSITIVITY: re-scoring of the fixed P5-24 decisions under the proposed safe-wpm/0.2; "
                    "not a new test of the guard", "B": B, "seed": SEED, "sets": {}}
    for name in ("t15", "t12"):
        res["sets"][name] = run_set(name)
        print(name, "done", res["sets"][name]["seconds"], "s", flush=True)
    try:
        import psutil  # noqa: PLC0415

        res["peak_mb"] = psutil.Process().memory_info().peak_wset / 2**20
    except Exception:  # noqa: BLE001
        res["peak_mb"] = None
    (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for name, s in res["sets"].items():
        print(f"== {name} (no-BCI {s['no_bci']}) break-even {json.dumps(s['break_even'])}")
        for r in s["table"]:
            p, q = r["prefix"], r["sentence"]
            print(f"{r['reading']:<58} m={r['min_prefix_words']}  prefix {p['value']:.2f} [{p['ci95'][0]:.2f}, "
                  f"{p['ci95'][1]:.2f}] ({p['n_commits']} commits)  sentence {q['value']:.2f}  "
                  f"delta {r['delta_prefix_minus_sentence']:+.2f} [{r['delta_ci95'][0]:+.2f}, {r['delta_ci95'][1]:+.2f}]")


if __name__ == "__main__":
    main()
