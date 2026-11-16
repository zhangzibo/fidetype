"""P15-05 (F2 / E3): LLM rescoring / rewrite with a run-time grounding check, on T15 (and T12). Plan: plan.md.

CPU only. The LLM runs through llama-cpp-python (repo venv extra ``[llm]``) on a local GGUF file outside the repo.

Stages (each resumes from its saved output):
  prep   base n-gram decode (cached), tau from the true val_select texts, LLM weight on val_select,
         fluent threshold.
  arms   per arm: fidetype.trust.calibrate on val_select, guard.decide on val_eval, held-out null controls
         (uniform 300, shuffled 300) and the swapped-signal control (701).

Run (repo root), detached: see launch_detached.py. Foreground:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-f2-e3-llm-grounding/run.py t15 prep arms
Per-trial outputs and caches: C:/Users/zhang/bci-data/derived/f2-e3-llm-grounding/ only. Repo: aggregates.
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
from fidetype.lm.llm import (  # noqa: E402
    CachedRewriter,
    CachedScorer,
    add_rewrite,
    lattice_words,
    rescore,
    within_lattice,
)
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust._align import align  # noqa: E402
from fidetype.trust.grounding import GroundingCheck, fit_tau, lexicon_label_fn  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
DER = Path("C:/Users/zhang/bci-data/derived")
OWN_ROOT = DER / "f2-e3-llm-grounding"  # the only place this task writes per-trial files and caches
assert OWN_ROOT.name == "f2-e3-llm-grounding"
OWN = OWN_ROOT  # set per data set by set_paths (t15: the root, as run; t12: the subfolder t12/)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOGF = OUT / "run.log"
SEED = CFG["seed"]


def set_paths(name: str, smoke: bool = False) -> Path:
    """Per-set output folder. t15 keeps the root folder (the T15 run used it); t12 writes only to t12/ and logs to
    results/run-t12.log. Smoke tests write to a smoke/ subfolder, so no cache or guard file mixes with a real run."""
    global OWN, LOGF
    OWN = OWN_ROOT if name == "t15" else OWN_ROOT / name
    LOGF = OUT / ("run.log" if name == "t15" else f"run-{name}.log")
    if smoke:
        OWN = OWN / "smoke"
    OWN.mkdir(parents=True, exist_ok=True)
    return OWN


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cp(k: int, n: int, level: float = 0.95) -> list:
    from scipy.stats import beta

    a = 1 - level
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def xkey(x: np.ndarray) -> bytes:
    return hashlib.sha1(np.ascontiguousarray(x, dtype=np.float32).tobytes()).digest()


# ---------------------------------------------------------------------------
# persistent memo (sqlite; survives a stop, so a re-run resumes)
# ---------------------------------------------------------------------------


class DiskDict(dict):
    """A dict backed by a sqlite table (values: JSON). Writes go to disk at once (batched commits)."""

    def __init__(self, path: Path, table: str) -> None:
        super().__init__()
        self.db = sqlite3.connect(str(path))
        self.t = table
        self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} (k TEXT PRIMARY KEY, v TEXT)")
        for k, v in self.db.execute(f"SELECT k, v FROM {table}"):
            super().__setitem__(k, json.loads(v))
        self._n = 0

    def __setitem__(self, k, v) -> None:
        super().__setitem__(k, v)
        self.db.execute(f"INSERT OR REPLACE INTO {self.t} VALUES (?, ?)", (k, json.dumps(v)))
        self._n += 1
        if self._n % 50 == 0:
            self.db.commit()

    def flush(self) -> None:
        self.db.commit()


# ---------------------------------------------------------------------------
# data (same sets and splits as P14-03)
# ---------------------------------------------------------------------------


def ph_symbols(npz: dict, folder: Path, s: str, part: str, i: int) -> str:
    if s not in npz:
        npz[s] = np.load(folder / f"{s}.npz")
    return B.phonemes_to_symbols([B.VOCAB[j] for j in npz[s][f"{part}_ph{i}"]])


def data_t15():
    d_in = DER / "m4-01-02-lookahead"
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    order = {s: j for j, s in enumerate(sessions)}
    npz: dict = {}

    def part(path: Path, name: str):
        z = np.load(path)
        keys = sorted((k for k in z.files if f"|{name}|" in k),
                      key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
        xs, ts, ph = [], [], []
        for k in keys:
            s, p, i, _ = k.split("|")
            xs.append(z[k].astype(np.float32))
            ts.append(" ".join(texts[s][p][int(i)].split()))
            ph.append(ph_symbols(npz, d_in, s, p, int(i)))
        return xs, ts, ph

    cal = part(DER / "m2-19-trust-retune/logprobs-m2-19-m4-12-fixed0.npz", "val_select")
    held = part(d_in / "logprobs-m4-12-fixed0.npz", "val_eval")
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    return cal, held, dec


def data_t12():
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    meta = json.loads((d_in / "logprobs-meta.json").read_text(encoding="utf-8"))
    assert meta["checkpoint_sha256"] == cfg["decoder_checkpoint_sha256"]
    z = np.load(d_in / "logprobs.npz")
    npz: dict = {}

    def part(roles):
        xs, ts, ph = [], [], []
        for r in prep["sessions"]:
            if r["role"] not in roles:
                continue
            s = r["session"]
            for i, w in enumerate(texts[s]["pool"]):
                xs.append(z[f"{s}|pool|{i}"].astype(np.float32))
                ts.append(" ".join(w.split()))
                ph.append(ph_symbols(npz, d_in, s, "pool", i))
        return xs, ts, ph

    cal, held = part(("fit_a", "calibration")), part(("test",))
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
    return cal, held, dec


# ---------------------------------------------------------------------------
# the pipeline
# ---------------------------------------------------------------------------


class Pipeline:
    def __init__(self, name: str, dec, llm_scorer, llm_rewriter):
        self.name = name
        self.dec = dec
        self.scorer = llm_scorer
        self.rewriter = llm_rewriter
        self.base_cache_path = OWN / f"base-nbest-{name}.pkl"
        self.base: dict = pickle.loads(self.base_cache_path.read_bytes()) if self.base_cache_path.exists() else {}
        self._new_base = 0
        sym = {s: i for i, s in enumerate(B.SYMBOL_VOCAB)}
        self.label_fn = lexicon_label_fn(dec.lex.prons, sym, word_sep=" ", max_variants=CFG["grounding"]["max_variants"])
        self.grounding = GroundingCheck(self.label_fn, tau=math.inf, blank=0,
                                        demote_margin=CFG["grounding"]["demote_margin"])
        self.lam = 0.0
        self.stats: dict = {}
        self.calls = 0
        self.last: dict = {"base": [], "items": []}
        self.frame_T = 1.0

    def save_base(self) -> None:
        if self._new_base:
            tmp = self.base_cache_path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps(self.base))
            tmp.replace(self.base_cache_path)
            self._new_base = 0

    def base_nbest(self, x: np.ndarray) -> list[dict]:
        """The current decoder: phoneme beam + lexicon + n-gram LM (the P14-03 word route)."""
        k = xkey(x)
        hit = self.base.get(k)
        if hit is not None:
            return hit
        lp = np.ascontiguousarray(x, dtype=np.float32)
        st = NeuralTextStream(log_probs=lp, frame_times=np.arange(lp.shape[0]) * 0.08, vocab=list(B.SYMBOL_VOCAB),
                              blank_id=0, vocab_type="phoneme")
        self.dec._wcache = {}
        nb = self.dec.words_fn(st)
        out = []
        for c in nb.candidates:
            d = {"text": c.text, "score": float(c.score)}
            for f in ("logp_acoustic", "logp_lm"):
                v = float(getattr(c, f))
                if math.isfinite(v) and v <= 0:
                    d[f] = v
            if c.char_confidences:
                d["char_confidences"] = [min(1.0, max(0.0, float(x))) for x in c.char_confidences]
            out.append(d)
        self.base[k] = out
        self._new_base += 1
        if self._new_base >= 200:
            self.save_base()
        return out

    def run(self, arm: dict, x: np.ndarray, lang_x: np.ndarray | None = None) -> list[dict]:
        """One arm on input ``x``. ``lang_x``: the swapped-signal control (language side from another trial)."""
        self.calls += 1
        items = self._run(arm, x, lang_x)
        self.last = {"base": self.base_nbest(x) if lang_x is None else [], "items": items}
        return items

    def _run(self, arm: dict, x: np.ndarray, lang_x: np.ndarray | None) -> list[dict]:
        lx = x if lang_x is None else lang_x
        base = self.base_nbest(lx)
        if not base:
            return []
        items = rescore(base, self.scorer, self.lam) if arm["rescore"] else [dict(d) for d in base]
        if arm["rewrite"]:
            guesses = [d["text"] for d in items[: CFG["rewrite"]["n_guesses"]] if d["text"]]
            rw = self.rewriter.rewrite(guesses, constrained=arm["rewrite"] == "lattice") if guesses else ""
            if arm["rewrite"] == "lattice" and rw and not within_lattice(rw, [d["text"] for d in base]):
                self.stats["lattice_rejects"] = self.stats.get("lattice_rejects", 0) + 1
                rw = ""
            items = add_rewrite(items, rw, CFG["rewrite"]["margin"])
        if arm["ground"]:
            own = self.base_nbest(x)
            if not own or not own[0]["text"]:
                return []
            items, _ = self.grounding.apply(items, x, own[0]["text"], key=xkey(x))
        return items


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def word_errors(ref: str, hyp: str) -> int:
    r, h = ref.split(), hyp.split()
    return sum(1 for i, j in align(r, h) if i is None or j is None or r[i] != h[j])


def wrong_hyp_words(ref: str, hyp: str) -> list[str]:
    """Words of ``hyp`` that the alignment does not match to an equal word of ``ref``."""
    r, h = ref.split(), hyp.split()
    ok = [False] * len(h)
    for i, j in align(r, h):
        if i is not None and j is not None and r[i] == h[j]:
            ok[j] = True
    return [w for w, o in zip(h, ok) if not o]


def wer(refs, hyps) -> float:
    n = sum(len(r.split()) for r in refs)
    return sum(word_errors(r, h) for r, h in zip(refs, hyps)) / n


def paired_bootstrap(refs, h_a, h_b, B_: int, seed: int) -> dict:
    """WER(b) - WER(a): point and 95 % percentile interval over trials."""
    e_a = np.array([word_errors(r, h) for r, h in zip(refs, h_a)], dtype=np.float64)
    e_b = np.array([word_errors(r, h) for r, h in zip(refs, h_b)], dtype=np.float64)
    n_w = np.array([len(r.split()) for r in refs], dtype=np.float64)
    rng = np.random.default_rng(seed)
    n = len(refs)
    d = []
    for _ in range(B_):
        idx = rng.integers(0, n, n)
        d.append((e_b[idx].sum() - e_a[idx].sum()) / n_w[idx].sum())
    return {"diff": float((e_b.sum() - e_a.sum()) / n_w.sum()), "ci95": [float(np.percentile(d, 2.5)),
                                                                         float(np.percentile(d, 97.5))]}


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------


def make_llm():
    from fidetype.lm.llm import LlamaCppLLM

    m = CFG["llm"]
    path = Path(m["path"])
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    assert h.hexdigest() == m["sha256"], "model file SHA-256 mismatch"
    llm = LlamaCppLLM(str(path), n_threads=m["n_threads"], n_ctx=m["n_ctx"], seed=SEED, max_tokens=m["max_tokens"])
    sc = CachedScorer(llm, DiskDict(OWN / "llm-cache.sqlite", "scores"))
    rw = CachedRewriter(llm, DiskDict(OWN / "llm-cache.sqlite", "rewrites"))
    return sc, rw


def temper(x: np.ndarray, T: float) -> np.ndarray:
    """What a calibrated guard gives its decode_fn: log_softmax(x / frame T) (checked in the smoke test)."""
    z = np.asarray(x, dtype=np.float64) / T
    m = z.max(axis=1, keepdims=True)
    return (z - (m + np.log(np.exp(z - m).sum(axis=1, keepdims=True)))).astype(np.float32)


def stage_prep(name: str, pipe: Pipeline, cal) -> dict:
    """Fluent threshold: median LLM log-prob per word of the true val_select texts."""
    _, ct, _ = cal
    lps = pipe.scorer.score(ct)
    per_word = [lp / max(1, len(t.split())) for lp, t in zip(lps, ct)]
    pipe.scorer.store.flush()
    out = {"fluent_logp_per_word": float(np.median(per_word)), "n_cal": len(ct)}
    log(f"{name} prep done: {out}")
    return out


def stage_ground_prep(name: str, pipe: Pipeline, cal, frame_T: float) -> dict:
    """tau and the LLM weight, on val_select inputs as the guard sees them (tempered with the A0 frame T)."""
    t0 = time.time()
    cx, ct, _ = cal
    xs = [temper(x, frame_T) for x in cx]
    d_true = []
    n_oov = 0
    base_top = []
    for i, (x, t) in enumerate(zip(xs, ct)):
        own = pipe.base_nbest(x)
        base_top.append(own[0]["text"] if own else "")
        if not own or not own[0]["text"]:
            d_true.append(math.inf)
            continue
        d = float(pipe.grounding.deficits(x, [t], own[0]["text"], key=xkey(x))[0])
        n_oov += not math.isfinite(d)
        d_true.append(d)
        if i % 200 == 0:
            log(f"{name} ground prep: {i}/{len(xs)}")
    pipe.save_base()
    tau = fit_tau(d_true, CFG["grounding"]["coverage"])
    fin = np.array([d for d in d_true if math.isfinite(d)])
    log(f"{name} ground prep: tau {tau:.4f}, true texts without labels {n_oov}")
    grid = {}
    for lam in CFG["llm_weight_grid"]:
        pipe.lam = lam
        tops = [(pipe.run({"rescore": True, "rewrite": None, "ground": False}, x) or [{"text": ""}])[0]["text"]
                for x in xs]
        grid[str(lam)] = wer(ct, tops)
        log(f"{name} ground prep: lambda {lam}: val_select WER {grid[str(lam)]:.4f}")
    lam = float(min(CFG["llm_weight_grid"], key=lambda v: (grid[str(v)], v)))
    pipe.scorer.store.flush()
    out = {"frame_temperature": frame_T, "tau": tau,
           "true_deficit_quantiles": {str(q): float(np.quantile(fin, q)) for q in (0.5, 0.9, 0.95, 0.99)}
           if fin.size else {}, "true_deficit_pass_rate_at_tau": float(np.mean(np.array(d_true) <= tau)),
           "true_without_labels": n_oov, "llm_weight_grid_wer": grid, "llm_weight": lam,
           "base_val_select_wer": wer(ct, base_top), "seconds": round(time.time() - t0, 1)}
    log(f"{name} ground prep done: {out}")
    return out


def run_arm(name: str, pipe: Pipeline, arm_name: str, arm: dict, cal, held, alpha: float) -> dict:
    t0 = time.time()
    cx, ct, cph = cal
    hx, ht, _ = held
    fluent_thr = pipe.fluent_thr

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    row: dict = {"arm": arm, "alpha": alpha}
    pipe.stats = {}
    try:
        guard = ft.calibrate(cx, ct, alpha=alpha, delta=CFG["delta"], vocab=list(B.SYMBOL_VOCAB), blank=0,
                             input_scale="log_probs", frame_period=0.08, decode_fn=fn, stream_texts=cph,
                             decoder_name=f"f2-e3-{name}-{arm_name}", modality="intracortical",
                             name=f"f2-e3-{name}-{arm_name}", seed=SEED, null_trials=NULL_TRIALS)
    except ft.NullControlError as e:
        row.update(status="refused", controls=[c.to_dict() for c in e.report], message=str(e))
        log(f"{name} {arm_name}: REFUSED {row['controls']}")
        guard = None
    if guard is not None:
        row["status"] = "ok"
        row["config_id"] = guard.config_id
        row["sheet"] = guard.sheet.to_dict()
        guard.save(OWN / f"guard-{name}-{arm_name}.json")
    # held-out: pipeline top-1 for WER; guard decisions for commits
    # held-out: the guard decides; the pipeline output of that same call (pipe.last) gives the top-1 for WER
    tops, res, bags, base_tops = [], [], [], []
    T_used = guard.config.frame_temperature if guard is not None else pipe.frame_T
    row["frame_temperature"] = T_used
    for i, x in enumerate(hx):
        n0 = pipe.calls
        if guard is not None:
            res.append(guard.decide(x, utterance_id=f"{name}-{arm_name}-{i}"))
        else:
            pipe.run(arm, temper(x, T_used))
        assert pipe.calls == n0 + 1, "expected one decode per decision"
        items = pipe.last["items"]
        tops.append(items[0]["text"] if items else "")
        bags.append(lattice_words(d["text"] for d in pipe.last["base"]))
        base_tops.append(pipe.last["base"][0]["text"] if pipe.last["base"] else "")
    row["wer"] = wer(ht, tops)
    row["sentence_acc"] = float(np.mean([a == b for a, b in zip(tops, ht)]))
    row["top1_changed_vs_base"] = int(sum(a != b for a, b in zip(tops, base_tops)))
    row["stats"] = dict(pipe.stats)
    per_trial = {"tops": tops}
    if guard is not None:
        n = len(res)
        com = [(r, t) for r, t in zip(res, ht) if r.action == "commit"]
        nw = sum(r.text != t for r, t in com)
        # hallucination: wrong words outside the decoder lattice, in commits and first offers
        out_words = unsup = unsup_commit = 0
        fluent_wrong = 0
        for r, t, bag in zip(res, ht, bags):
            shown = r.text if r.action == "commit" else (r.choices[0] if r.action == "offer" and r.choices else None)
            if not shown:
                continue
            ws = shown.split()
            bad = [w for w in wrong_hyp_words(t, shown) if w not in bag]
            out_words += len(ws)
            unsup += len(bad)
            if r.action == "commit":
                unsup_commit += len(bad)
                if r.text != t:
                    lp = pipe.scorer.score([r.text])[0]
                    fluent_wrong += lp / max(1, len(ws)) >= fluent_thr
        acts = {a: sum(r.action == a for r in res) for a in ("commit", "offer", "withhold")}
        row.update(n=n, actions=acts, n_commit=len(com), n_wrong_commit=nw, wrong_commit_rate=nw / n,
                   wrong_commit_cp95=cp(nw, n), error_among_commits=(nw / len(com)) if com else None,
                   shown_words=out_words, unsupported_words=unsup, hallucination_rate=(unsup / out_words)
                   if out_words else 0.0, unsupported_committed_words=unsup_commit,
                   fluent_wrong_commits=int(fluent_wrong), pass_alpha=nw / n <= alpha)
        per_trial["decisions"] = [{"action": r.action, "text": r.text, "choices": list(r.choices), "p": r.p_top1,
                                   "risk": r.guard_risk} for r in res]
        # held-out null controls (own seeded draws from val_eval) and the swapped-signal control
        rng = np.random.default_rng([SEED, 7])
        idx = rng.integers(0, n, NULL_TRIALS)
        V = len(B.SYMBOL_VOCAB)
        ctrl = {}
        for kind in ("uniform", "shuffled"):
            commits = fluent_c = 0
            texts_c = []
            for i in idx:
                x = hx[i]
                if kind == "uniform":
                    z = np.full((x.shape[0], V), -math.log(V)) + 0.05 * rng.standard_normal((x.shape[0], V))
                    z = (z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32)
                else:
                    z = x[rng.permutation(x.shape[0])]
                r = guard.decide(z, utterance_id=f"{kind}")
                if r.action == "commit":
                    commits += 1
                    texts_c.append(r.text)
                    fluent_c += bool(r.text) and len(r.text.split()) >= 2
            ctrl[kind] = {"n": int(len(idx)), "commits": commits, "commits_2plus_words": fluent_c,
                          "max_allowed_plan": CFG["null_max_commits"]}
        # swapped signal: language side from trial i, evidence (grounding input and trust input) from trial j
        perm = swap_pairs(len(hx), ht, SEED)
        sw_commit = sw_unsup = sw_leak = 0
        state = {"i": 0}
        sguard = ft.load(OWN / f"guard-{name}-{arm_name}.json",
                         decode_fn=lambda lp: pipe.run(arm, np.asarray(lp, dtype=np.float32),
                                                       lang_x=temper(hx[state["i"]], T_used)))
        for j, i in enumerate(perm):
            state["i"] = i
            r = sguard.decide(hx[j], utterance_id=f"swapped-{j}")
            if r.action == "commit":
                sw_commit += 1
                sw_unsup += r.text != ht[j]
                sw_leak += r.text == ht[i]
        ctrl["swapped"] = {"n": len(hx), "commits": sw_commit, "commits_not_truth_of_signal": sw_unsup,
                           "commits_equal_truth_of_language_trial": sw_leak}
        row["controls_held_out"] = ctrl
    row["seconds"] = round(time.time() - t0, 1)
    (OWN / f"trials-{name}-{arm_name}.json").write_text(json.dumps(per_trial), encoding="utf-8")
    pipe.save_base()
    for st in (pipe.scorer.store, pipe.rewriter.store):
        st.flush()
    return row


def swap_pairs(n: int, texts, seed: int) -> list[int]:
    """A seeded derangement with a different text in each pair (i = perm[j], texts differ)."""
    rng = np.random.default_rng([seed, 11])
    while True:
        p = rng.permutation(n)
        bad = [j for j in range(n) if p[j] == j or texts[p[j]] == texts[j]]
        if not bad:
            return [int(v) for v in p]
        for j in bad:  # local repair
            k = int(rng.integers(0, n))
            p[j], p[k] = p[k], p[j]
        if all(p[j] != j and texts[p[j]] != texts[j] for j in range(n)):
            return [int(v) for v in p]


ARMS = CFG["arms"]
NULL_TRIALS = int(os.environ.get("F2E3_NULL", CFG["null_trials"]))  # smoke tests only; the runs use the config


def main() -> None:
    args = sys.argv[1:]
    name = args[0]
    stages = args[1:] or ["prep", "arms"]
    only = os.environ.get("F2E3_ARMS")
    limit = int(os.environ.get("F2E3_LIMIT", "0"))  # smoke tests only (val_select subset); 0 = all
    set_paths(name, smoke=bool(limit))
    path = OUT / (f"results-{name}.json" if not limit else f"smoke-{name}.json")
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = FT_VERSION
    allr["config"] = CFG
    log(f"{name}: start stages {stages} limit {limit}")
    cal, held, dec = {"t15": data_t15, "t12": data_t12}[name]()
    if limit:  # smoke test: val_select only (the held-out set is not touched)
        held = tuple(v[limit: 2 * limit] for v in cal)
        cal = tuple(v[:limit] for v in cal)
    sc, rw = make_llm()
    pipe = Pipeline(name, dec, sc, rw)
    if "prep" not in allr:
        allr["prep"] = stage_prep(name, pipe, cal)
        path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
    pipe.fluent_thr = allr["prep"]["fluent_logp_per_word"]
    if "arms" in stages:
        allr.setdefault("arms", {})
        order = ["A0_ngram"] + [a for a in ARMS if a != "A0_ngram"]
        for arm_name in order:
            arm = ARMS[arm_name]
            if arm_name != "A0_ngram" and "ground_prep" not in allr:
                T = allr["arms"]["A0_ngram"]["frame_temperature"]
                allr["ground_prep"] = stage_ground_prep(name, pipe, cal, T)
                path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
            if "ground_prep" in allr:
                gp = allr["ground_prep"]
                pipe.grounding.tau, pipe.lam, pipe.frame_T = gp["tau"], gp["llm_weight"], gp["frame_temperature"]
            if only and arm_name not in only.split(","):
                continue
            if arm_name in allr["arms"]:
                log(f"{name} {arm_name}: done before, skip")
                continue
            log(f"{name} {arm_name}: start {arm}")
            row = run_arm(name, pipe, arm_name, arm, cal, held, CFG["alpha"])
            if "ground_prep" in allr:
                row["frame_temperature_matches_ground_prep"] = abs(row["frame_temperature"] - pipe.frame_T) < 1e-9
            allr["arms"][arm_name] = row
            path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
            keys = ("status", "wer", "sentence_acc", "n_commit", "n_wrong_commit", "hallucination_rate",
                    "fluent_wrong_commits", "controls_held_out", "seconds")
            log(f"{name} {arm_name}: done {json.dumps({k: row.get(k) for k in keys}, default=str)}")
    log(f"{name}: all done")


if __name__ == "__main__":
    main()
