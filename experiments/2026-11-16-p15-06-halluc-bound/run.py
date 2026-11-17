"""P15-06 (F2): risk-controlled fluent-wrong (hallucination) bound on T15, from the cached P15-05 artefacts. Plan: plan.md.

For each P15-05 arm (same pipeline, same caches), ``fidetype.trust.calibrate(..., grounding=, llm=)`` fits the
P14-03 guard and then the P15-06 joint Learn then Test of (commit_p, tau_commit, tau_word) on val_select. The
final guard decides the 701 held-out val_eval trials, the held-out uniform / shuffled controls (the same seeded
draws as P15-05) and the swapped-signal control (the same derangement as P15-05).

Caches (read only): C:/Users/zhang/bci-data/derived/f2-e3-llm-grounding/ (base n-best pickle, LLM sqlite). The
LLM sqlite is copied once to the own folder; new LLM scores (if any) go into the copy only. New base n-best
entries (if any) go into an own pickle. Per-trial outputs: C:/Users/zhang/bci-data/derived/p15-06-halluc-bound/.

    .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
        .venv\\Scripts\\python.exe -I experiments/2026-11-16-p15-06-halluc-bound/run.py explore B1_rescore_G
    ... run.py arms            (all arms; finished arms are skipped)
    ... run.py t12 arms        (T12: the P15-05 T12 caches in f2-e3-llm-grounding/t12/, read only; outputs in
                                p15-06-halluc-bound/t12/, results/results-t12.json, log results/run-t12.log)

A first argument ``t15`` or ``t12`` selects the data set (default ``t15``, as run before). T12 uses the P15-05
T12 data (T12 v2 confirmatory logits; fit_a + calibration sessions -> calibration, test sessions -> held out),
the P15-05 T12 fluent threshold, tau and LLM weight. RAM: the T12 word decoder (char LM + word trigram, about
3.5 GB) loads only on a base n-best cache miss; the label function needs only the CMUdict lexicon.
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
import shutil  # noqa: E402
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
from fidetype.lm.llm import CachedRewriter, CachedScorer, add_rewrite, lattice_words, rescore, within_lattice  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust import halluc_bound as H  # noqa: E402
from fidetype.trust._align import align  # noqa: E402
from fidetype.trust.grounding import GroundingCheck, lexicon_label_fn  # noqa: E402

CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
P5 = json.loads((REPO / CFG["p15_05_config"]).read_text(encoding="utf-8"))  # the P15-05 config (read only)
P5RES = json.loads((REPO / CFG["p15_05_results"]).read_text(encoding="utf-8"))
DER = Path("C:/Users/zhang/bci-data/derived")
SRC_ROOT = DER / "f2-e3-llm-grounding"  # P15-05 caches: READ ONLY
OWN_ROOT = DER / "p15-06-halluc-bound"  # the only place this task writes per-trial files and caches
assert OWN_ROOT.name == "p15-06-halluc-bound" and SRC_ROOT != OWN_ROOT
SRC, OWN = SRC_ROOT, OWN_ROOT  # per data set (set_data): t15 = the roots (as run), t12 = the t12/ subfolders
SET = "t15"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOGF = OUT / "run.log"
SEED = P5["seed"]


def set_data(name: str) -> None:
    """Select the data set. t15 keeps the paths of the T15 run; t12 reads SRC_ROOT/t12 and writes OWN_ROOT/t12."""
    global SET, SRC, OWN, LOGF, P5RES
    assert name in ("t15", "t12")
    SET = name
    SRC = SRC_ROOT if name == "t15" else SRC_ROOT / name
    OWN = OWN_ROOT if name == "t15" else OWN_ROOT / name
    assert OWN_ROOT in (OWN, *OWN.parents) and SRC_ROOT not in (OWN, *OWN.parents)
    OWN.mkdir(parents=True, exist_ok=True)
    LOGF = OUT / ("run.log" if name == "t15" else f"run-{name}.log")
    P5RES = json.loads((REPO / CFG["p15_05_results" if name == "t15" else f"p15_05_results_{name}"])
                       .read_text(encoding="utf-8"))


def private_mb() -> int:
    """Private bytes of this process in MB (Windows; -1 elsewhere), for the RAM budget check in the log."""
    if os.name != "nt":
        return -1
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
    return int(m.PagefileUsage / 2**20)


def log(*a) -> None:
    mb = f"[{private_mb()} MB] " if SET != "t15" else ""
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + mb + " ".join(str(x) for x in a)
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


def temper(x: np.ndarray, T: float) -> np.ndarray:
    """As P15-05 run.temper (the swapped-signal language side uses it; the cache keys depend on it)."""
    z = np.asarray(x, dtype=np.float64) / T
    m = z.max(axis=1, keepdims=True)
    return (z - (m + np.log(np.exp(z - m).sum(axis=1, keepdims=True)))).astype(np.float32)


class DiskDict(dict):
    """A dict backed by a sqlite table (values: JSON); as P15-05, on the OWN copy of the cache."""

    def __init__(self, path: Path, table: str) -> None:
        super().__init__()
        assert OWN in path.parents
        self.db = sqlite3.connect(str(path))
        self.t = table
        self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} (k TEXT PRIMARY KEY, v TEXT)")
        for k, v in self.db.execute(f"SELECT k, v FROM {table}"):
            super().__setitem__(k, json.loads(v))
        self.new = 0

    def __setitem__(self, k, v) -> None:
        super().__setitem__(k, v)
        self.db.execute(f"INSERT OR REPLACE INTO {self.t} VALUES (?, ?)", (k, json.dumps(v)))
        self.new += 1
        if self.new % 20 == 0:
            self.db.commit()

    def flush(self) -> None:
        self.db.commit()


class LazyLLM:
    """The P15-05 LLM, loaded only on a cache miss (CPU, 4 threads)."""

    def __init__(self) -> None:
        self._m = None
        self.loaded = False

    def _get(self):
        if self._m is None:
            from fidetype.lm.llm import LlamaCppLLM

            m = P5["llm"]
            h = hashlib.sha256()
            with open(m["path"], "rb") as f:
                for b in iter(lambda: f.read(1 << 22), b""):
                    h.update(b)
            assert h.hexdigest() == m["sha256"], "model file SHA-256 mismatch"
            log("LLM cache miss: loading the model (CPU, 4 threads)")
            self._m = LlamaCppLLM(m["path"], n_threads=4, n_ctx=m["n_ctx"], seed=SEED, max_tokens=m["max_tokens"])
            self.loaded = True
        return self._m

    def score(self, texts):
        return self._get().score(texts)

    def rewrite(self, nbest_texts, constrained=True):
        return self._get().rewrite(nbest_texts, constrained)


# ---------------------------------------------------------------------------
# data (as P15-05 run.data_t15)
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


class LazyT12Decoder:
    """The P15-05 T12 word decoder, built only on the first base n-best cache miss (RAM: about 3.5 GB).

    ``lex`` (CMUdict lexicon; the grounding label function needs only ``lex.prons``) loads at once. The full
    decoder is the one of P15-05 ``data_t12`` (char LM + word trigram, tuned word decoder, smaller LRU memos)."""

    def __init__(self, bt, exp: Path, cfg: dict) -> None:
        self.bt, self.exp, self.cfg = bt, exp, cfg
        self.lex = bt.build_lexicon()
        self._dec = None
        self.loaded = False

    def _get(self):
        if self._dec is None:
            log("T12 base n-best cache miss: loading the T12 word decoder (char LM + word trigram)")
            dec = self.bt.Decoders([], self.cfg["word_decoder_tuned"])
            sys.path.insert(0, str(self.exp))
            import wordlm  # noqa: E402

            beta = self.cfg["word_lm"]["beta"]
            cache = Path(self.cfg["word_lm"]["cache"])
            assert cache.exists(), "word LM cache missing (would be rebuilt)"
            wm = wordlm.load_or_build(self.bt.CONFIG["tatoeba_eng"], cache, B.normalize_words)
            char = dec.lm.score_sentence
            dec.wdec.sentence_lm = lambda t: char(t) + beta * wm.score_sentence(t)
            dec.wdec.clear_caches()
            dec._wcache.clear()
            dec.wdec.set_cache_sizes(500, 5_000)  # a memo changes the speed of a call, never its result
            dec.lm._cache.resize(20_000)
            self._dec, self.loaded = dec, True
        return self._dec

    @property
    def _wcache(self):
        return self._get()._wcache

    @_wcache.setter
    def _wcache(self, v) -> None:
        self._get()._wcache = v

    def words_fn(self, stream):
        return self._get().words_fn(stream)


def data_t12():
    """As P15-05 run.data_t12 (same sessions, order and texts); the decoder is lazy (LazyT12Decoder)."""
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
    npz.clear()
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    return cal, held, LazyT12Decoder(bt, exp, cfg)


# ---------------------------------------------------------------------------
# the P15-05 pipeline, from the caches
# ---------------------------------------------------------------------------


class Pipeline:
    def __init__(self, dec, scorer, rewriter) -> None:
        self.dec = dec
        self.scorer = scorer
        self.rewriter = rewriter
        self.base: dict = pickle.loads((SRC / f"base-nbest-{SET}.pkl").read_bytes())
        self.extra_path = OWN / "base-nbest-extra.pkl"
        self.extra: dict = pickle.loads(self.extra_path.read_bytes()) if self.extra_path.exists() else {}
        self.base_miss = 0
        sym = {s: i for i, s in enumerate(B.SYMBOL_VOCAB)}
        g = P5["grounding"]
        self.label_fn = lexicon_label_fn(dec.lex.prons, sym, word_sep=" ", max_variants=g["max_variants"])
        gp = P5RES["ground_prep"]
        self.grounding = GroundingCheck(self.label_fn, tau=gp["tau"], blank=0, demote_margin=g["demote_margin"])
        self.lam = gp["llm_weight"]
        self.sep_id = sym[" "]
        self.calls = 0
        self.last: dict = {"base": [], "items": []}
        self.stats: dict = {}

    def save_extra(self) -> None:
        if self.base_miss:
            tmp = self.extra_path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps(self.extra))
            tmp.replace(self.extra_path)

    def base_nbest(self, x: np.ndarray) -> list[dict]:
        k = xkey(x)
        hit = self.base.get(k)
        if hit is None:
            hit = self.extra.get(k)
        if hit is not None:
            return hit
        self.base_miss += 1
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
        self.extra[k] = out
        if self.base_miss % 50 == 0:
            self.save_extra()
        return out

    def run(self, arm: dict, x: np.ndarray, lang_x: np.ndarray | None = None) -> list[dict]:
        self.calls += 1
        lx = x if lang_x is None else lang_x
        base = self.base_nbest(lx)
        items = self._run(arm, x, base)
        self.last = {"base": self.base_nbest(x) if lang_x is None else [], "items": items}
        return items

    def _run(self, arm: dict, x: np.ndarray, base: list[dict]) -> list[dict]:
        if not base:
            return []
        items = rescore(base, self.scorer, self.lam) if arm["rescore"] else [dict(d) for d in base]
        if arm["rewrite"]:
            guesses = [d["text"] for d in items[: P5["rewrite"]["n_guesses"]] if d["text"]]
            rw = self.rewriter.rewrite(guesses, constrained=arm["rewrite"] == "lattice") if guesses else ""
            if arm["rewrite"] == "lattice" and rw and not within_lattice(rw, [d["text"] for d in base]):
                self.stats["lattice_rejects"] = self.stats.get("lattice_rejects", 0) + 1
                rw = ""
            items = add_rewrite(items, rw, P5["rewrite"]["margin"])
        if arm["ground"]:
            own = self.base_nbest(x)
            if not own or not own[0]["text"]:
                return []
            items, _ = self.grounding.apply(items, x, own[0]["text"], key=xkey(x))
        return items

    def anchor(self, lp: np.ndarray) -> str:
        """The decoder top-1 without the LLM on the guard's input (the sentence-deficit anchor)."""
        b = self.base_nbest(np.asarray(lp, dtype=np.float32))
        return b[0]["text"] if b else ""


# ---------------------------------------------------------------------------
# metrics (as P15-05)
# ---------------------------------------------------------------------------


def word_errors(ref: str, hyp: str) -> int:
    r, h = ref.split(), hyp.split()
    return sum(1 for i, j in align(r, h) if i is None or j is None or r[i] != h[j])


def wrong_hyp_words(ref: str, hyp: str) -> list[str]:
    r, h = ref.split(), hyp.split()
    ok = [False] * len(h)
    for i, j in align(r, h):
        if i is not None and j is not None and r[i] == h[j]:
            ok[j] = True
    return [w for w, o in zip(h, ok) if not o]


def wer(refs, hyps) -> float:
    n = sum(len(r.split()) for r in refs)
    return sum(word_errors(r, h) for r, h in zip(refs, hyps)) / n


def swap_pairs(n: int, texts, seed: int) -> list[int]:
    """As P15-05 run.swap_pairs (same derangement)."""
    rng = np.random.default_rng([seed, 11])
    while True:
        p = rng.permutation(n)
        bad = [j for j in range(n) if p[j] == j or texts[p[j]] == texts[j]]
        if not bad:
            return [int(v) for v in p]
        for j in bad:
            k = int(rng.integers(0, n))
            p[j], p[k] = p[k], p[j]
        if all(p[j] != j and texts[p[j]] != texts[j] for j in range(n)):
            return [int(v) for v in p]


# ---------------------------------------------------------------------------
# one arm
# ---------------------------------------------------------------------------


def make_grounding(pipe: Pipeline) -> H.CommitGrounding:
    return H.CommitGrounding(pipe.label_fn, blank=0, word_sep_id=pipe.sep_id, anchor_fn=pipe.anchor,
                             name="cmudict-phonemes (16 variants), anchor = base top-1 without LLM")


def split_name(name: str) -> tuple[str, str]:
    """``"B1_rescore_G@most_right"`` -> (P15-05 arm, selection rule); no ``@``: the primary rule."""
    arm, _, rule = name.partition("@")
    return arm, rule or CFG["halluc"]["select"]


def calibrate_arm(pipe: Pipeline, arm_name: str, arm: dict, cal, explore: bool = False, select: str | None = None):
    cx, ct, cph = cal
    g = CFG["halluc"]

    def fn(lp: np.ndarray) -> list[dict]:
        return pipe.run(arm, np.asarray(lp, dtype=np.float32))

    t0 = time.time()
    guard = ft.calibrate(cx, ct, alpha=P5["alpha"], delta=P5["delta"], vocab=list(B.SYMBOL_VOCAB), blank=0,
                         input_scale="log_probs", frame_period=0.08, decode_fn=fn, stream_texts=cph,
                         decoder_name=f"f2-e3-{SET}-{arm_name}", modality="intracortical",
                         name=f"f2-e3-{SET}-{arm_name}", seed=SEED, null_trials=P5["null_trials"],
                         grounding=make_grounding(pipe), llm=pipe.scorer, halluc_alpha=g["alpha_h"],
                         halluc_delta=g["delta_h"], fluent_threshold=P5RES["prep"]["fluent_logp_per_word"],
                         halluc_select=select or g["select"],
                         halluc_grid=None if explore else {k: [math.inf if v == "inf" else v for v in g["grid"][k]]
                                                           for k in ("commit_p", "tau_commit", "tau_word")})
    return guard, time.time() - t0


def item_table(items) -> list[dict]:
    return [{"can": it.can_commit, "p": it.p_top1, "wrong": it.wrong, "fluent": it.fluent, "fb": it.fallback_wrong,
             "sd": it.stats.sentence_deficit, "wd": it.stats.max_word_deficit} for it in items]


def explore(pipe: Pipeline, arm_name: str, cal) -> None:
    """Design check on val_select only (no held-out trial): statistics of the would-be commits."""
    arm = P5["arms"][arm_name]
    guard, sec = calibrate_arm(pipe, arm_name, arm, cal, explore=True)
    rows = item_table(guard.halluc_items["order"] + guard.halluc_items["test"])
    (OWN / f"explore-items-{arm_name}.json").write_text(
        json.dumps({k: item_table(v) for k, v in guard.halluc_items.items()}), encoding="utf-8")
    com = [r for r in rows if r["can"]]
    rec = {"arm": arm_name, "seconds": round(sec, 1), "n": len(rows), "can_commit_at_p0": len(com),
           "halluc": guard.sheet.halluc, "base_commit_p": guard.sheet.halluc["base_commit_p"]}
    for lab, sel in (("right", [r for r in com if not r["wrong"]]),
                     ("wrong_fluent", [r for r in com if r["wrong"] and r["fluent"]]),
                     ("wrong_not_fluent", [r for r in com if r["wrong"] and not r["fluent"]])):
        rec[lab] = {"n": len(sel)}
        for k in ("p", "sd", "wd"):
            v = np.array([r[k] for r in sel], dtype=float)
            v = v[np.isfinite(v)]
            if v.size:
                rec[lab][k] = [float(np.quantile(v, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)]
    (OUT / (f"explore-{arm_name}.json" if SET == "t15" else f"explore-{SET}-{arm_name}.json")).write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    log(f"explore {arm_name}: {json.dumps(rec, default=str)}")


def run_arm(pipe: Pipeline, name: str, cal, held) -> dict:
    arm_name, rule = split_name(name)
    arm = P5["arms"][arm_name]
    hx, ht, _ = held
    fluent_thr = P5RES["prep"]["fluent_logp_per_word"]
    pipe.stats = {}
    t0 = time.time()
    row: dict = {"arm": arm, "p15_05_arm": arm_name, "select": rule}
    try:
        guard, sec = calibrate_arm(pipe, arm_name, arm, cal, select=rule)
    except ft.NullControlError as e:
        row.update(status="refused", controls=[c.to_dict() for c in e.report], message=str(e))
        log(f"{arm_name}: REFUSED {row['controls']}")
        return row
    row.update(status="ok", calibrate_seconds=round(sec, 1), config_id=guard.config_id, sheet=guard.sheet.to_dict())
    fname = name.replace("@", "-")
    guard.save(OWN / f"guard-{fname}.json")
    items = guard.halluc_items
    (OWN / f"cal-items-{fname}.json").write_text(json.dumps({k: item_table(v) for k, v in items.items()}),
                                                     encoding="utf-8")
    p5_guard = json.loads((SRC / f"guard-{SET}-{arm_name}.json").read_text(encoding="utf-8"))
    row["p15_05_config_id"] = p5_guard["sheet"]["config_id"]
    row["p15_05_commit_p"] = p5_guard["sheet"]["commit_threshold"]
    row["base_config_matches_p15_05"] = guard.sheet.halluc["base_config_id"] == row["p15_05_config_id"]
    # held-out decisions
    T_used = guard.config.frame_temperature
    row["frame_temperature"] = T_used
    tops, res, bags = [], [], []
    for i, x in enumerate(hx):
        n0 = pipe.calls
        res.append(guard.decide(x, utterance_id=f"p15-06-{fname}-{i}"))
        assert pipe.calls >= n0 + 1
        it = pipe.last["items"]
        tops.append(it[0]["text"] if it else "")
        bags.append(lattice_words(d["text"] for d in pipe.last["base"]))
    n = len(res)
    row["wer"] = wer(ht, tops)
    row["sentence_acc"] = float(np.mean([a == b for a, b in zip(tops, ht)]))
    com = [(r, t) for r, t in zip(res, ht) if r.action == "commit"]
    nw = sum(r.text != t for r, t in com)
    out_words = unsup = unsup_commit = fluent_wrong = 0
    fw_list = []
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
                f = H.is_fluent(r.text, pipe.scorer, fluent_thr)
                fluent_wrong += f
                fw_list.append({"fluent": bool(f)})
    acts = {a: sum(r.action == a for r in res) for a in ("commit", "offer", "withhold")}
    blocked = sum(r.reason.startswith("commit blocked: text not grounded") for r in res)
    row.update(n=n, actions=acts, n_commit=len(com), n_wrong_commit=nw, wrong_commit_rate=nw / n,
               wrong_commit_cp95=cp(nw, n), fluent_wrong_commits=int(fluent_wrong),
               fluent_wrong_rate=fluent_wrong / n, fluent_wrong_cp95=cp(int(fluent_wrong), n),
               halluc_gate_blocked=int(blocked), shown_words=out_words, unsupported_words=unsup,
               hallucination_rate=(unsup / out_words) if out_words else 0.0,
               unsupported_committed_words=unsup_commit,
               bound_holds_wc=nw / n <= P5["alpha"], bound_holds_fw=fluent_wrong / n <= CFG["halluc"]["alpha_h"])
    per_trial = {"tops": tops, "decisions": [{"action": r.action, "text": r.text, "choices": list(r.choices),
                                              "p": r.p_top1, "risk": r.guard_risk, "reason": r.reason} for r in res]}
    # held-out null controls: the same seeded draws as P15-05 run_arm
    rng = np.random.default_rng([SEED, 7])
    idx = rng.integers(0, n, P5["null_trials"])
    V = len(B.SYMBOL_VOCAB)
    ctrl = {}
    for kind in ("uniform", "shuffled"):
        commits = 0
        for i in idx:
            x = hx[i]
            if kind == "uniform":
                z = np.full((x.shape[0], V), -math.log(V)) + 0.05 * rng.standard_normal((x.shape[0], V))
                z = (z - np.log(np.exp(z).sum(1, keepdims=True))).astype(np.float32)
            else:
                z = x[rng.permutation(x.shape[0])]
            commits += guard.decide(z, utterance_id=kind).action == "commit"
        ctrl[kind] = {"n": int(len(idx)), "commits": commits}
    # swapped signal: language side from trial i, evidence from trial j (as P15-05)
    perm = swap_pairs(n, ht, SEED)
    sw_commit = sw_unsup = sw_leak = 0
    state = {"i": 0}
    sguard = ft.load(OWN / f"guard-{fname}.json", grounding=make_grounding(pipe),
                     decode_fn=lambda lp: pipe.run(arm, np.asarray(lp, dtype=np.float32),
                                                   lang_x=temper(hx[state["i"]], T_used)))
    for j, i in enumerate(perm):
        state["i"] = i
        r = sguard.decide(hx[j], utterance_id=f"swapped-{j}")
        if r.action == "commit":
            sw_commit += 1
            sw_unsup += r.text != ht[j]
            sw_leak += r.text == ht[i]
    ctrl["swapped"] = {"n": n, "commits": sw_commit, "commits_not_truth_of_signal": sw_unsup,
                       "commits_equal_truth_of_language_trial": sw_leak}
    row["controls_held_out"] = ctrl
    row["stats"] = dict(pipe.stats)
    row["cache"] = {"base_misses": pipe.base_miss, "llm_new_scores": pipe.scorer.store.new,
                    "llm_new_rewrites": pipe.rewriter.store.new}
    row["seconds"] = round(time.time() - t0, 1)
    (OWN / f"trials-{fname}.json").write_text(json.dumps(per_trial), encoding="utf-8")
    pipe.save_extra()
    pipe.scorer.store.flush()
    pipe.rewriter.store.flush()
    return row


def main() -> None:
    args = sys.argv[1:]
    set_data(args.pop(0) if args and args[0] in ("t15", "t12") else "t15")
    stage = args[0] if args else "arms"
    only = args[1:]
    db = OWN / "llm-cache.sqlite"
    if not db.exists():
        shutil.copy2(SRC / "llm-cache.sqlite", db)  # the P15-05 cache stays untouched
    llm = LazyLLM()
    sc = CachedScorer(llm, DiskDict(db, "scores"))
    rw = CachedRewriter(llm, DiskDict(db, "rewrites"))
    log(f"start {stage} {only} (fidetype {FT_VERSION}); cached LLM scores {len(sc.store)}, rewrites {len(rw.store)}")
    cal, held, dec = {"t15": data_t15, "t12": data_t12}[SET]()
    log(f"{SET} data: {len(cal[0])} calibration, {len(held[0])} held-out trials")
    pipe = Pipeline(dec, sc, rw)
    if stage == "explore":
        for a in only or ["B1_rescore_G"]:
            explore(pipe, a, cal)
        log(f"explore done; T12 decoder loaded {getattr(dec, 'loaded', None)}; base misses {pipe.base_miss}, new LLM scores {sc.store.new}, LLM loaded {llm.loaded}")
        return
    path = OUT / f"results-{SET}.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.update(fidetype_version=FT_VERSION, config=CFG)
    allr.setdefault("arms", {})
    for a in only or (CFG["arms_primary"] + CFG["arms_secondary"]):
        if a in allr["arms"]:
            log(f"{a}: done before, skip")
            continue
        log(f"{a}: start")
        row = run_arm(pipe, a, cal, held)
        allr["arms"][a] = row
        path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
        keys = ("status", "wer", "n_commit", "n_wrong_commit", "fluent_wrong_commits", "halluc_gate_blocked",
                "controls_held_out", "cache", "seconds")
        log(f"{a}: done {json.dumps({k: row.get(k) for k in keys}, default=str)}")
    log(f"all done; T12 decoder loaded {getattr(dec, 'loaded', None)}, LLM loaded {llm.loaded}")


if __name__ == "__main__":
    main()
