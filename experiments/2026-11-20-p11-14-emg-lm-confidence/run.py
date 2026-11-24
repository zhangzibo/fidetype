"""P11-14: a guard confidence for the P11-07 in-beam LM EMG decoder. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files stay
in C:/Users/zhang/bci-data/derived/p11-14/. The P11-01, P11-07, P11-09, P11-11 and P11-12 files are read only.
The repo gets aggregates only (no per-user value, no text, no id).

Stages (repo root; launch.py runs them detached):

  feat     decodes and confidence signals of the calibration windows and the 300 null windows (both decoders).
  select   tuning criterion of the 6 primary candidates (P, A, L x F, FL); L models fitted on the tuning items.
  guards   fidetype.trust.calibrate per arm (P, A, L, BL x F, FL).
  decide   decisions on the evaluation prompts (real, time-shuffled, zero EMG).
  score    safe WPM, verdicts, AUROCs -> results/results.json.
  all      every stage in this order.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import hashlib  # noqa: E402
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

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-14"  # the only place this task writes per-prompt files
P1111 = DER / "p11-11"  # READ ONLY (LM, lexicon, no-LM beam cache)
P1112 = DER / "p11-12"  # READ ONLY (gate.json)
EXP1107 = REPO / "experiments" / "2026-11-20-p11-07-emg-beam-lm"
EXP1111 = REPO / "experiments" / "2026-11-19-p11-11-emg-nonvacuous"
EXP1112 = REPO / "experiments" / "2026-11-20-p11-12-emg-nosignal-gate"
OUT = HERE / "results"

# --- pre-registered constants (plan.md) ------------------------------------------------------------
DECODERS = {"F": {"w": 0.5, "beta": 1.0, "lam": 0.0, "B": 8},
            "FL": {"w": 0.25, "beta": 1.0, "lam": 8.0, "B": 8}}
PRIMARY_ARMS = ("P", "A", "L")
ARMS = tuple(f"{a}-{d}" for d in ("F", "FL") for a in ("P", "A", "L", "BL"))
NBEST_OUT = 20
C_CLIP = 1e-6
LG_CLIP = 12.0
L2 = 1.0
N_FOLDS = 5
FEATS = ("lg_p_nb", "lg_p_fU", "lg_p_aU", "agree_b0", "agree_g", "dist_g", "ac_gap", "lm_pc", "log_nw", "kps")
SIGNS = (+1, +1, +1, +1, +1, -1, -1, +1, 0, 0)
SIGNALS = ("p_nb", "p_fU", "p_aU", "agree_b0", "agree_g", "dist_g", "ac_gap", "lm_pc", "log_nw", "kps")
SIGNAL_DIR = {"dist_g": -1, "ac_gap": -1}  # AUROC direction (higher = more evidence for right otherwise)
REF = {"p1112_S": 4.10, "p1112_SL": 5.08, "p1107_S": 3.37, "no_bci": 3.09}
C0_REF = {"commits": 154, "wrong": 43, "value": 3.37}
ARM_ORDER = {"P": 0, "A": 1, "L": 2}
DEC_ORDER = {"F": 0, "FL": 1}


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents or p == OWN
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def p1107():
    """The P11-07 runner as a module (make_dec, lm, lex_norm). Read-only use: never call its stages or own()."""
    if "p1107run" not in sys.modules:
        load_module("p1107run", EXP1107 / "run.py")
    return sys.modules["p1107run"]


def p1111():
    return p1107().p1111()


def p1112():
    return p1107().p1112()


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def ctc_logliks(x: np.ndarray, seqs: list[tuple[int, ...]], blank: int = 0) -> np.ndarray:
    """Exact CTC log-likelihood of each label sequence on the (T, V) log-prob matrix ``x`` (forward algorithm).

    All sequences of one window run in one batch (padded). Our own code (Apache-2.0).
    """
    x = np.asarray(x, np.float64)
    T = x.shape[0]
    H = len(seqs)
    out = np.full(H, -np.inf)
    if H == 0 or T == 0:
        return out
    lens = np.array([len(s) for s in seqs], np.int64)
    Lm = int(lens.max()) if H else 0
    S = 2 * Lm + 1
    ext = np.full((H, S), blank, np.int64)
    for h, s in enumerate(seqs):
        if len(s):
            ext[h, 1:2 * len(s):2] = s
    sidx = np.arange(S)[None, :]
    valid = sidx < (2 * lens[:, None] + 1)
    skip = np.zeros((H, S), bool)
    if S > 2:
        skip[:, 2:] = (sidx[:, 2:] % 2 == 1) & (ext[:, 2:] != ext[:, :-2])
    neg = -np.inf
    a = np.full((H, S), neg)
    a[:, 0] = x[0, blank]
    has = lens > 0
    if S > 1:
        a[has, 1] = x[0, ext[has, 1]]
    a[~valid] = neg
    for t in range(1, T):
        a1 = np.empty_like(a)
        a1[:, 0] = neg
        a1[:, 1:] = a[:, :-1]
        a2 = np.full_like(a, neg)
        if S > 2:
            a2[:, 2:] = np.where(skip[:, 2:], a[:, :-2], neg)
        with np.errstate(invalid="ignore"):
            m = np.logaddexp(np.logaddexp(a, a1), a2)
        a = m + x[t][ext]
        a[~valid] = neg
    for h in range(H):
        e = 2 * int(lens[h])
        out[h] = np.logaddexp(a[h, e], a[h, e - 1]) if e > 0 else a[h, 0]
    return out


def lse(v) -> float:
    v = np.asarray(list(v), np.float64)
    if v.size == 0:
        return -np.inf
    m = float(v.max())
    if not np.isfinite(m):
        return m
    return m + float(np.log(np.exp(v - m).sum()))


def logit_clip(p: float) -> float:
    p = float(p)
    if p <= 0.0:
        return -LG_CLIP
    if p >= 1.0:
        return LG_CLIP
    return float(min(max(math.log(p) - math.log1p(-p), -LG_CLIP), LG_CLIP))


def two_item(text: str, c: float) -> list[tuple[str, float]]:
    """The A / L n-best: the commit text with log c and an empty reject item with log(1 - c).

    Amendment 1 (before any real-window run): if c <= 0.5 the n-best is empty (the guard withholds). The guard could
    not commit there anyway (the reject item would be the top-1), and an always-wrong empty top-1 distorts the
    temperature fit of ``calibrate`` (synthetic check: p_top1 compressed into [0.50, 0.56]).
    """
    c = float(min(max(c, C_CLIP), 1.0 - C_CLIP))
    if c <= 0.5:
        return []
    return [(text, math.log(c)), ("", math.log1p(-c))]


def feat_vec(sig: dict) -> np.ndarray:
    v = {"lg_p_nb": logit_clip(sig["p_nb"]), "lg_p_fU": logit_clip(sig["p_fU"]), "lg_p_aU": logit_clip(sig["p_aU"])}
    return np.array([v[f] if f in v else float(sig[f]) for f in FEATS], np.float64)


class Learned:
    """Sign-constrained L2 logistic regression on FEATS (plan: standardise + clip to the fit range)."""

    def __init__(self, mean, scale, lo, hi, coef, b, dropped):
        self.mean, self.scale, self.lo, self.hi = (np.asarray(v, np.float64) for v in (mean, scale, lo, hi))
        self.coef = np.asarray(coef, np.float64)
        self.b = float(b)
        self.dropped = list(dropped)

    @classmethod
    def fit(cls, X: np.ndarray, y: np.ndarray, l2: float = L2, signs=SIGNS) -> "Learned":
        from fidetype.trust.commit_score import fit_logistic

        X = np.asarray(X, np.float64)
        y = np.asarray(y, np.float64)
        lo, hi = X.min(0), X.max(0)
        mean, scale = X.mean(0), X.std(0)
        usable = scale > 1e-12
        scale = np.where(usable, scale, 1.0)
        Z = (X - mean) / scale
        active = [j for j in range(X.shape[1]) if usable[j]]
        dropped = [FEATS[j] for j in range(X.shape[1]) if not usable[j]]
        sg = np.asarray(signs, np.float64)
        coef = np.zeros(X.shape[1])
        b = 0.0
        while True:
            if not active:
                ybar = float(np.clip(y.mean(), 1e-6, 1 - 1e-6))
                b = math.log(ybar / (1 - ybar))
                break
            c, b = fit_logistic(Z[:, active], y, l2=l2)
            bad = [(abs(c[k]), j) for k, j in enumerate(active) if sg[j] != 0 and np.sign(c[k]) == -sg[j]
                   and abs(c[k]) > 0]
            if not bad:
                coef[:] = 0.0
                coef[active] = c
                break
            j = max(bad)[1]
            active.remove(j)
            dropped.append(FEATS[j])
        return cls(mean, scale, lo, hi, coef, b, dropped)

    def prob(self, X: np.ndarray) -> np.ndarray:
        X = np.clip(np.atleast_2d(np.asarray(X, np.float64)), self.lo, self.hi)
        z = np.clip(((X - self.mean) / self.scale) @ self.coef + self.b, -35.0, 35.0)
        return 1.0 / (1.0 + np.exp(-z))

    def to_dict(self) -> dict:
        r = lambda a: [float(f"{v:.12g}") for v in np.asarray(a).ravel()]  # noqa: E731
        return {"features": list(FEATS), "signs": list(SIGNS), "mean": r(self.mean), "scale": r(self.scale),
                "lo": r(self.lo), "hi": r(self.hi), "coef": r(self.coef), "intercept": float(f"{self.b:.12g}"),
                "dropped": self.dropped, "l2": L2}

    @classmethod
    def from_dict(cls, d: dict) -> "Learned":
        return cls(d["mean"], d["scale"], d["lo"], d["hi"], d["coef"], d["intercept"], d["dropped"])

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:12]


def auroc(score: np.ndarray, right: np.ndarray) -> float | None:
    """P(score of a right item > score of a wrong item), ties count 1/2 (Mann-Whitney)."""
    s = np.asarray(score, np.float64)
    y = np.asarray(right, bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return None
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# --- window analysis ----------------------------------------------------------------------------------


class Analyser:
    """Decode one window with a decoder (gate -> in-beam beam -> intended merge -> OOV gate) + the signals."""

    def __init__(self) -> None:
        R = p1111()
        g = load_json(P1112 / "gate.json")
        p1112().GATE.update({k: g[k] for k in ("k_min", "r_min", "r_max")})  # type: ignore[index]
        R.DEC.lex = frozenset(load_json(P1111 / "lexicon.json")["words"])  # type: ignore[index]  # OOV gate only
        R.DEC.load_cache()  # P11-11 no-LM beam-64 cache, read only (never saved here)
        self.KV = p1107().key_vocab()
        self.kidx = {c: i for i, c in enumerate(self.KV)}
        self.memo: dict[str, dict | None] = {}
        self.dirty = 0
        self._lm: dict[str, float] = {}
        self._oov: dict[str, int] = {}

    # persistence
    def load(self) -> None:
        f = own("feat.pkl")
        if f.exists():
            with open(f, "rb") as fh:
                self.memo.update(pickle.load(fh))

    def save(self) -> None:
        f = own("feat.pkl")
        tmp = f.with_suffix(".tmp")
        with open(tmp, "wb") as fh:
            pickle.dump(self.memo, fh, protocol=4)
        os.replace(tmp, f)
        self.dirty = 0

    def lm_s(self, text: str) -> float:
        v = self._lm.get(text)
        if v is None:
            v = float(p1107().lm().score_sentence(text))
            if len(self._lm) > 300_000:
                self._lm.clear()
            self._lm[text] = v
        return v

    def n_oov_norm(self, text: str) -> int:
        v = self._oov.get(text)
        if v is None:
            from fidetype.streams.vocab import normalize_text

            lex = p1107().lex_norm()
            v = sum(w not in lex for w in normalize_text(text).split())
            if len(self._oov) > 300_000:
                self._oov.clear()
            self._oov[text] = v
        return v

    def get(self, x: np.ndarray, dec: str) -> dict | None:
        k = p1111().window_key(x) + "|" + dec
        if k in self.memo:
            return self.memo[k]
        a = self.analyse(x, dec)
        self.memo[k] = a
        self.dirty += 1
        if self.dirty >= 500:
            self.save()
        return a

    def analyse(self, x: np.ndarray, dec: str) -> dict | None:
        """None if the no-signal gate fails; {"status": "oov"} if the OOV gate (or an empty best text) withholds."""
        R = p1111()
        P7 = p1107()
        x = np.asarray(x, np.float64)
        if not p1112().gate_pass(x):
            return None
        cfg = DECODERS[dec]
        d = P7.make_dec(self.KV, cfg)
        d.push(x)
        hyps = d.nbest(None, eos=True)
        merged: dict[str, float] = {}
        for h in hyps:
            t = R.resolve("".join(self.KV[q] for q in h.tokens))
            merged[t] = float(np.logaddexp(merged.get(t, -np.inf), h.score))
        native = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:NBEST_OUT]
        if not native or R.oov_gate(native[0][0]):
            return {"status": "oov"}
        native = [(t, s) for t, s in native if t]
        top = native[0][0]
        sc = np.array([s for _, s in native])
        p_nb = float(np.exp(sc[0] - lse(sc)))
        # competitor set U: the decoder's beam + the P11-11 no-LM beam-64 n-best
        nb64 = R.DEC.beam(x)
        seqs: list[tuple[int, ...]] = []
        seen: set[tuple[int, ...]] = set()
        for h in hyps:
            s = tuple(int(q) for q in h.tokens)
            if s not in seen:
                seen.add(s)
                seqs.append(s)
        for kt, _ in nb64:
            s = tuple(self.kidx[c] for c in kt)
            if s not in seen:
                seen.add(s)
                seqs.append(s)
        ac = ctc_logliks(x, seqs)
        ac_g: dict[str, list[float]] = {}
        f_g: dict[str, list[float]] = {}
        for s, a in zip(seqs, ac):
            t = R.resolve("".join(self.KV[q] for q in s))
            lmv = self.lm_s(t) - cfg["lam"] * (self.n_oov_norm(t) if cfg["lam"] > 0 else 0)
            ac_g.setdefault(t, []).append(float(a))
            f_g.setdefault(t, []).append(float(a) + cfg["w"] * lmv + cfg["beta"] * len(s))
        acm = {t: lse(v) for t, v in ac_g.items()}
        fm = {t: lse(v) for t, v in f_g.items()}
        a_all, f_all = lse(acm.values()), lse(fm.values())
        p_aU = float(np.exp(acm[top] - a_all)) if top in acm else 0.0
        p_fU = float(np.exp(fm[top] - f_all)) if top in fm else 0.0
        b0 = R.resolve(nb64[0][0]) if nb64 else ""
        from lmbeam import greedy_tokens  # noqa: PLC0415  (P11-07 folder on sys.path via p1107())

        g = R.resolve("".join(self.KV[q] for q in greedy_tokens(x)))
        n = max(1, len(top))
        sig = {"p_nb": p_nb, "p_fU": p_fU, "p_aU": p_aU, "agree_b0": float(R.same(top, b0)),
               "agree_g": float(R.same(top, g)), "dist_g": P7.char_lev(top, g) / n,
               "ac_gap": (max(acm.values()) - acm.get(top, -np.inf)) / n if top in acm else 1e3,
               "lm_pc": self.lm_s(top) / (len(top) + 1), "log_nw": math.log(1 + len(top.split())),
               "kps": p1112().kps(x)}
        items_bl = []
        for t, s in native:
            it = {"text": t, "score": float(s)}
            if t in acm and np.isfinite(acm[t]):
                it["logp_acoustic"] = min(0.0, float(acm[t]))
            it["logp_lm"] = min(0.0, self.lm_s(t) - cfg["lam"] * (self.n_oov_norm(t) if cfg["lam"] > 0 else 0))
            items_bl.append(it)
        return {"status": "ok", "top": top, "native": native, "bl": items_bl, "sig": sig, "n_u": len(seqs)}


class GuardFn:
    """``decode_fn`` of one arm."""

    def __init__(self, an: Analyser, arm: str, model: Learned | None = None) -> None:
        self.an = an
        self.kind, self.dec = arm.split("-")
        self.model = model
        self.__name__ = self.__qualname__ = f"p11_14_{self.kind}_{self.dec}"

    def conf(self, a: dict) -> float:
        if self.kind == "A":
            return a["sig"]["p_aU"]
        if self.kind == "L":
            return float(self.model.prob(feat_vec(a["sig"]))[0])
        raise ValueError(self.kind)

    def __call__(self, x: np.ndarray):
        a = self.an.get(x, self.dec)
        if a is None or a["status"] != "ok":
            return []
        if self.kind == "P":
            return list(a["native"])
        if self.kind == "BL":
            return [dict(it) for it in a["bl"]]
        return two_item(a["top"], self.conf(a))


# --- data -----------------------------------------------------------------------------------------------


def setup():
    R = p1111()
    rows = R.prompts()
    cal, ev = R.split_rows(rows)
    R.p1109().check_track_splits(R.p1109().sessions())
    return R, cal, ev


def tune_pos(cal: list[dict]) -> list[int]:
    return p1111().tune_items(len(cal))


# --- stage feat ---------------------------------------------------------------------------------------


def stage_feat(an: Analyser, cal: list[dict]) -> dict:
    f = own("feat.status.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    R = p1111()
    W = R.p1109().Windows()
    t0 = time.time()
    xs = [("real", r) for r in cal] + [("shuffled", cal[i]) for i in R.null_pick(len(cal))]
    for n, (kind, r) in enumerate(xs, 1):
        x = W.get(r, kind)
        for dec in DECODERS:
            an.get(x, dec)
        if n % 200 == 0:
            log(f"feat: {n}/{len(xs)} windows ({time.time() - t0:.0f} s)")
    an.save()
    rec = {"windows": len(xs), "seconds": round(time.time() - t0, 1), "memo": len(an.memo)}
    save_json(rec, f)
    log(f"feat: {rec}")
    return rec


# --- stage select -------------------------------------------------------------------------------------


def tuning_table(an: Analyser, cal: list[dict], dec: str) -> dict:
    R = p1111()
    W = R.p1109().Windows()
    rows = [cal[i] for i in tune_pos(cal)]
    ok, right, X, sig, nw, nch, neu = [], [], [], [], [], [], []
    for r in rows:
        a = an.get(W.get(r), dec)
        truth = R.intended_truth(r)
        good = a is not None and a["status"] == "ok"
        ok.append(good)
        right.append(bool(good and R.same(a["top"], truth)))
        X.append(feat_vec(a["sig"]) if good else np.full(len(FEATS), np.nan))
        sig.append(a["sig"] if good else None)
        nw.append(len(truth.split()))
        nch.append(len(truth))
        neu.append(r["neural_s"])
    return {"ok": np.array(ok), "right": np.array(right), "X": np.array(X), "sig": sig, "nw": nw, "nch": nch,
            "neural": neu}


def cv_scores(tab: dict) -> np.ndarray:
    n = len(tab["ok"])
    perm = np.random.default_rng(0).permutation(n)
    folds = np.array_split(perm, N_FOLDS)
    s = np.full(n, -np.inf)
    for k in range(N_FOLDS):
        te = np.zeros(n, bool)
        te[folds[k]] = True
        tr = (~te) & tab["ok"]
        m = Learned.fit(tab["X"][tr], tab["right"][tr])
        idx = np.nonzero(te & tab["ok"])[0]
        if idx.size:
            s[idx] = m.prob(tab["X"][idx])
    return s


def criterion(s: np.ndarray, tab: dict) -> dict:
    from fidetype.benchmark import safe_wpm as SW
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID, ltt_threshold

    s = np.where(tab["ok"], s, -np.inf)
    loss = (~tab["right"]).astype(np.float64)
    res = ltt_threshold(s, loss, alpha=p1111().ALPHA, delta=p1111().DELTA, grid=DEFAULT_LTT_GRID, pvalue="binomial")
    thr = float(res.threshold)
    com = [bool(v >= thr) for v in s]
    cor = [c and bool(k) for c, k in zip(com, tab["right"])]
    sw = SW.safe_wpm(com, cor, tab["nw"], tab["nch"], tab["neural"], guarantee=None, metric_version="0.1")
    wrong = int(sum(c and not k for c, k in zip(com, cor)))
    return {"threshold": thr, "feasible": bool(res.feasible), "commits": int(sum(com)), "wrong": wrong,
            "right_words": int(sum(w for w, k in zip(tab["nw"], cor) if k)),
            "unguarded_wpm": float(sw.get("unguarded_wpm") or 0.0)}


def stage_select(an: Analyser, cal: list[dict]) -> dict:
    f = own("select.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    out: dict = {"n_tune": len(tune_pos(cal)), "tune_digest": p1107().tune_digest(cal), "candidates": {},
                 "tuning_auroc": {}, "models": {}}
    for dec in DECODERS:
        tab = tuning_table(an, cal, dec)
        okm = tab["ok"]
        out["tuning_auroc"][dec] = {
            "n_committable": int(okm.sum()), "n_right": int(tab["right"].sum()),
            **{s: auroc(np.array([SIGNAL_DIR.get(s, 1) * tab["sig"][i][s] for i in np.nonzero(okm)[0]]),
                        tab["right"][okm]) for s in SIGNALS}}
        sc = {"P": np.array([t["p_nb"] if t else -np.inf for t in tab["sig"]]),
              "A": np.array([t["p_aU"] if t else -np.inf for t in tab["sig"]]),
              "L": cv_scores(tab)}
        out["tuning_auroc"][dec]["L_cv"] = auroc(sc["L"][okm], tab["right"][okm])
        for k in ("A", "L"):  # amendment 1: the two-item n-best is empty at c <= 0.5 (no commit possible)
            sc[k] = np.where(sc[k] > 0.5, sc[k], -np.inf)
        for arm in PRIMARY_ARMS:
            out["candidates"][f"{arm}-{dec}"] = criterion(sc[arm], tab)
        m = Learned.fit(tab["X"][okm], tab["right"][okm])
        out["models"][dec] = {**m.to_dict(), "digest": m.digest(), "n_fit": int(okm.sum())}
        save_json(m.to_dict(), own(f"model-L-{dec}.json"))
    key = lambda kv: (-kv[1]["unguarded_wpm"], kv[1]["wrong"], ARM_ORDER[kv[0].split("-")[0]],  # noqa: E731
                      DEC_ORDER[kv[0].split("-")[1]])
    out["primary"] = sorted(out["candidates"].items(), key=key)[0][0]
    save_json(out, f)
    log(f"select: primary {out['primary']}; " + "; ".join(f"{k} {v['unguarded_wpm']:.3f} ({v['commits']}/{v['wrong']})"
                                                        for k, v in out["candidates"].items()))
    return out


def load_model(dec: str) -> Learned:
    return Learned.from_dict(load_json(own(f"model-L-{dec}.json")))  # type: ignore[arg-type]


def guard_fn(an: Analyser, arm: str) -> GuardFn:
    kind, dec = arm.split("-")
    return GuardFn(an, arm, load_model(dec) if kind == "L" else None)


# --- stage guards / decide ----------------------------------------------------------------------------


def decoder_meta(arm: str) -> tuple[str, str]:
    kind, dec = arm.split("-")
    c = DECODERS[dec]
    name = ("fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram" + ("+lexicon" if c["lam"] > 0 else "")
            + f"+intended-text+nosignal-gate+conf-{kind}")
    ver = f"p11-14-w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}"
    if kind == "L":
        ver += "-L" + load_model(dec).digest()
    return name, ver


def stage_guards(an: Analyser, cal: list[dict], ev: list[dict], arms=ARMS) -> dict:
    import fidetype.trust as ft

    R = p1111()
    W = R.p1109().Windows()
    out = {}
    for arm in arms:
        rec_f = own(f"guard-{arm}.status.json")
        if rec_f.exists():
            out[arm] = load_json(rec_f)
            continue
        t0 = time.time()
        kind = arm.split("-")[0]
        name, ver = decoder_meta(arm)
        rec: dict = {"arm": arm, "n_cal": len(cal), "n_eval": len(ev), "cal_digest": R.p1109().split_digest(cal),
                     "eval_digest": R.p1109().split_digest(ev), "gate": dict(p1112().GATE),
                     "decoder": DECODERS[arm.split("-")[1]], "decoder_name": name, "decoder_version": ver}
        xs = [W.get(r) for r in cal]
        texts = [R.intended_truth(r) for r in cal]
        nulls = [W.get(cal[i], "shuffled") for i in R.null_pick(len(cal))]
        kw = {"confidence": "learned"} if kind == "BL" else {}
        try:
            g = ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=an.KV, blank=0,
                             input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=guard_fn(an, arm),
                             null_inputs=nulls, decoder_name=name, decoder_version=ver, modality="emg",
                             name=f"p11-14-{arm}", seed=R.SEED, audit_text=False, **kw)
        except ft.NullControlError as e:
            rec.update(status="refused", reason=str(e)[:2000])
            log(f"guards {arm}: REFUSED ({time.time() - t0:.0f} s): {e}")
        else:
            g.save(own(f"guard-{arm}.json"))
            sh = g.sheet.to_dict()
            rec.update(status="guard", config_id=g.config_id, sheet=sh)
            save_json({"config_id": g.config_id, "sheet": sh, **R.RESEARCH}, OUT / f"guard-{arm}.json")
            log(f"guards {arm}: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
        del xs, nulls
        an.save()
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, rec_f)
        out[arm] = rec
    return out


def stage_decide(an: Analyser, ev: list[dict], arms=ARMS) -> dict:
    from fidetype.trust.dropin import load as load_guard

    R = p1111()
    W = R.p1109().Windows()
    out = {}
    for arm in arms:
        f = own(f"decisions-{arm}.json")
        if f.exists():
            out[arm] = {"done": True}
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        if st["status"] != "guard":  # type: ignore[index]
            save_json({"status": "refused"}, f)
            out[arm] = {"status": "refused"}
            continue
        fn = guard_fn(an, arm)
        g = load_guard(own(f"guard-{arm}.json"), decode_fn=fn)
        rec: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
        t0 = time.time()
        for kind in ("real", "shuffled", "zeros"):
            ds = []
            for r in ev:
                x = W.get(r, kind)
                t1 = time.perf_counter()
                res = g.decide(x)
                dt = time.perf_counter() - t1
                a = an.get(x, arm.split("-")[1])
                ds.append({"action": res.action, "text": res.text, "p_top1": float(res.p_top1),
                           "n_words_committed": res.n_words_committed, "complete": res.complete,
                           "top1": a["top"] if (a and a["status"] == "ok") else "", "s": round(dt, 5),
                           "gate": a is not None})
            rec[kind] = ds
            log(f"decide {arm} {kind}: {len(ev)} prompts ({time.time() - t0:.0f} s)")
        an.save()
        save_json(rec, f)
        out[arm] = {"done": True}
        del g, rec
    return out


# --- stage score --------------------------------------------------------------------------------------


def test_auroc(an: Analyser, ev: list[dict]) -> dict:
    R = p1111()
    W = R.p1109().Windows()
    out = {}
    for dec in DECODERS:
        sig, right = [], []
        model = load_model(dec)
        for r in ev:
            a = an.get(W.get(r), dec)
            if a is None or a["status"] != "ok":
                continue
            sig.append(a["sig"])
            right.append(R.same(a["top"], R.intended_truth(r)))
        y = np.array(right)
        out[dec] = {"n_committable": len(sig), "n_right": int(y.sum()),
                    **{s: auroc(np.array([SIGNAL_DIR.get(s, 1) * t[s] for t in sig]), y) for s in SIGNALS},
                    "L": auroc(model.prob(np.array([feat_vec(t) for t in sig])), y)}
    return out


def stage_score(an: Analyser, cal: list[dict], ev: list[dict]) -> dict:
    R = p1111()
    sel = load_json(own("select.json"))
    res: dict = {"task": "P11-14", "date": time.strftime("%Y-%m-%d %H:%M"), **R.RESEARCH,
                 "note": "aggregates only (no per-user value, no text, no id)", "decoders": DECODERS,
                 "gate": load_json(P1112 / "gate.json"), "select": sel, "references": REF, "arms": {}}
    for arm in ARMS:
        st_f = own(f"guard-{arm}.status.json")
        if not st_f.exists():
            continue
        st = load_json(st_f)
        a: dict = {"status": st["status"], "cal_digest": st["cal_digest"], "eval_digest": st["eval_digest"],
                   "decoder_name": st["decoder_name"], "decoder_version": st["decoder_version"]}
        if st["status"] == "guard" and own(f"decisions-{arm}.json").exists():
            sh = st["sheet"]
            a["config_id"] = st["config_id"]
            a["sheet"] = {k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt",
                                                 "feasible", "commit_threshold", "controls", "warnings", "confidence")}
            d = load_json(own(f"decisions-{arm}.json"))
            a.update(R.score_arm("S", d, ev, sh))
            a["verdicts"] = R.verdicts(a, sh, "S")
            a["gate_cost"] = {"real_eval_gated": sum(not x["gate"] for x in d["real"]) / len(ev)}
            log(f"score {arm}: commits {a['n_commits']} wrong {a['n_wrong_commits']} value "
                f"{a['safe_v01']['value']}; {a['verdicts']}")
        else:
            a["reason"] = st.get("reason")
        res["arms"][arm] = a
    p9 = load_json(DER / "p11-09" / "guard-P.status.json")
    res["digests_match_p1109"] = all(a["cal_digest"] == p9["cal_digest"] and a["eval_digest"] == p9["eval_digest"]
                                     for a in res["arms"].values())
    res["test_auroc"] = test_auroc(an, ev)
    prim = sel["primary"]
    pa = res["arms"].get(prim, {})
    v: dict = {"primary": prim}
    if pa.get("verdicts"):
        vv = pa["verdicts"]
        val = pa["safe_v01"]["value"] or 0.0
        h1 = (vv["V1_guard"] == "certified" and vv["V2_safety"] == "holds" and vv["V3_value"] == "non-vacuous"
              and vv["V6_controls"] == "pass")
        v["H1"] = {"core": h1, "value": val, "ge_4.10": val >= REF["p1112_S"], "pass": h1 and val >= REF["p1112_S"]}
        v["H2_gt_5.08"] = h1 and val > REF["p1112_SL"]
        ref_p = res["arms"].get("P-" + prim.split("-")[1], {})
        v["H3_gt_P_same_decoder"] = (val > (ref_p.get("safe_v01", {}).get("value") or 0.0)) if ref_p else None
        v["H4"] = vv.get("V4_vs_no_bci")
    else:
        v["H1"] = {"pass": False, "reason": pa.get("status")}
    c0 = res["arms"].get("P-FL", {})
    if c0.get("n_commits") is not None:
        v["C0"] = {"commits": c0["n_commits"], "wrong": c0["n_wrong_commits"], "value": c0["safe_v01"]["value"],
                   "threshold": c0["sheet"]["commit_threshold"],
                   "pass": c0["n_commits"] == C0_REF["commits"] and c0["n_wrong_commits"] == C0_REF["wrong"]
                   and abs((c0["safe_v01"]["value"] or 0) - C0_REF["value"]) < 0.005}
    res["verdicts"] = v
    save_json(res, OUT / "results.json")
    log(f"score: verdicts {v}")
    return res


# --- main ---------------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("feat", "select", "guards", "decide", "score", "all"))
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    st = set(a.stages)
    if "all" in st:
        st |= {"feat", "select", "guards", "decide", "score"}
    arms = tuple(x for x in a.arms.split(",") if x)
    keep_awake(True)
    try:
        R, cal, ev = setup()
        an = Analyser()
        an.load()
        if "feat" in st:
            stage_feat(an, cal)
        if "select" in st:
            stage_select(an, cal)
        if "guards" in st:
            stage_guards(an, cal, ev, arms)
        if "decide" in st:
            stage_decide(an, ev, arms)
        if "score" in st:
            stage_score(an, cal, ev)
        an.save()
        if "all" in a.stages:
            own("DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("all: DONE")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
