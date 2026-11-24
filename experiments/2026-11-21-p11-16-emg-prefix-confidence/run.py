"""P11-16: P11-14 confidence signals for EMG word-prefix commits. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files stay
in C:/Users/zhang/bci-data/derived/p11-16/. The P11-07, P11-09, P11-11, P11-12, P11-14 and P11-17 files are read
only. The repo gets aggregates and per-draw counts only (no per-user value, no text, no id).

Stages (repo root; launch.py runs them detached):

  feat     decodes, signals and the U fused scores of calibration, null and evaluation windows; check C0a.
  guards   LX-FL (primary), LS-FL (exploratory) outside calibrate; BX-FL with fidetype.trust.calibrate.
  decide   decisions on the evaluation prompts (real, time-shuffled, zero EMG).
  score    check C0b; safe WPM (proposed v0.2 and adopted v0.1 complete only); verdicts -> results/results.json.
  draws    z0 check, then the 40 P11-17 calibration draws for LX-FL.
  analyse  calibration-inclusive interval -> results/results.json.
  all      every stage in this order.

The P11-14 runner is imported as a module (``Analyser``, ``GuardFn``, ``Learned``, ``feat_vec``, ``logit_clip``,
``lse``, ``setup``); its stages, ``own()``, ``log`` and caches are never called (memo load / save are overridden).
The P11-17 runner is imported for ``draw_order``, ``cluster_weights`` and ``seed_of`` only.
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
from statistics import NormalDist  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-16"  # the only place this task writes per-prompt files
P1114 = DER / "p11-14"  # READ ONLY (feat.pkl memo for C0a, model-L-FL.json for LS-FL)
P1112 = DER / "p11-12"  # READ ONLY (arm X decisions and sheet for C0b)
EXP1114 = REPO / "experiments" / "2026-11-20-p11-14-emg-lm-confidence"
EXP1117 = REPO / "experiments" / "2026-11-21-p11-17-emg-calibration-ci"
OUT = Path(os.environ.get("P1116_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
DEC = "FL"
ARMS = ("LX-FL", "LS-FL", "BX-FL")
PRIMARY = "LX-FL"
FEATS16 = ("lg_pm_fU", "lg_pm_nb", "lm_pc_k", "lg_p_fU", "lm_pc", "dist_g", "kps", "log_nw", "log_k", "share",
           "complete")
SIGNS16 = (+1, +1, +1, +1, +1, -1, 0, 0, 0, 0, 0)
L2 = 1.0
N_NULL = 300
NULL_TRIALS = 300
K = 40
B = 2000
LEVEL = 0.95
REF = {"arm_X_v02": 4.25, "L_FL": 6.80, "no_bci": 3.09}
C0B_REF = {"value": 4.25, "commits": 423, "wrong": 34}
CTL_MAX = 0.05


def log(*a: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=_js) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _js(o: object) -> object:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def _load(name: str, path: Path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    return sys.modules[name]


def m14():
    """The P11-14 runner as a module (read-only use)."""
    return _load("p1114run", EXP1114 / "run.py")


def m17():
    """The P11-17 runner as a module (read-only use: draw_order, cluster_weights, seed_of)."""
    return _load("p1117run", EXP1117 / "run.py")


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def _lse(v: np.ndarray) -> float:
    v = np.asarray(v, np.float64)
    if v.size == 0:
        return -np.inf
    m = float(v.max())
    if not np.isfinite(m):
        return m
    return m + float(np.log(np.exp(v - m).sum()))


def prefix_mass(pairs: list[tuple[str, float]], words: list[str], k: int) -> float:
    """Softmax mass (temperature 1) of the texts whose first k words are ``words[:k]``.

    k = len(words) is the whole-sentence claim: only a text whose words equal ``words`` counts.
    """
    if not pairs:
        return 0.0
    sc = np.array([s for _, s in pairs], np.float64)
    p = np.exp(sc - _lse(sc))
    m = len(words)
    tot = 0.0
    for (t, _), pi in zip(pairs, p):
        tw = t.split()
        if (tw == words) if k == m else (tw[:k] == words[:k]):
            tot += float(pi)
    return tot


def prefix_lm_text(prefix: str) -> str:
    """The LM input of a proper prefix: normalised text + the word boundary (score with eos=False)."""
    from fidetype.streams.vocab import normalize_text

    return normalize_text(prefix) + " "


def logit_clip(p: float, clip: float = 12.0) -> float:
    p = float(p)
    if p <= 0.0:
        return -clip
    if p >= 1.0:
        return clip
    return float(min(max(math.log(p) - math.log1p(-p), -clip), clip))


def prefix_rows(top: str, native: list[tuple[str, float]], fU: list[tuple[str, float]], sig: dict,
                lm_prefix) -> np.ndarray:
    """The FEATS16 rows of the word prefixes k = 1..m of ``top``. ``lm_prefix(prefix) -> lm per char`` (k < m)."""
    words = top.split()
    m = len(words)
    out = np.zeros((m, len(FEATS16)))
    for k in range(1, m + 1):
        pre = " ".join(words[:k])
        r = {"lg_pm_fU": logit_clip(prefix_mass(fU, words, k)), "lg_pm_nb": logit_clip(prefix_mass(native, words, k)),
             "lm_pc_k": float(sig["lm_pc"]) if k == m else float(lm_prefix(pre)),
             "lg_p_fU": logit_clip(sig["p_fU"]), "lm_pc": float(sig["lm_pc"]), "dist_g": float(sig["dist_g"]),
             "kps": float(sig["kps"]), "log_nw": math.log(1 + m), "log_k": math.log(1 + k), "share": k / m,
             "complete": 1.0 if k == m else 0.0}
        out[k - 1] = [r[f] for f in FEATS16]
    return out


class PLearned:
    """Sign-constrained L2 logistic regression on FEATS16 (the P11-14 ``Learned`` rule, other feature set)."""

    def __init__(self, mean, scale, lo, hi, coef, b, dropped) -> None:
        self.mean, self.scale, self.lo, self.hi = (np.asarray(v, np.float64) for v in (mean, scale, lo, hi))
        self.coef = np.asarray(coef, np.float64)
        self.b = float(b)
        self.dropped = list(dropped)

    @classmethod
    def fit(cls, X: np.ndarray, y: np.ndarray, l2: float = L2, signs=SIGNS16, names=FEATS16) -> "PLearned":
        from fidetype.trust.commit_score import fit_logistic

        X = np.asarray(X, np.float64)
        y = np.asarray(y, np.float64)
        lo, hi = X.min(0), X.max(0)
        mean, scale = X.mean(0), X.std(0)
        usable = scale > 1e-12
        scale = np.where(usable, scale, 1.0)
        Z = (X - mean) / scale
        active = [j for j in range(X.shape[1]) if usable[j]]
        dropped = [names[j] for j in range(X.shape[1]) if not usable[j]]
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
            dropped.append(names[j])
        return cls(mean, scale, lo, hi, coef, b, dropped)

    def prob(self, X: np.ndarray) -> np.ndarray:
        X = np.clip(np.atleast_2d(np.asarray(X, np.float64)), self.lo, self.hi)
        z = np.clip(((X - self.mean) / self.scale) @ self.coef + self.b, -35.0, 35.0)
        return 1.0 / (1.0 + np.exp(-z))

    def to_dict(self) -> dict:
        r = lambda a: [float(f"{v:.12g}") for v in np.asarray(a).ravel()]  # noqa: E731
        return {"features": list(FEATS16), "signs": list(SIGNS16), "mean": r(self.mean), "scale": r(self.scale),
                "lo": r(self.lo), "hi": r(self.hi), "coef": r(self.coef), "intercept": float(f"{self.b:.12g}"),
                "dropped": self.dropped, "l2": L2}

    @classmethod
    def from_dict(cls, d: dict) -> "PLearned":
        return cls(d["mean"], d["scale"], d["lo"], d["hi"], d["coef"], d["intercept"], d["dropped"])

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:12]


def decide_k(mono: np.ndarray | None, thr: float) -> int:
    """Words to commit: the longest prefix whose monotone score is >= thr (0: no commit; None: not committable)."""
    from fidetype.trust.commit_score import longest_prefix

    if mono is None or len(mono) == 0:
        return 0
    return int(longest_prefix(mono, thr))


def v02_values(committed, correct, credit_words, penalty_chars, ns, W: np.ndarray) -> np.ndarray:
    """safe-wpm/0.2 (proposed) value of each weight vector (rows of W), default correction rule, no reading cost.

    ``credit_words``: words credited if the commit is right (k for a prefix commit, truth words if complete);
    ``penalty_chars``: characters typed again after a wrong commit (``prefix_outcome``).
    """
    from fidetype.benchmark.safe_wpm import CorrectionRule

    cm = np.asarray(committed, bool)
    ok = cm & np.asarray(correct, bool)
    wrong = cm & ~ok
    pen = CorrectionRule().penalty(np.asarray(penalty_chars, float))
    credit = W @ np.where(ok, np.asarray(credit_words, float), 0.0)
    den = W @ np.asarray(ns, float) + W @ np.where(wrong, pen, 0.0)
    return np.where(den > 0, 60.0 * credit / np.where(den > 0, den, 1.0), np.nan)


def combined_interval(draws: list[dict], ns, W: np.ndarray, *, level: float = LEVEL,
                      reference: float | None = REF["no_bci"], credit_key: str = "credited") -> dict:
    """Two-level interval (P11-17 rule, proposed v0.2 formula): pooled K x B percentiles; 0.0 for uncredited draws."""
    q = [(1.0 - level) / 2.0 * 100.0, (1.0 + level) / 2.0 * 100.0]
    vals, cond = [], []
    for d in draws:
        if d.get(credit_key):
            v = v02_values(d["committed"], d["correct"], d["credit_words"], d["penalty_chars"], ns, W)
            v = v[np.isfinite(v)]
            vals.append(float(d["value"]))
        else:
            v = np.zeros(W.shape[0])
            vals.append(0.0)
        cond.append(v)
    pooled = np.concatenate(cond)
    lo, hi = (float(x) for x in np.percentile(pooled, q))
    va = np.asarray(vals)
    Kd = len(va)
    sd_b = float(va.std(ddof=1)) if Kd > 1 else 0.0
    var_w = float(np.mean([c.var(ddof=1) for c in cond]))
    sd_t = math.sqrt(var_w + sd_b ** 2)
    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    mean = float(va.mean())
    out = {"n_draws": Kd, "n_credited": int(sum(bool(d.get(credit_key)) for d in draws)), "value": mean,
           "median_draw_value": float(np.median(va)), "sd_draw_values": sd_b,
           "draw_value_range": [float(va.min()), float(va.max())], "interval": [lo, hi],
           "zero_fraction_pooled": float(np.mean(pooled == 0.0)), "sd_between_draws": sd_b,
           "sd_within_draw": math.sqrt(var_w), "sd_total": sd_t,
           "between_to_within_sd": (sd_b / math.sqrt(var_w)) if var_w > 0 else None,
           "analytic_interval": [mean - z * sd_t, mean + z * sd_t]}
    if reference is not None:
        out["reference"] = float(reference)
        out["lower_above_reference"] = bool(lo > reference)
        out["fraction_of_draws_above_reference"] = float(np.mean(va > reference))
        out["verdict"] = verdict(mean, lo, reference)
    return out


def verdict(mean: float, lo: float, ref: float) -> str:
    if lo > ref:
        return "clearly above after calibration uncertainty"
    if mean > ref:
        return "above, but inside the combined interval"
    return "not above"


def ext_sheet(arm: str, model_dict: dict, ltt: dict, controls: list, n: int = 1224) -> dict:
    """The guarantee sheet of an external prefix guard (fields read by safe_wpm.guarantee_from_sheet / controls)."""
    from fidetype.trust.commit_score import RISK_PREFIX
    from fidetype.trust.dropin import _split

    n_fit, n_pol, n_ltt = _split(n)
    thr = float(ltt["threshold"])
    cid = "p1116-" + hashlib.sha256(json.dumps({"arm": arm, "model": model_dict, "threshold": thr},
                                               sort_keys=True).encode()).hexdigest()[:16]
    return {"config_id": cid, "alpha": 0.05, "delta": 0.1, "n_items": n, "n_fit": n_fit, "n_policy": n_pol,
            "n_ltt": n_ltt, "feasible": bool(ltt["feasible"]), "commit_threshold": thr if math.isfinite(thr) else None,
            "method": "commit_score.ltt_prefix_threshold on the LTT items (outside calibrate)",
            "ltt": {k: ltt[k] for k in ("empirical_risk", "p_value", "commit_rate", "n")},
            "controls": [c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in controls],
            "confidence": {"kind": "external learned prefix score", "unit": "prefix", "risk": RISK_PREFIX}}


# --- window analysis (own memo; the P11-14 memo is read only) ---------------------------------------


def make_analyser():
    M = m14()

    class A16(M.Analyser):  # type: ignore[misc, name-defined]
        """P11-14 Analyser + the merged fused score of every intended text in U (``fU``) + prefix LM cache."""

        _plm: dict[str, float] = {}

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

        def analyse(self, x: np.ndarray, dec: str) -> dict | None:
            cap: dict = {}
            orig = M.ctc_logliks

            def rec(xx, seqs, blank=0):
                out = orig(xx, seqs, blank)
                cap["seqs"], cap["ac"] = list(seqs), np.asarray(out)
                return out

            M.ctc_logliks = rec  # the P11-14 analyse looks the name up in its module at call time
            try:
                a = M.Analyser.analyse(self, x, dec)
            finally:
                M.ctc_logliks = orig
            if a is None or a.get("status") != "ok":
                return a
            R = M.p1111()
            cfg = M.DECODERS[dec]
            f_g: dict[str, list[float]] = {}
            for s, av in zip(cap["seqs"], cap["ac"]):
                t = R.resolve("".join(self.KV[q] for q in s))
                lmv = self.lm_s(t) - cfg["lam"] * (self.n_oov_norm(t) if cfg["lam"] > 0 else 0)
                f_g.setdefault(t, []).append(float(av) + cfg["w"] * lmv + cfg["beta"] * len(s))
            a = dict(a)
            a["fU"] = sorted(((t, float(M.lse(v))) for t, v in f_g.items()), key=lambda kv: (-kv[1], kv[0]))
            return a

        def lm_prefix(self, prefix: str) -> float:
            v = self._plm.get(prefix)
            if v is None:
                P7 = M.p1107()
                v = float(P7.lm().score_sentence(prefix_lm_text(prefix), eos=False, normalize=False)) / (len(prefix) + 1)
                if len(self._plm) > 300_000:
                    self._plm.clear()
                self._plm[prefix] = v
            return v

        def rows(self, a: dict | None) -> tuple[np.ndarray, list[str]] | None:
            if a is None or a.get("status") != "ok":
                return None
            return prefix_rows(a["top"], a["native"], a["fU"], a["sig"], self.lm_prefix), a["top"].split()

    an = A16()
    an.load()
    return an


# --- scorers --------------------------------------------------------------------------------------


class Scorer:
    """Monotone prefix scores of one window analysis, or None if not committable."""

    def __init__(self, arm: str, an, model=None) -> None:
        self.arm, self.an, self.model = arm, an, model

    def mono(self, a: dict | None) -> np.ndarray | None:
        from fidetype.trust.commit_score import monotone_prefix_scores

        r = self.an.rows(a)
        if r is None or len(r[1]) == 0:
            return None
        X, words = r
        if self.arm.startswith("LX"):
            return monotone_prefix_scores(self.model.prob(X))
        if self.arm.startswith("LS"):  # the frozen P11-14 sentence score, complete row only
            c = float(self.model.prob(m14().feat_vec(a["sig"]))[0])
            return np.full(len(words), c)
        raise ValueError(self.arm)


class ExtGuard:
    """Duck-typed guard for ``dropin._run_controls``: the external prefix rule on fresh decodes (no memo)."""

    def __init__(self, an, scorer: Scorer, thr: float) -> None:
        self.an, self.scorer, self.thr = an, scorer, float(thr)
        self._codec = SimpleNamespace(vocab=an.KV, input_scale="log_probs")

    def _decide_quiet(self, x, input_scale: str | None = None):
        from fidetype.adapters.ctc_logits import to_log_probs

        lp = np.asarray(to_log_probs(x, input_scale or "log_probs"), dtype=np.float64)
        a = self.an.analyse(lp, DEC)
        mono = self.scorer.mono(a)
        if mono is None:
            return SimpleNamespace(action="withhold")
        return SimpleNamespace(action="commit" if decide_k(mono, self.thr) > 0 else "offer")


def run_controls(an, scorer: Scorer, thr: float, inputs: list, seed: int, nulls: list) -> list:
    """The calibrate controls (uniform, frame-shuffled, user null inputs) with calibrate's random state."""
    from fidetype.trust.dropin import _run_controls

    rng = np.random.default_rng(seed)
    rng.permutation(len(inputs))  # calibrate draws its order first
    return _run_controls(ExtGuard(an, scorer, thr), inputs, "logits", rng, NULL_TRIALS, 0.05, nulls)


def certify(scorer: Scorer, an, items: list[tuple[dict | None, str]]) -> dict:
    """``ltt_prefix_threshold`` on (analysis, truth) items."""
    from fidetype.trust.commit_score import ltt_prefix_threshold, prefix_right
    from fidetype.trust.risk_control import DEFAULT_LTT_GRID

    sc, rt = [], []
    for a, truth in items:
        mono = scorer.mono(a)
        if mono is None:
            sc.append(np.zeros(0))
            rt.append(np.zeros(0, bool))
        else:
            sc.append(mono)
            rt.append(prefix_right(a["top"].split(), truth.split()))
    return ltt_prefix_threshold(sc, rt, alpha=0.05, delta=0.1, grid=DEFAULT_LTT_GRID)


def fit_lx(an, items: list[tuple[dict | None, str]]) -> tuple[PLearned, int, int]:
    from fidetype.trust.commit_score import prefix_right

    Xs, ys = [], []
    n_items = 0
    for a, truth in items:
        r = an.rows(a)
        if r is None or len(r[1]) == 0:
            continue
        n_items += 1
        Xs.append(r[0])
        ys.append(prefix_right(r[1], truth.split()))
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    return PLearned.fit(X, y), n_items, int(len(y))


def decision(scorer: Scorer, thr: float, a: dict | None) -> dict:
    mono = scorer.mono(a)
    top = a["top"] if (a is not None and a.get("status") == "ok") else ""
    if mono is None:
        return {"action": "withhold", "text": None, "complete": None, "n_words_committed": 0, "top1": top}
    k = decide_k(mono, thr)
    if k == 0:
        return {"action": "offer", "text": None, "complete": None, "n_words_committed": 0, "top1": top}
    w = top.split()
    return {"action": "commit", "text": " ".join(w[:k]), "complete": k == len(w), "n_words_committed": k, "top1": top}


# --- data -----------------------------------------------------------------------------------------------


def setup():
    M = m14()
    R, cal, ev = M.setup()
    return M, R, cal, ev


# --- stage feat -------------------------------------------------------------------------------------


def stage_feat(an, R, cal, ev) -> dict:
    f = own("feat.status.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    W = R.p1109().Windows()
    t0 = time.time()
    xs = ([("real", r) for r in cal] + [("shuffled", cal[i]) for i in R.null_pick(len(cal))]
          + [(k, r) for k in ("real", "shuffled", "zeros") for r in ev])
    for n, (kind, r) in enumerate(xs, 1):
        an.get(W.get(r, kind), DEC)
        if n % 250 == 0:
            log(f"feat: {n}/{len(xs)} windows ({time.time() - t0:.0f} s)")
    an.save()
    # C0a: the calibration and null windows equal the P11-14 memo
    with open(P1114 / "feat.pkl", "rb") as fh:
        ref = pickle.load(fh)
    n_cmp = n_bad = 0
    bad: list[str] = []
    for kind, r in xs[:len(cal) + N_NULL]:
        key = R.window_key(W.get(r, kind)) + "|" + DEC
        a, b = an.memo[key], ref.get(key, "missing")
        n_cmp += 1
        ok = True
        if isinstance(b, str):
            ok = False
        elif a is None or b is None:
            ok = a is None and b is None
        elif a["status"] != b["status"]:
            ok = False
        elif a["status"] == "ok":
            ok = (a["top"] == b["top"] and len(a["native"]) == len(b["native"])
                  and all(t1 == t2 and abs(s1 - s2) <= 1e-9 for (t1, s1), (t2, s2) in zip(a["native"], b["native"]))
                  and all(abs(float(a["sig"][s]) - float(b["sig"][s])) <= 1e-9 for s in m14().SIGNALS))
            if ok and a["fU"]:  # the fU softmax of the top text must give p_fU
                ok = abs(prefix_mass(a["fU"], a["top"].split(), len(a["top"].split())) - a["sig"]["p_fU"]) <= 1e-9
        if not ok:
            n_bad += 1
            if len(bad) < 5:
                bad.append(f"{kind}")
    del ref
    rec = {"windows": len(xs), "seconds": round(time.time() - t0, 1), "memo": len(an.memo),
           "C0a": {"compared": n_cmp, "mismatch": n_bad, "kinds_of_first_mismatches": bad, "pass": n_bad == 0}}
    save_json(rec, f)
    log(f"feat: {rec}")
    return rec


# --- stage guards -------------------------------------------------------------------------------------


def cal_items(an, R, W, cal, idx) -> list[tuple[dict | None, str]]:
    return [(an.get(W.get(cal[i]), DEC), R.intended_truth(cal[i])) for i in idx]


def stage_guards(an, R, cal, ev) -> dict:
    import fidetype.trust as ft
    from fidetype.trust.dropin import _split

    M = m14()
    W = R.p1109().Windows()
    n = len(cal)
    o = np.random.default_rng(R.SEED).permutation(n)
    n_fit, n_pol, _ = _split(n)
    tune = sorted(int(i) for i in o[:n_fit + n_pol])
    assert tune == R.tune_items(n)
    ltt_idx = [int(i) for i in o[n_fit + n_pol:]]
    out = {}
    for arm in ARMS:
        rec_f = own(f"guard-{arm}.status.json")
        if rec_f.exists():
            out[arm] = load_json(rec_f)
            continue
        t0 = time.time()
        rec: dict = {"arm": arm, "n_cal": n, "n_eval": len(ev), "cal_digest": R.p1109().split_digest(cal),
                     "eval_digest": R.p1109().split_digest(ev), "tune_digest": M.p1107().tune_digest(cal)}
        xs = [W.get(r) for r in cal]
        nulls = [W.get(cal[i], "shuffled") for i in R.null_pick(n)]
        if arm == "BX-FL":
            name, ver = M.decoder_meta("BL-FL")
            try:
                g = ft.calibrate(xs, [R.intended_truth(r) for r in cal], alpha=R.ALPHA, delta=R.DELTA,
                                 input_kind="logits", vocab=an.KV, blank=0, input_scale="log_probs",
                                 frame_period=R.FRAME_S, decode_fn=M.GuardFn(an, "BL-FL"), null_inputs=nulls,
                                 decoder_name=name + "+prefix", decoder_version=ver, modality="emg",
                                 name="p11-16-BX-FL", seed=R.SEED, audit_text=False, confidence="learned",
                                 commit_unit="prefix")
            except ft.NullControlError as e:
                rec.update(status="refused", reason=str(e)[:2000])
                log(f"guards {arm}: REFUSED: {e}")
            else:
                g.save(own(f"guard-{arm}.json"))
                sh = g.sheet.to_dict()
                rec.update(status="guard", config_id=g.config_id, sheet=sh)
                log(f"guards {arm}: {g.config_id}\n{g.sheet}")
        else:
            if arm == "LX-FL":
                model, n_items, n_rows = fit_lx(an, cal_items(an, R, W, cal, tune))
                md = {**model.to_dict(), "digest": model.digest(), "n_fit_items": n_items, "n_fit_rows": n_rows}
            else:
                model = M.Learned.from_dict(load_json(P1114 / "model-L-FL.json"))
                md = {**model.to_dict(), "digest": model.digest(), "source": "P11-14 model-L-FL.json (frozen)"}
            sc = Scorer(arm, an, model)
            ltt = certify(sc, an, cal_items(an, R, W, cal, ltt_idx))
            thr = float(ltt["threshold"])
            ctl = run_controls(an, sc, thr, xs, R.SEED, nulls) if math.isfinite(thr) else []
            sh = ext_sheet(arm, {k: v for k, v in md.items() if k != "digest"}, ltt, ctl, n)
            save_json(md, own(f"model-{arm}.json"))
            rec.update(status="guard", config_id=sh["config_id"], sheet=sh, model=md,
                       controls_failed=[c["name"] for c in sh["controls"] if not c["passed"]])
            log(f"guards {arm}: thr {thr} ltt {ltt} controls {[(c['name'], c['n_commit']) for c in sh['controls']]}")
        if rec.get("sheet"):
            save_json({"config_id": rec["config_id"], "sheet": rec["sheet"], **R.RESEARCH}, OUT / f"guard-{arm}.json")
        del xs, nulls
        an.save()
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, rec_f)
        out[arm] = rec
    return out


def load_scorer(an, arm: str) -> tuple[Scorer, float]:
    st = load_json(own(f"guard-{arm}.status.json"))
    md = st["model"]  # type: ignore[index]
    model = PLearned.from_dict(md) if arm.startswith("LX") else m14().Learned.from_dict(md)
    thr = st["sheet"]["commit_threshold"]  # type: ignore[index]
    return Scorer(arm, an, model), (math.inf if thr is None else float(thr))


# --- stage decide ---------------------------------------------------------------------------------------


def stage_decide(an, R, ev) -> dict:
    from fidetype.trust.dropin import load as load_guard

    M = m14()
    W = R.p1109().Windows()
    out = {}
    for arm in ARMS:
        f = own(f"decisions-{arm}.json")
        if f.exists():
            out[arm] = {"done": True}
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        if st["status"] != "guard":  # type: ignore[index]
            save_json({"status": "refused"}, f)
            continue
        rec: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
        t0 = time.time()
        if arm == "BX-FL":
            g = load_guard(own(f"guard-{arm}.json"), decode_fn=M.GuardFn(an, "BL-FL"))
            for kind in ("real", "shuffled", "zeros"):
                ds = []
                for r in ev:
                    x = W.get(r, kind)
                    t1 = time.perf_counter()
                    res = g.decide(x)
                    dt = time.perf_counter() - t1
                    a = an.get(x, DEC)
                    ds.append({"action": res.action, "text": res.text, "complete": res.complete,
                               "n_words_committed": res.n_words_committed,
                               "top1": a["top"] if (a and a["status"] == "ok") else "", "s": round(dt, 5)})
                rec[kind] = ds
        else:
            sc, thr = load_scorer(an, arm)
            for kind in ("real", "shuffled", "zeros"):
                ds = []
                for r in ev:
                    x = W.get(r, kind)
                    t1 = time.perf_counter()
                    a = an.analyse(np.asarray(x, np.float64), DEC) if kind == "real" else an.get(x, DEC)
                    d = decision(sc, thr, a)
                    d["s"] = round(time.perf_counter() - t1, 5)  # real: decode not memoised
                    ds.append(d)
                rec[kind] = ds
        log(f"decide {arm}: done ({time.time() - t0:.0f} s)")
        an.save()
        save_json(rec, f)
        out[arm] = {"done": True}
    return out


# --- stage score --------------------------------------------------------------------------------------


def test_auroc(an, R, ev, sc: Scorer) -> dict:
    from fidetype.trust.commit_score import prefix_right

    M = m14()
    W = R.p1109().Windows()
    s_pm, s_lm, s_L, y = [], [], [], []
    for r in ev:
        a = an.get(W.get(r), DEC)
        rr = an.rows(a)
        if rr is None or len(rr[1]) == 0:
            continue
        X, words = rr
        s_pm += list(X[:, FEATS16.index("lg_pm_fU")])
        s_lm += list(X[:, FEATS16.index("lm_pc_k")])
        s_L += list(sc.model.prob(X))
        y += list(prefix_right(words, R.intended_truth(r).split()))
    yv = np.array(y, bool)
    return {"n_rows": len(y), "n_right_rows": int(yv.sum()), "lg_pm_fU": M.auroc(np.array(s_pm), yv),
            "lm_pc_k": M.auroc(np.array(s_lm), yv), "LX_raw": M.auroc(np.array(s_L), yv)}


def stage_score(an, R, cal, ev) -> dict:
    # C0b: the P11-11 scorer reproduces P11-12 arm X
    d12 = load_json(P1112 / "decisions-X.json")
    st12 = load_json(P1112 / "guard-X.status.json")
    a12 = R.score_arm("X", d12, ev, st12["sheet"])  # type: ignore[index]
    v12 = a12["safe_v02"]["value"] or 0.0
    c0b = {"value": v12, "commits": a12["n_commits"], "wrong": a12["n_wrong_commits"],
           "pass": round(v12, 2) == C0B_REF["value"] and a12["n_commits"] == C0B_REF["commits"]
           and a12["n_wrong_commits"] == C0B_REF["wrong"]}
    log(f"score: C0b {c0b}")
    feat = load_json(own("feat.status.json"))
    res: dict = {"task": "P11-16", "date": time.strftime("%Y-%m-%d %H:%M"), **R.RESEARCH,
                 "note": "aggregates only (no per-user value, no text, no id); safe-wpm/0.2 is PROPOSED, not adopted",
                 "decoder": m14().DECODERS[DEC], "references": REF, "C0a": feat["C0a"], "C0b": c0b,  # type: ignore[index]
                 "arms": {}}
    if not (feat["C0a"]["pass"] and c0b["pass"]):  # type: ignore[index]
        res["stopped"] = "C0a or C0b failed: no result (plan)"
        save_json(res, OUT / "results.json")
        log("score: C0 failed; no result")
        return res
    for arm in ARMS:
        st = load_json(own(f"guard-{arm}.status.json"))
        a: dict = {"status": st["status"], "cal_digest": st["cal_digest"], "eval_digest": st["eval_digest"]}
        if st["status"] == "guard":
            sh = st["sheet"]
            a["config_id"] = st["config_id"]
            a["sheet"] = {k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt",
                                                 "feasible", "commit_threshold", "controls", "warnings", "ltt")}
            conf = sh.get("confidence") or {}
            a["model"] = ({k: conf.get(k) for k in ("features", "dropped", "n_used", "coef", "intercept", "fit_rows")}
                          if arm == "BX-FL" else
                          {k: st["model"].get(k) for k in ("features", "coef", "intercept", "dropped", "digest",
                                                           "n_fit_items", "n_fit_rows", "source")})
            d = load_json(own(f"decisions-{arm}.json"))
            a.update(R.score_arm("X", d, ev, sh))
            a["verdicts"] = R.verdicts(a, sh, "X")
            log(f"score {arm}: commits {a['n_commits']} ({a['n_prefix_commits']} prefix) wrong "
                f"{a['n_wrong_commits']} v0.2 {a['safe_v02']['value']} v0.1c {a['safe_v01_complete_only']['value']};"
                f" {a['verdicts']}")
        else:
            a["reason"] = st.get("reason")
        res["arms"][arm] = a
    p9 = load_json(DER / "p11-09" / "guard-P.status.json")
    res["digests_match_p1109"] = all(a["cal_digest"] == p9["cal_digest"] and a["eval_digest"] == p9["eval_digest"]
                                     for a in res["arms"].values())
    sc, _ = load_scorer(an, PRIMARY)
    res["test_auroc_prefix_rows"] = test_auroc(an, R, ev, sc)
    pa = res["arms"].get(PRIMARY, {})
    v: dict = {"primary": PRIMARY}
    if pa.get("verdicts"):
        vv = pa["verdicts"]
        val = pa["safe_v02"]["value"] or 0.0
        core = (vv["V1_guard"] == "certified" and vv["V2_safety"] == "holds" and vv["V3_value"] == "non-vacuous"
                and vv["V6_controls"] == "pass")
        v["H1"] = {"core": core, "value_v02": val, "gt_4.25": val > REF["arm_X_v02"],
                   "pass": core and val > REF["arm_X_v02"]}
        v["H2_gt_6.80"] = core and val > REF["L_FL"]
        bx = res["arms"].get("BX-FL", {}).get("safe_v02", {})
        v["H3_gt_BX"] = (val > (bx.get("value") or 0.0)) if bx else None
        v["H4"] = vv.get("V4_vs_no_bci")
    else:
        v["H1"] = {"pass": False, "reason": pa.get("status")}
    res["verdicts"] = v
    save_json(res, OUT / "results.json")
    log(f"score: verdicts {v}")
    return res


# --- stage draws / analyse ----------------------------------------------------------------------------


def jobs() -> list[dict]:
    S = m17()
    js = [{"name": "z0", "k": 0, "seed": 0, "boot_seed": None}]
    for k in range(1, K + 1):
        js.append({"name": f"k{k:02d}", "k": k, "seed": S.seed_of(f"p11-17|emg|cal|{k}"),
                   "boot_seed": S.seed_of(f"p11-17|emg|boot|{k}")})
    return js


def eval_arrays(R, ev: list[dict]) -> dict:
    truths = [R.intended_truth(r) for r in ev]
    return {"truths": truths, "nw": [len(t.split()) for t in truths], "nch": [len(t) for t in truths],
            "ns": [r["neural_s"] for r in ev], "clusters": [{"group": f"u{r['i']}"} for r in ev]}


def outcomes(decs: list[dict], truths: list[str]) -> dict:
    from fidetype.benchmark.safe_wpm import prefix_outcome

    com, cor, cw, full, pen, credit = [], [], [], [], [], []
    for x, t in zip(decs, truths):
        c = x["action"] == "commit"
        o = prefix_outcome(x["text"] or "", t, bool(x["complete"])) if c else None
        com.append(c)
        cor.append(bool(o and o["correct"]))
        cw.append(o["committed_words"] if o else 0)
        full.append(bool(x["complete"]) if c else True)
        pen.append(o["penalty_chars"] if o else 0)
        credit.append((o["committed_words"] if not o["complete"] else len(t.split())) if o else 0)
    return {"committed": com, "correct": cor, "committed_words": cw, "complete": full, "penalty_chars": pen,
            "credit_words": credit}


def run_draw(jb: dict, an, R, cal, ev, E: dict) -> dict:
    from fidetype.benchmark import safe_wpm as SW

    path = own(f"draw-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
    W = R.p1109().Windows()
    n = len(cal)
    L, desired, info = m17().draw_order(n, jb["seed"], jb["boot_seed"])
    n_tune = info["split"][0] + info["split"][1]
    model, n_items, n_rows = fit_lx(an, cal_items(an, R, W, cal, sorted(int(i) for i in desired[:n_tune])))
    sc = Scorer(PRIMARY, an, model)
    ltt = certify(sc, an, cal_items(an, R, W, cal, [int(i) for i in desired[n_tune:]]))
    thr = float(ltt["threshold"])
    xs = [W.get(cal[int(i)]) for i in L]
    pick = sorted(np.random.default_rng(jb["seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
    nulls = [W.get(cal[i], "shuffled") for i in pick]
    ctl = run_controls(an, sc, thr, xs, jb["seed"], nulls) if math.isfinite(thr) else []
    del xs, nulls
    md = model.to_dict()
    sh = ext_sheet(PRIMARY, md, ltt, ctl, n)
    dec = {kind: [decision(sc, thr, an.get(W.get(r, kind), DEC)) for r in ev] for kind in ("real", "shuffled", "zeros")}
    oc = outcomes(dec["real"], E["truths"])
    sw = SW.safe_wpm(oc["committed"], oc["correct"], E["nw"], E["nch"], E["ns"], guarantee=SW.guarantee_from_sheet(sh),
                     controls=SW.controls_from_sheet(sh), gaze_chars_per_min=None, metric_version="0.2",
                     committed_words=oc["committed_words"], complete=oc["complete"], penalty_chars=oc["penalty_chars"], read_s_per_commit=0.0, read_s_per_word=0.0)
    ectl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ectl[k] / len(ev) <= CTL_MAX for k in ectl)
    cal_ok = bool(ctl) and all(c.passed for c in ctl)
    credited = cal_ok and sw["status"] == "certified" and sw["value"] is not None and v6
    res = {**jb, "draw_info": info, "model": {**md, "digest": model.digest(), "n_fit_items": n_items,
                                              "n_fit_rows": n_rows, "n_kept": int(np.sum(model.coef != 0))},
           "threshold": thr if math.isfinite(thr) else None, "feasible": bool(ltt["feasible"]), "ltt": ltt,
           "cal_controls": [c.to_dict() for c in ctl], "cal_controls_pass": cal_ok,
           "safe_status": sw["status"], "raw_value": float(sw["value"]) if sw["value"] is not None else None,
           "value": float(sw["value"]) if credited else 0.0, "credited": bool(credited), "v6_eval": bool(v6),
           "eval_controls": ectl, "n_commits": int(sum(oc["committed"])),
           "n_prefix_commits": int(sum(c and not f for c, f in zip(oc["committed"], oc["complete"]))),
           "n_wrong": int(sum(c and not k for c, k in zip(oc["committed"], oc["correct"]))),
           **{k: oc[k] for k in ("committed", "correct", "credit_words", "penalty_chars")},
           "actions": {kind: [x["action"] for x in dec[kind]] for kind in dec},
           "n_words": {kind: [x["n_words_committed"] for x in dec[kind]] for kind in dec},
           "seconds": round(time.time() - t0, 1)}
    save_json(res, path)
    log(f"draw {jb['name']}: thr {res['threshold']} commits {res['n_commits']} ({res['n_prefix_commits']} prefix) "
        f"wrong {res['n_wrong']} status {sw['status']} raw {res['raw_value']} credited {credited} eval ctl {ectl} "
        f"cal ctl {[c['n_commit'] for c in res['cal_controls']]} kept {res['model']['n_kept']} ({res['seconds']} s)")
    return res


def z0_check(d: dict, an, R, ev, E: dict) -> dict:
    """z0 must give exactly the primary LX-FL model, threshold and decisions (plan)."""
    st = load_json(own(f"guard-{PRIMARY}.status.json"))
    ref = load_json(own(f"decisions-{PRIMARY}.json"))
    same = {k: sum(a == b["action"] and m == b["n_words_committed"]
                   for a, m, b in zip(d["actions"][k], d["n_words"][k], ref[k])) for k in ("real", "shuffled", "zeros")}
    v = v02_values(d["committed"], d["correct"], d["credit_words"], d["penalty_chars"], E["ns"],
                   np.ones((1, len(ev))))[0]
    n = len(ev)
    thr_ref = st["sheet"]["commit_threshold"]  # type: ignore[index]
    out = {"model_digest": d["model"]["digest"], "ref_model_digest": st["model"]["digest"],  # type: ignore[index]
           "threshold": d["threshold"], "ref_threshold": thr_ref, "same_decisions": same, "n_eval": n,
           "unit_weight_value": float(v), "safe_wpm_value": d["raw_value"]}
    out["pass"] = bool(out["model_digest"] == out["ref_model_digest"] and d["threshold"] == thr_ref
                       and all(s == n for s in same.values()) and d["raw_value"] is not None
                       and abs(float(v) - d["raw_value"]) < 1e-9)
    return out


def stage_draws(an, R, cal, ev) -> int:
    E = eval_arrays(R, ev)
    for jb in jobs():
        d = run_draw(jb, an, R, cal, ev, E)
        if jb["name"] == "z0":
            z = z0_check(d, an, R, ev, E)
            save_json(z, own("z0.json"))
            log(f"z0: {'PASS' if z['pass'] else 'FAIL'} {z}")
            if not z["pass"]:
                log("z0 failed: stop (plan: the draws do not count)")
                return 2
    return 0


def stage_analyse(R, ev) -> int:
    E = eval_arrays(R, ev)
    z = load_json(own("z0.json"))
    res = load_json(OUT / "results.json")
    if not z["pass"]:  # type: ignore[index]
        log("analyse: z0 did not pass; no interval")
        return 2
    ds = [load_json(own(f"draw-{jb['name']}.json")) for jb in jobs() if jb["k"] > 0]
    assert len(ds) == K, len(ds)
    Wt = m17().cluster_weights(E["clusters"])
    prim = combined_interval(ds, E["ns"], Wt)
    for d in ds:  # P11-17 variant (a): above-alpha draws keep their value (descriptive)
        d["keep"] = bool(d.get("cal_controls_pass") and d.get("v6_eval") and d.get("raw_value") is not None
                         and d.get("safe_status") in ("certified", "above-alpha"))
        d["value_keep"] = d["raw_value"] if d["keep"] else 0.0
    va = combined_interval([{**d, "value": d["value_keep"]} for d in ds], E["ns"], Wt, credit_key="keep")
    statuses: dict[str, int] = {}
    for d in ds:
        s = ("cal-control-fail" if not d.get("cal_controls_pass") else
             d["safe_status"] if d.get("v6_eval") else "v6-fail")
        statuses[s] = statuses.get(s, 0) + 1
    p17 = load_json(EXP1117 / "results" / "results.json")
    p17v = {x["k"]: x["value"] for x in p17["draws"]}  # type: ignore[index]
    per = [{k: d.get(k) for k in ("name", "k", "safe_status", "credited", "value", "raw_value", "n_commits",
                                  "n_prefix_commits", "n_wrong", "threshold", "eval_controls", "v6_eval", "seconds")}
           | {"cal_controls": [c["n_commit"] for c in d.get("cal_controls", [])],
              "model_kept": d["model"]["n_kept"], "p11_17_lfl_value": p17v.get(d["k"])} for d in ds]
    both = [(x["value"], x["p11_17_lfl_value"]) for x in per if x["p11_17_lfl_value"] is not None]
    res["calibration_inclusive"] = {  # type: ignore[index]
        "arm": PRIMARY, "metric": "safe-wpm/0.2 (PROPOSED)", "K": K, "B": int(Wt.shape[0]), "level": LEVEL,
        "z0": z, "statuses": statuses, "primary_user_cluster": prim, "variant_a_keep_above_alpha": va,
        "mean_commits": float(np.mean([d["n_commits"] for d in ds])),
        "mean_wrong": float(np.mean([d["n_wrong"] for d in ds])),
        "threshold_range": [min(d["threshold"] for d in ds if d["threshold"] is not None),
                            max(d["threshold"] for d in ds if d["threshold"] is not None)],
        "vs_p11_17_same_draw": {"n": len(both), "lx_higher": int(sum(a > b for a, b in both)),
                                "equal": int(sum(a == b for a, b in both)),
                                "mean_difference": float(np.mean([a - b for a, b in both])) if both else None},
        "verdict_H5": prim["verdict"], "draws": per}
    save_json(res, OUT / "results.json")
    log(f"analyse: {prim['value']:.3f} [{prim['interval'][0]:.2f}, {prim['interval'][1]:.2f}] '{prim['verdict']}'; "
        f"statuses {statuses}")
    return 0


# --- main ---------------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("feat", "guards", "decide", "score", "draws", "analyse", "all"))
    a = ap.parse_args()
    st = set(a.stages)
    if "all" in st:
        st |= {"feat", "guards", "decide", "score", "draws", "analyse"}
    keep_awake(True)
    try:
        M, R, cal, ev = setup()
        an = make_analyser()
        if "feat" in st:
            rec = stage_feat(an, R, cal, ev)
            if not rec["C0a"]["pass"]:
                log("C0a failed: stop (plan)")
                return 2
        if "guards" in st:
            stage_guards(an, R, cal, ev)
        if "decide" in st:
            stage_decide(an, R, ev)
        if "score" in st:
            res = stage_score(an, R, cal, ev)
            if res.get("stopped"):
                return 2
        if "draws" in st:
            if stage_draws(an, R, cal, ev) != 0:
                return 2
        if "analyse" in st:
            if stage_analyse(R, ev) != 0:
                return 2
        an.save()
        if "all" in a.stages:
            own("DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("all: DONE")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
