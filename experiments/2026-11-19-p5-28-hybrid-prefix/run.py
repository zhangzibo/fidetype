"""P5-28: hybrid streaming + end-of-trial prefix guard vs the one-commit prefix guard (pre-registered: plan.md).
CPU only. No decoding: it reuses the P5-27 checkpoint views (read only).

Stages (one process per stage, background class, 4 threads):
  dry       check that the P5-27 views and guard files load and match (val_select chunk 0 only; no LTT, no val_eval)
  evaluate  certify lam_end on the joint trial loss (lam_mid fixed), run the null controls, decide val_eval,
            score (safe-wpm/0.2 + the proposed several-commits rule + reading cost), latency, paired bootstrap
  verdict   apply the pre-registered decision rule to results.json (no data access)

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-19-p5-28-hybrid-prefix/run.py evaluate
Per-trial files (with text): C:/Users/zhang/bci-data/derived/p5-28/ only. Repo: aggregates + guard file (no text).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import format_line  # noqa: E402
from fidetype.trust import hybrid_commit as H  # noqa: E402
from fidetype.trust import stream_commit as S  # noqa: E402
from fidetype.trust.commit_score import LearnedCommitScore  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-28"  # the only place this task writes per-trial files
assert OWN.name == "p5-28"
P527_DIR = REPO / "experiments/2026-11-18-p5-27-streaming-prefix"
P527_OWN = DER / "p5-27"  # read only
OUT = HERE / "results"
LOGF = OUT / "run.log"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
LAM_MID = 0.99  # fixed before certification (the P5-27 stream threshold; see plan.md, disclosure)
SENS_MID = (0.99, 0.98, 0.97)  # secondary: Bonferroni over these, delta / 3 each
NI_MARGIN = 0.25  # secondary non-inferiority margin (WPM)
P527_BASE = "tcfg-e9758d5133d07fa6"
P527_STREAM = "scfg-9171461e4f8cf0c2"
P524_THR = 0.94


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.mkdir(exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


P527 = load_module("p527run", P527_DIR / "run.py")  # functions only; its writing functions are not called
STEP, TIMING, NO_BCI, B = P527.STEP, P527.TIMING, P527.NO_BCI, P527.B
peak_mb, norm, split_hashes = P527.peak_mb, P527.norm, P527.split_hashes


def load_guards(d: dict):
    """The P5-27 base guard (P5-24 recipe) and the P5-27 streaming score, read only, with id checks."""
    meta = json.loads((P527_OWN / "base.json").read_text(encoding="utf-8"))
    base = ft.load(P527_DIR / "results/guard-p5-27-base.json", decode_fn=d["fn"])
    sj = json.loads((P527_DIR / "results/guard-p5-27-stream.json").read_text(encoding="utf-8"))
    mid = LearnedCommitScore.from_dict(sj["score"])
    sg = S.StreamingPrefixGuard(base, mid, STEP, frame_timing=TIMING)
    checks = {"base_config_id": base.config_id, "base_equals_p5_24": base.config_id == P527_BASE,
              "views_base_config_id": meta["config_id"], "views_step": meta["step"],
              "views_match_base": meta["config_id"] == base.config_id and meta["step"] == STEP,
              "stream_config_id": sg.config_id, "stream_equals_p5_27": sg.config_id == P527_STREAM == sj["config_id"],
              "base_threshold": float(base.commit_score.threshold)}
    return base, mid, checks


def decide_rows(g: H.HybridPrefixGuard, views: list, truths: list[str], name: str) -> list[dict]:
    rows = []
    for i, vs in enumerate(views):
        r = g.decide_views(vs, utterance_id=f"{name}-{i}")
        assert H.HybridPrefixGuard.check_chain(r.events)
        commits = [{"k_from": e["n_words_committed"] - e["words_added"], "k_to": e["n_words_committed"],
                    "at_end": e["at_end"], "t_s": e["t_s"], "checkpoint": e["checkpoint"], "complete": e["complete"]}
                   for e in r.events]
        rows.append({"action": "commit" if r.n_commits else "no-commit", "text": r.text, "truth": truths[i],
                     "complete": r.complete, "n_words_committed": r.n_words_committed, "n_commits": r.n_commits,
                     "n_conflicts": r.n_conflicts, "commits": commits, "events": r.events})
    return rows


def first_word_latency(rows: list[dict], ends: list, durs: list[float]) -> dict | None:
    """Per committing trial whose first committed word is right: time of the commit that holds word 1 - end
    time of true word 1 (s)."""
    v = []
    for r, e, dur in zip(rows, ends, durs):
        if r["action"] != "commit" or e is None or not r["text"]:
            continue
        if r["text"].split()[0] != r["truth"].split()[0]:
            continue
        cm = (r.get("commits") or [{"at_end": True, "t_s": dur}])[0]
        v.append((dur if cm["at_end"] else cm["t_s"]) - e[0])
    if not v:
        return None
    a = np.asarray(v)
    return {"n": int(a.size), "median": float(np.median(a)), "mean": float(a.mean()),
            "p10": float(np.percentile(a, 10)), "p90": float(np.percentile(a, 90))}


def stage_dry() -> dict:
    t0 = time.time()
    d = P527.load_t15()
    base, mid, checks = load_guards(d)
    with open(P527_OWN / "views" / "cal-000.pkl", "rb") as f:
        vs = pickle.load(f)
    g = H.HybridPrefixGuard(base, mid, STEP, LAM_MID, P524_THR, frame_timing=TIMING)
    t1 = time.time()
    n = sum(g.decide_views(v).n_commits >= 0 for v in vs[:12])
    out = {"checks": checks, "items": int(n), "checkpoints": int(sum(len(v) for v in vs[:12])),
           "s_decide_12": time.time() - t1, "load_s": t1 - t0, "peak_mb": peak_mb()}
    log(f"dry: {out}")
    return out


def stage_evaluate() -> dict:
    t0 = time.time()
    d = P527.load_t15()
    base, mid, checks = load_guards(d)
    log(f"evaluate: checks {checks}; peak {peak_mb():.0f} MB")
    n_cal, n_ev = len(d["cx"]), len(d["hx"])
    cal_v, ev_v = P527.read_views("cal", n_cal), P527.read_views("eval", n_ev)
    names = json.loads((P527_OWN / "controls.json").read_text(encoding="utf-8"))
    null_v = list(zip(names, P527.read_views("null", len(names))))
    log(f"views read ({sum(len(v) for v in cal_v)} cal, {sum(len(v) for v in ev_v)} eval, "
        f"{sum(len(v) for _, v in null_v)} null checkpoints); peak {peak_mb():.0f} MB")
    out: dict = {"info": d["info"], "split": split_hashes(n_cal), "checks": checks, "lam_mid": LAM_MID}
    single = json.loads((P527_OWN / "decisions-single.json").read_text(encoding="utf-8"))
    stream = json.loads((P527_OWN / "decisions-stream.json").read_text(encoding="utf-8"))
    # reference check 1: the end decision alone (lam_mid = inf, lam_end = 0.94) reproduces the single arm
    one = H.HybridPrefixGuard(base, mid, STEP, math.inf, P524_THR, frame_timing=TIMING)
    rec = decide_rows(one, ev_v, d["ht"], "ref")
    same = sum(a["action"] == b["action"] and norm(a["text"] or "") == norm(b["text"] or "")
               for a, b in zip(rec, single))
    out["ref_end_only_vs_single"] = [same, n_ev]
    log(f"reference: end-only decisions vs single arm {same}/{n_ev}")
    # reference check 2: with lam_mid = inf the joint LTT gives the P5-24 threshold 0.94
    g_inf = H.calibrate_hybrid(base, mid, cal_v, d["ct"], step_frames=STEP, lam_mid=math.inf, alpha=ALPHA,
                               delta=DELTA, seed=SEED, frame_timing=TIMING)
    out["ref_lam_end_without_mid"] = g_inf.sheet["lam_end"]
    log(f"reference: lam_end with lam_mid = inf: {g_inf.sheet['lam_end']} (P5-24: {P524_THR})")
    # primary hybrid
    try:
        g = H.calibrate_hybrid(base, mid, cal_v, d["ct"], step_frames=STEP, lam_mid=LAM_MID, alpha=ALPHA,
                               delta=DELTA, seed=SEED, frame_timing=TIMING, control_views=null_v, progress=log)
    except ft.NullControlError as e:
        log(f"hybrid REFUSED: {[c.to_dict() for c in e.report]}")
        out["hybrid"] = {"status": "refused", "controls": [c.to_dict() for c in e.report]}
        return out
    g.save(OUT / "guard-p5-28-hybrid.json")
    out["hybrid_sheet"] = g.sheet
    out["hybrid_config_id"] = g.config_id
    durs = d["durs"]
    hyb = decide_rows(g, ev_v, d["ht"], d["name"].replace("p5-27", "p5-28"))
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "decisions-hybrid.json").write_text(json.dumps(hyb, indent=0), encoding="utf-8")
    sg_ = g.guarantee()
    controls = {"rule": g.sheet["controls_rule"], "results": g.sheet["controls"],
                "passed": all(c["passed"] for c in g.sheet["controls"])}
    from fidetype.benchmark.safe_wpm import controls_from_sheet, guarantee_from_sheet

    bsheet = json.loads((P527_DIR / "results/guard-p5-27-base.json").read_text(encoding="utf-8"))["sheet"]
    s_g, s_c = guarantee_from_sheet(bsheet), controls_from_sheet(bsheet)
    out["hybrid"] = {"v0_2_read": P527.score(hyb, sg_, controls, durs),
                     "v0_2_no_read": P527.score(hyb, sg_, controls, durs, read=False),
                     "v0_1_complete_only": P527.score(hyb, sg_, controls, durs, view="complete")}
    out["single"] = {"v0_2_read": P527.score(single, s_g, s_c, durs),
                     "v0_2_no_read": P527.score(single, s_g, s_c, durs, read=False),
                     "v0_1_complete_only": P527.score(single, s_g, s_c, durs, view="complete")}
    for arm in ("hybrid", "single"):
        for k, v in out[arm].items():
            log(f"{arm} {k}: {format_line(v)}")
    out["paired_v0_2_read"] = P527.paired(single, hyb, durs, True)
    out["paired_v0_2_no_read"] = P527.paired(single, hyb, durs, False)
    out["paired_vs_stream_v0_2_read"] = P527.paired(stream, hyb, durs, True)
    ends = [P527.word_ends(x, ids, len(y.split())) for x, ids, y in zip(d["hx"], d["hid"], d["ht"])]
    out["latency"] = {"word_end": "CTC forced alignment of the true phonemes on the full-trial log-probs",
                      "n_trials_aligned": int(sum(e is not None for e in ends))}
    for nm, rows in (("hybrid", hyb), ("single", single), ("stream", stream)):
        out["latency"][nm] = P527.latency(rows, ends, durs)
        out["latency"][nm]["first_right_word"] = first_word_latency(rows, ends, durs)
    ncm = [r["n_commits"] for r in hyb]
    ext = sum(any(not c["at_end"] for c in r["commits"]) and any(c["at_end"] for c in r["commits"]) for r in hyb)
    out["hybrid_stats"] = {
        "commits_per_trial_hist": {str(k): ncm.count(k) for k in sorted(set(ncm))},
        "trials_with_mid_commit": int(sum(any(not c["at_end"] for c in r["commits"]) for r in hyb)),
        "trials_with_end_commit": int(sum(any(c["at_end"] for c in r["commits"]) for r in hyb)),
        "trials_mid_then_end_extension": int(ext),
        "n_conflicts_total": int(sum(r["n_conflicts"] for r in hyb)),
        "end_conflict_trials": int(sum(r["n_conflicts"] > 0 and r["n_commits"] > 0 for r in hyb)),
        "words_committed": int(sum(r["n_words_committed"] for r in hyb)),
        "complete_final": int(sum(bool(r["complete"]) for r in hyb if r["action"] == "commit")),
        "overlap_with_single": {
            "both": int(sum(a["action"] == "commit" and b["action"] == "commit" for a, b in zip(hyb, single))),
            "hybrid_only": int(sum(a["action"] == "commit" and b["action"] != "commit" for a, b in zip(hyb, single))),
            "single_only": int(sum(a["action"] != "commit" and b["action"] == "commit" for a, b in zip(hyb, single)))}}
    # secondary: Bonferroni over SENS_MID (delta / 3 each), each lam_mid with its own certified lam_end
    sens = {}
    for lm in SENS_MID:
        try:
            gs = H.calibrate_hybrid(base, mid, cal_v, d["ct"], step_frames=STEP, lam_mid=lm, alpha=ALPHA,
                                    delta=DELTA / len(SENS_MID), seed=SEED, frame_timing=TIMING, control_views=null_v)
        except ft.NullControlError as e:
            sens[str(lm)] = {"status": "refused", "controls": [c.to_dict() for c in e.report]}
            continue
        rows = decide_rows(gs, ev_v, d["ht"], f"sens-{lm}")
        ctrl = {"passed": all(c["passed"] for c in gs.sheet["controls"]), "results": gs.sheet["controls"]}
        sv = P527.score(rows, gs.guarantee(), ctrl, durs)
        sens[str(lm)] = {"lam_end": gs.sheet["lam_end"], "ltt_empirical_risk": gs.sheet["ltt_empirical_risk"],
                         "controls": gs.sheet["controls"], "v0_2_read": {k: sv.get(k) for k in (
                             "value", "ci", "status", "n_wrong_commits", "measured_wrong_commit",
                             "measured_wrong_commit_cp95")},
                         "paired_vs_single": P527.paired(single, rows, durs, True)}
        log(f"sensitivity lam_mid {lm}: lam_end {gs.sheet['lam_end']}, value {sv.get('value')}")
    out["sensitivity_bonferroni"] = {"delta_each": DELTA / len(SENS_MID), "arms": sens}
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


def stage_verdict() -> dict:
    allr = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    st = (allr.get("stages") or {}).get("evaluate", {}).get("result")
    if not st:
        return {"verdict": "not run"}
    if st.get("hybrid", {}).get("status") == "refused":
        return {"verdict": "hybrid fails a control"}
    v2 = st["hybrid"]["v0_2_read"]
    pr = st["paired_v0_2_read"]
    safe = v2["measured_wrong_commit"] <= ALPHA
    clear = v2["measured_wrong_commit_cp95"][0] > ALPHA
    ctrl = bool((v2.get("controls") or {}).get("passed"))
    dd, hw = pr["diff"], pr["diff_half_width"]
    if not ctrl:
        v = "hybrid fails a control"
    elif not safe:
        v = "hybrid fails safety"
    elif v2["status"] != "certified":
        v = f"hybrid not certified ({v2['status']})"
    elif dd > hw:
        v = "hybrid beats single"
    elif dd < -hw:
        v = "single beats hybrid"
    else:
        v = "no clear difference"
    lat = st["latency"]
    lh = (lat["hybrid"].get("right_committed_words") or {}).get("median")
    ls = (lat["single"].get("right_committed_words") or {}).get("median")
    v1 = st["hybrid"]["v0_1_complete_only"]
    out = {"verdict": v, "diff": dd, "half_width": hw, "diff_ci95": pr["diff_ci95"], "hybrid_value": v2["value"],
           "hybrid_ci95": pr["b_ci95"], "single_value": st["single"]["v0_2_read"]["value"], "hybrid_safe": safe,
           "hybrid_clear_violation": clear, "hybrid_controls_pass": ctrl,
           "hybrid_wrong": [v2["n_wrong_commits"], v2["n_trials"]], "hybrid_cp95": v2["measured_wrong_commit_cp95"],
           "non_inferior": bool(ctrl and safe and v2["status"] == "certified" and pr["diff_ci95"][0] > -NI_MARGIN),
           "ni_margin": NI_MARGIN, "latency_median_right_words": {"hybrid": lh, "single": ls},
           "latency_lower": (lh is not None and ls is not None and lh < ls),
           "hybrid_above_no_bci": isinstance(v2["value"], float) and v2["value"] > NO_BCI,
           "hybrid_ci_above_no_bci": pr["b_ci95"][0] > NO_BCI, "no_bci": NO_BCI,
           "v0_1_complete_only_value": v1.get("value"),
           "v0_1_above_no_bci": isinstance(v1.get("value"), float) and v1["value"] > NO_BCI}
    log(f"verdict: {out}")
    return out


STAGES = {"evaluate": stage_evaluate, "verdict": stage_verdict, "dry": stage_dry}


def main() -> None:
    stages = sys.argv[1:] or ["dry"]
    bad = [s for s in stages if s not in STAGES]
    if bad:
        raise SystemExit(f"unknown stage(s) {bad}; known: {list(STAGES)}")
    OUT.mkdir(exist_ok=True)
    path = OUT / "results.json"
    from fidetype.benchmark.scoring import to_jsonable

    for st in stages:
        t0 = time.time()
        log(f"stage {st} start")
        out = STAGES[st]()
        if st == "dry":
            continue
        allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        allr["fidetype_version"] = FT_VERSION
        allr["plan"] = "plan.md (pre-registration)"
        allr.setdefault("stages", {})
        allr["stages"][st] = {"seconds": round(time.time() - t0, 1), "result": out}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(to_jsonable(allr), indent=1, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        log(f"stage {st} done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
