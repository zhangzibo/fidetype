"""P15-25 shared helpers (NumPy only; no torch). Our own code (Apache-2.0).

The verdict rule (``beats``, ``verdict``) re-implements the frozen E1a rule of
``experiments/2026-11-19-p15-08-e1-cross-body/run.py`` without torch, and adds a Bonferroni interval from the
same bootstrap draws (plan: multiple comparisons).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "results"
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p15-25"  # the only place this task writes per-sentence files and log-probs
E1A_OUT = DER / "p15-08"  # READ ONLY
P3_12_DONE = DER / "p3-12" / "DONE"
ARMS = ("R", "T", "E", "S")
BUDGETS = ("3", "10", "30", "100", "all")
SEEDS = (0, 1)
#: The P11-01 / E1a vocabulary (``e1.VOCAB``), copied so that this module needs no torch.
VOCAB: list[str] = ["<blank>"] + [chr(c) for c in range(32, 127)] + ["⌫", "⏎"]
TOK = {c: i for i, c in enumerate(VOCAB)}
assert len(VOCAB) == 98 and VOCAB[1] == " " and VOCAB[97] == "⏎"


def config() -> dict:
    return json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def e1a_config() -> dict:
    return json.loads((REPO / config()["e1a_config"]).read_text(encoding="utf-8"))


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json(obj: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def stop_requested() -> bool:
    return (OWN / "STOP").exists()


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def peak_mb() -> float:
    """Peak working set of this process in MB (Windows; 0 elsewhere)."""
    if os.name != "nt":
        return 0.0
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k32 = ctypes.WinDLL("kernel32")
    psapi = ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return 0.0
    return c.PeakWorkingSetSize / 2**20


# --- runs -----------------------------------------------------------------------------------------------


def run_name(arm: str, budget: str, seed: int, label_shuffle: bool = False) -> str:
    return f"{arm}-b{budget}-s{seed}" + ("-labelshuf" if label_shuffle else "")


def main_runs() -> list[str]:
    return [run_name(a, b, s) for a in ARMS for b in BUDGETS for s in SEEDS]


def all_runs() -> list[str]:
    return main_runs() + [run_name("E", "30", 0, True)]


def tune_runs(cfg: dict) -> list[str]:
    t = cfg["fv_tuning"]
    return [run_name(a, b, s) for a in t["arms"] for b in t["budgets"] for s in t["seeds"]]


def c1_runs() -> list[str]:
    return [run_name(a, b, s) for a in ARMS for b in e1a_config()["c1_budgets"] for s in SEEDS]


def parse_run(name: str) -> dict:
    parts = name.split("-")
    return {"arm": parts[0], "budget": parts[1][1:], "seed": int(parts[2][1:]), "label_shuffle": len(parts) > 3}


# --- metric -----------------------------------------------------------------------------------------------


def levenshtein(ref, hyp) -> int:
    """Edit distance with unit costs (row-wise NumPy DP)."""
    a = np.asarray(list(ref), np.int64)
    b = np.asarray(list(hyp), np.int64)
    if len(a) == 0:
        return int(len(b))
    if len(b) == 0:
        return int(len(a))
    prev = np.arange(len(b) + 1, dtype=np.int64)
    for i in range(1, len(a) + 1):
        cur = np.empty_like(prev)
        cur[0] = i
        sub = prev[:-1] + (b != a[i - 1])
        dele = prev[1:] + 1
        best = np.minimum(sub, dele)
        # insertions need a left-to-right scan: cur[j] = min(best[j-1], cur[j-1] + 1)
        run = i
        for j in range(1, len(b) + 1):
            v = best[j - 1]
            run = run + 1
            if v < run:
                run = v
            cur[j] = run
        prev = cur
    return int(prev[-1])


def encode(text: str) -> list[int]:
    return [TOK[c] for c in text]


def greedy_tokens(lp: np.ndarray, blank: int = 0) -> list[int]:
    a = np.asarray(lp).argmax(1)
    if len(a) == 0:
        return []
    keep = np.concatenate([[True], a[1:] != a[:-1]])
    a = a[keep]
    return [int(x) for x in a[a != blank]]


# --- verdict (E1a rule, torch-free) -------------------------------------------------------------------------


def bootstrap(e_a: np.ndarray, e_b: np.ndarray, ref: np.ndarray, n: int, seed: int, k_bonf: int) -> dict:
    """Paired bootstrap over sentences of (sum e_a - sum e_b) / sum ref. Same draws as E1a
    ``bootstrap_delta`` (``default_rng(seed).integers(0, k, (n, k))``). 95 % and Bonferroni (1 - 0.05 / k_bonf)
    percentile intervals; ``p_le0`` = share of draws <= 0."""
    rng = np.random.default_rng(seed)
    k = len(ref)
    d0 = (e_a.sum() - e_b.sum()) / ref.sum()
    ii = rng.integers(0, k, size=(n, k))
    d = (e_a[ii].sum(1) - e_b[ii].sum(1)) / ref[ii].sum(1)
    q = 100 * 0.05 / k_bonf / 2
    return {"delta": float(d0), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)),
            "lo_bonf": float(np.percentile(d, q)), "hi_bonf": float(np.percentile(d, 100 - q)),
            "p_le0": float(np.mean(d <= 0)), "n": n}


def beats(cer: dict, edits: dict, ref: np.ndarray, a: str, b: str, budget: str, rules: dict, k_bonf: int,
          need_ci: bool = True) -> dict:
    ca = [cer[(a, budget, s)] for s in SEEDS]
    cb = [cer[(b, budget, s)] for s in SEEDS]
    delta = float(np.mean(cb) - np.mean(ca))
    spread = float(max(max(ca) - min(ca), max(cb) - min(cb)))
    ea = np.mean([edits[(a, budget, s)] for s in SEEDS], axis=0)
    eb = np.mean([edits[(b, budget, s)] for s in SEEDS], axis=0)
    bs = bootstrap(eb, ea, ref, int(rules["bootstrap_n"]), int(rules["bootstrap_seed"]), k_bonf)
    win = delta > spread and delta > float(rules.get("win_min_abs", 0.0)) and (bs["lo"] > 0 or not need_ci)
    robust = bool(win and bs["lo_bonf"] > 0)
    return {"a": a, "b": b, "budget": budget, "cer_a": float(np.mean(ca)), "cer_b": float(np.mean(cb)),
            "delta": delta, "spread": spread, "ci95": [bs["lo"], bs["hi"]],
            "ci_bonf": [bs["lo_bonf"], bs["hi_bonf"]], "win": bool(win), "robust": robust}


def minutes_to(curve: list[tuple[float, float]], thr: float) -> float | None:
    pts = sorted(curve)
    for (m0, c0), (m1, c1) in zip(pts, pts[1:]):
        if c0 <= thr:
            return m0
        if c1 <= thr:
            f = (c0 - thr) / (c0 - c1)
            return float(np.exp(np.log(m0) + f * (np.log(m1) - np.log(m0))))
    return pts[0][0] if pts and pts[0][1] <= thr else None


def verdict(res: dict[str, dict], minutes: dict[str, float], e1a: dict, k_bonf: int,
            shuf: dict[str, float] | None = None) -> dict:
    """res[run] = {"cer", "edits", "ref"} for one decoder. Applies V1, H1-H6, roadmap rule, C1, C2."""
    rules = e1a["rules"]
    cer, edits = {}, {}
    for name, r in res.items():
        p = parse_run(name)
        if p["label_shuffle"]:
            continue
        cer[(p["arm"], p["budget"], p["seed"])] = r["cer"]
        edits[(p["arm"], p["budget"], p["seed"])] = np.asarray(r["edits"], float)
    ref = np.asarray(next(iter(res.values()))["ref"], float)
    table = {a: {b: {"mean": float(np.mean([cer[(a, b, s)] for s in SEEDS])),
                     "seeds": [cer[(a, b, s)] for s in SEEDS],
                     "minutes": float(np.mean([minutes[run_name(a, b, s)] for s in SEEDS]))}
                 for b in BUDGETS} for a in ARMS}
    out: dict = {"table": table}
    best_all = min(table[a]["all"]["mean"] for a in ARMS)
    v1 = best_all <= rules["v1_max_cer_all"]
    out["V1"] = {"best_cer_all": best_all, "pass": bool(v1)}
    hb = e1a["h_budgets"]
    for hid, (a, b) in {"H1": ("E", "T"), "H2": ("E", "R"), "H3": ("T", "R"), "H4": ("E", "S")}.items():
        per = [beats(cer, edits, ref, a, b, bb, rules, k_bonf) for bb in hb]
        wins = sum(p["win"] for p in per)
        status = "pass" if wins >= rules["h_min_wins"] else ("partial" if wins == 1 else "fail")
        out[hid] = {"claim": f"{a} beats {b}", "per_budget": per, "wins": wins,
                    "robust_wins": sum(p["robust"] for p in per), "status": status if v1 else "inconclusive"}
    for hid, (a, b) in {"H5": ("E", "T"), "H6": ("E", "R")}.items():
        p = beats(cer, edits, ref, a, b, "all", rules, k_bonf)
        st = "pass" if p["win"] else "fail"
        out[hid] = {"claim": f"{a} beats {b} at all", "per_budget": [p], "wins": int(p["win"]),
                    "robust_wins": int(p["robust"]), "status": st if v1 else "inconclusive"}
    per = [beats(cer, edits, ref, "E", "T", bb, rules, k_bonf, need_ci=False) for bb in e1a["roadmap_rule_budgets"]]
    out["roadmap_rule"] = {"per_budget": per, "pass": bool(any(p["win"] for p in per))}
    if shuf is not None:
        c1 = []
        for name, sc in sorted(shuf.items()):
            if res[name]["cer"] <= rules["c1_applies_if_cer_below"]:
                c1.append({"run": name, "cer": res[name]["cer"], "shuffled": sc, "pass": sc >= rules["c1_min_cer"]})
        out["C1"] = {"runs": c1, "pass": bool(all(x["pass"] for x in c1)), "n_applicable": len(c1)}
    ls = [n for n in res if parse_run(n)["label_shuffle"]]
    if ls:
        n = ls[0]
        p = parse_run(n)
        normal = cer[(p["arm"], p["budget"], p["seed"])]
        need = max(rules["c2_min_cer"], normal + rules["c2_min_gap"])
        out["C2"] = {"run": n, "cer": res[n]["cer"], "normal_cer": normal, "needed": need,
                     "pass": bool(res[n]["cer"] >= need)}
    curve = {}
    for a in ARMS:
        pts = [(table[a][b]["minutes"], table[a][b]["mean"]) for b in BUDGETS]
        curve[a] = {"points": pts, "minutes_to_cer": minutes_to(pts, rules["curve_cer_threshold"])}
    out["curve"] = {"threshold": rules["curve_cer_threshold"], "arms": curve}
    return out
