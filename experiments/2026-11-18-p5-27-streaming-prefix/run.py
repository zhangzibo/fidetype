"""P5-27: streaming word-by-word prefix commits within one trial vs the one-commit prefix guard (pre-registered:
plan.md). CPU only.

Stages (one process per stage, background class, 4 threads):
  views     calibrate the base prefix guard (the P5-24 recipe) on val_select (722); decide val_eval (701) with it
            (the one-commit arm); decode every checkpoint (every STEP frames + the end) of all val_select,
            val_eval and null-control inputs. Resumable: chunk files in derived/p5-27/views/.   (long)
  evaluate  fit + certify the streaming score on val_select, run the streaming null controls, decide val_eval,
            score (safe-wpm/0.2 + the proposed several-commits rule + reading cost), latency, paired bootstrap
  verdict   apply the pre-registered decision rule to results.json (no data access)
  dry       pipeline + timing check on 12 val_select items only (scratch output; no evaluation data)

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-18-p5-27-streaming-prefix/run.py views
Per-trial files (with text): C:/Users/zhang/bci-data/derived/p5-27/ only. Repo: aggregates + guard files (no text).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import gc  # noqa: E402
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
from fidetype.benchmark.safe_wpm import (CorrectionRule, format_line, prefix_outcome,  # noqa: E402
                                         safe_wpm)
from fidetype.trust import stream_commit as S  # noqa: E402
from fidetype.trust.commit_score import monotone_prefix_scores  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-27"  # the only place this task writes per-trial files
assert OWN.name == "p5-27"
VIEWS = OWN / "views"
OUT = HERE / "results"
LOGF = OUT / "run.log"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
B = 2000
NO_BCI = 4.02  # P14-05 T15 no-BCI reference (gaze typing)
FRAME_S = 0.08
STEP = 6  # checkpoint step in decoder frames (0.48 s)
TIMING = {"patch": 14, "stride": 4, "bin_s": 0.02}  # M4-13: patch 14, stride 4, 20 ms bins (causal, L 0)
READ_C, READ_W = 0.5, 0.3  # P14-28 recommended reading cost (aac-gaze-v1): 0.5 s per commit + 0.3 s per word
CONTROL_SEED = (0, 527)
N_NULL = 300
CHUNK = 50
P524_DEC = DER / "p5-24" / "decisions-p5-24-t15-m4-13-prefix.json"
P524_CONFIG = "tcfg-e9758d5133d07fa6"


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


P524 = load_module("p524run", REPO / "experiments/2026-11-18-p5-24-prefix-commits/run.py")
peak_mb, norm, split_hashes = P524.peak_mb, P524.norm, P524.split_hashes


def make_decode_fn(holder: dict):
    """The P14-03 word decoder behind a resettable cache (same qualified name, so the same config id)."""

    def phoneme_words_decoder(log_probs: np.ndarray) -> list[dict]:
        return holder["fn"](log_probs)

    return phoneme_words_decoder


def load_t15() -> dict:
    """As P5-23 / P5-24 data_t15, plus the val_eval keys and phoneme ids (latency), with a resettable cache."""
    p1405 = load_module("p1405run", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    p1403 = p1405.load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    cal_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
    held_p = DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
    npz: dict = {}

    def part(path: Path, name: str, ids: bool):
        z = np.load(path)
        keys = p1405.t15_keys(path, sessions, name)
        xs, ts, ph, pid = [], [], [], []
        for k in keys:
            s, p, i, _ = k.split("|")
            xs.append(z[k].astype(np.float32))
            ts.append(texts[s][p][int(i)])
            ph.append(p1403.ph_symbols(npz, d_in, s, p, int(i)))
            if ids:
                pid.append([int(v) for v in npz[s][f"{p}_ph{int(i)}"]])
        return keys, xs, ts, ph, pid

    _, cx, ct, cph, _ = part(cal_p, "val_select", False)
    hkeys, hx, ht, _, hid = part(held_p, "val_eval", True)
    npz.clear()
    bt = p1405.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    wkw = {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")}
    dec = bt.Decoders([], wkw)
    holder = {"fn": p1403.make_decode_fn(dec), "make": lambda: p1403.make_decode_fn(dec)}
    durs = p1405.t15_durations(hkeys)
    info = {"calibration": "val_select (722)", "evaluation": "val_eval (701)", "word_decoder": wkw,
            "timing": "measured trial duration: 20 ms neural bins per val_eval trial (B2T '25)",
            "streaming": f"prefix truncations of the causal M4-13 log-probs, every {STEP} frames + the end"}
    return dict(cx=cx, ct=[norm(t) for t in ct], cph=cph, hx=hx, ht=[norm(t) for t in ht], hid=hid, hkeys=hkeys,
                holder=holder, fn=make_decode_fn(holder), durs=durs, info=info, name="p5-27-t15-m4-13", B=p1403.B)


def reset(d: dict) -> None:
    d["holder"]["fn"] = d["holder"]["make"]()


def calibrate_base(d: dict, cx=None, ct=None, cph=None):
    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(d["B"].SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=FRAME_S, decode_fn=d["fn"], stream_texts=d["cph"] if cph is None else cph,
              decoder_name="p5-24-t15-m4-13", modality="intracortical", name="p5-24-t15-m4-13-prefix", seed=SEED,
              confidence="learned", commit_unit="prefix")
    return ft.calibrate(d["cx"] if cx is None else cx, d["ct"] if ct is None else ct, **kw)


# ---------------------------------------------------------------------------
# views (decodes of every checkpoint)
# ---------------------------------------------------------------------------


def chunk_path(part: str, j: int) -> Path:
    return VIEWS / f"{part}-{j:03d}.pkl"


def compute_views(d: dict, base, part: str, xs: list, scales: list | None = None) -> None:
    VIEWS.mkdir(parents=True, exist_ok=True)
    n_chunks = (len(xs) + CHUNK - 1) // CHUNK
    for j in range(n_chunks):
        p = chunk_path(part, j)
        if p.exists():
            continue
        t0 = time.time()
        out = []
        for i in range(j * CHUNK, min(len(xs), (j + 1) * CHUNK)):
            out.append(S.stream_views(base, xs[i], STEP, None if scales is None else scales[i]))
            reset(d)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(out, f, protocol=4)
        os.replace(tmp, p)
        nv = sum(len(v) for v in out)
        log(f"views {part} chunk {j + 1}/{n_chunks}: {len(out)} items, {nv} checkpoints in {time.time() - t0:.0f} s; "
            f"peak {peak_mb():.0f} MB")
        del out
        gc.collect()


def read_views(part: str, n: int) -> list:
    out = []
    for j in range((n + CHUNK - 1) // CHUNK):
        with open(chunk_path(part, j), "rb") as f:
            out += pickle.load(f)
    assert len(out) == n, (part, len(out), n)
    return out


def stage_views() -> dict:
    t0 = time.time()
    d = load_t15()
    log(f"views: calibration {len(d['cx'])}, evaluation {len(d['hx'])}; peak {peak_mb():.0f} MB")
    base = calibrate_base(d)
    reset(d)
    log(f"base guard {base.config_id} (P5-24 prefix guard: {P524_CONFIG}); threshold {base.sheet.commit_threshold}; "
        f"{time.time() - t0:.0f} s; peak {peak_mb():.0f} MB")
    OWN.mkdir(parents=True, exist_ok=True)
    meta_p = OWN / "base.json"
    if meta_p.exists():
        old = json.loads(meta_p.read_text(encoding="utf-8"))
        assert old["config_id"] == base.config_id, "base guard changed between runs: views not reusable"
    meta_p.write_text(json.dumps({"config_id": base.config_id, "step": STEP}), encoding="utf-8")
    base.save(OUT / "guard-p5-27-base.json")
    # the one-commit arm (the P5-24 prefix guard) on val_eval
    single_p = OWN / "decisions-single.json"
    if not single_p.exists():
        rows = []
        for i, x in enumerate(d["hx"]):
            r = base._decide_quiet(x)
            rows.append({"i": i, "action": r.action, "text": r.text, "truth": d["ht"][i], "complete": r.complete,
                         "n_words_committed": r.n_words_committed})
            reset(d)
        single_p.write_text(json.dumps(rows, indent=0), encoding="utf-8")
    rows = json.loads(single_p.read_text(encoding="utf-8"))
    ref = json.loads(P524_DEC.read_text(encoding="utf-8"))
    same = sum(a["action"] == r["action"] and norm(a["text"]) == norm(r["text"]) for a, r in zip(rows, ref))
    log(f"one-commit arm vs P5-24 prefix decisions: {same}/{len(ref)}")
    compute_views(d, base, "cal", d["cx"])
    compute_views(d, base, "eval", d["hx"])
    nulls = S.null_control_inputs(base, d["cx"], N_NULL, CONTROL_SEED)
    (OWN / "controls.json").write_text(json.dumps([nm for nm, _, _ in nulls]), encoding="utf-8")
    compute_views(d, base, "null", [x for _, x, _ in nulls], [sc for _, _, sc in nulls])
    return {"base_config_id": base.config_id, "p5_24_config_id": P524_CONFIG,
            "base_equals_p5_24": base.config_id == P524_CONFIG, "single_vs_p5_24": [same, len(ref)],
            "seconds": round(time.time() - t0, 1), "peak_mb": round(peak_mb(), 1), "step_frames": STEP,
            "split": split_hashes(len(d["cx"]))}


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------


def word_ends(lp: np.ndarray, ids: list[int], n_words: int) -> list[float] | None:
    """End time (s) of each true word: CTC forced alignment of the true phonemes (SIL = 1 separates words) on
    the full-trial log-probs; a word ends when its last phoneme's last aligned frame exists."""
    from fidetype.lm.beam import ctc_forced_align

    lab = [i for i in ids if i != 0]
    while lab and lab[-1] == 1:
        lab.pop()
    while lab and lab[0] == 1:
        lab.pop(0)
    spans = ctc_forced_align(lp, lab, blank=0)
    if spans is None:
        return None
    ends, last = [], None
    for tok, (_, b) in zip(lab, spans):
        if tok == 1:
            if last is not None:
                ends.append(last)
            last = None
        else:
            last = b
    if last is not None:
        ends.append(last)
    if len(ends) != n_words:
        return None
    return [S.checkpoint_time_s(f + 1, **TIMING) for f in ends]


def trial_arrays(rows: list[dict]) -> dict:
    """Per-trial arrays of one arm (the final committed text of each trial; n_commits commit events)."""
    cm, ok, kw, comp, pc, nc = [], [], [], [], [], []
    for r in rows:
        y = r["truth"]
        c = r["action"] == "commit"
        cm.append(c)
        if not c:
            ok.append(False)
            kw.append(math.nan)
            comp.append(True)
            pc.append(math.nan)
            nc.append(0)
            continue
        po = prefix_outcome(r["text"], y, bool(r["complete"]))
        ok.append(po["correct"])
        kw.append(po["committed_words"])
        comp.append(po["complete"])
        pc.append(po["penalty_chars"])
        nc.append(int(r.get("n_commits", 1)))
    t = [r["truth"] for r in rows]
    return {"committed": cm, "correct": ok, "n_words": [len(y.split()) for y in t], "n_chars": [len(y) for y in t],
            "committed_words": kw, "complete": comp, "penalty_chars": pc, "n_commits": nc}


def score(rows: list[dict], guarantee: dict, controls: dict | None, durs: list[float], read: bool = True,
          view: str = "all") -> dict:
    a = trial_arrays(rows)
    if view == "complete":  # v0.1 complete-only: a trial counts as committed only if its final commit is complete
        keep = [c and bool(f) for c, f in zip(a["committed"], a["complete"])]
        y = [r["truth"] for r in rows]
        return safe_wpm(keep, [k and norm(r["text"]) == t for k, r, t in zip(keep, rows, y)], a["n_words"],
                        a["n_chars"], durs, guarantee=dict(guarantee, risk="wrong-commit"), controls=controls, B=B,
                        seed=SEED, timing="measured trial duration (20 ms neural bins)")
    kw = dict(read_s_per_commit=READ_C, read_s_per_word=READ_W) if read else {}
    return safe_wpm(a["committed"], a["correct"], a["n_words"], a["n_chars"], durs, guarantee=guarantee,
                    controls=controls, B=B, seed=SEED, timing="measured trial duration (20 ms neural bins)",
                    metric_version="0.2", committed_words=a["committed_words"], complete=a["complete"],
                    penalty_chars=a["penalty_chars"], n_commits=a["n_commits"], **kw)


def credit_arrays(rows: list[dict], read: bool = True):
    a = trial_arrays(rows)
    rule = CorrectionRule()
    cm = np.array(a["committed"])
    ok = cm & np.array(a["correct"])
    nw = np.array(a["n_words"], float)
    nc = np.array(a["n_chars"], float)
    comp = np.array(a["complete"], bool)
    kw = np.nan_to_num(np.array(a["committed_words"], float))
    pc = np.nan_to_num(np.array(a["penalty_chars"], float))
    ncm = np.array(a["n_commits"], float)
    partial = cm & ~comp
    credit = np.where(ok, np.where(partial, kw, nw), 0.0)
    pen = np.where(cm & ~ok, rule.penalty(np.where(partial, pc, nc)), 0.0)
    rd = np.where(cm, READ_C * ncm + READ_W * np.where(partial | (kw > 0), kw, nw), 0.0) if read else np.zeros(len(cm))
    return credit, pen + rd


def paired(ra: list[dict], rb: list[dict], durs: list[float], read: bool = True) -> dict:
    ca, xa = credit_arrays(ra, read)
    cb, xb = credit_arrays(rb, read)
    ns = np.asarray(durs, float)

    def wpm(c, x, w):
        return 60.0 * (c * w).sum() / ((ns * w).sum() + (x * w).sum())

    n = len(ns)
    rng = np.random.default_rng(SEED)
    da, db, dd = [], [], []
    for _ in range(B):
        w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        x, y = wpm(ca, xa, w), wpm(cb, xb, w)
        da.append(x)
        db.append(y)
        dd.append(y - x)
    one = np.ones(n)
    va, vb = wpm(ca, xa, one), wpm(cb, xb, one)
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]  # noqa: E731
    cd = ci(dd)
    return {"a": va, "b": vb, "diff": vb - va, "diff_ci95": cd, "diff_half_width": (cd[1] - cd[0]) / 2,
            "a_ci95": ci(da), "b_ci95": ci(db), "B": B, "seed": SEED, "reading_cost": read,
            "method": "paired percentile trial bootstrap, decisions fixed (conditional on the calibration)"}


def latency(rows: list[dict], ends: list, durs: list[float]) -> dict:
    """Commit latency of committed words: commit time - end time of the same true word (s)."""
    lat_right, lat_all, before_end, n_words = [], [], 0, 0
    for r, e, dur in zip(rows, ends, durs):
        if r["action"] != "commit" or e is None:
            continue
        y = r["truth"].split()
        commits = r.get("commits") or [{"k_from": 0, "k_to": r["n_words_committed"], "at_end": True, "t_s": dur}]
        words = r["text"].split()
        for cmt in commits:
            t = dur if cmt["at_end"] else cmt["t_s"]
            for j in range(cmt["k_from"], cmt["k_to"]):
                if j >= len(y):
                    continue
                n_words += 1
                before_end += int(not cmt["at_end"])
                lat_all.append(t - e[j])
                if words[: j + 1] == y[: j + 1]:
                    lat_right.append(t - e[j])

    def summ(v):
        if not v:
            return None
        a = np.asarray(v)
        return {"n": int(a.size), "mean": float(a.mean()), "median": float(np.median(a)),
                "p10": float(np.percentile(a, 10)), "p90": float(np.percentile(a, 90))}

    return {"right_committed_words": summ(lat_right), "all_committed_words": summ(lat_all),
            "share_committed_before_trial_end": before_end / n_words if n_words else None}


def stream_rows_of(views_list: list, guard_like, truths: list[str], name: str) -> list[dict]:
    out = []
    for i, vs in enumerate(views_list):
        r = guard_like(vs, f"{name}-{i}")
        out.append(r)
    return out


def decide_with(g: S.StreamingPrefixGuard, vs: list, uid: str, truth: str) -> dict:
    r = g.decide_views(vs, utterance_id=uid)
    commits = [{"k_from": e["n_words_committed"] - e["words_added"], "k_to": e["n_words_committed"],
                "at_end": e["at_end"], "t_s": e["t_s"], "checkpoint": e["checkpoint"], "complete": e["complete"]}
               for e in r.events]
    assert S.StreamingPrefixGuard.check_chain(r.events)
    return {"action": "commit" if r.n_commits else "no-commit", "text": r.text, "truth": truth,
            "complete": r.complete, "n_words_committed": r.n_words_committed, "n_commits": r.n_commits,
            "n_conflicts": r.n_conflicts, "commits": commits, "events": r.events}


def p524_score_arm(base, cal_views, cal_truth, order_cert, eval_views, null_views, ht) -> dict:
    """Secondary arm: the P5-24 prefix score (no refit, no streaming features) streamed; threshold re-certified
    by LTT on the stream loss (same certify items), streaming null controls."""
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    cs = base.commit_score

    def scores(vs):
        return [monotone_prefix_scores(cs.scores(v.rows)) if (v.gate_ok and len(v.rows)) else np.zeros(0) for v in vs]

    res = S.ltt_stream_threshold([cal_views[i] for i in order_cert], [scores(cal_views[i]) for i in order_cert],
                                 [cal_truth[i].split() for i in order_cert], ALPHA, DELTA, DEFAULT_LTT_GRID)
    thr = res["threshold"]
    cnt: dict = {}
    for nm, vs in null_views:
        cnt[nm] = cnt.get(nm, 0) + int(bool(S.run_stream(vs, scores(vs), thr)["commits"]))
    allowed = int(math.floor(ALPHA * N_NULL + 1e-9))
    rows = []
    for vs, y in zip(eval_views, ht):
        r = S.run_stream(vs, scores(vs), thr)
        w = r["words"]
        rows.append({"action": "commit" if r["commits"] else "no-commit", "text": " ".join(w) if w else None,
                     "truth": y, "complete": r["complete"] if w else None, "n_words_committed": len(w),
                     "n_commits": len(r["commits"])})
    return {"ltt": {k: (v if not (isinstance(v, float) and math.isnan(v)) else None) for k, v in res.items()},
            "controls": {k: {"n_commit": v, "allowed": allowed, "passed": v <= allowed} for k, v in cnt.items()},
            "rows": rows}


def stage_evaluate() -> dict:
    t0 = time.time()
    d = load_t15()
    meta = json.loads((OWN / "base.json").read_text(encoding="utf-8"))
    base = ft.load(OUT / "guard-p5-27-base.json", decode_fn=d["fn"])
    assert base.config_id == meta["config_id"]
    n_cal, n_ev = len(d["cx"]), len(d["hx"])
    cal_v, ev_v = read_views("cal", n_cal), read_views("eval", n_ev)
    names = json.loads((OWN / "controls.json").read_text(encoding="utf-8"))
    null_v = list(zip(names, read_views("null", len(names))))
    log(f"evaluate: views read ({sum(len(v) for v in cal_v)} cal, {sum(len(v) for v in ev_v)} eval checkpoints); "
        f"peak {peak_mb():.0f} MB")
    try:
        g = S.calibrate_streaming(base, d["cx"], d["ct"], step_frames=STEP, alpha=ALPHA, delta=DELTA, seed=SEED,
                                  frame_timing=TIMING, views=cal_v, control_views=null_v, null_trials=N_NULL,
                                  progress=log)
    except ft.NullControlError as e:
        log(f"stream arm REFUSED: {[c.to_dict() for c in e.report]}")
        return {"stream": {"status": "refused", "controls": [c.to_dict() for c in e.report]}}
    g.save(OUT / "guard-p5-27-stream.json")
    durs = d["durs"]
    stream_rows = [decide_with(g, vs, f"{d['name']}-{i}", d["ht"][i]) for i, vs in enumerate(ev_v)]
    single = json.loads((OWN / "decisions-single.json").read_text(encoding="utf-8"))
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "decisions-stream.json").write_text(json.dumps(stream_rows, indent=0), encoding="utf-8")
    sg = g.guarantee()
    sc_ctrl = {c["name"]: c for c in g.sheet["controls"]}
    controls = {"rule": g.sheet["controls_rule"], "results": g.sheet["controls"],
                "passed": all(c["passed"] for c in g.sheet["controls"])}
    gsheet = json.loads((OUT / "guard-p5-27-base.json").read_text(encoding="utf-8"))["sheet"]
    from fidetype.benchmark.safe_wpm import controls_from_sheet, guarantee_from_sheet

    s_g, s_c = guarantee_from_sheet(gsheet), controls_from_sheet(gsheet)
    out: dict = {"info": d["info"], "split": split_hashes(n_cal), "stream_sheet": g.sheet,
                 "stream_config_id": g.config_id, "base_config_id": base.config_id}
    out["stream"] = {"v0_2_read": score(stream_rows, sg, controls, durs),
                     "v0_2_no_read": score(stream_rows, sg, controls, durs, read=False),
                     "v0_1_complete_only": score(stream_rows, sg, controls, durs, view="complete")}
    out["single"] = {"v0_2_read": score(single, s_g, s_c, durs), "v0_2_no_read": score(single, s_g, s_c, durs,
                                                                                         read=False),
                     "v0_1_complete_only": score(single, s_g, s_c, durs, view="complete")}
    for arm in ("stream", "single"):
        for k, v in out[arm].items():
            log(f"{arm} {k}: {format_line(v)}")
    out["paired_v0_2_read"] = paired(single, stream_rows, durs, True)
    out["paired_v0_2_no_read"] = paired(single, stream_rows, durs, False)
    # latency
    ends = [word_ends(x, ids, len(y.split())) for x, ids, y in zip(d["hx"], d["hid"], d["ht"])]
    out["latency"] = {"word_end": "CTC forced alignment of the true phonemes on the full-trial log-probs",
                      "n_trials_aligned": int(sum(e is not None for e in ends)),
                      "stream": latency(stream_rows, ends, durs), "single": latency(single, ends, durs)}
    secs = np.array([v.seconds for vs in ev_v for v in vs], float)
    out["compute_s_per_checkpoint"] = {"median": float(np.median(secs)), "p95": float(np.percentile(secs, 95)),
                                       "max": float(secs.max()), "step_s": STEP * FRAME_S,
                                       "note": "wall clock, CPU 4 threads, background class, decode + features"}
    ncm = [r["n_commits"] for r in stream_rows]
    out["stream_stats"] = {
        "commits_per_trial_hist": {str(k): ncm.count(k) for k in sorted(set(ncm))},
        "n_conflicts_total": int(sum(r["n_conflicts"] for r in stream_rows)),
        "trials_with_conflict_after_commit": int(sum(r["n_conflicts"] > 0 and r["n_commits"] > 0
                                                     for r in stream_rows)),
        "words_committed": int(sum(r["n_words_committed"] for r in stream_rows)),
        "complete_final": int(sum(bool(r["complete"]) for r in stream_rows if r["action"] == "commit")),
        "mean_checkpoints_per_trial": float(np.mean([len(v) for v in ev_v]))}
    # secondary arm: P5-24 score streamed
    order = np.random.default_rng(SEED).permutation(n_cal)
    from fidetype.trust.dropin import _split

    a, b_, _c = _split(n_cal)
    sec = p524_score_arm(base, cal_v, d["ct"], order[a + b_:], ev_v, null_v, d["ht"])
    sec_g = dict(sg, commit_threshold=sec["ltt"]["threshold"])
    sec_ok = all(c["passed"] for c in sec["controls"].values())
    out["stream_p524_score"] = {"ltt": sec["ltt"], "controls": sec["controls"],
                                "v0_2_read": score(sec["rows"], sec_g, {"passed": sec_ok}, durs) if sec_ok else None}
    if sec_ok:
        out["stream_p524_score"]["paired_vs_single_v0_2_read"] = paired(single, sec["rows"], durs, True)
    log(f"secondary stream-p524-score: ltt {sec['ltt']}, controls {sec['controls']}")
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


def stage_verdict() -> dict:
    allr = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    st = (allr.get("stages") or {}).get("evaluate", {}).get("result")
    if not st:
        return {"verdict": "not run"}
    if st.get("stream", {}).get("status") == "refused":
        return {"verdict": "stream fails a control"}
    v2 = st["stream"]["v0_2_read"]
    pr = st["paired_v0_2_read"]
    safe = v2["measured_wrong_commit"] <= ALPHA
    clear = v2["measured_wrong_commit_cp95"][0] > ALPHA
    ctrl = bool((v2.get("controls") or {}).get("passed"))
    dd, hw = pr["diff"], pr["diff_half_width"]
    if not ctrl:
        v = "stream fails a control"
    elif not safe:
        v = "stream fails safety"
    elif v2["status"] != "certified":
        v = f"stream not certified ({v2['status']})"
    elif dd > hw:
        v = "stream beats single"
    elif dd < -hw:
        v = "single beats stream"
    else:
        v = "no clear difference"
    out = {"verdict": v, "diff": dd, "half_width": hw, "diff_ci95": pr["diff_ci95"], "stream_value": v2["value"],
           "stream_ci95": pr["b_ci95"], "single_value": st["single"]["v0_2_read"]["value"], "stream_safe": safe,
           "stream_clear_violation": clear, "stream_controls_pass": ctrl,
           "stream_wrong": [v2["n_wrong_commits"], v2["n_trials"]], "stream_cp95": v2["measured_wrong_commit_cp95"],
           "stream_above_no_bci": isinstance(v2["value"], float) and v2["value"] > NO_BCI,
           "stream_ci_above_no_bci": pr["b_ci95"][0] > NO_BCI, "no_bci": NO_BCI}
    log(f"verdict: {out}")
    return out


def stage_dry() -> dict:
    """Pipeline and timing check on 12 val_select items (no val_eval data is decoded or scored)."""
    t0 = time.time()
    d = load_t15()
    base = calibrate_base(d)
    reset(d)
    t1 = time.time()
    vs = []
    for x in d["cx"][:12]:
        vs.append(S.stream_views(base, x, STEP))
        reset(d)
    t2 = time.time()
    nv = sum(len(v) for v in vs)
    nulls = S.null_control_inputs(base, d["cx"], 4, CONTROL_SEED)
    t3 = time.time()
    nvn = 0
    for _, x, sc in nulls:
        nvn += len(S.stream_views(base, x, STEP, sc))
        reset(d)
    t4 = time.time()
    out = {"calibrate_s": t1 - t0, "items": 12, "checkpoints": nv, "s_per_checkpoint": (t2 - t1) / nv,
           "null_inputs": len(nulls), "null_checkpoints": nvn, "null_s_per_checkpoint": (t4 - t3) / max(1, nvn),
           "peak_mb": peak_mb(), "base_config_id": base.config_id}
    log(f"dry: {out}")
    return out


STAGES = {"views": stage_views, "evaluate": stage_evaluate, "verdict": stage_verdict, "dry": stage_dry}


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
        path.write_text(json.dumps(to_jsonable(allr), indent=1, default=str) + "\n", encoding="utf-8")
        log(f"stage {st} done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
