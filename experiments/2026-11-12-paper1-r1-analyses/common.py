"""Shared code for the Paper 1 round-1 analyses (CPU only).

Builds the six evaluation conditions of the Paper 1 main table exactly as the
source experiments did, and gives one set of tools for per-item outcomes,
cluster bootstraps and the CRC / LTT thresholds:

- ``b2t``: Brain-to-Text '25 (T15), our phoneme -> word decoder (``ours``) and
  the published-sentence gate (``published``). Source: 2026-11-10-b2t25-trust,
  2026-11-11-m2-13-conformal. Fit = first half of each day's 125k trials (file
  order), test = second half. CI unit: day cluster (14 test days).
- ``meg``: SpanishBCBL async M1-09 r4b-full-medium streams. Source:
  2026-11-11-g1-async-meg-trust. Fit on val (11 sentences), test 637 instances.
  CI unit: two-way bootstrap (17 sentences x 19 participants).
- ``emg``: Toronto sEMG composed sentences, conditions ``calib`` (session-
  calibrated), ``xsession``, ``xsubject``. Source: 2026-11-11-emg-toronto,
  2026-11-11-m2-16-online-recal/emg_items.py. Fit = fit-A (temperatures,
  conformal) + fit-B (policy grid). CI unit: participant cluster (19).

Decodes are cached on disk outside the repo (``CACHE``), keyed by a hash of the
(frame-scaled) log-probabilities and the decoder settings, so the analyses can
share them. No raw signal, text or participant data is written into the repo.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import hashlib
import importlib.util
import json
import math
import pickle
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.eval.ewpm import correct_words_strict  # noqa: E402
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.interact.simulated_user import UserConfig  # noqa: E402
from fidetype.trust.risk_control import crc_threshold, ltt_threshold  # noqa: E402

CACHE = Path("C:/Users/zhang/bci-data/cache/paper1-r1")
CACHE.mkdir(parents=True, exist_ok=True)
ALPHA = 0.05
DELTA = 0.1
SEED = 0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Log:
    path: Path | None = None


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    if Log.path is not None:
        with open(Log.path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        v = float(o)
        if math.isnan(v):
            return None
        if math.isinf(v):
            return "inf" if v > 0 else "-inf"
        return v
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), indent=1, default=str), encoding="utf-8")


def fnum(x) -> float:
    if isinstance(x, str):
        return {"inf": math.inf, "-inf": -math.inf}.get(x, float("nan"))
    return float("nan") if x is None else float(x)


# ---------------------------------------------------------------------------
# Disk cache for decodes
# ---------------------------------------------------------------------------


class DiskCachedDecoder:
    """Wrap ``fn(stream) -> NBest`` with a pickle cache keyed by the stream's log-probs.

    ``tag`` must name every setting that changes the output (LM, weights, ...).
    The frame temperature is inside the log-probs, so it needs no tag.
    """

    def __init__(self, fn, tag: str):
        self.fn = fn
        self.tag = tag
        self.path = CACHE / f"decode-{tag}.pkl"
        self.d: dict = {}
        if self.path.exists():
            try:
                self.d = pickle.loads(self.path.read_bytes())
            except Exception:  # noqa: BLE001
                self.d = {}
        self.new = 0
        self.__name__ = f"cached_{tag}"

    def key(self, stream) -> str:
        h = hashlib.sha1(np.ascontiguousarray(stream.log_probs, dtype=np.float32).tobytes())
        h.update(str(stream.meta.get("fidetype.trial_index", "")).encode())
        return h.hexdigest()

    def __call__(self, stream):
        k = self.key(stream)
        hit = self.d.get(k)
        if hit is None:
            hit = self.fn(stream)
            self.d[k] = hit
            self.new += 1
            if self.new % 400 == 0:
                self.save()
        return hit

    def save(self) -> None:
        if not self.new:
            return
        cur = {}
        if self.path.exists():  # merge with what another process saved
            try:
                cur = pickle.loads(self.path.read_bytes())
            except Exception:  # noqa: BLE001
                cur = {}
        cur.update(self.d)
        self.d = cur
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(pickle.dumps(cur, protocol=pickle.HIGHEST_PROTOCOL))
        os.replace(tmp, self.path)
        self.new = 0


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def b2t_ctx(char_lm_path: str | None = None, word_counts: dict | None = None, tag: str = "main"):
    """Brain-to-Text '25 context. ``char_lm_path`` / ``word_counts`` replace the LMs (leakage run)."""
    from fidetype.lm import CharNgramLM
    from fidetype.lm.phoneme_words import unigram_logprobs

    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
    best = tune["best"]
    dec = bt.Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    if char_lm_path is not None or word_counts is not None:
        if char_lm_path is not None:
            dec.lm = CharNgramLM.load(char_lm_path)
        if word_counts is not None:
            dec.uni = unigram_logprobs(word_counts, dec.lex.words)
            dec.lex.set_fallback_words(w for w in dec.lex.words if word_counts.get(w, 0) >= bt.CONFIG["fallback_min_count"])
        del dec.wdec  # fresh caches: the LM scores change
        dec.wdec = dec.make_wdec(dec.wkw)
        dec._wcache = {}
    cached = DiskCachedDecoder(dec.words_fn, f"b2t-words-{tag}")
    dec.words_fn = cached  # published_plus_fn calls self.words_fn: now cached too
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in fit + test}

    def items(ts):
        return [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in ts]

    return SimpleNamespace(bt=bt, prep=prep, trials=trials, fit=fit, test=test, dec=dec, cached=[cached], user=user,
                           items=items, gaze_cpm=bt.CONFIG["gaze_chars_per_min"],
                           days_fit=[t.post_implant_day for t in fit], days_test=[t.post_implant_day for t in test])


def b2t_condition(ctx, which: str):
    """One B2T condition as a generic ``cond`` namespace (main fit: fit(fit, fit))."""
    fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
    fi, ti = ctx.items(ctx.fit), ctx.items(ctx.test)
    return SimpleNamespace(
        name=f"b2t-{which}", decode=fn, user=ctx.user, base=dict(max_wrong_commit=ALPHA), calib=fi, val=fi, test=ti,
        cluster=np.unique(ctx.days_test, return_inverse=True)[1], cluster_name="day", scheme="cluster",
        sent=None, gaze_cpm=ctx.gaze_cpm, extra={"days_test": ctx.days_test})


def meg_ctx(root: str = "C:/Users/zhang/bci-data/streams/m1-09-r4b-full-medium", lm_weight: float = 0.5, tag: str = "",
            insertion_bonus: float | None = None):
    from fidetype.lm import RETUNED, CharNgramLM, ctc_prefix_beam_search
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.types import from_lm_hypotheses

    m2 = load_module("m2ow", REPO / "experiments/2026-11-08-m2-offer-words/run.py")
    lm = CharNgramLM.load(m2.SPA_LM)
    kw = {**dict(RETUNED), "n_best": 10, "lm_weight": lm_weight}
    if insertion_bonus is not None:
        kw["insertion_bonus"] = insertion_bonus
        tag = f"{tag}-b{insertion_bonus}"

    def dec(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm, **kw), stream.meta, confidence_variant="frame")

    def load_split(split):
        rows = [json.loads(x) for x in (Path(root) / split / "labels.jsonl").read_text(encoding="utf-8").splitlines() if x]
        out = []
        for r in rows:
            s = NeuralTextStream.from_npz(Path(root) / split / r["file"])
            r = dict(r)
            r.setdefault("participant", s.meta.get("participant"))
            out.append((s, r))
        return out

    val_raw, test_raw = load_split("val"), load_split("test")
    val = [Item(s, r["target_text"]) for s, r in val_raw]
    test = [Item(s, r["target_text"]) for s, r in test_raw]
    sid = {t: i for i, t in enumerate(sorted({it.text for it in test}))}
    part_names = [r["participant"] for _, r in test_raw]
    cached = DiskCachedDecoder(dec, f"meg-async-w{lm_weight}{tag}")
    return SimpleNamespace(
        name="meg-async", decode=cached, cached=[cached], user=UserConfig.aac_gaze(), base=dict(grid=m2.BASE_GRID, max_wrong_commit=ALPHA),
        calib=val, val=val, test=test, sent=np.array([sid[it.text] for it in test]),
        cluster=np.unique(part_names, return_inverse=True)[1], cluster_name="participant", scheme="two_way",
        gaze_cpm=20.0, m2=m2, kw=kw, lm=lm, part_names=part_names, val_raw=val_raw, test_raw=test_raw,
        val_sent=np.array([{t: i for i, t in enumerate(sorted({it.text for it in val}))}[it.text] for it in val]),
        extra={})


EMG_CACHE: dict = {}


def emg_base():
    """Shared sEMG data: the composition plan (same seed and config as M6-07)."""
    if "base" in EMG_CACHE:
        return EMG_CACHE["base"]
    E = load_module("emgtrust", REPO / "experiments/2026-11-11-emg-toronto/trust.py")
    old = json.loads((REPO / "experiments/2026-11-11-emg-toronto/results/trust.json").read_text(encoding="utf-8"))
    y, file_idx, files, info = E.load_meta()
    period = float(info["inter_key_interval_s"]["median"])
    texts = E.sentences()
    nfit, ntest = E.CONFIG["sentences_per_participant"]["fit"], E.CONFIG["sentences_per_participant"]["test"]
    P = E.pools(y, file_idx, files)
    pids = sorted(P, key=lambda s: int(s[1:]))
    half = len(texts) // 2
    fit_texts, test_texts = texts[:half], texts[half:]
    per_p = len(fit_texts) // len(pids)
    rng = np.random.default_rng(E.SEED)
    plan = {}
    for k, p in enumerate(pids):
        plan[p] = {"fit": E.compose(fit_texts[k * per_p: (k + 1) * per_p], P[p]["fit"], rng, nfit),
                   "test": E.compose(test_texts[k * per_p: (k + 1) * per_p], P[p]["test"], rng, ntest)}
    base = SimpleNamespace(E=E, old=old, y=y, period=period, pids=pids, plan=plan, texts=texts,
                           user=UserConfig.aac_gaze(chars_per_min=60.0 / period))
    EMG_CACHE["base"] = base
    return base


def emg_condition(cond: str, lm_path: str | None = None, lm_weight: float | None = None, tag: str = ""):
    """sEMG condition. Default LM weight = the M6-07 value (tuned on fit-A CER, raw streams)."""
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.types import from_lm_hypotheses

    b = emg_base()
    E = b.E
    fit_run, test_run, _ = E.CONDITIONS[cond]
    lg_fit, _, _ = E.load_logits(fit_run, len(b.y))
    lg_test, _, zeros_t = E.load_logits(test_run, len(b.y))

    def items_of(which, lg):
        its, who, idxs = [], [], []
        for p in b.pids:
            for t, idx in b.plan[p][which]:
                its.append(Item(E.make_stream(lg[idx], b.period, p, cond), t))
                who.append(p)
                idxs.append(idx)
        return its, who, idxs

    fit_items, fit_who, _ = items_of("fit", lg_fit)
    test_items, test_who, test_idx = items_of("test", lg_test)
    order = np.random.default_rng(E.SEED + 7).permutation(len(fit_items))
    fit_items = [fit_items[i] for i in order]
    fit_who = [fit_who[i] for i in order]
    h = len(fit_items) // 2
    A, Bv = fit_items[:h], fit_items[h:]
    lm_path = lm_path or E.CONFIG["char_lm"]
    lm = CharNgramLM.load(lm_path)
    w = b.old["conditions"][cond]["lm_weight"] if lm_weight is None else lm_weight

    def make_decode(weight):
        kw = {**E.CONFIG["beam"], "lm_weight": weight}

        def decode_fn(s):
            return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

        return DiskCachedDecoder(decode_fn, f"emg-{cond}-w{weight}{tag}")

    dec = make_decode(w)
    return SimpleNamespace(
        name=f"emg-{cond}", cond=cond, decode=dec, cached=[dec], make_decode=make_decode, lm=lm, lm_weight=w,
        user=b.user, base=dict(max_wrong_commit=ALPHA), calib=A, val=Bv, test=test_items,
        cluster=np.unique(test_who, return_inverse=True)[1], cluster_name="participant", scheme="cluster", sent=None,
        gaze_cpm=E.CONFIG["gaze_chars_per_min"], fit_who=fit_who, test_who=test_who, test_idx=test_idx, A=A, Bv=Bv,
        zeros=zeros_t, E=E, extra={})


def save_caches(*conds) -> None:
    for c in conds:
        for d in getattr(c, "cached", []):
            d.save()


# ---------------------------------------------------------------------------
# Pipelines and per-item outcomes
# ---------------------------------------------------------------------------


def make_pipe(cond, cache: dict | None = None, user: UserConfig | None = None, **over) -> TrustPipeline:
    cfg = HarnessConfig(seed=SEED, user_config=user or cond.user, **{**cond.base, **over})
    return TrustPipeline(cond.decode, cfg, cache if cache is not None else {})


def rec_arrays(recs) -> dict[str, np.ndarray]:
    com = np.array([("COMMIT" in r.actions) for r in recs], float)
    wc = np.array([float(r.wrong_commit) for r in recs])
    return {"w": np.array([correct_words_strict(r) for r in recs], float), "t": np.array([r.time_s for r in recs], float),
            "wc": wc, "com": com, "wcc": wc * com, "se": np.array([float(r.silent_error) for r in recs]),
            "offer": np.array([float(r.actions[-1] in ("OFFER", "OFFER_WORDS")) for r in recs])}


def gaze_arrays(truths, cpm: float) -> dict[str, np.ndarray]:
    nc = np.array([len(s) for s in truths], float)
    z = np.zeros(len(truths))
    return {"w": np.array([len(s.split()) for s in truths], float), "t": nc * 60.0 / cpm, "wc": z, "com": z, "wcc": z,
            "se": z, "offer": z}


def item_arrays(tab: dict, lam: float) -> dict[str, np.ndarray]:
    """Outcome arrays of an M2-13 item table at commit threshold ``lam``."""
    s = np.array([fnum(x) for x in tab["score"]])
    on = s >= lam
    g = lambda k: np.asarray(tab[k], float)  # noqa: E731
    wc = np.where(on, g("wc_c"), g("wc_f"))
    return {"w": np.where(on, g("words_c"), g("words_f")), "t": np.where(on, g("time_c"), g("time_f")), "wc": wc,
            "com": on.astype(float), "wcc": wc * on, "se": np.where(on, g("silent_c"), g("silent_f")),
            "offer": (~on).astype(float)}


def metrics(a: dict, wt: np.ndarray | None = None) -> dict[str, float]:
    wt = np.ones(len(a["w"])) if wt is None else wt
    sw = wt.sum()
    ncom = float((a["com"] * wt).sum())
    return {"ewpm": 60.0 * float((a["w"] * wt).sum() / (a["t"] * wt).sum()),
            "wrong_commit": float((a["wc"] * wt).sum() / sw),
            "commit_rate": ncom / sw,
            "error_among_commits": float((a["wcc"] * wt).sum() / ncom) if ncom > 0 else float("nan"),
            "silent_error": float((a["se"] * wt).sum() / sw)}


def boot_weights(rng, scheme: str, n: int, cluster: np.ndarray | None, sent: np.ndarray | None) -> np.ndarray:
    if scheme == "trials":
        return np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
    if scheme == "cluster":
        k = cluster.max() + 1
        return np.bincount(rng.integers(0, k, k), minlength=k)[cluster].astype(float)
    if scheme == "sentences":
        k = sent.max() + 1
        return np.bincount(rng.integers(0, k, k), minlength=k)[sent].astype(float)
    if scheme == "two_way":
        ks, kp = sent.max() + 1, cluster.max() + 1
        cs = np.bincount(rng.integers(0, ks, ks), minlength=ks)
        cp = np.bincount(rng.integers(0, kp, kp), minlength=kp)
        return (cs[sent] * cp[cluster]).astype(float)
    raise ValueError(scheme)


MK = ("ewpm", "wrong_commit", "commit_rate", "error_among_commits", "silent_error")


def bootstrap(arrs: dict[str, dict], cond, B: int = 2000, seed: int = 11, diffs=(), scheme: str | None = None) -> dict:
    """Percentile 95 % CIs of every metric and of paired differences, at the condition's CI unit."""
    scheme = scheme or cond.scheme
    n = len(next(iter(arrs.values()))["w"])
    rng = np.random.default_rng(seed)
    samp = {p: {k: [] for k in MK} for p in arrs}
    dsamp = {f"{a}-{b}": {k: [] for k in MK} for a, b in diffs}
    for _ in range(B):
        wt = boot_weights(rng, scheme, n, cond.cluster, cond.sent)
        if wt.sum() == 0:
            continue
        vals = {p: metrics(a, wt) for p, a in arrs.items()}
        for p, v in vals.items():
            for k in MK:
                samp[p][k].append(v[k])
        for a, b in diffs:
            for k in MK:
                dsamp[f"{a}-{b}"][k].append(vals[a][k] - vals[b][k])

    def ci(v):
        v = np.asarray(v, float)
        v = v[np.isfinite(v)]
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size >= 20 else None

    return {"scheme": scheme, "B": B,
            "policies": {p: {k: ci(v) for k, v in d.items()} for p, d in samp.items()},
            "diffs": {name: {k: ci(v) for k, v in d.items()} for name, d in dsamp.items()}}


def point(arrs: dict[str, dict]) -> dict:
    return {p: metrics(a) for p, a in arrs.items()}


def thresholds(tab: dict, alpha: float = ALPHA, delta: float = DELTA) -> dict:
    """CRC and LTT thresholds on an item table (calibration data)."""
    s = np.array([fnum(x) for x in tab["score"]])
    c, f = np.asarray(tab["loss_c"], float), np.asarray(tab["loss_f"], float)
    crc = crc_threshold(s, c, alpha, f)
    ltt = ltt_threshold(s, c, alpha, delta, f)
    return {"crc": crc.threshold, "ltt": ltt.threshold, "crc_feasible": crc.feasible, "crc_bound": crc.bound,
            "ltt_feasible": ltt.feasible, "n": int(len(s))}


def subset_tab(tab: dict, idx) -> dict:
    idx = np.asarray(idx)
    out = {k: (list(np.asarray(v, dtype=object)[idx]) if isinstance(v, list) and len(v) == tab["n"] else v)
           for k, v in tab.items()}
    out["n"] = int(len(idx))
    return out


def fmt(x, nd=3) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def fci(c, nd=3) -> str:
    return f"[{c[0]:.{nd}f}, {c[1]:.{nd}f}]" if c else ""
