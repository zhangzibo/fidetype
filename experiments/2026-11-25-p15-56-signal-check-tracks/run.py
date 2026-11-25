"""P15-56: score the shipped hallucination-benchmark baselines on the signal-check tracks. CPU only. Plan: plan.md.

Tracks (fidetype.benchmark.hallucination, opt-in): truncated_25/50/75, noise_mix_25/50/75, near_miss; plus the real
track again (the pairs; checked against the committed outcomes file).

Sets and systems (guards read only; nothing is re-calibrated):
  t15    b2t25-t15-val-eval, M4-12 fixed0 log-probs: p14-03-guard, p15-05-B0_rescore, p15-06-B1_rescore_G
  m413   b2t25-t15-val-eval, M4-13 long0 log-probs:  m4-13-p15-05-A0_ngram, m4-13-p15-05-B0_rescore,
         m4-13-p15-06-B1_rescore_G, m4-13-p15-06-B1_rescore_G@single
  t12    b2t24-t12-test, T12 v2 log-probs:           p14-03-guard, p15-05-B0_rescore, p15-06-B1_rescore_G

The decoders and the LLM first use the saved caches (read only). New inputs miss them: then the same word decoder
(CPU) decodes and the same LLM (Qwen2.5-1.5B-Instruct Q4_K_M, llama-cpp-python, CPU) scores. New cache entries go to
C:/Users/zhang/bci-data/derived/p15-56/ only. A stop loses at most the current system's guard decisions (the caches
survive); a rerun skips finished systems.

Run (repo root), detached:
  .venv\\Scripts\\python.exe -I experiments/2026-11-25-p15-56-signal-check-tracks/run.py m413 t15 t12
  (--limit N: smoke run on the first N items, outputs to the derived smoke/ folder only)
Repo outputs: results/ (flags only). Our own code (Apache-2.0).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "3"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sqlite3  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.benchmark import hallucination as HB  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN_ROOT = DER / "p15-56"  # the only derived folder this task writes
assert OWN_ROOT.name == "p15-56"
OUT = HERE / "results"
LLM_PATH = Path("C:/Users/zhang/bci-data/models/qwen2.5-1.5b-instruct-gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf")
LLM_SHA = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
V01 = REPO / "benchmark/results/halluc-v0.1"
V02 = REPO / "benchmark/results/halluc-v0.2"
LOGF = OUT / "run.log"
NEAR_MISS_ADAPTER = ("language side = the system's own base n-best list with the top candidate's text replaced by the "
                     "near-miss text (all score fields kept; char_confidences mapped by relative position)")


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    LOGF.parent.mkdir(parents=True, exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = load_module("p1507_run", REPO / "experiments/2026-11-16-p15-07-halluc-bench/run.py")  # read only; not changed
R.OWN = OWN_ROOT  # never write into the P15-07 folders
R.LOGF = OWN_ROOT / "p1507-module.log"


# ---------------------------------------------------------------------------
# live caches (read the saved ones; write only ours)
# ---------------------------------------------------------------------------


class LiveScorer:
    """LLM scores: frozen tables first, then our sqlite, then the LLM itself (loaded on the first miss)."""

    def __init__(self, frozen: dict, path: Path) -> None:
        self.frozen = frozen
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS scores (k TEXT PRIMARY KEY, v TEXT)")
        self.mine = {k: json.loads(v) for k, v in self.db.execute("SELECT k, v FROM scores")}
        self.llm = None
        self.new = 0

    def _model(self):
        if self.llm is None:
            from fidetype.lm.llm import LlamaCppLLM

            h = hashlib.sha256()
            with open(LLM_PATH, "rb") as f:
                for b in iter(lambda: f.read(1 << 22), b""):
                    h.update(b)
            assert h.hexdigest() == LLM_SHA, "model file SHA-256 mismatch"
            self.llm = LlamaCppLLM(str(LLM_PATH), n_threads=3, n_ctx=1024, seed=0, max_tokens=48)
            log("LLM loaded (CPU, 3 threads)")
        return self.llm

    def get(self, t: str):
        v = self.frozen.get(t)
        return v if v is not None else self.mine.get(t)

    def score(self, texts):
        miss = sorted({t for t in texts if self.get(t) is None})
        if miss:
            vals = self._model().score(miss)
            for t, v in zip(miss, vals):
                self.mine[t] = float(v)
                self.db.execute("INSERT OR REPLACE INTO scores VALUES (?, ?)", (t, json.dumps(float(v))))
            self.new += len(miss)
            self.db.commit()
        return [float(self.get(t)) for t in texts]

    def table(self) -> dict:
        return {**self.frozen, **self.mine}


def make_live_pipeline(s: str, lex, p5res: dict, scorer: LiveScorer, dec, own: Path):
    """A P15-07 FrozenPipeline whose base n-best falls back to a live CPU decode (stored in our pickle)."""

    class Live(R.FrozenPipeline):
        def __init__(self) -> None:
            super().__init__(s, lex, p5res, scorer)
            self.mine_path = own / "base-nbest-new.pkl"
            self.mine: dict = pickle.loads(self.mine_path.read_bytes()) if self.mine_path.exists() else {}
            self.new = 0
            self.decodes = 0

        def save(self) -> None:
            if self.new:
                tmp = self.mine_path.with_suffix(".tmp")
                tmp.write_bytes(pickle.dumps(self.mine))
                tmp.replace(self.mine_path)
                self.new = 0

        def base_nbest(self, x: np.ndarray) -> list[dict]:
            k = R.xkey(x)
            hit = self.base.get(k)
            if hit is None:
                hit = self.mine.get(k)
            if hit is not None:
                return hit
            lp = np.ascontiguousarray(x, dtype=np.float32)  # the P15-05 Pipeline.base_nbest code
            st = NeuralTextStream(log_probs=lp, frame_times=np.arange(lp.shape[0]) * 0.08,
                                  vocab=list(B.SYMBOL_VOCAB), blank_id=0, vocab_type="phoneme")
            dec._wcache = {}
            nb = dec.words_fn(st)
            out = []
            for c in nb.candidates:
                d = {"text": c.text, "score": float(c.score)}
                for f in ("logp_acoustic", "logp_lm"):
                    v = float(getattr(c, f))
                    if math.isfinite(v) and v <= 0:
                        d[f] = v
                if c.char_confidences:
                    d["char_confidences"] = [min(1.0, max(0.0, float(z))) for z in c.char_confidences]
                out.append(d)
            self.mine[k] = out
            self.new += 1
            self.decodes += 1
            if self.new >= 200:
                self.save()
            return out

        def run_lang(self, arm: dict, x: np.ndarray, lang_items: list[dict]) -> list[dict]:
            """FrozenPipeline.run with a given language-side n-best list (the near-miss track)."""
            from fidetype.lm.llm import rescore

            base = [dict(d) for d in lang_items]
            if not base:
                return []
            items = rescore(base, self.scorer, self.lam) if arm["rescore"] else base
            if arm["ground"]:
                own_nb = self.base_nbest(x)
                if not own_nb or not own_nb[0]["text"]:
                    return []
                items, _ = self.grounding.apply(items, x, own_nb[0]["text"], key=R.xkey(x))
            return items

    return Live()


def near_miss_list(own: list[dict], v: str) -> list[dict]:
    """The near-miss language side of our baselines (plan, track 3)."""
    if not own:
        return []
    top = dict(own[0])
    top["text"] = v
    cc = list(own[0].get("char_confidences") or [])
    top.pop("char_confidences", None)
    if cc:
        L0, L1 = len(cc), len(v)
        top["char_confidences"] = ([cc[0]] * L1 if L1 <= 1 or L0 <= 1
                                   else [cc[int(round(c * (L0 - 1) / (L1 - 1)))] for c in range(L1)])
    rest = [dict(d) for d in own[1:] if " ".join(str(d["text"]).split()) != v]
    return [top] + rest


# ---------------------------------------------------------------------------
# sets
# ---------------------------------------------------------------------------


def t12_decoder():
    """The T12 word decoder of P15-05 data_t12 (word trigram added), without loading the calibration data."""
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    dec = bt.Decoders([], cfg["word_decoder_tuned"])
    sys.path.insert(0, str(exp))
    import wordlm  # noqa: E402

    beta = cfg["word_lm"]["beta"]
    cache = Path(cfg["word_lm"]["cache"])
    assert cache.exists(), "word LM cache missing (would be rebuilt)"
    wm = wordlm.load_or_build(bt.CONFIG["tatoeba_eng"], cache, B.normalize_words)
    char = dec.lm.score_sentence
    dec.wdec.sentence_lm = lambda t: char(t) + beta * wm.score_sentence(t)
    dec.wdec.clear_caches()
    dec._wcache.clear()
    dec.wdec.set_cache_sizes(1_000, 10_000)
    dec.lm._cache.resize(50_000)
    return dec, bt


def set_config(name: str) -> dict:
    if name == "t15":
        ids, xs, ts = R.held_t15()
        return {"s": "t15", "dataset": "b2t25-t15-val-eval", "ids": ids, "xs": xs, "ts": ts,
                "p5": R.DER / "f2-e3-llm-grounding", "p6": R.DER / "p15-06-halluc-bound",
                "p5res": REPO / "experiments/2026-11-16-f2-e3-llm-grounding/results/results-t15.json",
                "systems": {k: dict(v) for k, v in R.SYSTEMS.items()}, "outcomes_dir": V01,
                "decoder_label": "M4-12 fixed0"}
    if name == "t12":
        ids, xs, ts = R.held_t12()
        return {"s": "t12", "dataset": "b2t24-t12-test", "ids": ids, "xs": xs, "ts": ts,
                "p5": R.DER / "f2-e3-llm-grounding", "p6": R.DER / "p15-06-halluc-bound",
                "p5res": REPO / "experiments/2026-11-16-f2-e3-llm-grounding/results/results-t12.json",
                "systems": {k: dict(v) for k, v in R.SYSTEMS.items()}, "outcomes_dir": V01,
                "decoder_label": "T12 v2"}
    if name == "m413":
        import common as K

        A = load_module("p1515_add", REPO / "experiments/2026-11-17-p15-15-halluc-0.2/add_m4_13.py")
        xs, ts, _, keys = K.load_part(K.SOURCES["m4-13"]["held"], "val_eval", 0, True, True)
        ids = [f"{k.split('|')[0]}|val|{k.split('|')[2]}" for k in keys]
        p5, p6 = A.RERUN / "p15-05", A.RERUN / "p15-06"
        sy = {k: {**v, "guard": (lambda s, g=v["guard"]: g)} for k, v in A.systems(p5, p6).items()}
        return {"s": "t15", "dataset": "b2t25-t15-val-eval", "ids": ids, "xs": xs, "ts": ts, "p5": p5, "p6": p6,
                "p5res": A.M413_RES / "results-t15.json", "systems": sy, "outcomes_dir": V02,
                "decoder_label": "M4-13 long0"}
    raise SystemExit(f"unknown set {name!r}")


def stem(dataset: str, system: str, mode: str) -> str:
    return f"{dataset}--{system.replace('@', '-at-')}--{mode}"


# ---------------------------------------------------------------------------
# one system
# ---------------------------------------------------------------------------


def run_system(cfg: dict, name: str, pipe, sc: HB.SignalChecks, limit: int) -> tuple[list[HB.Record], str]:
    sysd = cfg["systems"][name]
    arm = R.P5["arms"][sysd["arm"]]
    gpath = sysd["guard"](cfg["s"])
    kw = {"grounding": pipe.commit_grounding()} if sysd["grounded"] else {}
    guard = ft.load(gpath, decode_fn=lambda lp: pipe.run(arm, np.asarray(lp, dtype=np.float32)), **kw)
    T = guard.config.frame_temperature
    state: dict = {"items": None}
    nguard = ft.load(gpath, decode_fn=lambda lp: pipe.run_lang(arm, np.asarray(lp, dtype=np.float32), state["items"]),
                     **kw)

    def decide_near_miss(x, v, j):
        state["items"] = near_miss_list(pipe.base_nbest(R.temper(x, T)), v)
        return nguard.decide(x, utterance_id="near_miss")

    t0 = time.time()

    def progress(track, i):
        if i % 250 == 249:
            log(f"  {name} {track} {i + 1}; new decodes {pipe.decodes}, new LLM scores {pipe.scorer.new}, "
                f"{time.time() - t0:.0f} s")
            pipe.save()

    xs, ts = cfg["xs"], cfg["ts"]
    if limit:
        xs, ts = xs[:limit], ts[:limit]
    log(f"{name}: guard {guard.config_id} (frame T {T:.4f}) from {Path(gpath).name}")
    recs = HB.run_signal_checks(lambda x: guard.decide(x, utterance_id="p15-07"), xs, ts, sc,
                                decide_near_miss=decide_near_miss, progress=progress)
    pipe.save()
    return recs, guard.config_id


def check_real(cfg: dict, name: str, recs: list[HB.Record], limit: int) -> list[str]:
    """Check 1 of the plan: the real-track flags equal the committed outcomes file."""
    f = cfg["outcomes_dir"] / f"{stem(cfg['dataset'], name, 'llm')}.outcomes.json"
    ref = json.loads(f.read_text(encoding="utf-8"))["tracks"]["real"]
    real = sorted((r for r in recs if r.track == "real"), key=lambda r: r.item)
    got_c = "".join("1" if r.committed else "0" for r in real)
    got_w = "".join("1" if r.wrong else "0" for r in real)
    n = len(real)
    probs = []
    if got_c != ref["committed"][:n]:
        probs.append(f"real committed flags differ from {f.name}")
    if got_w != ref["wrong"][:n]:
        probs.append(f"real wrong flags differ from {f.name}")
    return probs


def run_set(name: str, systems: list[str] | None, limit: int, summary: dict) -> None:
    t0 = time.time()
    cfg = set_config(name)
    own = OWN_ROOT / name / ("smoke" if limit else "")
    own.mkdir(parents=True, exist_ok=True)
    xs, ts = cfg["xs"], cfg["ts"]
    sc = HB.make_signal_checks(xs[:limit] if limit else xs, ts[:limit] if limit else ts, seed=R.SEED,
                               vocab_size=len(B.SYMBOL_VOCAB))
    if limit:  # the near-miss pool must be the full held-out vocabulary, as in the real run
        full, ed = HB.near_miss_texts(ts, R.SEED)
        sc.near_miss, sc.near_miss_edits = full[:limit], ed[:limit]
    for t, v, e in zip(ts, sc.near_miss, sc.near_miss_edits):  # check 2 of the plan
        assert len(t.split()) == len(v.split()) and sum(a != b for a, b in zip(t.split(), v.split())) == e, (t, v, e)
    log(f"set {name} ({cfg['decoder_label']}): {len(sc.near_miss)} items, signal digest {sc.digest()[:16]}, "
        f"near-miss edits 1: {sc.near_miss_edits.count(1)}, 2: {sc.near_miss_edits.count(2)}")
    R.P5_ROOT, R.P6_ROOT = cfg["p5"], cfg["p6"]  # FrozenPipeline reads its base caches here (read only)
    s = cfg["s"]
    p5res = json.loads(Path(cfg["p5res"]).read_text(encoding="utf-8"))
    thr = p5res["prep"]["fluent_logp_per_word"]
    frozen: dict = {}
    for d in (cfg["p5"] if s == "t15" else cfg["p5"] / s, cfg["p6"] if s == "t15" else cfg["p6"] / s):
        frozen.update(R.ro_table(d / "llm-cache.sqlite", "scores"))
    scorer = LiveScorer(frozen, own / "llm-cache-new.sqlite")
    if s == "t12":
        dec, bt = t12_decoder()
    else:
        import common as K

        dec, bt = K.word_decoder()
    pipe = make_live_pipeline(s, bt.build_lexicon(), p5res, scorer, dec, own)
    out = summary.setdefault(name, {"dataset": cfg["dataset"], "decoder": cfg["decoder_label"], "n": len(sc.near_miss),
                                    "fluent_threshold": thr, "signal_digest": sc.digest(), "systems": {}})
    for sname in systems or list(cfg["systems"]):
        if sname not in cfg["systems"]:
            continue
        rec_path = own / f"records-{sname.replace('@', '-at-')}.jsonl"
        if rec_path.exists() and out["systems"].get(sname, {}).get("status") == "ok":
            log(f"{name} {sname}: done before; skipped")
            continue
        ta = time.time()
        recs, cfg_id = run_system(cfg, sname, pipe, sc, limit)
        probs = check_real(cfg, sname, recs, limit)
        with open(rec_path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps({"track": r.track, "item": r.item, "action": r.action, "text": r.text,
                                    "truth": r.truth, "language": r.language_truth}, ensure_ascii=False) + "\n")
        if probs:
            log(f"{name} {sname}: STOPPED by check 1: {probs}")
            out["systems"][sname] = {"status": "stopped (real-track replay differs)", "problems": probs}
            continue
        # LLM scores for every unsupported commit text (the llm-table fluency must not miss any)
        bad = sorted({HB._norm(r.text) for r in recs if r.committed and (r.wrong if r.track == "real"
                                                                         else HB.signal_unsupported(r))})
        if bad:
            scorer.score(bad)
        row = {"status": "ok", "guard_config_id": cfg_id, "description": cfg["systems"][sname]["desc"], "cards": {}}
        for mode, fl in (("llm", HB.TableFluency(scorer.table(), thr, name="Qwen2.5-1.5B-Instruct Q4_K_M (caches + P15-56)")),
                         ("conservative", HB.ConservativeFluency())):
            oc = HB.to_signal_outcomes(recs, fl, dataset=cfg["dataset"], system=sname,
                                       meta={"guard_config_id": cfg_id, "description": cfg["systems"][sname]["desc"],
                                             "decoder": cfg["decoder_label"], "fidetype_version": FT_VERSION,
                                             "seed": R.SEED, "near_miss_language_side": NEAR_MISS_ADAPTER,
                                             "signal_digest": sc.digest(), "limit": limit})
            card = HB.score_signal_outcomes(oc)
            dst = OUT if not limit else own
            dst.mkdir(parents=True, exist_ok=True)
            st = stem(cfg["dataset"], sname, mode)
            (dst / f"{st}.signal-outcomes.json").write_text(json.dumps(oc, indent=0) + "\n", encoding="utf-8")
            (dst / f"{st}.signal-card.json").write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
            row["cards"][mode] = {"file": f"{st}.signal-card.json", "verdict": card["signal_checks_verdict"],
                                  "families": card["families"], "summary": HB.signal_summary_line(card)}
            log(f"{name} {sname} [{mode}]: {HB.signal_summary_line(card)}")
        row["seconds"] = round(time.time() - ta, 1)
        row["new_decodes_total"], row["new_llm_scores_total"] = pipe.decodes, scorer.new
        out["systems"][sname] = row
        save_summary(summary, limit)
    out["seconds_last_run"] = round(time.time() - t0, 1)
    save_summary(summary, limit)


def save_summary(summary: dict, limit: int) -> None:
    p = (OWN_ROOT / "smoke-summary.json") if limit else (OUT / "results.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    global LOGF
    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="+", choices=("t15", "m413", "t12"))
    ap.add_argument("--systems", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0, help="smoke run on the first N items (derived smoke/ folder only)")
    a = ap.parse_args(argv)
    if a.limit:
        LOGF = OWN_ROOT / "smoke.log"
    p = (OWN_ROOT / "smoke-summary.json") if a.limit else (OUT / "results.json")
    summary = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    summary.update(fidetype_version=FT_VERSION, seed=R.SEED, protocol=HB.SIGNAL_PROTOCOL,
                   plan="experiments/2026-11-25-p15-56-signal-check-tracks/plan.md")
    for s in a.sets:
        log(f"stage {s} start (limit {a.limit})")
        run_set(s, a.systems, a.limit, summary)
        log(f"stage {s} done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
