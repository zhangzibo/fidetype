"""P5-24: certified word-prefix commits vs the sentence-level learned guard (pre-registered: plan.md). CPU only.

Stages (one process per stage, background class, 4 threads):
  t15   T15 M4-13: calibrate three guards on val_select (722), decide val_eval (701)   (primary)
  t12   T12 v2: calibrate three guards on the trust pool (480), decide the test sessions (400)   (replication)
  verdict   apply the pre-registered decision rule to the stage results (no data access)

Arms: current (p_top1, P14-03 recipe), sentence (confidence="learned", P5-23), prefix (confidence="learned",
commit_unit="prefix", P5-24). Same data, split, seed, alpha, delta and controls.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-18-p5-24-prefix-commits/run.py t15
Per-trial files (with text): C:/Users/zhang/bci-data/derived/p5-24/ only. Repo: aggregates + guard files (no text).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import ctypes  # noqa: E402
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
    prefix_outcome,
    safe_wpm,
)

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-24"  # the only place this task writes per-trial files
assert OWN.name == "p5-24"
OUT = HERE / "results"
LOGF = OUT / "run.log"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
B = 2000
NO_BCI = {"t15": 4.02, "t12": 4.11}  # P14-05 / P5-23 no-BCI references (gaze typing)
ARMS = ("current", "sentence", "prefix")
FRAME_S = 0.08  # log-prob frame period (4 x 20 ms bins), as in calibrate(frame_period=0.08)


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def peak_mb() -> float:
    """Peak working set of this process (Windows, K32GetProcessMemoryInfo), MB; nan elsewhere."""
    try:
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return math.nan
        return c.PeakWorkingSetSize / 2**20
    except Exception:  # noqa: BLE001
        return math.nan


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


P523 = load_module("p523run", REPO / "experiments/2026-11-18-p5-23-learned-confidence/run.py")
norm, auroc, split_hashes = P523.norm, P523.auroc, P523.split_hashes


def speech_span_s(lp: np.ndarray) -> float:
    """Active-speech span of one trial from our CTC output: first to last frame whose argmax is not blank (0)."""
    nb = np.flatnonzero(np.asarray(lp).argmax(axis=1) != 0)
    return float((nb[-1] - nb[0] + 1) * FRAME_S) if nb.size else 0.0


def load_set(set_name: str) -> dict:
    d = P523.data_t15() if set_name == "t15" else P523.data_t12()
    d["name"] = d["name"].replace("p5-23", "p5-24")
    d["speech"] = [speech_span_s(x) for x in d["hx"]]
    ref523 = DER / "p5-23" / f"decisions-p5-23-{'t15-m4-13' if set_name == 't15' else 't12-v2'}-learned.json"
    d["ref_sentence"] = json.loads(ref523.read_text(encoding="utf-8"))
    d["info"] = dict(d["info"], reference_sentence=f"derived/p5-23/{ref523.name} (P5-23 learned arm, read only)",
                     speech_time="active-speech span of our CTC output (first to last non-blank argmax frame, "
                                 f"{FRAME_S:g} s frames); secondary only")
    return d


# ---------------------------------------------------------------------------
# one arm
# ---------------------------------------------------------------------------


def run_arm(d: dict, arm: str) -> dict:
    t0 = time.time()
    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(d["B"].SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=FRAME_S, decode_fn=d["fn"], stream_texts=d["cph"], decoder_name=d["name"],
              modality="intracortical", name=f"{d['name']}-{arm}", seed=SEED)
    if arm in ("sentence", "prefix"):
        kw["confidence"] = "learned"
    if arm == "prefix":
        kw["commit_unit"] = "prefix"
    try:
        guard = ft.calibrate(d["cx"], d["ct"], **kw)
    except ft.NullControlError as e:
        log(f"{d['name']} {arm}: REFUSED {[c.to_dict() for c in e.report]}")
        return {"status": "refused", "controls": [c.to_dict() for c in e.report], "message": str(e)}
    log(f"{d['name']} {arm}: calibrated {guard.config_id} in {time.time() - t0:.0f} s; threshold "
        f"{guard.sheet.commit_threshold}; controls {[(c.name, c.n_commit, c.allowed) for c in guard.sheet.controls]}; "
        f"peak {peak_mb():.0f} MB")
    rows = []
    for i, x in enumerate(d["hx"]):
        r = guard.decide(x, utterance_id=f"{d['name']}-{i}")
        nb = guard._last_nb
        top1 = norm(nb.candidates[0].text) if nb is not None and len(nb) else ""
        rows.append({"i": i, "action": r.action, "raw": r.raw_action, "p_top1": r.p_top1, "score": r.commit_score,
                     "guard_risk": r.guard_risk, "text": r.text, "top1": top1, "truth": d["ht"][i],
                     "complete": r.complete, "n_words_committed": r.n_words_committed,
                     "n_words_top1": r.event.get("n_words_top1", len(top1.split()))})
    guard.audit_log.clear()
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / f"decisions-{d['name']}-{arm}.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    guard.save(OUT / f"guard-{d['name']}-{arm}.json")
    log(f"{d['name']} {arm}: decided {len(rows)} in {time.time() - t0:.0f} s total; peak {peak_mb():.0f} MB")
    return {"status": "ok", "config_id": guard.config_id, "sheet": guard.sheet.to_dict(), "rows": rows,
            "seconds": round(time.time() - t0, 1)}


def trial_arrays(rows: list[dict], version: str, view: str = "all") -> dict:
    """Per-trial arrays of one arm for one metric version.

    ``version="0.1"``: a commit is right only if its text is the truth (v0.1 rule). ``view="complete"``: only
    complete commits count as commits (partial prefix commits count as not committed). ``version="0.2"``: the
    proposed prefix rule (prefix_outcome).
    """
    t = [r["truth"] for r in rows]
    cm, ok, kw, comp, pc = [], [], [], [], []
    for r, y in zip(rows, t):
        c = r["action"] == "commit"
        full = True if r.get("complete") is None else bool(r["complete"])
        if c and view == "complete" and not full:
            c = False
        cm.append(c)
        if not c:
            ok.append(False)
            kw.append(math.nan)
            comp.append(True)
            pc.append(math.nan)
            continue
        if version == "0.1":
            ok.append(norm(r["text"]) == y)
            kw.append(math.nan)
            comp.append(True)
            pc.append(math.nan)
        else:
            po = prefix_outcome(r["text"], y, full)
            ok.append(po["correct"])
            kw.append(po["committed_words"])
            comp.append(po["complete"])
            pc.append(po["penalty_chars"])
    return {"committed": cm, "correct": ok, "n_words": [len(y.split()) for y in t], "n_chars": [len(y) for y in t],
            "committed_words": kw, "complete": comp, "penalty_chars": pc}


def score(rows: list[dict], sheet: dict, durs: list[float], version: str, view: str = "all",
          speech: list[float] | None = None) -> dict:
    a = trial_arrays(rows, version, view)
    kw = dict(guarantee=guarantee_from_sheet(sheet), controls=controls_from_sheet(sheet), B=B, seed=SEED,
              timing="measured trial duration (20 ms neural bins)")
    if version == "0.1":
        return safe_wpm(a["committed"], a["correct"], a["n_words"], a["n_chars"], durs, metric_version="0.1", **kw)
    return safe_wpm(a["committed"], a["correct"], a["n_words"], a["n_chars"], durs, metric_version="0.2",
                    committed_words=a["committed_words"], complete=a["complete"], penalty_chars=a["penalty_chars"],
                    speech_s=speech, speech_timing="active-speech span of our CTC output (secondary)",
                    read_s_per_commit=0.0, read_s_per_word=0.0, **kw)  # v0.2 as proposed then (no reading cost)


def credit_arrays(rows: list[dict], version: str, view: str = "all"):
    """(credit words, wrong, penalty seconds) per trial, for the paired bootstrap."""
    a = trial_arrays(rows, version, view)
    rule = CorrectionRule()
    cm = np.array(a["committed"])
    ok = cm & np.array(a["correct"])
    nw = np.array(a["n_words"], float)
    nc = np.array(a["n_chars"], float)
    comp = np.array(a["complete"], bool)
    kw = np.nan_to_num(np.array(a["committed_words"], float))
    pc = np.nan_to_num(np.array(a["penalty_chars"], float))
    partial = cm & ~comp
    credit = np.where(ok, np.where(partial, kw, nw), 0.0)
    pen = rule.penalty(np.where(partial, pc, nc))
    return credit, cm & ~ok, pen


def paired(ra: list[dict], rb: list[dict], durs: list[float], version: str, view_a: str = "all",
           view_b: str = "all") -> dict:
    """Paired percentile trial bootstrap (decisions fixed) of safe WPM: B - A, and both arms."""
    ca, wa, pa = credit_arrays(ra, version, view_a)
    cb, wb, pb = credit_arrays(rb, version, view_b)
    ns = np.asarray(durs, float)

    def wpm(c, wr, pen, w):
        return 60.0 * (c * w).sum() / ((ns * w).sum() + (np.where(wr, pen, 0.0) * w).sum())

    n = len(ns)
    rng = np.random.default_rng(SEED)
    da, db, dd = [], [], []
    for _ in range(B):
        w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        x, y = wpm(ca, wa, pa, w), wpm(cb, wb, pb, w)
        da.append(x)
        db.append(y)
        dd.append(y - x)
    one = np.ones(n)
    va, vb = wpm(ca, wa, pa, one), wpm(cb, wb, pb, one)
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]  # noqa: E731
    cd = ci(dd)
    return {"a": va, "b": vb, "diff": vb - va, "diff_ci95": cd, "diff_half_width": (cd[1] - cd[0]) / 2,
            "a_ci95": ci(da), "b_ci95": ci(db), "B": B, "seed": SEED, "version": version,
            "method": "paired percentile trial bootstrap, decisions fixed (conditional on the calibration)"}


def arm_metrics(res: dict, d: dict, arm: str) -> dict:
    rows, sheet, durs = res["rows"], res["sheet"], d["durs"]
    out = {"config_id": res["config_id"], "commit_threshold": sheet.get("commit_threshold"),
           "controls_sheet": sheet.get("controls"), "ltt_in_sample": [sheet.get("ltt_commits"),
                                                                        sheet.get("ltt_wrong_commits")],
           "confidence": sheet.get("confidence"), "seconds": res["seconds"]}
    out["v0_2"] = score(rows, sheet, durs, "0.2", speech=d["speech"])
    out["v0_1"] = score(rows, sheet, durs, "0.1")  # literal v0.1: a partial prefix commit is a wrong commit
    if arm == "prefix":
        out["v0_1_complete_only"] = score(rows, sheet, durs, "0.1", view="complete")
    exact = np.array([r["top1"] == r["truth"] for r in rows])
    cm = np.array([r["action"] == "commit" for r in rows])
    sc = np.array([r["score"] if r["score"] is not None else r["p_top1"] for r in rows], float)
    out.update({"top1_exact": float(exact.mean()), "n_top1_exact": int(exact.sum()),
                "recall_of_exact": float((cm & exact).sum() / max(1, exact.sum())),
                "auroc_p_top1": auroc(np.array([r["p_top1"] for r in rows], float), exact)})
    if arm != "prefix":
        out["auroc_commit_score"] = auroc(sc, exact)
    else:
        ks = [r["n_words_committed"] for r in rows if r["action"] == "commit"]
        right_prefix_words = 0
        for r in rows:  # words in the right prefixes of all top-1 texts (the ceiling of a perfect prefix guard)
            tw, yw = r["top1"].split(), r["truth"].split()
            j = 0
            while j < min(len(tw), len(yw)) and tw[j] == yw[j]:
                j += 1
            right_prefix_words += j
        out.update({"commit_words_hist": {str(k): ks.count(k) for k in sorted(set(ks))},
                    "mean_words_per_commit": float(np.mean(ks)) if ks else None,
                    "n_complete_commits": sum(1 for r in rows if r["action"] == "commit" and r["complete"]),
                    "words_in_right_top1_prefixes": right_prefix_words})
    return out


def stage(set_name: str) -> dict:
    t0 = time.time()
    d = load_set(set_name)
    log(f"{set_name}: calibration {len(d['cx'])}, evaluation {len(d['hx'])}; mean speech span "
        f"{np.mean(d['speech']):.2f} s, mean trial {np.mean(d['durs']):.2f} s; peak {peak_mb():.0f} MB")
    out: dict = {"info": d["info"], "split": split_hashes(len(d["cx"])), "arms": {}}
    res = {}
    for arm in ARMS:
        res[arm] = run_arm(d, arm)
        if res[arm]["status"] != "ok":
            out["arms"][arm] = res[arm]
            continue
        out["arms"][arm] = arm_metrics(res[arm], d, arm)
        log(f"{set_name} {arm} v0.1: {format_line(out['arms'][arm]['v0_1'])}")
        log(f"{set_name} {arm} v0.2: {format_line(out['arms'][arm]['v0_2'])}")
    checks = {}
    for arm, ref in (("current", d["ref"]), ("sentence", d["ref_sentence"])):
        if res[arm]["status"] == "ok":
            same = sum(a["action"] == r["action"] and norm(a["text"]) == norm(r["text"])
                       for a, r in zip(res[arm]["rows"], ref))
            checks[arm] = {"same_action_and_text": same, "n": len(ref)}
            log(f"{set_name}: {arm} arm vs committed reference decisions: {same}/{len(ref)}")
    out["reference_check"] = checks
    ok = {a for a in ARMS if res[a]["status"] == "ok"}
    if {"sentence", "prefix"} <= ok:
        out["paired_v0_2"] = paired(res["sentence"]["rows"], res["prefix"]["rows"], d["durs"], "0.2")
        out["paired_v0_1_complete_only"] = paired(res["sentence"]["rows"], res["prefix"]["rows"], d["durs"], "0.1",
                                                  view_b="complete")
    if {"current", "prefix"} <= ok:
        out["paired_v0_2_vs_current"] = paired(res["current"]["rows"], res["prefix"]["rows"], d["durs"], "0.2")
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


# ---------------------------------------------------------------------------
# pre-registered decision rule (plan.md)
# ---------------------------------------------------------------------------


def verdict_of(st: dict, set_name: str) -> dict:
    s, p = st["arms"].get("sentence", {}), st["arms"].get("prefix", {})
    if p.get("status") == "refused":
        return {"verdict": "prefix refused (a null control failed)"}
    if s.get("status") == "refused":
        return {"verdict": "sentence refused (not expected)"}
    v2 = p["v0_2"]
    pr = st["paired_v0_2"]
    safe = v2["measured_wrong_commit"] <= ALPHA
    clear_violation = v2["measured_wrong_commit_cp95"][0] > ALPHA
    controls_ok = bool((v2.get("controls") or {}).get("passed"))
    d, hw = pr["diff"], pr["diff_half_width"]
    if not (safe and controls_ok):
        v = "prefix fails safety" if not safe else "prefix fails a control"
    elif v2["status"] != "certified":
        v = f"prefix not certified ({v2['status']})"
    elif d > hw:
        v = "prefix beats sentence"
    elif d < -hw:
        v = "sentence beats prefix"
    else:
        v = "no clear difference"
    ref = NO_BCI[set_name]
    c1 = p.get("v0_1_complete_only", {})
    return {"verdict": v, "diff_v0_2": d, "half_width": hw, "diff_ci95": pr["diff_ci95"],
            "prefix_safe": safe, "prefix_clear_violation": clear_violation, "prefix_controls_pass": controls_ok,
            "prefix_v0_2": v2["value"], "prefix_v0_2_ci95": pr["b_ci95"], "sentence_v0_2": s["v0_2"]["value"],
            "current_v0_2": st["arms"].get("current", {}).get("v0_2", {}).get("value"),
            "prefix_v0_1_literal": p["v0_1"]["value"], "prefix_v0_1_literal_status": p["v0_1"]["status"],
            "prefix_v0_1_complete_only": c1.get("value"), "prefix_v0_1_complete_only_status": c1.get("status"),
            "sentence_v0_1": s["v0_1"]["value"], "no_bci": ref,
            "prefix_v0_2_above_no_bci": isinstance(v2["value"], float) and v2["value"] > ref,
            "prefix_v0_2_ci_above_no_bci": pr["b_ci95"][0] > ref,
            "any_v0_1_above_no_bci": any(isinstance(x, float) and x > ref for x in
                                         (c1.get("value"), s["v0_1"]["value"]))}


def stage_verdict() -> dict:
    allr = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    out = {}
    for s in ("t15", "t12"):
        st = (allr.get("stages") or {}).get(s, {}).get("result")
        if not st:
            out[s] = {"verdict": "not run"}
            continue
        out[s] = verdict_of(st, s)
        log(f"verdict {s}: {out[s]}")
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
