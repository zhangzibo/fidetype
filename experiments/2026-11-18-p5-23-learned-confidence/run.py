"""P5-23: learned commit-confidence score vs the p_top1 drop-in guard (pre-registered: plan.md). CPU only.

Stages (one process per stage, background class, 4 threads):
  t15   T15 M4-13: calibrate both guards on val_select (722), decide val_eval (701)   (primary)
  t12   T12 v2: calibrate both guards on the trust pool (480), decide the test sessions (400)   (replication)
  verdict   apply the pre-registered decision rule to the stage results (no data access)

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-18-p5-23-learned-confidence/run.py t15
Per-trial files (with text): C:/Users/zhang/bci-data/derived/p5-23/ only. Repo: aggregates + guard files (no text).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import ctypes  # noqa: E402
import hashlib  # noqa: E402
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
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import (  # noqa: E402
    CorrectionRule,
    controls_from_sheet,
    format_line,
    guarantee_from_sheet,
    safe_wpm,
)

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-23"  # the only place this task writes per-trial files
assert OWN.name == "p5-23"
OUT = HERE / "results"
LOGF = OUT / "run.log"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
B = 2000
NO_BCI_T15 = 4.02  # P14-23 reference (gaze typing, T15 val_eval)
ARMS = ("current", "learned")


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def peak_mb() -> float:
    """Peak working set of this process (Windows), MB; nan elsewhere."""
    try:
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
        return c.PeakWorkingSetSize / 2**20
    except Exception:  # noqa: BLE001
        return math.nan


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def norm(t: str | None) -> str:
    return " ".join((t or "").split())


def auroc(score: np.ndarray, label: np.ndarray) -> float | None:
    """Mann-Whitney AUROC (ties count 1/2)."""
    pos, neg = score[label], score[~label]
    if not len(pos) or not len(neg):
        return None
    allv = np.concatenate([pos, neg])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(len(allv))
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


# ---------------------------------------------------------------------------
# data (read only; the P14-05 / P14-03 loaders)
# ---------------------------------------------------------------------------


def data_t15():
    """M4-13 log-probs: calibration val_select (722), evaluation val_eval (701); B2T '25 word decoder (tune.json)."""
    p1405 = load_module("p1405run", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    p1403 = p1405.load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    cal_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
    held_p = DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
    npz: dict = {}

    def part(path: Path, name: str):
        z = np.load(path)
        keys = p1405.t15_keys(path, sessions, name)
        xs, ts, ph = [], [], []
        for k in keys:
            s, p, i, _ = k.split("|")
            xs.append(z[k].astype(np.float32))
            ts.append(texts[s][p][int(i)])
            ph.append(p1403.ph_symbols(npz, d_in, s, p, int(i)))
        return keys, xs, ts, ph

    _, cx, ct, cph = part(cal_p, "val_select")
    hkeys, hx, ht, _ = part(held_p, "val_eval")
    bt = p1405.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    wkw = {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")}
    dec = bt.Decoders([], wkw)
    fn = p1403.make_decode_fn(dec)
    durs = p1405.t15_durations(hkeys)
    ref = json.loads((DER / "p14-05-safe-wpm" / "decisions-t15-m4-13.json").read_text(encoding="utf-8"))
    info = {"calibration": "val_select (722)", "evaluation": "val_eval (701)", "word_decoder": wkw,
            "timing": "measured trial duration: 20 ms neural bins per val_eval trial (B2T '25)",
            "reference_decisions": "derived/p14-05-safe-wpm/decisions-t15-m4-13.json (P14-05, read only)"}
    return dict(cx=cx, ct=ct, cph=cph, hx=hx, ht=[norm(t) for t in ht], fn=fn, durs=durs, ref=ref, info=info,
                name="p5-23-t15-m4-13", B=p1403.B)


def data_t12():
    """T12 v2 (P14-03 loader): calibration trust pool of fit_a + calibration sessions (480), test sessions (400)."""
    p1403 = load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    (cx, ct, cph), (hx, ht, _), dec, _cpm, split = p1403.data_t12()
    fn = p1403.make_decode_fn(dec)
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    durs = []  # as P14-05 stage t12
    for r in prep["sessions"]:
        if r["role"] != "test":
            continue
        z = np.load(d_in / f"{r['session']}.npz")
        for i, _w in enumerate(texts[r["session"]]["pool"]):
            durs.append(z[f"pool_X{i}"].shape[0] * 0.02)
    assert len(durs) == len(hx) == 400, (len(durs), len(hx))
    ref = json.loads((DER / "p14-03-replay-validation" / "decisions-t12-a0.05.json").read_text(encoding="utf-8"))
    info = {**split, "timing": "measured trial duration: 20 ms neural bins per trial (B2T '24)",
            "reference_decisions": "derived/p14-03-replay-validation/decisions-t12-a0.05.json (P14-03, read only)"}
    return dict(cx=cx, ct=ct, cph=cph, hx=hx, ht=[norm(t) for t in ht], fn=fn, durs=durs, ref=ref, info=info,
                name="p5-23-t12-v2", B=p1403.B)


# ---------------------------------------------------------------------------
# one set
# ---------------------------------------------------------------------------


def split_hashes(n: int) -> dict:
    from fidetype.trust.dropin import _split

    o = np.random.default_rng(SEED).permutation(n)
    a, b, c = _split(n)

    def h(v: list) -> str:
        return hashlib.sha256(json.dumps(sorted(int(x) for x in v)).encode()).hexdigest()[:16]

    return {"n": n, "fit": a, "policy_grid": b, "ltt": c, "score_fit_sha": h(o[:a + b]), "certify_sha": h(o[a + b:])}


def run_arm(d: dict, arm: str) -> dict:
    t0 = time.time()
    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(d["B"].SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=0.08, decode_fn=d["fn"], stream_texts=d["cph"], decoder_name=d["name"],
              modality="intracortical", name=f"{d['name']}-{arm}", seed=SEED)
    if arm == "learned":
        kw["confidence"] = "learned"
    try:
        guard = ft.calibrate(d["cx"], d["ct"], **kw)
    except ft.NullControlError as e:
        log(f"{d['name']} {arm}: REFUSED {[c.to_dict() for c in e.report]}")
        return {"status": "refused", "controls": [c.to_dict() for c in e.report], "message": str(e)}
    log(f"{d['name']} {arm}: calibrated {guard.config_id} in {time.time() - t0:.0f} s; threshold "
        f"{guard.sheet.commit_threshold}; controls {[(c.name, c.n_commit, c.allowed) for c in guard.sheet.controls]}")
    rows = []
    for i, x in enumerate(d["hx"]):
        r = guard.decide(x, utterance_id=f"{d['name']}-{i}")
        nb = guard._last_nb
        top1 = norm(nb.candidates[0].text) if nb is not None and len(nb) else ""
        rows.append({"i": i, "action": r.action, "raw": r.raw_action, "p_top1": r.p_top1, "score": r.commit_score,
                     "guard_risk": r.guard_risk, "text": r.text, "top1": top1, "truth": d["ht"][i]})
    guard.audit_log.clear()
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / f"decisions-{d['name']}-{arm}.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    guard.save(OUT / f"guard-{d['name']}-{arm}.json")
    log(f"{d['name']} {arm}: decided {len(rows)} in {time.time() - t0:.0f} s total; peak {peak_mb():.0f} MB")
    return {"status": "ok", "config_id": guard.config_id, "sheet": guard.sheet.to_dict(), "rows": rows,
            "seconds": round(time.time() - t0, 1)}


def arm_metrics(res: dict, durs: list[float]) -> dict:
    rows, sheet = res["rows"], res["sheet"]
    truths = [r["truth"] for r in rows]
    committed = [r["action"] == "commit" for r in rows]
    correct = [c and norm(r["text"]) == t for c, r, t in zip(committed, rows, truths)]
    blk = safe_wpm(committed, correct, [len(t.split()) for t in truths], [len(t) for t in truths], durs,
                   guarantee=guarantee_from_sheet(sheet), controls=controls_from_sheet(sheet), B=B, seed=SEED,
                   timing="measured trial duration (20 ms neural bins)", metric_version="0.1")
    exact = np.array([r["top1"] == r["truth"] for r in rows])
    score = np.array([r["score"] if r["score"] is not None else r["p_top1"] for r in rows], float)
    ptop = np.array([r["p_top1"] for r in rows], float)
    cm = np.array(committed)
    blk.update({
        "config_id": res["config_id"], "commit_threshold": sheet.get("commit_threshold"),
        "controls_sheet": sheet.get("controls"), "ltt_in_sample": [sheet.get("ltt_commits"),
                                                                     sheet.get("ltt_wrong_commits")],
        "top1_exact": float(exact.mean()), "n_top1_exact": int(exact.sum()),
        "recall_of_exact": float((cm & exact).sum() / max(1, exact.sum())),
        "auroc_commit_score": auroc(score, exact), "auroc_p_top1": auroc(ptop, exact),
        "confidence": sheet.get("confidence"),
    })
    return blk


def paired(rows_a: list[dict], rows_b: list[dict], durs: list[float]) -> dict:
    """Paired trial bootstrap (decisions fixed) of safe WPM v0.1: B - A, and both arms."""
    rule = CorrectionRule()

    def arrays(rows):
        t = [r["truth"] for r in rows]
        cm = np.array([r["action"] == "commit" for r in rows])
        ok = cm & np.array([norm(r["text"]) == x for r, x in zip(rows, t)])
        nw = np.array([len(x.split()) for x in t], float)
        nc = np.array([len(x) for x in t], float)
        return ok, cm & ~ok, nw, rule.penalty(nc)

    oa, wa, nw, pen = arrays(rows_a)
    ob, wb, _, _ = arrays(rows_b)
    ns = np.asarray(durs, float)

    def wpm(ok, wr, w):
        t = (ns * w).sum() + (np.where(wr, pen, 0.0) * w).sum()
        return 60.0 * (np.where(ok, nw, 0.0) * w).sum() / t

    n = len(ns)
    rng = np.random.default_rng(SEED)
    da, db, dd = [], [], []
    for _ in range(B):
        w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        a, b = wpm(oa, wa, w), wpm(ob, wb, w)
        da.append(a)
        db.append(b)
        dd.append(b - a)
    one = np.ones(n)
    pa, pb = wpm(oa, wa, one), wpm(ob, wb, one)
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]  # noqa: E731
    cd = ci(dd)
    return {"current": pa, "learned": pb, "diff": pb - pa, "diff_ci95": cd, "diff_half_width": (cd[1] - cd[0]) / 2,
            "current_ci95": ci(da), "learned_ci95": ci(db), "B": B, "seed": SEED,
            "method": "paired percentile trial bootstrap, decisions fixed (conditional on the calibration)"}


def stage(set_name: str) -> dict:
    t0 = time.time()
    d = data_t15() if set_name == "t15" else data_t12()
    log(f"{set_name}: calibration {len(d['cx'])}, evaluation {len(d['hx'])}; peak {peak_mb():.0f} MB")
    out: dict = {"info": d["info"], "split": split_hashes(len(d["cx"])), "arms": {}}
    res = {}
    for arm in ARMS:
        res[arm] = run_arm(d, arm)
        if res[arm]["status"] != "ok":
            out["arms"][arm] = res[arm]
            continue
        out["arms"][arm] = arm_metrics(res[arm], d["durs"])
        log(f"{set_name} {arm}: {format_line(out['arms'][arm])}")
    if res["current"]["status"] == "ok":
        ref = d["ref"]
        same = sum(a["action"] == r["action"] and norm(a["text"]) == norm(r["text"])
                   for a, r in zip(res["current"]["rows"], ref))
        out["reference_check"] = {"same_action_and_text": same, "n": len(ref)}
        log(f"{set_name}: current arm vs committed reference decisions: {same}/{len(ref)}")
    if all(res[a]["status"] == "ok" for a in ARMS):
        out["paired"] = paired(res["current"]["rows"], res["learned"]["rows"], d["durs"])
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


# ---------------------------------------------------------------------------
# pre-registered decision rule (plan.md)
# ---------------------------------------------------------------------------


def verdict_of(st: dict) -> dict:
    a, b = st["arms"].get("current", {}), st["arms"].get("learned", {})
    if b.get("status") == "refused":
        return {"verdict": "learned refused (a null control failed)"}
    if a.get("status") == "refused":
        return {"verdict": "current refused (not expected)"}
    p = st["paired"]
    safe = b["measured_wrong_commit"] <= ALPHA
    clear_violation = b["measured_wrong_commit_cp95"][0] > ALPHA
    controls_ok = bool((b.get("controls") or {}).get("passed"))
    thr = b.get("commit_threshold")
    feasible = isinstance(thr, (int, float)) and math.isfinite(float(thr))
    d, hw = p["diff"], p["diff_half_width"]
    if not (safe and controls_ok):
        v = "learned fails safety" if not safe else "learned fails a control"
    elif d > hw:
        v = "learned beats current"
    elif d < -hw:
        v = "current beats learned"
    else:
        v = "no clear difference"
    return {"verdict": v, "diff": d, "half_width": hw, "diff_ci95": p["diff_ci95"], "learned_safe": safe,
            "learned_clear_violation": clear_violation, "learned_controls_pass": controls_ok,
            "learned_feasible": feasible, "learned_safe_wpm": b["value"], "current_safe_wpm": a["value"]}


def stage_verdict() -> dict:
    allr = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    out = {}
    for s in ("t15", "t12"):
        st = (allr.get("stages") or {}).get(s, {}).get("result")
        if not st:
            out[s] = {"verdict": "not run"}
            continue
        out[s] = verdict_of(st)
        log(f"verdict {s}: {out[s]}")
    t15 = out.get("t15", {})
    out["p14_23_learned_above_no_bci"] = (isinstance(t15.get("learned_safe_wpm"), float)
                                          and t15["learned_safe_wpm"] > NO_BCI_T15)
    return out


STAGES = {"t15": lambda: stage("t15"), "t12": lambda: stage("t12"), "verdict": stage_verdict}


def main() -> None:
    stages = sys.argv[1:] or ["t15"]
    bad = [s for s in stages if s not in STAGES]
    if bad:
        raise SystemExit(f"unknown stage(s) {bad}; known: {list(STAGES)}")
    OUT.mkdir(exist_ok=True)
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = FT_VERSION
    allr["plan"] = "plan.md (pre-registration)"
    allr.setdefault("stages", {})
    from fidetype.benchmark.scoring import to_jsonable

    for st in stages:
        t0 = time.time()
        log(f"stage {st} start")
        out = STAGES[st]()
        allr["stages"][st] = {"seconds": round(time.time() - t0, 1), "result": out}
        path.write_text(json.dumps(to_jsonable(allr), indent=1, default=str) + "\n", encoding="utf-8")
        log(f"stage {st} done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
