"""P15-07 baselines: the hallucination benchmark (fidetype.benchmark.hallucination) on T15 and T12. CPU only.

Systems (guards are read only; nothing is re-calibrated):
  p14-03-guard      the P14-03 drop-in guard (alpha 0.05), n-gram word decoder, no LLM
  p15-05-B0_rescore the P15-05 LLM-rescoring arm without grounding (its P15-05 guard)
  p15-06-B1_rescore_G  the P15-06 guard: LLM rescoring + grounding + fluent-wrong bound (joint LTT)

The decoders run from the P15-05 / P15-06 caches only (base n-best pickles, LLM sqlite opened read only).
A cache miss stops that system (we never load the 3.5 GB T12 word decoder or the LLM here; RAM < 2 GB).
Fluency: the LLM scores in the P15-06 cache (TableFluency, the P15-05 fluent threshold of each set);
also the conservative fallback.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p15-07-halluc-bench/run.py t15 t12
Per-trial records (texts): C:/Users/zhang/bci-data/derived/p15-07-halluc-bench/ only.
Repo: split files (hashes), outcomes (flags), score cards, results.json.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

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

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.benchmark import hallucination as HB  # noqa: E402
from fidetype.lm.llm import rescore  # noqa: E402
from fidetype.trust import halluc_bound as H  # noqa: E402
from fidetype.trust.grounding import GroundingCheck, lexicon_label_fn  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p15-07-halluc-bench"  # the only place this task writes per-trial files
assert OWN.name == "p15-07-halluc-bench"
OWN.mkdir(parents=True, exist_ok=True)
P5_ROOT = DER / "f2-e3-llm-grounding"  # read only
P6_ROOT = DER / "p15-06-halluc-bound"  # read only
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CARDS = REPO / "benchmark/results/halluc-v0.1"
CARDS.mkdir(parents=True, exist_ok=True)
SPLITS = REPO / "src/fidetype/benchmark/splits/halluc-v0.1"
SPLITS.mkdir(parents=True, exist_ok=True)
LOGF = OUT / "run.log"
P5 = json.loads((REPO / "experiments/2026-11-16-f2-e3-llm-grounding/config.json").read_text(encoding="utf-8"))
SEED = P5["seed"]
N_NULL = P5["null_trials"]
DATASETS = {
    "t15": {"dataset": "b2t25-t15-val-eval", "licence": "CC0 1.0",
            "rule": "Brain-to-Text '25 (T15), M4-12 fixed0 phoneme log-probs; val split, odd-index trials per session "
                    "(val_eval, 701), session order of m4-01-02-lookahead/sessions.json. Trial id = <session>|val|<i>."},
    "t12": {"dataset": "b2t24-t12-test", "licence": "CC0 1.0",
            "rule": "Brain-to-Text '24 (T12), T12 v2 confirmatory log-probs; trust pool of the 10 test sessions (400), "
                    "session order of confirmatory-t12-v2 prep.json. Trial id = <session>|pool|<i>."},
}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def xkey(x: np.ndarray) -> bytes:
    return hashlib.sha1(np.ascontiguousarray(x, dtype=np.float32).tobytes()).digest()


def temper(x: np.ndarray, T: float) -> np.ndarray:
    z = np.asarray(x, dtype=np.float64) / T
    m = z.max(axis=1, keepdims=True)
    return (z - (m + np.log(np.exp(z - m).sum(axis=1, keepdims=True)))).astype(np.float32)


class CacheMiss(RuntimeError):
    pass


def ro_table(path: Path, table: str) -> dict:
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {k: json.loads(v) for k, v in db.execute(f"SELECT k, v FROM {table}")}
    finally:
        db.close()


class FrozenScorer:
    """LLM scores from the read-only cache; a miss raises CacheMiss (no model is loaded)."""

    def __init__(self, table: dict) -> None:
        self.table = table
        self.misses = 0

    def score(self, texts):
        out = []
        for t in texts:
            v = self.table.get(t)
            if v is None:
                self.misses += 1
                raise CacheMiss(f"LLM score missing: {t!r}")
            out.append(float(v))
        return out


# ---------------------------------------------------------------------------
# held-out data (as P15-06 data_t15 / data_t12; held-out part only)
# ---------------------------------------------------------------------------


def held_t15():
    d_in = DER / "m4-01-02-lookahead"
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    order = {s: j for j, s in enumerate(sessions)}
    z = np.load(d_in / "logprobs-m4-12-fixed0.npz")
    keys = sorted((k for k in z.files if "|val_eval|" in k), key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
    ids, xs, ts = [], [], []
    for k in keys:
        s, p, i, _ = k.split("|")
        ids.append(f"{s}|val|{i}")
        xs.append(z[k].astype(np.float32))
        ts.append(" ".join(texts[s][p][int(i)].split()))
    return ids, xs, ts


def held_t12():
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    meta = json.loads((d_in / "logprobs-meta.json").read_text(encoding="utf-8"))
    assert meta["checkpoint_sha256"] == cfg["decoder_checkpoint_sha256"]
    z = np.load(d_in / "logprobs.npz")
    ids, xs, ts = [], [], []
    for r in prep["sessions"]:
        if r["role"] != "test":
            continue
        s = r["session"]
        for i, w in enumerate(texts[s]["pool"]):
            ids.append(f"{s}|pool|{i}")
            xs.append(z[f"{s}|pool|{i}"].astype(np.float32))
            ts.append(" ".join(w.split()))
    return ids, xs, ts


# ---------------------------------------------------------------------------
# cache-only pipeline (logic of P15-05 / P15-06 Pipeline, no writes, no decoder load)
# ---------------------------------------------------------------------------


class FrozenPipeline:
    def __init__(self, s: str, lex, p5res: dict, scorer: FrozenScorer) -> None:
        src = P5_ROOT if s == "t15" else P5_ROOT / s
        own6 = P6_ROOT if s == "t15" else P6_ROOT / s
        self.base: dict = pickle.loads((src / f"base-nbest-{s}.pkl").read_bytes())
        extra = own6 / "base-nbest-extra.pkl"
        if extra.exists():
            self.base.update(pickle.loads(extra.read_bytes()))
        sym = {c: i for i, c in enumerate(B.SYMBOL_VOCAB)}
        g = P5["grounding"]
        self.label_fn = lexicon_label_fn(lex.prons, sym, word_sep=" ", max_variants=g["max_variants"])
        gp = p5res["ground_prep"]
        self.grounding = GroundingCheck(self.label_fn, tau=gp["tau"], blank=0, demote_margin=g["demote_margin"])
        self.lam = gp["llm_weight"]
        self.sep_id = sym[" "]
        self.scorer = scorer
        self.misses = 0

    def base_nbest(self, x: np.ndarray) -> list[dict]:
        hit = self.base.get(xkey(x))
        if hit is None:
            self.misses += 1
            raise CacheMiss("base n-best missing")
        return hit

    def run(self, arm: dict, x: np.ndarray, lang_x: np.ndarray | None = None) -> list[dict]:
        assert not arm["rewrite"], "rewrite arms are not in the P15-07 baseline set"
        base = self.base_nbest(x if lang_x is None else lang_x)
        if not base:
            return []
        items = rescore(base, self.scorer, self.lam) if arm["rescore"] else [dict(d) for d in base]
        if arm["ground"]:
            own = self.base_nbest(x)
            if not own or not own[0]["text"]:
                return []
            items, _ = self.grounding.apply(items, x, own[0]["text"], key=xkey(x))
        return items

    def anchor(self, lp: np.ndarray) -> str:
        b = self.base_nbest(np.asarray(lp, dtype=np.float32))
        return b[0]["text"] if b else ""

    def commit_grounding(self) -> H.CommitGrounding:
        return H.CommitGrounding(self.label_fn, blank=0, word_sep_id=self.sep_id, anchor_fn=self.anchor,
                                 name="cmudict-phonemes (16 variants), anchor = base top-1 without LLM")


SYSTEMS = {
    "p14-03-guard": {"arm": "A0_ngram", "guard": lambda s: REPO / f"experiments/2026-11-16-p14-03-replay-validation/results/guard-{s}-a0.05.json",
                     "grounded": False, "desc": "P14-03 drop-in guard (alpha 0.05, delta 0.1), n-gram word decoder, no LLM"},
    "p15-05-B0_rescore": {"arm": "B0_rescore", "guard": lambda s: (P5_ROOT if s == "t15" else P5_ROOT / s) / f"guard-{s}-B0_rescore.json",
                          "grounded": False, "desc": "P15-05 LLM rescoring (Qwen2.5-1.5B), no grounding, P14-03-type guard"},
    "p15-06-B1_rescore_G": {"arm": "B1_rescore_G", "guard": lambda s: (P6_ROOT if s == "t15" else P6_ROOT / s) / "guard-B1_rescore_G.json",
                            "grounded": True, "desc": "P15-06 guard: LLM rescoring + CTC grounding + fluent-wrong bound (joint LTT)"},
}


def run_system(s: str, name: str, pipe: FrozenPipeline, ids, xs, ts, ctl) -> tuple[list[HB.Record], str]:
    sysd = SYSTEMS[name]
    arm = P5["arms"][sysd["arm"]]
    gpath = sysd["guard"](s)
    kw = {"grounding": pipe.commit_grounding()} if sysd["grounded"] else {}
    guard = ft.load(gpath, decode_fn=lambda lp: pipe.run(arm, np.asarray(lp, dtype=np.float32)), **kw)
    T = guard.config.frame_temperature
    state = {"i": None}
    sguard = ft.load(gpath, decode_fn=lambda lp: pipe.run(arm, np.asarray(lp, dtype=np.float32),
                                                         lang_x=temper(xs[state["i"]], T)), **kw)

    def decide_swapped(x, i):
        state["i"] = i
        return sguard.decide(x, utterance_id="swapped")

    log(f"{s} {name}: guard {guard.config_id} (frame T {T:.4f}) from {gpath.name}")
    return HB.run_tracks(lambda x: guard.decide(x, utterance_id="p15-07"), xs, ts, controls=ctl,
                         decide_swapped=decide_swapped), guard.config_id


def run_set(s: str, systems: list[str]) -> dict:
    t0 = time.time()
    ids, xs, ts = {"t15": held_t15, "t12": held_t12}[s]()
    meta = DATASETS[s]
    ctl = HB.make_controls(xs, ts, seed=SEED, n_null=N_NULL, vocab_size=len(B.SYMBOL_VOCAB))
    split = HB.split_definition(meta["dataset"], ids, ts, ctl, licence=meta["licence"], rule=meta["rule"], n_null=N_NULL)
    (SPLITS / f"{meta['dataset']}.json").write_text(json.dumps(split, indent=0) + "\n", encoding="utf-8")
    log(f"{s}: {len(xs)} held out; split written; controls sha256 {split['controls_sha256'][:16]}")
    p5res = json.loads((REPO / f"experiments/2026-11-16-f2-e3-llm-grounding/results/results-{s}.json").read_text(encoding="utf-8"))
    thr = p5res["prep"]["fluent_logp_per_word"]
    llm_tab = ro_table((P6_ROOT if s == "t15" else P6_ROOT / s) / "llm-cache.sqlite", "scores")
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    lex = bt.build_lexicon()
    pipe = FrozenPipeline(s, lex, p5res, FrozenScorer(llm_tab))
    out = {"dataset": meta["dataset"], "n_real": len(xs), "fluent_threshold": thr, "systems": {}}
    for name in systems:
        ta = time.time()
        try:
            recs, cfg_id = run_system(s, name, pipe, ids, xs, ts, ctl)
        except CacheMiss as e:
            log(f"{s} {name}: CACHE MISS ({e}); system skipped")
            out["systems"][name] = {"status": "cache miss", "message": str(e)}
            continue
        with open(OWN / f"records-{s}-{name}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps({"track": r.track, "item": r.item, "signal": r.signal_trial, "language": r.language_trial,
                                    "action": r.action, "text": r.text, "truth": r.truth}) + "\n")
        row = {"status": "ok", "guard_config_id": cfg_id, "description": SYSTEMS[name]["desc"], "cards": {}}
        for mode, fl in (("llm", HB.TableFluency(llm_tab, thr, name="Qwen2.5-1.5B-Instruct Q4_K_M (P15-05/06 cache)")),
                         ("conservative", HB.ConservativeFluency())):
            oc = HB.to_outcomes(recs, fl, dataset=meta["dataset"], system=name,
                                meta={"guard_config_id": cfg_id, "description": SYSTEMS[name]["desc"],
                                      "fidetype_version": FT_VERSION, "seed": SEED})
            card = HB.score_outcomes(oc, alpha_wrong=0.05, alpha_fluent=0.01)
            stem = f"{meta['dataset']}--{name}--{mode}"
            (CARDS / f"{stem}.outcomes.json").write_text(json.dumps(oc, indent=0) + "\n", encoding="utf-8")
            (CARDS / f"{stem}.card.json").write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
            row["cards"][mode] = {"file": f"{stem}.card.json", "headline": card["headline"],
                                  "controls_passed": card["controls_passed"], "summary": HB.summary_line(card)}
            log(f"{s} {name} [{mode}]: {HB.summary_line(card)}")
        row["seconds"] = round(time.time() - ta, 1)
        out["systems"][name] = row
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main() -> None:
    args = sys.argv[1:] or ["t15", "t12"]
    sets = [a for a in args if a in ("t15", "t12")]
    systems = [a for a in args if a in SYSTEMS] or list(SYSTEMS)
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.update(fidetype_version=FT_VERSION, seed=SEED, n_null=N_NULL, protocol=HB.PROTOCOL)
    for s in sets:
        log(f"stage {s} start; systems {systems}")
        allr[s] = run_set(s, systems)
        path.write_text(json.dumps(allr, indent=1, default=str) + "\n", encoding="utf-8")
        log(f"stage {s} done in {allr[s]['seconds']} s")


if __name__ == "__main__":
    main()
