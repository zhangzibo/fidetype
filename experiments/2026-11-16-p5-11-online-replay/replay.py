"""P5-11: the P15-04 replay again, but through the drop-in API ``guard.online(...)`` (plan.md). CPU only.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p5-11-online-replay/replay.py t12 t15

Inputs (read only): the P14-03 data loaders and decode_fn (as in P5-02), the P5-02 per-item files
(C:/Users/zhang/bci-data/derived/p5-02-precision/items-*.json) for the item-level check, and the P15-04
summary. Per-item outputs (no text): C:/Users/zhang/bci-data/derived/p5-11-online-replay/ only.
Repo: results/summary.json (aggregates).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

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

import fidetype.trust as ft  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
SRC = DER / "p5-02-precision"  # read only
OWN = DER / "p5-11-online-replay"
assert OWN.name == "p5-11-online-replay"
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOGF = OWN / "replay.log"
P1504 = REPO / "experiments/2026-11-16-p15-04-bandit/results/summary.json"
P502 = REPO / "experiments/2026-11-16-p5-02-precision/results/results.json"

ALPHA, DELTA, ETA, LAM0, ALPHA_P = 0.05, 0.1, 0.05, 0.3, 0.5
N_SEEDS = 20


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_p14_03():
    path = REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py"
    spec = importlib.util.spec_from_file_location("p14_03_run", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def notice_coins(n: int, seed: int) -> np.ndarray:
    """The P15-04 notice coins (same generator and seed)."""
    return np.random.default_rng(50000 + seed).uniform(size=n)


def run(og, hx, ht, *, q: float = 1.0, u: np.ndarray | None = None) -> dict:
    """Decide every held-out item with the online guard, then give the user's final text back.

    q < 1: a wrong commit is noticed with probability q; an unnoticed one is fed back as the committed text
    (the user leaves it), as the P15-04 ``seen_c`` rule.
    """
    n = len(hx)
    com, wrong, score, thr, expl, shown = (np.zeros(n, bool), np.zeros(n, bool), np.zeros(n), np.zeros(n),
                                           np.zeros(n, bool), np.zeros(n, bool))
    for t, (x, truth) in enumerate(zip(hx, ht)):
        thr[t] = og.threshold
        r, tk = og.decide(x)
        com[t] = r.action == "commit"
        score[t] = tk.score
        expl[t] = bool(getattr(tk, "explore", False))
        shown[t] = bool(getattr(tk, "shown", com[t]))
        w = tk.top1 is None or tk.top1 != truth
        wrong[t] = w
        fb = truth
        if com[t] and w and q < 1.0 and u[t] >= q:
            fb = r.text  # not noticed: the user leaves the wrong commit
        og.feedback(tk, fb)
    k = int((com & wrong).sum())
    rep = og.report()
    return {"commits": int(com.sum()), "wrong": k, "rate": k / n, "cp95": clopper_pearson(k, n, 0.95),
            "observed_rate": rep.get("mean_loss", rep.get("realised")), "certificate": rep.get("certificate"),
            "explored": int(expl.sum()), "_com": com, "_wrong": wrong, "_score": score, "_thr": thr}


def strip(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def run_set(name: str, M, ref: dict) -> dict:
    t0 = time.time()
    loader = {"t15": M.data_t15, "t12": M.data_t12}[name]
    (cx, ct, cph), (hx, ht, hph), dec, cpm, split = loader()
    fn = M.make_decode_fn(dec)
    ht = [" ".join(t.split()) for t in ht]
    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=0.08, decode_fn=fn, stream_texts=cph, decoder_name=f"p5-02-{name}",
              modality="intracortical", name=f"p5-02-{name}", seed=0)
    base = ft.calibrate(cx, ct, **kw)  # the P5-02 base guard, rebuilt with the same arguments
    p502 = json.loads(P502.read_text(encoding="utf-8"))[name]["base"]
    out: dict = {"n_held_out": len(hx), "base_config_id": base.config_id, "commit_p": base.sheet.commit_threshold,
                 "base_matches_p5_02": base.config_id == p502["config_id"]}
    log(name, "base", base.config_id, "commit_p", base.sheet.commit_threshold, "matches P5-02",
        out["base_matches_p5_02"], f"{time.time() - t0:.0f}s")
    arms: dict = {}

    # A: aci, no floor, start 0.3 (the P15-04 setting), q 1.0 and q 0.9
    a = run(base.online("aci", floor=False, lam_init=LAM0, eta=ETA), hx, ht)
    items = json.loads((SRC / f"items-{name}.json").read_text(encoding="utf-8"))
    s_ref = np.array([x["p_top1"] if x["can_commit"] else -math.inf for x in items])
    c_ref = np.array([bool(x["wrong"]) for x in items])
    out["item_check"] = {"scores_equal": int((a["_score"] == s_ref).sum()), "wrong_equal": int((a["_wrong"] == c_ref).sum()),
                         "n": len(items), "max_abs_score_diff": float(np.nanmax(np.abs(
                             np.where(np.isfinite(s_ref) & np.isfinite(a["_score"]), a["_score"] - s_ref, 0.0)))),
                         "finite_pattern_equal": bool(np.array_equal(np.isfinite(a["_score"]), np.isfinite(s_ref)))}
    log(name, "item check", out["item_check"])
    arms["A_aci_q1.0"] = a
    arms["A_aci_q0.9"] = run(base.online("aci", floor=False, lam_init=LAM0, eta=ETA), hx, ht, q=0.9,
                             u=notice_coins(len(hx), 0))
    # A-floor: the drop-in default (floor = offline commit_p, start = commit_p)
    arms["A_aci_floor_q1.0"] = run(base.online("aci", eta=ETA), hx, ht)
    log(name, "aci done", {k: strip(v)["commits"] for k, v in arms.items()}, f"{time.time() - t0:.0f}s")
    # B05: bandit, explore 0.05, no floor, start 0.3; N_SEEDS seeds
    b_rows, same = [], 0
    for seed in range(N_SEEDS):
        r = run(base.online("bandit", explore=0.05, floor=False, lam_init=LAM0, eta=ETA, seed=seed), hx, ht)
        same += bool(np.array_equal(r["_com"], a["_com"]))
        b_rows.append(r)
    arms["B05_q1.0"] = b_rows[0]
    out["B05_seeds"] = {"n_seeds": N_SEEDS, "same_commits_as_A": same,
                        "rate_min": min(r["rate"] for r in b_rows), "rate_max": max(r["rate"] for r in b_rows),
                        "commits_median": float(np.median([r["commits"] for r in b_rows])),
                        "explored_median": float(np.median([r["explored"] for r in b_rows]))}
    arms["B05_floor_q1.0"] = run(base.online("bandit", explore=0.05, eta=ETA, seed=0), hx, ht)
    log(name, "bandit done", out["B05_seeds"], f"{time.time() - t0:.0f}s")
    # report only: precision bandit, window with full feedback
    p_rows = [run(base.online("bandit", explore=0.05, target="precision", alpha=ALPHA_P, floor=False,
                              lam_init=LAM0, eta=ETA, seed=s), hx, ht) for s in range(N_SEEDS)]
    arms["P_bandit_q1.0"] = p_rows[0]
    out["P_bandit_seeds"] = {"commits_median": float(np.median([r["commits"] for r in p_rows])),
                             "error_among_commits_median": float(np.median(
                                 [r["wrong"] / r["commits"] if r["commits"] else math.nan for r in p_rows]))}
    arms["C_window_full"] = run(base.online("window", floor=False, lam_init=LAM0, window=200), hx, ht)
    np.savez_compressed(OWN / f"per-item-{name}.npz", **{f"{k}{f}": v[f] for k, v in arms.items()
                                                          for f in ("_com", "_wrong", "_thr")})
    out["arms"] = {k: strip(v) for k, v in arms.items()}
    # comparison with P15-04
    to = ref["sets"][name]["time_order"]
    cmp = {}
    for k_ours, k_ref in (("A_aci_q1.0", "A_aci_q1.0"), ("A_aci_q0.9", "A_aci_q0.9"), ("C_window_full", "C_window_full")):
        o, r = out["arms"][k_ours], to[k_ref]
        cmp[k_ours] = {"p15_04": [r["commits"], r["wrong"]], "online_api": [o["commits"], o["wrong"]],
                       "equal": [r["commits"], r["wrong"]] == [o["commits"], o["wrong"]]}
    r = to["B05_q1.0"]
    o = out["arms"]["B05_q1.0"]
    cmp["B05_q1.0"] = {"p15_04": [r["commits_median"], round(r["true_rate_median"] * len(hx))],
                       "online_api": [o["commits"], o["wrong"]], "equal": [int(r["commits_median"]),
                       round(r["true_rate_median"] * len(hx))] == [o["commits"], o["wrong"]],
                       "p15_04_explored_median": r["explored_median"], "online_api_explored_median":
                       out["B05_seeds"]["explored_median"]}
    r = to["P_bandit_q1.0"]
    cmp["P_bandit_q1.0"] = {"p15_04_commits_median": r["commits_median"],
                            "online_api_commits_median": out["P_bandit_seeds"]["commits_median"]}
    out["compare_p15_04"] = cmp
    out["seconds"] = round(time.time() - t0, 1)
    log(name, "compare", json.dumps(cmp))
    return out


def main() -> None:
    sets = sys.argv[1:] or ["t12", "t15"]
    M = load_p14_03()
    ref = json.loads(P1504.read_text(encoding="utf-8"))
    path = OUT / "summary.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.update({"plan": "experiments/2026-11-16-p5-11-online-replay/plan.md", "alpha": ALPHA, "eta": ETA,
                 "lam_init": LAM0, "n_seeds": N_SEEDS, "fidetype_version": ft.__version__
                 if hasattr(ft, "__version__") else None})
    allr.setdefault("sets", {})
    for st in sets:
        log("stage", st, "start")
        allr["sets"][st] = run_set(st, M, ref)
        txt = json.dumps(allr, indent=1, default=float)
        path.write_text(txt, encoding="utf-8")
        (OWN / "summary.json").write_text(txt, encoding="utf-8")
        log("stage", st, "done")


if __name__ == "__main__":
    main()
