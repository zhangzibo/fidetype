r"""P14-41: the trust guard of the pretrained decoder ``willett-hw`` (CPU only). Our own code. Plan: plan.md.

Stages (each one writes a checkpoint and skips work that is done):
  lp      ``load("willett-hw")`` (NumPy runtime) on the P15-08 val and test blocks: log-probs of the real,
          time-shuffled and zero input, one npz per (split, kind) in the derived folder. The sessions are read
          one at a time; only the val and test sentences are kept (uint8), the rest is freed at once.
  guard   ``fidetype.trust.calibrate`` on the 106 val sentences (nulls = their time-shuffled input), alpha 0.05,
          delta 0.1, seed 0: the same call as the P14-33 ``guard`` stage. A refusal is a result (saved).
  decide  ``guard.decide`` on the 80 test sentences: real, time-shuffled, zero, frame-shuffled and near-uniform
          input. One JSONL line per decision (resume skips the lines that exist).
  score   aggregates, V1-V7 of plan.md, safe WPM v0.1 -> ``results/results.json`` (no text).
  all     lp guard decide score, then the DONE file.

Memory (gap 121): the P14-33 guard stage ran out of memory in the CTC forced alignment of
``fidetype.lm.beam`` (an emit array (T, S) float64 for all n-best texts at once; garbage texts on null input
are long). The fix is in the library (frame-by-frame scores, groups of texts, no alignment when a text has
more labels than frames); this script adds float32 storage, one session at a time, and a peak-RSS log.

Safety: a watcher thread stops the process (exit 3) if the file ``STOP`` exists in the derived folder or the
working set passes ``RSS_LIMIT_MB``. Per-sentence records (decoded text, truth) stay in
``C:\Users\zhang\bci-data\derived\p14-41``; the repo gets aggregates only.

Run (repo root; the detached form is launch.py)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-20-p14-41-willett-guard/run.py all
"""

from __future__ import annotations

import ctypes
import gc
import hashlib
import json
import math
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", r"C:\Users\zhang\bci-data\pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"  # CPU only: the GPU belongs to another job
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DATA = Path(r"C:\Users\zhang\bci-data")
RAW = DATA / "raw/willett-handwriting/extracted/handwritingBCIData/Datasets"
P15 = DATA / "derived/p15-08"  # read only (splits.json)
OWN = DATA / "derived/p14-41"
OUT = HERE / "results"
SALT = "fidetype-p15-08-2026-11-19"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
KINDS = ("real", "timeshuf", "zero")
TEST_KINDS = ("real", "timeshuf", "zero", "frameshuf", "uniform")
RSS_LIMIT_MB = 6000.0
V6_LIMIT = 0.05


# --- logging, memory, stop -----------------------------------------------------------------------------

class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QPPPU", ctypes.c_size_t), ("QPPU", ctypes.c_size_t),
                ("QPNPPU", ctypes.c_size_t), ("QNPPU", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_mb() -> tuple[float, float]:
    """(working set, peak working set) of this process in MB (Windows; (nan, nan) elsewhere)."""
    if os.name != "nt":
        return math.nan, math.nan
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    c = _PMC()
    c.cb = ctypes.sizeof(_PMC)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20


def log(msg: str) -> None:
    w, p = mem_mb()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] (rss {w:.0f} MB, peak {p:.0f} MB) {msg}"
    print(line, flush=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def watcher() -> None:
    """Stop at once on the STOP file or a working set above RSS_LIMIT_MB; a heartbeat every 10 min."""
    last = time.time()
    while True:
        time.sleep(2.0)
        w, _ = mem_mb()
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)
        if w > RSS_LIMIT_MB:
            log(f"working set {w:.0f} MB > limit {RSS_LIMIT_MB:.0f} MB: exit 3 (not restarted; see plan.md)")
            os._exit(3)
        if time.time() - last > 600:
            log("heartbeat")
            last = time.time()


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def update_results(key: str, val) -> None:
    p = OUT / "results.json"
    r = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    r[key] = val
    save_json(r, p)


def item_rng(split: str, i: int, kind: str) -> np.random.Generator:
    """A fixed generator per (split, sentence, control): the same input on a resume."""
    h = hashlib.sha256(f"p14-41|{SEED}|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


# --- split (P15-08, recomputed as in P14-33) -------------------------------------------------------------

def val_block(si: int, blocks: list[int], test_b: int) -> int:
    rest = sorted(b for b in set(blocks) if b != test_b)
    return min(rest, key=lambda b: hashlib.sha256("|".join([SALT, "val", str(si), str(b)]).encode()).hexdigest())


def stage_lp() -> None:
    import fidetype.pretrained as ftp
    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB

    if (OWN / "items.json").exists() and all((OWN / f"lp_{s}_{k}.npz").exists() for s in ("val", "test") for k in KINDS):
        log("lp: checkpoint found, skipped")
        return
    t0 = time.time()
    vocab = set(VOCAB[1:])
    m = ftp.load("willett-hw")
    sessions = m.manifest.architecture["sessions"]
    meta: dict = {"val": [], "test": [], "test_blocks": {}, "val_blocks": {}}
    lps: dict = {(s, k): [] for s in ("val", "test") for k in KINDS}
    for si, sess in enumerate(sessions):
        items = [it for it in R.read_willett_session(RAW / sess) if it.truth and all(c in vocab for c in it.truth)]
        tb = R.willett_test_block(items)
        vb = val_block(si, [it.extra["block"] for it in items], tb)
        meta["test_blocks"][str(si)], meta["val_blocks"][str(si)] = tb, vb
        keep = {"test": [it for it in items if it.extra["block"] == tb], "val": [it for it in items if it.extra["block"] == vb]}
        del items
        for split, its in keep.items():
            for it in its:
                i = len(meta[split])
                x = np.asarray(it.x)
                lps[(split, "real")].append(m.log_probs(x, it.session).astype(np.float32))
                xs = x[item_rng(split, i, "timeshuf").permutation(len(x))]
                lps[(split, "timeshuf")].append(m.log_probs(xs, it.session).astype(np.float32))
                lps[(split, "zero")].append(m.log_probs(np.zeros_like(x), it.session).astype(np.float32))
                meta[split].append({"key": it.key, "session": it.session, "truth": it.truth, "T": int(len(x)),
                                    "block": int(it.extra["block"])})
        del keep
        gc.collect()
        log(f"lp: session {si + 1}/{len(sessions)} {sess}: {len(meta['val'])} val, {len(meta['test'])} test so far")
    ref = json.loads((P15 / "willett/splits.json").read_text(encoding="utf-8"))
    meta["split_equal_p15_08"] = (meta["test_blocks"] == {k: int(v) for k, v in ref["test_blocks"].items()}
                                  and meta["val_blocks"] == ref["val_blocks"])
    for (split, kind), arrs in lps.items():
        np.savez(OWN / f"lp_{split}_{kind}.npz", *arrs)
    save_json(meta, OWN / "items.json")
    log(f"lp: {len(meta['val'])} val, {len(meta['test'])} test sentences; split equal to P15-08: "
        f"{meta['split_equal_p15_08']} ({time.time() - t0:.0f} s)")
    update_results("lp", {"n_val": len(meta["val"]), "n_test": len(meta["test"]),
                          "val_frames": int(sum(r["T"] for r in meta["val"])),
                          "test_frames": int(sum(r["T"] for r in meta["test"])),
                          "split_equal_p15_08": bool(meta["split_equal_p15_08"]),
                          "seconds": round(time.time() - t0, 1), "peak_rss_mb": round(mem_mb()[1])})


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(OWN / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def vocab_obj():
    import fidetype.pretrained as ftp
    from fidetype.adapters.ctc_logits import vocab_from_list
    from fidetype.pretrained import _xbody

    m = ftp.load("willett-hw")
    return vocab_from_list(list(_xbody.VOCAB), blank=0, vocab_type="char", vocab_id=m.manifest.output["vocab_id"])


def stage_guard() -> None:
    import fidetype.trust as ft
    from fidetype.pretrained import _xbody, sha256_file

    if (OWN / "guard_record.json").exists():
        log("guard: checkpoint found, skipped")
        return
    t0 = time.time()
    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    lp_val, nulls = load_lps("val", "real"), load_lps("val", "timeshuf")
    texts = [r["truth"] for r in meta["val"]]
    rec: dict = {"alpha": ALPHA, "delta": DELTA, "n_cal": len(lp_val), "n_null": len(nulls), "cal": "val blocks",
                 "null": "time-shuffled input of the val sentences (decoder run on the shuffled bins)"}
    log(f"guard: calibrate on {len(lp_val)} val sentences, {len(nulls)} time-shuffled nulls")
    try:
        g = ft.calibrate(lp_val, texts, alpha=ALPHA, delta=DELTA, input_kind="logits", vocab=vocab_obj(), blank=0,
                         input_scale="log_probs", frame_period=_xbody.BIN_S, null_inputs=nulls,
                         decoder_name="fidetype-willett-hw", decoder_version="1", modality="intracortical",
                         name="p14-41-willett-hw", seed=SEED, audit_text=False, language="en")
    except ft.NullControlError as e:
        rec.update(status="refused", reason=str(e)[:2000], controls=[c.to_dict() for c in e.report],
                   seconds=round(time.time() - t0, 1), peak_rss_mb=round(mem_mb()[1]))
        log(f"guard: REFUSED ({time.time() - t0:.0f} s): {e}")
        save_json(rec, OWN / "guard_record.json")
        update_results("guard", rec)
        return
    gp = OWN / "willett-hw.guard.json"
    g.save(gp)
    log(f"guard: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
    rec.update(status="guard", config_id=g.config_id, guard_sha256=sha256_file(gp), guard_size=gp.stat().st_size,
               sheet=g.sheet.to_dict(), seconds=round(time.time() - t0, 1), peak_rss_mb=round(mem_mb()[1]))
    save_json(rec, OWN / "guard_record.json")
    update_results("guard", rec)


def test_input(kind: str, i: int, lp_real: np.ndarray, cache: dict) -> np.ndarray:
    if kind in ("real", "timeshuf", "zero"):
        return cache[kind][i]
    if kind == "frameshuf":  # decoder frames in a random time order (the automatic calibrate control)
        return lp_real[item_rng("test", i, "frameshuf").permutation(len(lp_real))]
    # near-uniform frames: log 1/V + 0.05 N(0,1), as logits (the automatic calibrate control)
    T, V = lp_real.shape
    z = np.full((T, V), -math.log(V)) + 0.05 * item_rng("test", i, "uniform").standard_normal((T, V))
    return z - np.log(np.exp(z).sum(1, keepdims=True))


def stage_decide() -> None:
    import fidetype.trust as ft

    rec = json.loads((OWN / "guard_record.json").read_text(encoding="utf-8"))
    if rec["status"] != "guard":
        log("decide: no guard (refused), skipped")
        return
    t0 = time.time()
    g = ft.load(OWN / "willett-hw.guard.json")
    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    out = OWN / "decisions.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["kind"], d["i"]))
    cache = {k: load_lps("test", k) for k in ("real", "timeshuf", "zero")}
    n_new = 0
    with open(out, "a", encoding="utf-8") as fh:
        for kind in TEST_KINDS:
            for i, r in enumerate(meta["test"]):
                if (kind, i) in done:
                    continue
                x = test_input(kind, i, cache["real"][i], cache)
                d = g.decide(x)
                top = d.choices[0] if d.choices else ""
                fh.write(json.dumps({"kind": kind, "i": i, "key": r["key"], "action": d.action,
                                     "right": bool(d.action == "commit" and g.is_right(d, r["truth"])),
                                     "top1": top, "p_top1": float(d.p_top1), "guard_risk": float(d.guard_risk),
                                     "reason": d.reason, "truth": r["truth"]}, ensure_ascii=False) + "\n")
                fh.flush()
                n_new += 1
            log(f"decide: {kind} done ({time.time() - t0:.0f} s)")
    log(f"decide: {n_new} new decisions ({time.time() - t0:.0f} s)")
    update_results("decide_run", {"seconds": round(time.time() - t0, 1), "new_decisions": n_new,
                                  "peak_rss_mb": round(mem_mb()[1])})


def stage_score() -> None:
    from fidetype.benchmark.safe_wpm import controls_from_sheet, format_line, guarantee_from_sheet, safe_wpm
    from fidetype.eval.metrics import edit_distance
    from fidetype.utils.binomial import clopper_pearson

    rec = json.loads((OWN / "guard_record.json").read_text(encoding="utf-8"))
    res: dict = {"guard_status": rec["status"]}
    if rec["status"] != "guard":
        res["V1"] = "refused"
        update_results("score", res)
        log(f"score: V1 refused; controls {rec.get('controls')}")
        return
    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    sheet = rec["sheet"]
    dec = [json.loads(x) for x in (OWN / "decisions.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    by = {k: sorted((d for d in dec if d["kind"] == k), key=lambda d: d["i"]) for k in TEST_KINDS}
    n = len(meta["test"])
    assert all(len(by[k]) == n for k in TEST_KINDS), {k: len(v) for k, v in by.items()}
    counts = {}
    for k in TEST_KINDS:
        c = sum(d["action"] == "commit" for d in by[k])
        w = sum(d["action"] == "commit" and not d["right"] for d in by[k])
        counts[k] = {"n": n, "commit": c, "wrong_commit": w, "offer": sum(d["action"] == "offer" for d in by[k]),
                     "withhold": sum(d["action"] == "withhold" for d in by[k]), "commit_rate": round(c / n, 4),
                     "wrong_commit_rate": round(w / n, 4), "wrong_commit_cp95": clopper_pearson(w, n)}
    real = by["real"]
    truths = [r["truth"] for r in meta["test"]]
    committed = [d["action"] == "commit" for d in real]
    correct = [d["right"] for d in real]
    durations = [r["T"] * 0.01 for r in meta["test"]]
    blk = safe_wpm(committed, correct, [len(t.split()) for t in truths], [len(t) for t in truths], durations,
                   guarantee=guarantee_from_sheet(sheet), timing="neural time = 10 ms bins of the sentence window "
                   "(go cue to sentence end + up to 1 s tail, P15-08 cut)", controls=controls_from_sheet(sheet),
                   B=2000, seed=SEED)
    blk["ci_note"] = "no CI: one participant (T5); a sentence bootstrap would be too narrow"
    # descriptive: the offered top-1 text
    ed = [edit_distance(t, d["top1"]) for t, d in zip(truths, real)]
    top_exact = sum(e == 0 for e in ed)
    feasible = bool(sheet.get("feasible"))
    certified = rec["status"] == "guard" and feasible
    ctl = {c["name"]: c for c in sheet.get("controls", [])}
    cal_ok = all(c.get("passed") for c in sheet.get("controls", []))
    v6 = {k: counts[k]["commit_rate"] <= V6_LIMIT for k in ("timeshuf", "zero")}
    w_real = counts["real"]["wrong_commit"]
    cp = clopper_pearson(w_real, n)
    res.update({
        "V1": "certified" if certified else "guard returned, LTT not feasible (no certified commit threshold)",
        "V1_detail": {"feasible": feasible, "n_ltt": sheet.get("n_ltt"), "n_ltt_min": sheet.get("n_ltt_min"),
                      "commit_threshold": sheet.get("commit_threshold"), "lambda_hat": sheet.get("lambda_hat"),
                      "ltt_commits": sheet.get("ltt_commits"), "ltt_wrong_commits": sheet.get("ltt_wrong_commits"),
                      "warnings": sheet.get("warnings")},
        "V2": ("clear violation" if cp[0] is not None and cp[0] > ALPHA else
               "holds" if w_real / n <= ALPHA else "fails"),
        "V3": "non-vacuous" if (certified and counts["real"]["commit"] > 0 and (blk.get("value") or 0) > 0) else "vacuous",
        "V6": {"calibrate_controls": {k: {"n": c["n"], "n_commit": c["n_commit"], "allowed": c["allowed"],
                                          "passed": c["passed"]} for k, c in ctl.items()},
               "calibrate_controls_pass": cal_ok,
               "test_timeshuf_commit_rate": counts["timeshuf"]["commit_rate"],
               "test_zero_commit_rate": counts["zero"]["commit_rate"],
               "pass": bool(cal_ok and all(v6.values()))},
        "V7_offer_top1": {"exact": top_exact, "n": n, "cer": round(sum(ed) / sum(len(t) for t in truths), 4),
                          "offers": counts["real"]["offer"]},
        "test": counts, "safe_wpm": blk})
    update_results("score", res)
    log(f"score: V1 {res['V1']}; V2 {res['V2']}; V3 {res['V3']}; V6 pass {res['V6']['pass']}; "
        f"counts real {counts['real']}; top-1 exact {top_exact}/{n}; {format_line(blk)}")


def main(argv: list[str]) -> int:
    from fidetype.utils.power import keep_awake

    stages = {"lp": stage_lp, "guard": stage_guard, "decide": stage_decide, "score": stage_score}
    want = argv or ["all"]
    run_all = "all" in want
    order = list(stages) if run_all else want
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "DONE").unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    with keep_awake(log):
        log(f"start {order} (pid {os.getpid()})")
        for s in order:
            stages[s]()
            gc.collect()
            log(f"stage {s} finished")
    peak = mem_mb()[1]
    update_results("peak_rss_mb_last_run", round(peak))
    log(f"end; peak RSS of this run {peak:.0f} MB")
    if run_all:
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
