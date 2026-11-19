"""P15-26: replication of the P15-22 headline (LLM rescoring + learned commit confidence).
Pre-registered: plan.md (commit 39e9419). CPU only, our own code (Apache-2.0).

Stages (one process each; resumable: finished arms and units are saved in the derived folder and skipped):
  t12      part (b): T12 v2, calibration pool 480 -> test sessions 400; arms L0, L1, L2 + hallucination protocol 0.2
  c0       code check: the P15-22 split (val_select -> val_eval, seed 0) with the refit steps; must reproduce P15-22
  c1 c2 c3 part (a): T15 calibration draws (calibrate seed 1, 2, 3), val_eval 701; arms R1', L0, L1 + protocol 0.2 (L1)
  p1       part (a): T15 pooled draw (722 calibration / 701 evaluation of the 1,423 validation trials), seed 0
  verdict  the pre-registered decision rules (no data access)
  smoke    calibration subsets only (P1526_SMOKE=1); never reads an evaluation set

Run (repo root): launch.py (detached chain of all stages), or one stage in the foreground:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-19-p15-26-replication/run.py c1
Per-trial files (with text) and caches: C:/Users/zhang/bci-data/derived/p15-26/ only. Repo: aggregates + guard files.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))

import common as K  # noqa: E402

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import format_line  # noqa: E402
from fidetype.lm.llm import CachedRewriter, CachedScorer, lattice_words  # noqa: E402

DER = K.DER
SMOKE = os.environ.get("P1526_SMOKE", "0") == "1"
STUB = SMOKE and os.environ.get("P1526_STUB_LLM", "0") == "1"  # smoke tests only: a fake LLM, no model load
OWN_ROOT = DER / "p15-26"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-26"
ROOT = OWN_ROOT / "smoke" if SMOKE else OWN_ROOT
OUT = ROOT / "results-smoke" if SMOKE else HERE / "results"  # smoke output never goes into the repo
LOGF = OUT / "run.log"
PLAN = "plan.md (pre-registration, commit 39e9419)"

# READ ONLY sources
P1522_OWN = DER / "p15-22"  # P15-22 caches (superset of the P15-05 / P15-06 M4-13 caches) and arm rows
SRC_T12 = DER / "f2-e3-llm-grounding" / "t12"  # P15-05 T12 caches, guards, trials
SRC_T12_P606 = DER / "f2-reruns-m4-13" / "p15-06-t12-single"  # P15-06 T12 LLM cache
M413_RES = REPO / "experiments/2026-11-17-f2-m4-13/results/results-t15.json"
T12_RES = REPO / "experiments/2026-11-16-f2-e3-llm-grounding/results/results-t12.json"
R1_T15 = DER / "p5-23" / "decisions-p5-23-t15-m4-13-learned.json"
R1_T12 = DER / "p5-23" / "decisions-p5-23-t12-v2-learned.json"
R2_T12 = DER / "p5-24" / "decisions-p5-24-t12-v2-prefix.json"
SPLIT_T15 = REPO / "src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json"
SPLIT_T12 = REPO / "src/fidetype/benchmark/splits/halluc-v0.1/b2t24-t12-test.json"

ALPHA, DELTA = 0.05, 0.1
NULL_TRIALS = 20 if SMOKE else 300
NO_BCI = {"t15_val_eval": 4.0153, "t15_p1": 4.0005, "t12": 4.11}  # plan.md (fixed before any result)

A0 = {"rescore": False, "rewrite": None, "ground": False}  # P15-05 arm A0: the base n-gram n-best
ARM_DEF = {
    "ngram_learned": (A0, {"confidence": "learned"}),
    "llm": (None, {}),  # None = arm B1 (filled below)
    "llm_learned": (None, {"confidence": "learned"}),
    "llm_prefix": (None, {"confidence": "learned", "commit_unit": "prefix"}),
}
ROLE = {"ngram_learned": "R1' (n-gram n-best + learned score: the P5-23 guard on this calibration)",
        "llm": "L0 (LLM arm alone, p_top1)", "llm_learned": "L1 (primary: LLM + learned score)",
        "llm_prefix": "L2 (secondary: LLM + learned prefix score)"}

# pre-registered draws (plan.md)
DRAWS = {
    "c0": {"seed": 0, "pool": None, "sha": ("285b8c0d9baf5a41", "fadfd84557fcb24b")},
    "c1": {"seed": 1, "pool": None, "sha": ("bcbc9f41affce5a0", "7301b55487e33bc9")},
    "c2": {"seed": 2, "pool": None, "sha": ("6c4953f83f65f929", "6c389cf380dd30c7")},
    "c3": {"seed": 3, "pool": None, "sha": ("d8f686737ff07fa5", "713099bd5a9ac403")},
    "p1": {"seed": 0, "pool": "p15-26|t15|pool|p1", "sha": ("8fdc279ebbb6e526", "186ba508a9fa6aef"),
           "pool_sha": ("3d0342243119a38c", "597f37bd70ec02f1"), "pool_seed": 11118116894105730765},
}
T12_SHA = ("630db9ca864af56f", "3fe1b31e8e46a035")
C0_EXPECT = {"frame_temperature": 2.37015800035291, "tau": 0.06996627059278283, "llm_weight": 1.0,
             "fluent": -7.88165954200173}


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


# P15-22 (pure helpers only: metrics, paired bootstrap, decision rule), P15-05 (Pipeline, ground prep), P5-23
P22 = load_module("p1522run_p1526", REPO / "experiments/2026-11-19-p15-22-llm-learned/run.py")
F, P523, P524 = P22.F, P22.P523, P22.P524
F.log = log  # P15-05 stage_prep / stage_ground_prep must log here, never into the P15-05 log
P22.ROLE.update(ROLE)  # in memory only: arm_metrics looks the role up by name
norm, _right = P22.norm, P22._right
ARM_B1 = P22.ARM_B1
for _k in ("llm", "llm_learned", "llm_prefix"):
    ARM_DEF[_k] = (ARM_B1, ARM_DEF[_k][1])


def peak_mb() -> float:
    return P22.peak_mb()


def h16(v) -> str:
    return hashlib.sha256(json.dumps(sorted(int(x) for x in v)).encode()).hexdigest()[:16]


def split_hashes(n: int, seed: int, base: list[int] | None = None) -> tuple[str, str]:
    """SHA-256 (first 16 hex) of the sorted score-fit and certify positions of calibrate's split (seed)."""
    from fidetype.trust.dropin import _split

    o = np.random.default_rng(seed).permutation(n)
    a, b, _c = _split(n)
    pos = np.arange(n) if base is None else np.asarray(base)
    return h16(pos[o[:a + b]]), h16(pos[o[a + b:]])


def no_bci(texts: list[str]) -> float:
    """Gaze typing of every sentence at 20 chars/min (the P14-05 / docs/safe-wpm.md no-BCI reference)."""
    return 20.0 * sum(len(t.split()) for t in texts) / sum(len(t) for t in texts)


# ---------------------------------------------------------------------------
# LLM and caches (copies in our folder; the originals stay read only)
# ---------------------------------------------------------------------------


class LazyLLM:
    """The P15-05 LLM, loaded on the CPU only at the first cache miss."""

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
            log("LLM cache miss: loading Qwen2.5-1.5B on the CPU (CPU wheel)")
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


def merged_llm_cache(dst: Path, sources: list[Path]) -> int:
    """Copy the first source and INSERT OR IGNORE the others into ``dst`` (once). Returns the number of scores."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        tmp = dst.with_suffix(".tmp")
        shutil.copy2(sources[0], tmp)
        con = sqlite3.connect(f"file:{tmp.as_posix()}", uri=True)
        for t in ("scores", "rewrites"):
            con.execute(f"CREATE TABLE IF NOT EXISTS {t} (k TEXT PRIMARY KEY, v TEXT)")
        for src in sources[1:]:
            if not src.exists():
                continue
            con.execute(f"ATTACH DATABASE 'file:{src.as_posix()}?mode=ro' AS s")
            have = {r[0] for r in con.execute("SELECT name FROM s.sqlite_master WHERE type='table'")}
            for t in ("scores", "rewrites"):
                if t in have:
                    con.execute(f"INSERT OR IGNORE INTO {t} SELECT k, v FROM s.{t}")
            con.commit()
            con.execute("DETACH DATABASE s")
        con.commit()
        con.close()
        tmp.replace(dst)
    con = sqlite3.connect(f"file:{dst.as_posix()}?mode=ro", uri=True)
    n = con.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    con.close()
    return int(n)


def make_pipe(name: str, own: Path, dec, cache: Path, base_seed: Path | None):
    """A P15-05 Pipeline whose base n-best cache lives in ``own`` (seeded from ``base_seed`` once)."""
    own.mkdir(parents=True, exist_ok=True)
    if base_seed is not None and not (own / f"base-nbest-{name}.pkl").exists():
        shutil.copy2(base_seed, own / f"base-nbest-{name}.pkl")
    F.OWN = own  # the P15-05 Pipeline keeps its base n-best cache in F.OWN
    lazy = LazyLLM()
    sc = CachedScorer(lazy, F.DiskDict(cache, "scores"))
    rw = CachedRewriter(lazy, F.DiskDict(cache, "rewrites"))
    pipe = F.Pipeline(name, dec, sc, rw)
    return pipe, lazy


# ---------------------------------------------------------------------------
# one arm (as P15-22 run_arm, with the unit folder and the decode arm as parameters)
# ---------------------------------------------------------------------------


def run_arm(u: SimpleNamespace, name: str) -> dict:
    done = u.own / f"arm-{name}.json"
    if done.exists():
        log(f"{u.name} {name}: done before, loaded {done.name}")
        return json.loads(done.read_text(encoding="utf-8"))
    t0 = time.time()
    pipe = u.pipe
    arm, extra = ARM_DEF[name]

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    kw = dict(alpha=ALPHA, delta=DELTA, vocab=list(u.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
              frame_period=0.08, decode_fn=fn, stream_texts=u.cph, decoder_name=f"p15-26-{u.name}-{name}",
              modality="intracortical", name=f"p15-26-{u.name}-{name}", seed=u.seed, null_trials=NULL_TRIALS,
              **extra)
    try:
        guard = ft.calibrate(u.cx, u.ct, **kw)
    except ft.NullControlError as e:
        log(f"{u.name} {name}: REFUSED {[x.to_dict() for x in e.report]}")
        res = {"status": "refused", "controls": [x.to_dict() for x in e.report], "message": str(e)}
        done.write_text(json.dumps(res), encoding="utf-8")
        return res
    T = guard.config.frame_temperature
    log(f"{u.name} {name}: calibrated {guard.config_id} in {time.time() - t0:.0f} s; frame T {T:.6f}; threshold "
        f"{guard.sheet.commit_threshold}; controls {[(x.name, x.n_commit, x.allowed) for x in guard.sheet.controls]}; "
        f"misses {misses(u)}")
    rows = []
    for i, x in enumerate(u.hx):
        n0 = pipe.calls
        r = guard.decide(x, utterance_id=f"p15-26-{u.name}-{name}-{i}")
        assert pipe.calls == n0 + 1, "expected one decode per decision"
        items, base = pipe.last["items"], pipe.last["base"]
        nb = guard._last_nb
        top1 = norm(nb.candidates[0].text) if nb is not None and len(nb) else ""
        truth = u.ht[i]
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
            pipe.save_base()
    guard.audit_log.clear()
    wrong_texts = [r["text"] for r in rows if r["action"] == "commit" and not _right(r)]
    lps = pipe.scorer.score(wrong_texts) if wrong_texts else []
    fluent = [lp / max(1, len(t.split())) >= u.fluent_thr for lp, t in zip(lps, wrong_texts)]
    pipe.scorer.store.flush()
    pipe.save_base()
    guard.save(guard_path(u, name))
    res = {"status": "ok", "config_id": guard.config_id, "sheet": guard.sheet.to_dict(), "rows": rows,
           "frame_temperature": T, "fluent_wrong_commits": int(sum(fluent)), "n_wrong_commit_texts": len(wrong_texts),
           "seconds": round(time.time() - t0, 1), "misses_after": misses(u), "peak_mb": round(peak_mb(), 1)}
    done.write_text(json.dumps(res), encoding="utf-8")
    log(f"{u.name} {name}: decided {len(rows)} in {time.time() - t0:.0f} s total; fluent-wrong "
        f"{res['fluent_wrong_commits']}; peak {peak_mb():.0f} MB")
    return res


def guard_path(u: SimpleNamespace, name: str) -> Path:
    return OUT / f"guard-p15-26-{u.name}-{name}.json"


def misses(u: SimpleNamespace) -> dict:
    return {"base_nbest_new_decodes": len(u.pipe.base) - u.base_start, "llm_texts_scored_live": u.lazy.texts_scored,
            "llm_loaded": u.lazy.llm is not None}


# ---------------------------------------------------------------------------
# hallucination protocol 0.2 (as P15-22 stage_halluc, for the given arms of one unit)
# ---------------------------------------------------------------------------


def run_halluc(u: SimpleNamespace, names: list[str]) -> dict:
    from fidetype.benchmark import hallucination as HB

    path = u.own / "halluc.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t0 = time.time()
    xs, ts = u.hx, u.ht
    ctl = HB.make_controls(xs, ts, seed=F.SEED, n_null=NULL_TRIALS, vocab_size=len(u.B.SYMBOL_VOCAB))
    out: dict = {"n_real": len(xs), "n_null": NULL_TRIALS, "dataset": u.dataset, "systems": {}}
    if u.split_file is not None:
        probs = [p for p in HB.verify_split(json.loads(u.split_file.read_text(encoding="utf-8")), u.ids, ts, ctl)
                 if not p.startswith("warning")]
        assert not probs, f"held-out set differs from the committed split {u.split_file.name}: {probs}"
        out["split_check"] = f"same trials, null indices and swap permutation as {u.split_file.name}"
    else:
        out["split_check"] = "no committed split for this evaluation set: make_controls seed 0 (plan.md)"
    hdir = OUT / "halluc"
    hdir.mkdir(parents=True, exist_ok=True)
    pipe = u.pipe
    for name in names:
        gp = guard_path(u, name)
        if not gp.exists():
            out["systems"][name] = {"status": "no guard"}
            continue
        arm = ARM_DEF[name][0]
        guard = ft.load(gp, decode_fn=lambda lp, arm=arm: pipe.run(arm, np.asarray(lp, dtype=np.float32)))
        T = guard.config.frame_temperature
        state = {"i": None}
        sguard = ft.load(gp, decode_fn=lambda lp, arm=arm: pipe.run(arm, np.asarray(lp, dtype=np.float32),
                                                                    lang_x=F.temper(xs[state["i"]], T)))

        def decide_swapped(x, i, sguard=sguard, state=state):
            state["i"] = i
            return sguard.decide(x, utterance_id="swapped")

        recs = HB.run_tracks(lambda x, g=guard: g.decide(x, utterance_id="p15-26-real"), xs, ts, controls=ctl,
                             decide_swapped=decide_swapped)
        guard.audit_log.clear()
        sguard.audit_log.clear()
        committed = sorted({r.text for r in recs if r.committed and r.text})
        pipe.scorer.score(committed)  # fill the fluency table (lazy LLM on a miss)
        pipe.scorer.store.flush()
        pipe.save_base()
        with open(u.own / f"halluc-records-{name}.jsonl", "w", encoding="utf-8") as f:
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
        for mode, fl in (("llm", HB.TableFluency(pipe.scorer.store, u.fluent_thr,
                                                 name="Qwen2.5-1.5B-Instruct Q4_K_M (P15-26 cache)")),
                         ("conservative", HB.ConservativeFluency())):
            oc = HB.to_outcomes(recs, fl, dataset=u.dataset, system=f"p15-26-{u.name}-{name}",
                                meta={"guard_config_id": guard.config_id, "description": ROLE[name],
                                      "unit": u.name, "seed": F.SEED})
            card = HB.score_outcomes(oc, alpha_wrong=0.05, alpha_fluent=0.01)
            stem = f"{u.dataset}--p15-26-{u.name}-{name}--{mode}"
            (hdir / f"{stem}.outcomes.json").write_text(json.dumps(oc, indent=0) + "\n", encoding="utf-8")
            (hdir / f"{stem}.card.json").write_text(json.dumps(card, indent=1, default=str) + "\n", encoding="utf-8")
            swc = card["tracks"]["swapped"]
            row[mode] = {"summary": HB.summary_line(card), "controls_verdict": card.get("controls_verdict"),
                         "swapped_verdict": swc.get("verdict"), "paired": swc.get("paired"),
                         "null": {k: card["tracks"]["null"].get(k) for k in ("commits", "n", "verdict")},
                         "scrambled": {k: card["tracks"]["scrambled"].get(k) for k in ("commits", "n", "verdict")},
                         "fluency": fl.describe()}
            log(f"{u.name} halluc {name} [{mode}]: {row[mode]['summary']}")
        out["systems"][name] = row
    out["seconds"] = round(time.time() - t0, 1)
    out["misses_after"] = misses(u)
    from fidetype.benchmark.scoring import to_jsonable

    path.write_text(json.dumps(to_jsonable(out), default=str), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------


def finish_unit(u: SimpleNamespace, res: dict, arms: list[str], pairs: list[tuple], extra: dict) -> dict:
    """Metrics per arm (P15-22 arm_metrics), paired comparisons (P15-22 paired), unit summary (no text)."""
    ctx = SimpleNamespace(durs=u.durs, gp={"frame_temperature": u.T}, ht=u.ht)
    out = {"unit": u.name, **extra, "arms": {}, "paired": {}}
    for name in arms:
        if res[name]["status"] != "ok":
            out["arms"][name] = {k: v for k, v in res[name].items() if k != "rows"}
            continue
        out["arms"][name] = P22.arm_metrics(res[name], ctx, name)
        log(f"{u.name} {name} v0.1: {format_line(out['arms'][name]['v0_1'])}")
    for key, ra, rb, version, reading in pairs:
        if ra is None or rb is None:
            continue
        p = P22.paired(ra, rb, u.durs, version, reading)
        out["paired"][key] = p
        log(f"{u.name} paired {key}: {p['a']:.3f} -> {p['b']:.3f}, diff {p['diff']:+.3f} {p['diff_ci95']}")
    out["misses"] = misses(u)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


def rows_of(res: dict) -> list[dict] | None:
    return res["rows"] if res.get("status") == "ok" else None


def t15_unit(name: str) -> dict:
    """Part (a): one T15 draw (or the c0 code check)."""
    from fidetype.adapters import b2t25 as Bm

    d = DRAWS[name]
    own = ROOT / name
    own.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    (cx, ct, cph, ckeys), (hx, ht, hph, hkeys) = K.load_t15("m4-13", norm_text=True, with_keys=True)
    extra: dict = {"draw": name, "calibrate_seed": d["seed"]}
    if SMOKE:  # calibration subsets only: the evaluation sets are never read
        n = int(os.environ.get("P1526_SMOKE_N", "120"))
        hx, ht, hph, hkeys = cx[n:n + 40], ct[n:n + 40], cph[n:n + 40], ckeys[n:n + 40]
        cx, ct, cph, ckeys = cx[:n], ct[:n], cph[:n], ckeys[:n]
        ref_key = None
    elif d["pool"] is None:
        sh = split_hashes(len(cx), d["seed"])
        extra["split"] = {"score_fit_sha": sh[0], "certify_sha": sh[1]}
        assert sh == d["sha"], f"{name}: split differs from plan.md: {sh}"
        ref_key = "t15_val_eval"
    else:
        X, Tt, Ph, Ks = cx + hx, ct + ht, cph + hph, ckeys + hkeys
        seed = int(hashlib.sha256(d["pool"].encode()).hexdigest()[:16], 16)
        assert seed == d["pool_seed"], seed
        perm = np.random.default_rng(seed).permutation(len(X))
        ci, ei = sorted(perm[:722].tolist()), sorted(perm[722:].tolist())
        assert (h16(ci), h16(ei)) == d["pool_sha"], f"{name}: pool split differs from plan.md"
        sh = split_hashes(len(ci), d["seed"], ci)
        assert sh == d["sha"], f"{name}: inner split differs from plan.md: {sh}"
        extra["split"] = {"pool_cal_sha": h16(ci), "pool_eval_sha": h16(ei), "score_fit_sha": sh[0],
                          "certify_sha": sh[1], "cal_from_val_select": sum(i < 722 for i in ci),
                          "eval_from_val_select": sum(i < 722 for i in ei)}
        cx, ct, cph, ckeys = [X[i] for i in ci], [Tt[i] for i in ci], [Ph[i] for i in ci], [Ks[i] for i in ci]
        hx, ht, hph, hkeys = [X[i] for i in ei], [Tt[i] for i in ei], [Ph[i] for i in ei], [Ks[i] for i in ei]
        ref_key = "t15_p1"
    ht = [norm(t) for t in ht]
    if SMOKE:
        durs = [float(x.shape[0]) * 0.08 for x in hx]
    else:
        p1405 = load_module("p1405run_p1526", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
        durs = p1405.t15_durations(hkeys)
    cache = ROOT / "llm-cache-t15.sqlite"
    n_cached = merged_llm_cache(cache, [P1522_OWN / "llm-cache.sqlite"])
    dec, _bt = K.word_decoder()
    pipe, lazy = make_pipe("t15", own, dec, cache, P1522_OWN / "base-nbest-t15.pkl" if name == "c0" else None)
    ids = [f"{k.split('|')[0]}|val|{k.split('|')[2]}" for k in hkeys]
    u = SimpleNamespace(name=name, own=own, pipe=pipe, lazy=lazy, base_start=len(pipe.base), B=Bm, seed=d["seed"],
                        cx=cx, ct=ct, cph=cph, hx=hx, ht=ht, durs=durs, ids=ids, T=None, fluent_thr=None,
                        dataset="b2t25-t15-val-eval" if d["pool"] is None else "b2t25-t15-p15-26-p1",
                        split_file=SPLIT_T15 if (d["pool"] is None and not SMOKE) else None)
    extra.update({"n_cal": len(cx), "n_eval": len(hx), "llm_scores_cached_at_start": n_cached})
    computed_ref = no_bci(ht)
    extra["no_bci_recomputed"] = computed_ref
    if ref_key:
        extra["no_bci_reference"] = NO_BCI[ref_key]
        extra["no_bci_matches_plan"] = abs(computed_ref - NO_BCI[ref_key]) < 5e-5
    log(f"{name}: calibration {len(cx)}, evaluation {len(hx)}, seed {d['seed']}, pool {d['pool']}; "
        f"llm cache {n_cached}; no-BCI {computed_ref:.4f}")
    # 1. fluent threshold (P15-05 stage_prep on the calibration truths)
    prep_path = own / "prep.json"
    if prep_path.exists():
        prep = json.loads(prep_path.read_text(encoding="utf-8"))
    else:
        prep = F.stage_prep("t15", pipe, (cx, ct, cph))
        prep_path.write_text(json.dumps(prep), encoding="utf-8")
    u.fluent_thr = prep["fluent_logp_per_word"]
    res: dict = {}
    # 2. R1' first: its guard fixes the frame temperature T of the draw (fitted inside calibrate)
    res["ngram_learned"] = run_arm(u, "ngram_learned")
    if res["ngram_learned"]["status"] != "ok":
        raise SystemExit(f"{name}: R1' refused; no frame temperature (reported as not run)")
    u.T = res["ngram_learned"]["frame_temperature"]
    # 3. grounding tau and the LLM weight (P15-05 stage_ground_prep, unchanged) at T on all calibration items
    gp_path = own / "ground_prep.json"
    if gp_path.exists():
        gp = json.loads(gp_path.read_text(encoding="utf-8"))
    else:
        gp = F.stage_ground_prep("t15", pipe, (cx, ct, cph), u.T)
        pipe.save_base()
        gp_path.write_text(json.dumps(gp), encoding="utf-8")
    pipe.grounding.tau, pipe.lam, pipe.frame_T = gp["tau"], gp["llm_weight"], u.T
    pipe.fluent_thr = u.fluent_thr
    extra["pipeline_values"] = {"frame_temperature": u.T, "tau": gp["tau"], "llm_weight": gp["llm_weight"],
                                "llm_weight_grid_wer": gp.get("llm_weight_grid_wer"),
                                "fluent_logp_per_word": u.fluent_thr}
    log(f"{name}: pipeline values {extra['pipeline_values']}")
    # 4. LLM arms
    for a in ("llm", "llm_learned"):
        res[a] = run_arm(u, a)
        if res[a]["status"] == "ok" and abs(res[a]["frame_temperature"] - u.T) > 1e-9:
            raise SystemExit(f"{name} {a}: frame temperature {res[a]['frame_temperature']} differs from R1' {u.T}")
    arms = ["ngram_learned", "llm", "llm_learned"]
    pairs = [("H1_llm_learned_vs_ngram_learned_v0_1", rows_of(res["ngram_learned"]), rows_of(res["llm_learned"]),
              "0.1", False),
             ("H2_llm_learned_vs_llm_v0_1", rows_of(res["llm"]), rows_of(res["llm_learned"]), "0.1", False),
             ("llm_vs_ngram_learned_v0_1", rows_of(res["ngram_learned"]), rows_of(res["llm"]), "0.1", False)]
    out = finish_unit(u, res, arms, pairs, extra)
    # 5. hallucination protocol 0.2 for L1
    out["halluc"] = run_halluc(u, ["llm_learned"]) if res["llm_learned"]["status"] == "ok" else {"status": "no L1"}
    out["misses"] = misses(u)
    # 6. c0: the code check against P15-22 and P5-23
    if name == "c0" and not SMOKE:
        out["c0_check"] = c0_check(res, gp, u)
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


def same_rows(a: list[dict], b: list[dict]) -> int:
    return sum(x["action"] == y["action"] and norm(x["text"]) == norm(y["text"]) for x, y in zip(a, b))


def c0_check(res: dict, gp: dict, u: SimpleNamespace) -> dict:
    p22 = json.loads((P1522_OWN / "arm-llm_learned.json").read_text(encoding="utf-8"))["rows"]
    p22_l0 = json.loads((P1522_OWN / "arm-llm.json").read_text(encoding="utf-8"))["rows"]
    r1 = json.loads(R1_T15.read_text(encoding="utf-8"))
    ok = {k: res[k]["status"] == "ok" for k in res}
    chk = {
        "frame_temperature": [u.T, C0_EXPECT["frame_temperature"], abs(u.T - C0_EXPECT["frame_temperature"]) < 1e-9],
        "tau": [gp["tau"], C0_EXPECT["tau"], abs(gp["tau"] - C0_EXPECT["tau"]) < 1e-12],
        "llm_weight": [gp["llm_weight"], C0_EXPECT["llm_weight"], gp["llm_weight"] == C0_EXPECT["llm_weight"]],
        "fluent": [u.fluent_thr, C0_EXPECT["fluent"], abs(u.fluent_thr - C0_EXPECT["fluent"]) < 1e-9],
        "l1_same_as_p15_22": same_rows(res["llm_learned"]["rows"], p22) if ok["llm_learned"] else 0,
        "l0_same_as_p15_22": same_rows(res["llm"]["rows"], p22_l0) if ok["llm"] else 0,
        "r1prime_same_as_p5_23": same_rows(res["ngram_learned"]["rows"], r1) if ok["ngram_learned"] else 0,
        "n": len(p22),
    }
    chk["reproduces"] = bool(all(v[2] for k, v in chk.items() if isinstance(v, list))
                             and chk["l1_same_as_p15_22"] == chk["l0_same_as_p15_22"]
                             == chk["r1prime_same_as_p5_23"] == chk["n"])
    log(f"c0 check: {chk}")
    return chk


def t12_unit() -> dict:
    """Part (b): T12 v2, calibration pool (480) -> test sessions (400)."""
    from fidetype.adapters import b2t25 as Bm

    name = "t12"
    own = ROOT / name
    own.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cal, held, dec = F.data_t12()  # P15-05 T12 loader (word trigram LM, smaller LRU memos)
    cx, ct, cph = cal
    hx, ht, _hph = held
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    ids, durs = [], []
    for r in prep["sessions"]:  # as P5-23 data_t12 (durations) and P15-07 held_t12 (trial ids)
        if r["role"] != "test":
            continue
        z = np.load(d_in / f"{r['session']}.npz")
        for i, _w in enumerate(texts[r["session"]]["pool"]):
            ids.append(f"{r['session']}|pool|{i}")
            durs.append(z[f"pool_X{i}"].shape[0] * 0.02)
    extra: dict = {"calibrate_seed": 0}
    r1 = r2 = None
    if SMOKE:  # calibration subsets only
        n = int(os.environ.get("P1526_SMOKE_N", "120"))
        hx, ht, ids = cx[n:n + 40], ct[n:n + 40], [f"smoke|{i}" for i in range(40)]
        durs = [float(x.shape[0]) * 0.02 for x in hx]
        cx, ct, cph = cx[:n], ct[:n], cph[:n]
    else:
        assert len(durs) == len(hx) == len(ids) == 400, (len(durs), len(hx), len(ids))
        sh = split_hashes(len(cx), 0)
        extra["split"] = {"score_fit_sha": sh[0], "certify_sha": sh[1]}
        assert sh == T12_SHA, f"T12 split differs from P5-23: {sh}"
        r1 = json.loads(R1_T12.read_text(encoding="utf-8"))
        r2 = json.loads(R2_T12.read_text(encoding="utf-8"))
    ht = [norm(t) for t in ht]
    if r1 is not None:
        rc = {"r1_same_truth": sum(norm(a["truth"]) == b for a, b in zip(r1, ht)),
              "r2_same_truth": sum(norm(a["truth"]) == b for a, b in zip(r2, ht)), "n": len(ht)}
        extra["row_check"] = rc
        assert rc["r1_same_truth"] == rc["r2_same_truth"] == len(ht) == len(r1) == len(r2), rc
    cache = ROOT / "llm-cache-t12.sqlite"
    n_cached = merged_llm_cache(cache, [SRC_T12 / "llm-cache.sqlite", SRC_T12_P606 / "llm-cache.sqlite"])
    pipe, lazy = make_pipe("t12", own, dec, cache, SRC_T12 / "base-nbest-t12.pkl")
    res5 = json.loads(T12_RES.read_text(encoding="utf-8"))
    gp, fl = res5["ground_prep"], res5["prep"]["fluent_logp_per_word"]
    pipe.grounding.tau, pipe.lam, pipe.frame_T, pipe.fluent_thr = gp["tau"], gp["llm_weight"], \
        gp["frame_temperature"], fl
    u = SimpleNamespace(name=name, own=own, pipe=pipe, lazy=lazy, base_start=len(pipe.base), B=Bm, seed=0,
                        cx=cx, ct=ct, cph=cph, hx=hx, ht=ht, durs=durs, ids=ids, T=gp["frame_temperature"],
                        fluent_thr=fl, dataset="b2t24-t12-test", split_file=None if SMOKE else SPLIT_T12)
    computed_ref = no_bci(ht)
    extra.update({"n_cal": len(cx), "n_eval": len(hx), "llm_scores_cached_at_start": n_cached,
                  "no_bci_recomputed": computed_ref, "no_bci_reference": NO_BCI["t12"],
                  "no_bci_matches_plan": abs(round(computed_ref, 2) - NO_BCI["t12"]) < 1e-9,
                  "pipeline_values": {"frame_temperature": gp["frame_temperature"], "tau": gp["tau"],
                                      "llm_weight": gp["llm_weight"], "fluent_logp_per_word": fl}})
    log(f"t12: calibration {len(cx)}, evaluation {len(hx)}; llm cache {n_cached}; no-BCI {computed_ref:.4f}; "
        f"pipeline {extra['pipeline_values']}; peak {peak_mb():.0f} MB")
    res: dict = {}
    for a in ("llm", "llm_learned", "llm_prefix"):
        res[a] = run_arm(u, a)
    extra["frame_temperature_matches"] = {a: (abs(res[a]["frame_temperature"] - u.T) < 1e-9
                                              if res[a]["status"] == "ok" else None) for a in res}
    if res["llm"]["status"] == "ok" and not SMOKE:
        ref = json.loads((SRC_T12 / "trials-t12-B1_rescore_G.json").read_text(encoding="utf-8"))["decisions"]
        extra["reference_check_llm"] = {"same_action_and_text": same_rows(res["llm"]["rows"], ref), "n": len(ref),
                                        "ref_commits": sum(r["action"] == "commit" for r in ref),
                                        "ref_wrong": sum(r["action"] == "commit" and norm(r["text"]) != norm(r["truth"])
                                                         for r in ref)}
        log(f"t12: L0 vs committed P15-05 T12 B1 decisions: {extra['reference_check_llm']}")
    L0, L1, L2 = rows_of(res["llm"]), rows_of(res["llm_learned"]), rows_of(res["llm_prefix"])
    pairs = [("H1_llm_learned_vs_p5_23_learned_v0_1", r1, L1, "0.1", False),
             ("H2_llm_learned_vs_llm_v0_1", L0, L1, "0.1", False),
             ("llm_vs_p5_23_learned_v0_1", r1, L0, "0.1", False),
             ("llm_prefix_vs_p5_24_prefix_v0_2_reading", r2, L2, "0.2", True),
             ("llm_prefix_vs_p5_24_prefix_v0_2", r2, L2, "0.2", False),
             ("llm_prefix_vs_llm_learned_v0_2_reading", L1, L2, "0.2", True)]
    out = finish_unit(u, res, ["llm", "llm_learned", "llm_prefix"], pairs, extra)
    out["halluc"] = run_halluc(u, [a for a in ("llm", "llm_learned", "llm_prefix") if res[a]["status"] == "ok"])
    out["misses"] = misses(u)
    out["seconds"] = round(time.time() - t0, 1)
    out["peak_mb"] = round(peak_mb(), 1)
    return out


# ---------------------------------------------------------------------------
# pre-registered decision rules (plan.md)
# ---------------------------------------------------------------------------


def test_a(unit: dict) -> dict:
    l1 = unit["arms"].get("llm_learned", {"status": "missing"})
    if l1.get("status") in ("refused", "missing"):
        return {"pass": False, "reason": f"L1 {l1.get('status')}"}
    v = l1["v0_1"]
    hl = ((unit.get("halluc") or {}).get("systems") or {}).get("llm_learned", {}).get("llm", {})
    ref = unit["no_bci_reference"]
    ci = v.get("ci")
    conds = {"certified": v.get("status") == "certified",
             "controls_pass": bool((v.get("controls") or {}).get("passed")),
             "safety_holds": v["measured_wrong_commit"] <= ALPHA,
             "halluc_swapped_pass": hl.get("swapped_verdict") == "pass",
             "halluc_controls_pass": hl.get("controls_verdict") == "pass",
             "above_reference": isinstance(v.get("value"), (int, float)) and v["value"] > ref}
    return {"pass": all(conds.values()), **conds, "value": v.get("value"), "ci95": ci, "reference": ref,
            "ci_lower_above_reference": bool(ci and ci[0] is not None and ci[0] > ref),
            "wrong_commits": v.get("n_wrong_commits"), "commits": v.get("n_commits"),
            "wrong_commit_cp95": v.get("measured_wrong_commit_cp95")}


def test_g(unit: dict, key: str) -> dict:
    l1 = unit["arms"].get("llm_learned", {"status": "missing"})
    p = unit["paired"].get(key)
    if l1.get("status") in ("refused", "missing") or p is None:
        return {"pass": False, "verdict": "L1 fails a control (refused)" if l1.get("status") == "refused"
                else "not computed"}
    vd = P22.verdict_rule(l1, p)
    return {"pass": vd == "L1 beats the other", "verdict": vd,
            **{k: p[k] for k in ("a", "b", "diff", "diff_ci95", "diff_half_width")}}


def stage_verdict() -> dict:
    allr = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    st = allr.get("stages", {})
    unit = lambda n: (st.get(n) or {}).get("result")  # noqa: E731
    out: dict = {"units": {}}
    c0 = unit("c0")
    out["c0_reproduces"] = bool(c0 and (c0.get("c0_check") or {}).get("reproduces"))
    draws = ["c1", "c2", "c3", "p1"]
    for n in draws + ["t12"]:
        r = unit(n)
        if not r or "arms" not in r:
            out["units"][n] = {"status": "not run"}
            continue
        g_key = "H1_llm_learned_vs_p5_23_learned_v0_1" if n == "t12" else "H1_llm_learned_vs_ngram_learned_v0_1"
        out["units"][n] = {"A": test_a(r), "G": test_g(r, g_key),
                           "H2": test_g(r, "H2_llm_learned_vs_llm_v0_1")}
    run = [n for n in draws if "A" in out["units"][n]]
    if not out["c0_reproduces"]:
        out["part_a"] = {"level": "not decided: c0 does not reproduce P15-22", "gain": None}
    elif len(run) < len(draws):
        out["part_a"] = {"level": f"incomplete: {len(run)} of 4 draws ran", "gain": None, "draws_run": run}
    else:
        def three(k: str) -> str:
            n = sum(out["units"][d][k]["pass"] for d in draws)
            return "replicates" if n == 4 else ("partly replicates" if n else "does not replicate")
        out["part_a"] = {"level": three("A"), "gain": three("G"),
                         "n_pass_A": sum(out["units"][d]["A"]["pass"] for d in draws),
                         "n_pass_G": sum(out["units"][d]["G"]["pass"] for d in draws)}
    vals = {n: (unit(n) or {}).get("arms", {}).get("llm_learned", {}).get("v0_1", {}).get("value")
            for n in ["c0"] + draws}
    fin = [v for v in vals.values() if isinstance(v, (int, float))]
    out["l1_values"] = vals
    if fin:
        out["l1_spread"] = {"n": len(fin), "mean": float(np.mean(fin)), "sd": float(np.std(fin, ddof=1))
                            if len(fin) > 1 else None, "min": min(fin), "max": max(fin)}
    t = out["units"]["t12"]
    if "A" in t:
        out["part_b"] = {"level": "replicates on T12" if t["A"]["pass"] else "does not replicate on T12",
                         "gain": "gain replicates on T12" if t["G"]["pass"] else "gain does not replicate on T12"}
    else:
        out["part_b"] = {"level": "not run", "gain": "not run"}
    la, lb = out["part_a"].get("level"), out["part_b"].get("level")
    if la == "replicates" and lb == "replicates on T12":
        claim = "above gaze typing, replicated on two participants and four calibration draws"
    elif la == "replicates" and lb == "does not replicate on T12":
        claim = "above gaze typing on T15 (stable over calibration draws); not replicated on T12"
    elif la == "partly replicates":
        claim = "above gaze typing on T15 in some calibration draws only; the 4.91 depends on the split"
    elif la == "does not replicate":
        claim = "the P15-22 result did not replicate; P15-22 was a favourable draw"
    else:
        claim = f"not decided (part a: {la}; part b: {lb})"
    out["headline_claim"] = claim
    log(f"verdict: part a {out['part_a']}; part b {out['part_b']}; claim: {claim}")
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def stage_unit(name: str):
    def f() -> dict:
        path = ROOT / name / "unit.json"
        if path.exists():
            log(f"{name}: unit done before, loaded {path}")
            return json.loads(path.read_text(encoding="utf-8"))
        if name not in ("t12", "c0") and not SMOKE:
            c0 = ROOT / "c0" / "unit.json"
            if not c0.exists() or not json.loads(c0.read_text(encoding="utf-8")).get("c0_check", {}).get("reproduces"):
                raise SystemExit(3)  # plan.md: no draw result from code that does not reproduce P15-22
        out = t12_unit() if name == "t12" else t15_unit(name)
        from fidetype.benchmark.scoring import to_jsonable

        path.write_text(json.dumps(to_jsonable(out), default=str), encoding="utf-8")
        return out
    return f


def stage_smoke() -> dict:
    assert SMOKE, "set P1526_SMOKE=1 (calibration subsets only)"
    return {"t15": t15_unit("c1"), "t12": t12_unit()}


STAGES = {**{n: stage_unit(n) for n in ("t12", "c0", "c1", "c2", "c3", "p1")}, "verdict": stage_verdict,
          "smoke": stage_smoke}


def main() -> None:
    args = sys.argv[1:]
    bad = [s for s in args if s not in STAGES]
    if not args or bad:
        raise SystemExit(f"unknown stage(s) {bad or args}; known: {list(STAGES)}")
    OUT.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    path = OUT / "results.json"
    from fidetype.benchmark.scoring import to_jsonable
    from fidetype.utils.power import keep_awake

    with keep_awake(log=log):
        for st in args:
            t0 = time.time()
            log(f"stage {st} start")
            out = STAGES[st]()
            allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}  # re-read: one stage each
            allr["fidetype_version"] = FT_VERSION
            allr["plan"] = PLAN
            allr.setdefault("stages", {})[st] = {"seconds": round(time.time() - t0, 1), "result": out}
            path.write_text(json.dumps(to_jsonable(allr), indent=1, default=str) + "\n", encoding="utf-8")
            log(f"stage {st} done in {time.time() - t0:.0f} s; peak {peak_mb():.0f} MB")


if __name__ == "__main__":
    main()
