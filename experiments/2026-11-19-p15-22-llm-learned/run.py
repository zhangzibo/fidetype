"""P15-22: LLM rescoring (P15-05 arm B1) + the learned commit confidence (P5-23) and prefix commits (P5-24) on
T15 M4-13. Pre-registered: plan.md (commit 7557b54). CPU only, our own code (Apache-2.0).

Stages (resumable; each finished arm is saved in the derived folder and skipped on a rerun):
  t15      arms L0 llm (p_top1), L1 llm_learned (primary), L2 llm_prefix on val_select 722 -> val_eval 701
  halluc   hallucination protocol 0.2 tracks (null 300, scrambled 300, swapped 701) for the arms of t15
  verdict  the pre-registered decision rule (no data access)
  all      t15, halluc, verdict, then the DONE file

Run (repo root): launch.py (detached), or in the foreground:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-19-p15-22-llm-learned/run.py all
Smoke test (val_select subsets only; val_eval is never read): P1522_SMOKE=1 run.py smoke
Per-trial files (with text) and caches: C:/Users/zhang/bci-data/derived/p15-22/ only. Repo: aggregates + guard files.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))

import common as K  # noqa: E402

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import (  # noqa: E402
    CorrectionRule,
    controls_from_sheet,
    format_line,
    guarantee_from_sheet,
    safe_wpm,
)
from fidetype.lm.llm import CachedRewriter, CachedScorer, lattice_words  # noqa: E402

DER = K.DER
SMOKE = os.environ.get("P1522_SMOKE", "0") == "1"
OWN_ROOT = DER / "p15-22"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-22"
OWN = OWN_ROOT / "smoke" if SMOKE else OWN_ROOT
OUT = HERE / ("results/smoke" if SMOKE else "results")
LOGF = OUT / "run.log"
SRC5 = DER / "f2-reruns-m4-13" / "p15-05"  # READ ONLY: committed P15-05 M4-13 caches, guards, trials
SRC6 = DER / "f2-reruns-m4-13" / "p15-06"  # READ ONLY: committed P15-06 M4-13 LLM cache
M413_RES = REPO / "experiments/2026-11-17-f2-m4-13/results/results-t15.json"  # READ ONLY (ground_prep, prep)
R1_FILE = DER / "p5-23" / "decisions-p5-23-t15-m4-13-learned.json"  # READ ONLY
R2_FILE = DER / "p5-24" / "decisions-p5-24-t15-m4-13-prefix.json"  # READ ONLY
SPLIT_V01 = REPO / "src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json"
DATASET = "b2t25-t15-val-eval"

ALPHA, DELTA, SEED, B = 0.05, 0.1, 0, 2000
NULL_TRIALS = 20 if SMOKE else 300  # smoke tests only use 20
STUB = SMOKE and os.environ.get("P1522_STUB_LLM", "0") == "1"  # smoke tests only: a fake LLM, no model load
NO_BCI_T15 = 4.02
READ_S_PER_COMMIT, READ_S_PER_WORD = 0.5, 0.3  # aac-gaze-v1 verify (P14-28)
SPLIT_SHA = ("285b8c0d9baf5a41", "fadfd84557fcb24b")  # P5-23 plan: score-fit / certify positions
ARMS = {"llm": {}, "llm_learned": {"confidence": "learned"},
        "llm_prefix": {"confidence": "learned", "commit_unit": "prefix"}}
ROLE = {"llm": "L0 (LLM arm alone, p_top1)", "llm_learned": "L1 (primary: LLM + learned score)",
        "llm_prefix": "L2 (secondary: LLM + learned prefix score)"}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + f"[{K.private_mb()} MB] " + " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


F = load_module("f2e3_run_p1522", REPO / "experiments/2026-11-16-f2-e3-llm-grounding/run.py")  # P15-05, unchanged
P523 = load_module("p523run_p1522", REPO / "experiments/2026-11-18-p5-23-learned-confidence/run.py")
P524 = load_module("p524run_p1522", REPO / "experiments/2026-11-18-p5-24-prefix-commits/run.py")
norm, auroc = P523.norm, P523.auroc
ARM_B1 = F.CFG["arms"]["B1_rescore_G"]
assert ARM_B1 == {"rescore": True, "rewrite": None, "ground": True}, ARM_B1


def peak_mb() -> float:
    """Peak private bytes (PeakPagefileUsage) of this process in MB (Windows; nan elsewhere)."""
    if os.name != "nt":
        return math.nan
    import ctypes
    import ctypes.wintypes as W

    class PMC(ctypes.Structure):
        _fields_ = [("cb", W.DWORD), ("PageFaultCount", W.DWORD)] + [(f, ctypes.c_size_t) for f in (
            "PeakWorkingSetSize", "WorkingSetSize", "QPPPU", "QPPU", "QPNPPU", "QNPPU", "PagefileUsage",
            "PeakPagefileUsage")]

    k32, ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = W.HANDLE
    ps.GetProcessMemoryInfo.argtypes = [W.HANDLE, ctypes.POINTER(PMC), W.DWORD]
    m = PMC()
    m.cb = ctypes.sizeof(m)
    ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(m), m.cb)
    return m.PeakPagefileUsage / 2**20


# ---------------------------------------------------------------------------
# caches (copies of the committed P15-05 / P15-06 M4-13 caches; the originals stay read only)
# ---------------------------------------------------------------------------


def prepare_caches() -> dict:
    OWN.mkdir(parents=True, exist_ok=True)
    info = {}
    db = OWN / "llm-cache.sqlite"
    if not db.exists():
        tmp = OWN / "llm-cache.tmp"
        shutil.copy2(SRC5 / "llm-cache.sqlite", tmp)
        con = sqlite3.connect(f"file:{tmp.as_posix()}", uri=True)  # uri=True: ATTACH may then use ?mode=ro
        con.execute(f"ATTACH DATABASE 'file:{(SRC6 / 'llm-cache.sqlite').as_posix()}?mode=ro' AS s6")
        for t in ("scores", "rewrites"):
            con.execute(f"CREATE TABLE IF NOT EXISTS {t} (k TEXT PRIMARY KEY, v TEXT)")
            have = {r[0] for r in con.execute("SELECT name FROM s6.sqlite_master WHERE type='table'")}
            if t in have:
                con.execute(f"INSERT OR IGNORE INTO {t} SELECT k, v FROM s6.{t}")
        con.commit()
        con.execute("DETACH DATABASE s6")
        con.close()
        tmp.replace(db)
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    info["llm_scores_cached"] = con.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    con.close()
    base = OWN / "base-nbest-t15.pkl"
    if not base.exists():
        shutil.copy2(SRC5 / "base-nbest-t15.pkl", base)
    info["base_nbest_file_bytes"] = base.stat().st_size
    return info


class LazyLLM:
    """The P15-05 LLM, loaded on the CPU only at the first cache miss (most runs never load it)."""

    def __init__(self) -> None:
        self.llm = None
        self.texts_scored = 0

    def _get(self):
        if self.llm is None:
            from fidetype.lm.llm import LlamaCppLLM

            m = F.CFG["llm"]
            h = hashlib.sha256()
            with open(m["path"], "rb") as f:
                for b in iter(lambda: f.read(1 << 22), b""):
                    h.update(b)
            assert h.hexdigest() == m["sha256"], "model file SHA-256 mismatch"
            log("LLM cache miss: loading Qwen2.5-1.5B on the CPU (n_gpu_layers 0)")
            self.llm = LlamaCppLLM(m["path"], n_threads=m["n_threads"], n_ctx=m["n_ctx"], seed=F.SEED,
                                   max_tokens=m["max_tokens"])
        return self.llm

    def score(self, texts):
        self.texts_scored += len(texts)
        if STUB:
            import zlib

            return [-2.5 * max(1, len(t.split())) - (zlib.crc32(t.encode()) % 100) / 50.0 for t in texts]
        return self._get().score(texts)

    def rewrite(self, nbest_texts, constrained=True):
        raise RuntimeError("arm B1 does not rewrite")


class Ctx:
    """Data, pipeline and references, loaded once per process."""

    def __init__(self, with_held: bool = True) -> None:
        self.cache_info = prepare_caches()
        res = json.loads(M413_RES.read_text(encoding="utf-8"))
        self.gp, self.fluent_thr = res["ground_prep"], res["prep"]["fluent_logp_per_word"]
        dec, _bt = K.word_decoder()
        F.OWN = OWN  # the P15-05 Pipeline keeps its base n-best cache in F.OWN
        self.lazy = LazyLLM()
        sc = CachedScorer(self.lazy, F.DiskDict(OWN / "llm-cache.sqlite", "scores"))
        rw = CachedRewriter(self.lazy, F.DiskDict(OWN / "llm-cache.sqlite", "rewrites"))
        self.pipe = F.Pipeline("t15", dec, sc, rw)
        self.base_start = len(self.pipe.base)
        self.pipe.grounding.tau = self.gp["tau"]
        self.pipe.lam = self.gp["llm_weight"]
        self.pipe.frame_T = self.gp["frame_temperature"]
        self.pipe.fluent_thr = self.fluent_thr
        (cx, ct, cph, ckeys), (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
        if SMOKE:  # val_select only: the held-out set is never touched
            n = int(os.environ.get("P1522_SMOKE_N", "120"))
            hx, ht, hph, hkeys = cx[n:n + 40], ct[n:n + 40], cph[n:n + 40], ckeys[n:n + 40]
            cx, ct, cph, ckeys = cx[:n], ct[:n], cph[:n], ckeys[:n]
            with_held = False
        self.cx, self.ct, self.cph = cx, ct, cph
        self.hx, self.ht, self.hkeys = hx, [norm(t) for t in ht], hkeys
        if with_held:
            p1405 = load_module("p1405run_p1522", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
            self.durs = p1405.t15_durations(hkeys)
            self.r1 = json.loads(R1_FILE.read_text(encoding="utf-8"))
            self.r2 = json.loads(R2_FILE.read_text(encoding="utf-8"))
        else:
            self.durs = [float(x.shape[0]) * 0.08 for x in hx]
            self.r1 = self.r2 = None
        from fidetype.adapters import b2t25 as Bm

        self.B = Bm
        self.provenance = K.provenance("m4-13")

    def misses(self) -> dict:
        return {"base_nbest_new_decodes": len(self.pipe.base) - self.base_start,
                "llm_texts_scored_live": self.lazy.texts_scored, "llm_loaded": self.lazy.llm is not None}


# ---------------------------------------------------------------------------
# one arm
# ---------------------------------------------------------------------------


def guard_path(name: str) -> Path:
    return OUT / f"guard-p15-22-t15-{name}.json"


def run_arm(c: Ctx, name: str) -> dict:
    done = OWN / f"arm-{name}.json"
    if done.exists():
        log(f"{name}: done before, loaded {done.name}")
        return json.loads(done.read_text(encoding="utf-8"))
    t0 = time.time()
    pipe = c.pipe

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(ARM_B1, np.asarray(lp, dtype=np.float32))

    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(c.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=0.08, decode_fn=fn, stream_texts=c.cph, decoder_name=f"p15-22-t15-{name}",
              modality="intracortical", name=f"p15-22-t15-{name}", seed=SEED, null_trials=NULL_TRIALS, **ARMS[name])
    try:
        guard = ft.calibrate(c.cx, c.ct, **kw)
    except ft.NullControlError as e:
        log(f"{name}: REFUSED {[x.to_dict() for x in e.report]}")
        res = {"status": "refused", "controls": [x.to_dict() for x in e.report], "message": str(e)}
        done.write_text(json.dumps(res), encoding="utf-8")
        return res
    T = guard.config.frame_temperature
    log(f"{name}: calibrated {guard.config_id} in {time.time() - t0:.0f} s; frame T {T:.6f}; threshold "
        f"{guard.sheet.commit_threshold}; controls {[(x.name, x.n_commit, x.allowed) for x in guard.sheet.controls]}; "
        f"misses {c.misses()}")
    rows = []
    for i, x in enumerate(c.hx):
        n0 = pipe.calls
        r = guard.decide(x, utterance_id=f"p15-22-{name}-{i}")
        assert pipe.calls == n0 + 1, "expected one decode per decision"
        items, base = pipe.last["items"], pipe.last["base"]
        nb = guard._last_nb
        top1 = norm(nb.candidates[0].text) if nb is not None and len(nb) else ""
        truth = c.ht[i]
        shown = r.text if r.action == "commit" else (r.choices[0] if r.action == "offer" and r.choices else None)
        bag = lattice_words(d["text"] for d in base)
        unsup = [w for w in F.wrong_hyp_words(truth, shown) if w not in bag] if shown else []
        rows.append({"i": i, "action": r.action, "raw": r.raw_action, "p_top1": r.p_top1, "score": r.commit_score,
                     "guard_risk": r.guard_risk, "text": r.text, "top1": top1,
                     "pipe_top1": norm(items[0]["text"]) if items else "", "truth": truth,
                     "complete": r.complete, "n_words_committed": r.n_words_committed,
                     "n_words_top1": r.event.get("n_words_top1", len(top1.split())),
                     "shown_words": len(shown.split()) if shown else 0, "unsupported_words": len(unsup),
                     "base_top1": norm(base[0]["text"]) if base else ""})
        if i % 100 == 99:
            guard.audit_log.clear()
    guard.audit_log.clear()
    wrong_texts = [r["text"] for r in rows if r["action"] == "commit" and not _right(r)]
    lps = pipe.scorer.score(wrong_texts) if wrong_texts else []
    fluent = [lp / max(1, len(t.split())) >= c.fluent_thr for lp, t in zip(lps, wrong_texts)]
    pipe.scorer.store.flush()
    pipe.save_base()
    guard.save(guard_path(name))
    res = {"status": "ok", "config_id": guard.config_id, "sheet": guard.sheet.to_dict(), "rows": rows,
           "frame_temperature": T, "fluent_wrong_commits": int(sum(fluent)), "n_wrong_commit_texts": len(wrong_texts),
           "seconds": round(time.time() - t0, 1), "misses_after": c.misses(), "peak_mb": round(peak_mb(), 1)}
    done.write_text(json.dumps(res), encoding="utf-8")
    log(f"{name}: decided {len(rows)} in {time.time() - t0:.0f} s total; fluent-wrong {res['fluent_wrong_commits']}; "
        f"peak {peak_mb():.0f} MB")
    return res


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def score_v02(rows: list[dict], sheet: dict, durs: list[float], reading: bool) -> dict:
    a = P524.trial_arrays(rows, "0.2")
    kw = dict(guarantee=guarantee_from_sheet(sheet), controls=controls_from_sheet(sheet), B=B, seed=SEED,
              timing="measured trial duration (20 ms neural bins)", metric_version="0.2",
              committed_words=a["committed_words"], complete=a["complete"], penalty_chars=a["penalty_chars"])
    if reading:
        kw.update(read_s_per_commit=READ_S_PER_COMMIT, read_s_per_word=READ_S_PER_WORD)
    else:  # the v0.2 of that date had no reading cost by default
        kw.update(read_s_per_commit=0.0, read_s_per_word=0.0)
    return safe_wpm(a["committed"], a["correct"], a["n_words"], a["n_chars"], durs, **kw)


def arrays_for(rows: list[dict], version: str, reading: bool = False, view: str = "all"):
    credit, wrong, pen = P524.credit_arrays(rows, version, view)
    if not reading:
        return credit, wrong, pen, np.zeros(len(rows))
    a = P524.trial_arrays(rows, version, view)
    cm = np.array(a["committed"])
    kw = np.array(a["committed_words"], float)
    kw = np.where(np.isfinite(kw), kw, np.array(a["n_words"], float))
    return credit, wrong, pen, np.where(cm, READ_S_PER_COMMIT + READ_S_PER_WORD * kw, 0.0)


def paired(ra: list[dict], rb: list[dict], durs: list[float], version: str, reading: bool = False,
           view_b: str = "all") -> dict:
    """Paired percentile trial bootstrap (decisions fixed) of safe WPM: B - A (seed 0, 2,000 resamples)."""
    ca, wa, pa, da_ = arrays_for(ra, version, reading)
    cb, wb, pb, db_ = arrays_for(rb, version, reading, view_b)
    ns = np.asarray(durs, float)

    def wpm(cr, wr, pen, rd, w):
        return 60.0 * (cr * w).sum() / ((ns * w).sum() + (np.where(wr, pen, 0.0) * w).sum() + (rd * w).sum())

    n = len(ns)
    rng = np.random.default_rng(SEED)
    xa, xb, dd = [], [], []
    for _ in range(B):
        w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        x, y = wpm(ca, wa, pa, da_, w), wpm(cb, wb, pb, db_, w)
        xa.append(x)
        xb.append(y)
        dd.append(y - x)
    one = np.ones(n)
    va, vb = wpm(ca, wa, pa, da_, one), wpm(cb, wb, pb, db_, one)
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]  # noqa: E731
    cd = ci(dd)
    return {"a": va, "b": vb, "diff": vb - va, "diff_ci95": cd, "diff_half_width": (cd[1] - cd[0]) / 2,
            "a_ci95": ci(xa), "b_ci95": ci(xb), "B": B, "seed": SEED, "version": version,
            "reading_cost": [READ_S_PER_COMMIT, READ_S_PER_WORD] if reading else None,
            "method": "paired percentile trial bootstrap, decisions fixed (conditional on the calibration)"}


def arm_metrics(res: dict, c: Ctx, name: str) -> dict:
    rows, sheet = res["rows"], res["sheet"]
    out = {"role": ROLE[name], "config_id": res["config_id"], "commit_threshold": sheet.get("commit_threshold"),
           "controls_sheet": sheet.get("controls"), "ltt_in_sample": [sheet.get("ltt_commits"),
                                                                        sheet.get("ltt_wrong_commits")],
           "confidence": sheet.get("confidence"), "frame_temperature": res["frame_temperature"],
           "frame_temperature_matches_ground_prep": abs(res["frame_temperature"] - c.gp["frame_temperature"]) < 1e-9,
           "seconds": res["seconds"], "peak_mb": res.get("peak_mb"), "misses_after": res.get("misses_after")}
    out["v0_1"] = P524.score(rows, sheet, c.durs, "0.1")
    out["v0_2"] = score_v02(rows, sheet, c.durs, reading=False)
    out["v0_2_reading"] = score_v02(rows, sheet, c.durs, reading=True)
    if name == "llm_prefix":
        out["v0_1_complete_only"] = P524.score(rows, sheet, c.durs, "0.1", view="complete")
    cm = np.array([r["action"] == "commit" for r in rows])
    exact = np.array([r["top1"] == r["truth"] for r in rows])
    n_wrong = sum(1 for r in rows if r["action"] == "commit" and not _right(r))
    shown = sum(r["shown_words"] for r in rows)
    unsup = sum(r["unsupported_words"] for r in rows)
    out.update({
        "n": len(rows), "n_commit": int(cm.sum()), "n_wrong_commit": n_wrong,
        "wrong_commit_rate": n_wrong / len(rows), "wrong_commit_cp95": F.cp(n_wrong, len(rows)),
        "error_among_commits": n_wrong / int(cm.sum()) if cm.sum() else None,
        "top1_exact": float(exact.mean()), "n_top1_exact": int(exact.sum()),
        "recall_of_exact": float((cm & exact).sum() / max(1, exact.sum())),
        "top1_equals_pipeline_top1": int(sum(r["top1"] == r["pipe_top1"] for r in rows)),
        "auroc_p_top1": auroc(np.array([r["p_top1"] for r in rows], float), exact),
        "fluent_wrong_commits": res["fluent_wrong_commits"],
        "fluent_wrong_rate": res["fluent_wrong_commits"] / len(rows),
        "fluent_wrong_cp95": F.cp(res["fluent_wrong_commits"], len(rows)),
        "shown_words": shown, "unsupported_words": unsup, "hallucination_rate": unsup / shown if shown else 0.0,
        "wer_top1": F.wer(c.ht, [r["top1"] for r in rows]),
    })
    if name != "llm_prefix":
        sc = np.array([r["score"] if r["score"] is not None else r["p_top1"] for r in rows], float)
        out["auroc_commit_score"] = auroc(sc, exact)
    else:
        ks = [r["n_words_committed"] for r in rows if r["action"] == "commit"]
        out.update({"commit_words_hist": {str(k): ks.count(k) for k in sorted(set(ks))},
                    "mean_words_per_commit": float(np.mean(ks)) if ks else None,
                    "n_complete_commits": sum(1 for r in rows if r["action"] == "commit" and r["complete"])})
    return out


def _right(r: dict) -> bool:
    """Right commit: the whole truth (sentence commit) or the first k words of the truth (prefix commit)."""
    full = True if r.get("complete") is None else bool(r["complete"])
    t, y = norm(r["text"]).split(), r["truth"].split()
    return t == y if full else (len(y) >= len(t) and y[:len(t)] == t)


def stage_t15() -> dict:
    t0 = time.time()
    c = Ctx()
    log(f"t15: calibration {len(c.cx)}, evaluation {len(c.hx)}, smoke {SMOKE}; caches {c.cache_info}; "
        f"peak {peak_mb():.0f} MB")
    out: dict = {"provenance": c.provenance, "caches": c.cache_info, "ground_prep": c.gp,
                 "fluent_threshold": c.fluent_thr, "arms": {}}
    if not SMOKE:
        sh = P523.split_hashes(len(c.cx))
        out["split"] = sh
        assert (sh["score_fit_sha"], sh["certify_sha"]) == SPLIT_SHA, f"split differs from P5-23: {sh}"
        rc = {"r1_same_truth": sum(a["truth"] == b for a, b in zip(c.r1, c.ht)),
              "r2_same_truth": sum(a["truth"] == b for a, b in zip(c.r2, c.ht)), "n": len(c.ht)}
        out["row_check"] = rc
        assert rc["r1_same_truth"] == rc["r2_same_truth"] == len(c.ht) == len(c.r1) == len(c.r2), rc
        log(f"t15: split {sh['score_fit_sha']} / {sh['certify_sha']}; row check {rc}")
    res = {}
    for name in ARMS:
        res[name] = run_arm(c, name)
        if res[name]["status"] != "ok":
            out["arms"][name] = {k: v for k, v in res[name].items() if k != "rows"}
            continue
        out["arms"][name] = arm_metrics(res[name], c, name)
        log(f"t15 {name} v0.1: {format_line(out['arms'][name]['v0_1'])}")
        log(f"t15 {name} v0.2: {format_line(out['arms'][name]['v0_2'])}")
    ok = {a for a in ARMS if res[a]["status"] == "ok"}
    if "llm" in ok and not SMOKE:  # reference check: the committed P15-05 M4-13 B1 decisions
        ref = json.loads((SRC5 / "trials-t15-B1_rescore_G.json").read_text(encoding="utf-8"))["decisions"]
        same = sum(a["action"] == r["action"] and norm(a["text"]) == norm(r["text"])
                   for a, r in zip(res["llm"]["rows"], ref))
        out["reference_check_llm"] = {"same_action_and_text": same, "n": len(ref),
                                      "ref_commits": sum(r["action"] == "commit" for r in ref)}
        log(f"t15: L0 vs committed P15-05 M4-13 B1 decisions: {same}/{len(ref)}")
    if not SMOKE:
        pr = {}
        rows = {a: res[a]["rows"] for a in ok}
        if "llm_learned" in ok:
            pr["H1_llm_learned_vs_p5_23_learned_v0_1"] = paired(c.r1, rows["llm_learned"], c.durs, "0.1")
            if "llm" in ok:
                pr["H2_llm_learned_vs_llm_v0_1"] = paired(rows["llm"], rows["llm_learned"], c.durs, "0.1")
        if "llm" in ok:
            pr["llm_vs_p5_23_learned_v0_1"] = paired(c.r1, rows["llm"], c.durs, "0.1")
        if "llm_prefix" in ok:
            pr["llm_prefix_vs_p5_24_prefix_v0_2_reading"] = paired(c.r2, rows["llm_prefix"], c.durs, "0.2", True)
            pr["llm_prefix_vs_p5_24_prefix_v0_2"] = paired(c.r2, rows["llm_prefix"], c.durs, "0.2")
            if "llm_learned" in ok:
                pr["llm_prefix_vs_llm_learned_v0_2_reading"] = paired(rows["llm_learned"], rows["llm_prefix"],
                                                                      c.durs, "0.2", True)
        # consistency: the bootstrap point values equal the safe_wpm values
        chk = {}
        for k, v in pr.items():
            arm = "llm_learned" if k.startswith("H") else k.split("_vs_")[0]
            if arm in out["arms"] and "v0_1" in out["arms"][arm]:
                blk = out["arms"][arm]["v0_2_reading" if v["reading_cost"] else
                                       ("v0_1" if v["version"] == "0.1" else "v0_2")]
                chk[k] = abs(blk["value"] - v["b"]) < 1e-9
        pr["point_value_check"] = chk
        out["paired"] = pr
        for k, v in pr.items():
            if k != "point_value_check":
                log(f"t15 paired {k}: {v['a']:.3f} -> {v['b']:.3f}, diff {v['diff']:+.3f} {v['diff_ci95']}")
    out["misses"] = c.misses()
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


# ---------------------------------------------------------------------------
# hallucination protocol 0.2 check
# ---------------------------------------------------------------------------


def stage_halluc() -> dict:
    from fidetype.benchmark import hallucination as HB

    t0 = time.time()
    c = Ctx(with_held=False) if SMOKE else Ctx()
    xs, ts = c.hx, c.ht
    ids = [f"{k.split('|')[0]}|val|{k.split('|')[2]}" for k in c.hkeys]
    n_null = 20 if SMOKE else NULL_TRIALS
    ctl = HB.make_controls(xs, ts, seed=F.SEED, n_null=n_null, vocab_size=len(c.B.SYMBOL_VOCAB))
    out: dict = {"n_real": len(xs), "n_null": n_null, "systems": {}}
    if not SMOKE:
        probs = [p for p in HB.verify_split(json.loads(SPLIT_V01.read_text(encoding="utf-8")), ids, ts, ctl)
                 if not p.startswith("warning")]
        assert not probs, f"held-out set differs from the committed v0.1 T15 split: {probs}"
        out["split_check"] = "same trials, null indices and swap permutation as the committed v0.1 T15 split"
    hdir = OUT / "halluc"
    hdir.mkdir(parents=True, exist_ok=True)
    pipe = c.pipe
    for name in ARMS:
        gp = guard_path(name)
        if not gp.exists():
            out["systems"][name] = {"status": "no guard"}
            continue
        guard = ft.load(gp, decode_fn=lambda lp: pipe.run(ARM_B1, np.asarray(lp, dtype=np.float32)))
        T = guard.config.frame_temperature
        state = {"i": None}
        sguard = ft.load(gp, decode_fn=lambda lp: pipe.run(ARM_B1, np.asarray(lp, dtype=np.float32),
                                                           lang_x=F.temper(xs[state["i"]], T)))

        def decide_swapped(x, i, sguard=sguard, state=state):
            state["i"] = i
            return sguard.decide(x, utterance_id="swapped")

        recs = HB.run_tracks(lambda x, g=guard: g.decide(x, utterance_id="p15-22-real"), xs, ts, controls=ctl,
                             decide_swapped=decide_swapped)
        guard.audit_log.clear()
        sguard.audit_log.clear()
        committed = sorted({r.text for r in recs if r.committed and r.text})
        pipe.scorer.score(committed)  # fill the fluency table (lazy LLM on a miss)
        pipe.scorer.store.flush()
        with open(OWN / f"halluc-records-{name}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps({"track": r.track, "item": r.item, "signal": r.signal_trial,
                                    "language": r.language_trial, "action": r.action, "text": r.text,
                                    "truth": r.truth}) + "\n")
        sw = [r for r in recs if r.track == "swapped"]
        sw_unsup = sum(1 for r in sw if r.committed and norm(r.text) != norm(r.truth))
        row = {"status": "ok", "guard_config_id": guard.config_id,
               "swapped_unsupported_commits": sw_unsup, "swapped_n": len(sw),
               "swapped_unsupported_rate": sw_unsup / len(sw) if sw else None,
               "swapped_unsupported_cp95": F.cp(sw_unsup, len(sw)) if sw else None}
        if name == "llm_prefix":
            row["note"] = "descriptive only: the protocol counts a right prefix commit as a wrong commit"
        for mode, fl in (("llm", HB.TableFluency(pipe.scorer.store, c.fluent_thr,
                                                 name="Qwen2.5-1.5B-Instruct Q4_K_M (P15-22 cache)")),
                         ("conservative", HB.ConservativeFluency())):
            oc = HB.to_outcomes(recs, fl, dataset=DATASET, system=f"p15-22-{name}",
                                meta={"guard_config_id": guard.config_id, "description": ROLE[name],
                                      "decoder": "M4-13 long0", "seed": F.SEED})
            card = HB.score_outcomes(oc, alpha_wrong=0.05, alpha_fluent=0.01)
            stem = f"{DATASET}--p15-22-{name}--{mode}"
            (hdir / f"{stem}.outcomes.json").write_text(json.dumps(oc, indent=0) + "\n", encoding="utf-8")
            (hdir / f"{stem}.card.json").write_text(json.dumps(card, indent=1, default=str) + "\n", encoding="utf-8")
            swc = card["tracks"]["swapped"]
            row[mode] = {"summary": HB.summary_line(card), "controls_verdict": card.get("controls_verdict"),
                         "swapped_verdict": swc.get("verdict"), "paired": swc.get("paired"),
                         "null": {k: card["tracks"]["null"].get(k) for k in ("commits", "n", "verdict")},
                         "scrambled": {k: card["tracks"]["scrambled"].get(k) for k in ("commits", "n", "verdict")},
                         "fluency": fl.describe()}
            log(f"halluc {name} [{mode}]: {row[mode]['summary']}")
        out["systems"][name] = row
    out["misses"] = c.misses()
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


# ---------------------------------------------------------------------------
# pre-registered decision rule (plan.md)
# ---------------------------------------------------------------------------


def verdict_rule(l1: dict, p: dict | None) -> str:
    if l1.get("status") == "refused":
        return "L1 fails a control (refused)"
    if l1["v0_1"]["measured_wrong_commit"] > ALPHA:
        return "L1 fails safety"
    if not bool((l1["v0_1"].get("controls") or {}).get("passed")):
        return "L1 fails a control"
    d, hw = p["diff"], p["diff_half_width"]
    if d > hw:
        return "L1 beats the other"
    if d < -hw:
        return "the other beats L1"
    return "no clear difference"


def stage_verdict() -> dict:
    allr = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    st = (allr.get("stages") or {}).get("t15", {}).get("result")
    if not st:
        return {"verdict": "t15 not run"}
    arms, pr = st["arms"], st.get("paired", {})
    l1 = arms.get("llm_learned", {"status": "missing"})
    out: dict = {}
    if l1.get("status") in ("refused", "missing"):
        out["H1"] = out["H2"] = {"verdict": "L1 fails a control (refused)" if l1.get("status") == "refused"
                                 else "L1 missing"}
    else:
        for h, key in (("H1", "H1_llm_learned_vs_p5_23_learned_v0_1"), ("H2", "H2_llm_learned_vs_llm_v0_1")):
            p = pr.get(key)
            out[h] = {"verdict": verdict_rule(l1, p) if p else "not computed", "comparison": key,
                      **({k: p[k] for k in ("a", "b", "diff", "diff_ci95", "diff_half_width")} if p else {})}
        v = l1["v0_1"]
        lo = (pr.get("H1_llm_learned_vs_p5_23_learned_v0_1") or {}).get("b_ci95", [math.nan])[0]
        certified = v.get("status") == "certified"
        ctl = bool((v.get("controls") or {}).get("passed"))
        above = isinstance(v.get("value"), float) and v["value"] > NO_BCI_T15
        out["P14_23"] = {"l1_v0_1": v.get("value"), "l1_ci95": (pr.get("H1_llm_learned_vs_p5_23_learned_v0_1")
                                                                or {}).get("b_ci95"),
                         "certified": certified, "controls_pass": ctl, "above_4_02": above,
                         "ci_lower_above_4_02": bool(lo > NO_BCI_T15),
                         "closes_gap_53": bool(certified and ctl and above),
                         "l0_v0_1_reported_only": (arms.get("llm", {}).get("v0_1") or {}).get("value")}
    for h in ("H1", "H2", "P14_23"):
        log(f"verdict {h}: {out.get(h)}")
    return out


def stage_smoke() -> dict:
    assert SMOKE, "set P1522_SMOKE=1 (val_select subsets only)"
    out = stage_t15()
    out["halluc"] = stage_halluc()
    return out


STAGES = {"t15": stage_t15, "halluc": stage_halluc, "verdict": stage_verdict, "smoke": stage_smoke}


def main() -> None:
    args = sys.argv[1:] or ["all"]
    stages = ["t15", "halluc", "verdict"] if args == ["all"] else args
    bad = [s for s in stages if s not in STAGES]
    if bad:
        raise SystemExit(f"unknown stage(s) {bad}; known: {list(STAGES)} or all")
    OUT.mkdir(parents=True, exist_ok=True)
    OWN.mkdir(parents=True, exist_ok=True)
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = FT_VERSION
    allr["plan"] = "plan.md (pre-registration, commit 7557b54)"
    allr.setdefault("stages", {})
    from fidetype.benchmark.scoring import to_jsonable
    from fidetype.utils.power import keep_awake

    with keep_awake(log=log):
        for st in stages:
            t0 = time.time()
            log(f"stage {st} start")
            out = STAGES[st]()
            allr["stages"][st] = {"seconds": round(time.time() - t0, 1), "result": out}
            path.write_text(json.dumps(to_jsonable(allr), indent=1, default=str) + "\n", encoding="utf-8")
            log(f"stage {st} done in {time.time() - t0:.0f} s")
    if args == ["all"] and not SMOKE:
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        log("all stages done; DONE written")


if __name__ == "__main__":
    main()
