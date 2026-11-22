"""LM readout of the character decoders: CTC prefix beam search with a character n-gram LM, and a no-signal gate.

Our own code (Apache-2.0). NumPy only (no torch).

The search (:class:`LMBeam`) is the P11-07 decoder (``experiments/2026-11-20-p11-07-emg-beam-lm/lmbeam.py``),
copied here without a change of method (P14-48). P15-25 used it as readout "F" (Tatoeba 6-gram, w 0.5,
beta 1, beam 8). It reads natural-log CTC frame probabilities over a key vocabulary (the P11-01 98-token
vocabulary or the 33-class key vocabulary) and searches key sequences. The LM scores the *intended text*
of a key prefix:

- a letter key (either case) appends its lower-case letter;
- Space and every other printable non-letter key append a space; runs of spaces join (the
  ``normalize_text`` rule that built the Tatoeba LM);
- Backspace removes the last intended character (the LM score returns to the score before it);
- Enter starts a new sentence (LM context reset to ``<s>``).

Score of a key prefix::

    score = logp_acoustic + w * (logp_LM(intended text) - lam * n_oov_words) + beta * n_keys

The no-signal gate (:class:`NoSignalGate`, the P11-12 design) reads only the acoustic output: the number
of greedy CTC emissions and their rate per second. On flat or empty frames the LM and the length bonus
alone decide the beam (P15-25: uniform frames give one token per frame), so the gate runs first and an
input that fails it gives no text. P14-49 adds :class:`ScoreGate`: a gate on one posterior feature (the share
of non-blank frames, the peak probability of the emissions, the entropy of the non-blank frames, the LM text
length per emission) or on a small logistic score of these features; :func:`gate_from_dict` reads either kind
from a manifest.

:class:`LmReadout` joins the two: ``text(log_probs)``, ``nbest(log_probs)`` and ``decode_fn()`` (the user
decoder form of :func:`fidetype.trust.calibrate`).
"""


from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np

NEG_INF = -math.inf

# token kinds
K_BLANK, K_LETTER, K_SPACE, K_PUNCT, K_BS, K_ENTER, K_NONE = range(7)
_BS = {"⌫", "\x08"}
_EN = {"⏎", "\r", "\n"}


def token_table(vocab: list[str], blank: int = 0) -> tuple[np.ndarray, list[str]]:
    """Kind of each token, and its letter (lower case) for letters.

    ``_`` is Space in the 33-class key vocabulary (``key_chars``); in the 98-token vocabulary ``_`` is a
    printable punctuation key. The caller says which by the vocabulary size: a vocabulary with a real ``" "``
    token treats ``_`` as punctuation.
    """
    has_space = " " in vocab
    kinds = np.full(len(vocab), K_NONE, np.int64)
    letters = [""] * len(vocab)
    for i, t in enumerate(vocab):
        if i == blank:
            kinds[i] = K_BLANK
        elif t in _BS:
            kinds[i] = K_BS
        elif t in _EN:
            kinds[i] = K_ENTER
        elif t == " " or (t == "_" and not has_space):
            kinds[i] = K_SPACE
        elif len(t) == 1 and t.isascii() and t.isalpha():
            kinds[i] = K_LETTER
            letters[i] = t.lower()
        elif len(t) == 1 and t.isprintable():
            kinds[i] = K_PUNCT
    return kinds, letters


@dataclass
class Hyp:
    tokens: list[int]
    frames: list[int]
    score: float
    logp_acoustic: float
    logp_lm: float


class LMBeam:
    """Streaming CTC prefix beam search with intended-text LM fusion (see the module docstring)."""

    def __init__(self, vocab: list[str], blank: int = 0, lm=None, lm_weight: float = 0.0, bonus: float = 0.0,
                 beam: int = 16, prune_logp: float = -8.0, lexicon: frozenset[str] | None = None,
                 lam: float = 0.0) -> None:
        self.vocab = list(vocab)
        self.V = V = len(vocab)
        self.blank = blank
        self.kinds, self.letters = token_table(self.vocab, blank)
        self.lm = lm
        self.w = float(lm_weight) if lm is not None else 0.0
        self.bonus = float(bonus)
        self.B = int(beam)
        self.prune = float(prune_logp)
        self.lex = lexicon if (lexicon is not None and lam > 0) else None
        self.lam = float(lam) if self.lex is not None else 0.0
        self.order1 = (lm.order - 1) if lm is not None else 0
        # LM column of each letter token in logprobs_vocab (1..26), space = 27
        self._let_col = np.array([(ord(self.letters[i]) - 96) if self.kinds[i] == K_LETTER else 0 for i in range(V)])
        self._is_let = self.kinds == K_LETTER
        self._is_sp = (self.kinds == K_SPACE) | (self.kinds == K_PUNCT)
        self._is_bs = self.kinds == K_BS
        self._is_en = self.kinds == K_ENTER
        self._allowed = (self.kinds != K_BLANK) & (self.kinds != K_NONE)
        self._row_cache: dict[tuple[str, int], np.ndarray] = {}
        # intended nodes: parent, cumulative LM, context, open word
        self.i_par: list[int] = [-1]
        self.i_cum: list[float] = [0.0]
        self.i_ctx: list[str] = [""]
        self.i_word: list[str] = [""]
        # key nodes: parent, token, frame, intended node
        self.k_par: list[int] = [-1]
        self.k_tok: list[int] = [-1]
        self.k_fr: list[int] = [-1]
        self.k_in: list[int] = [0]
        # beam state
        self.nodes = np.array([0], np.int64)
        self.par = np.array([-1], np.int64)
        self.last = np.array([-1], np.int64)
        self.pb = np.array([0.0])
        self.pnb = np.array([NEG_INF])
        self.lms = np.array([0.0])
        self.ln = np.array([0.0])
        self.L = self._row(0)[None, :].copy()
        self.t = 0

    # --- LM rows ---------------------------------------------------------------------------------------

    def _wstate(self, word: str) -> int:
        if not word or self.lex is None:
            return 0
        return 1 if word in self.lex else 2

    def _close(self, word: str) -> float:
        """LM-side cost of closing ``word`` (lexicon term)."""
        return -self.lam if (word and self.lex is not None and word not in self.lex) else 0.0

    def _row(self, n: int) -> np.ndarray:
        """LM delta of each token from intended node ``n`` (unweighted)."""
        ctx, word = self.i_ctx[n], self.i_word[n]
        key = (ctx, self._wstate(word))
        base = self._row_cache.get(key)
        if base is None:
            base = np.zeros(self.V)
            if self.lm is not None:
                lp = np.asarray(self.lm.logprobs_vocab(ctx), np.float64)
                base[self._is_let] = lp[self._let_col[self._is_let]]
                collapse = ctx == "" or ctx.endswith(" ")
                base[self._is_sp] = 0.0 if collapse else lp[27] + self._close(word)
            else:
                base[self._is_sp] = self._close(word)
            base[self._is_en] = self._close(word)
            if len(self._row_cache) > 400_000:
                self._row_cache.clear()
            self._row_cache[key] = base
        if self._is_bs.any():
            p = self.i_par[n]
            r = base.copy()
            r[self._is_bs] = (self.i_cum[p] - self.i_cum[n]) if p >= 0 else 0.0
            return r
        return base

    def _push_intended(self, n: int, tok: int) -> int:
        k = self.kinds[tok]
        if k == K_BS:
            p = self.i_par[n]
            return p if p >= 0 else n
        ctx, word, cum = self.i_ctx[n], self.i_word[n], self.i_cum[n]
        if k == K_ENTER:
            nctx, nword, d = "", "", self._close(word)
        elif k == K_LETTER:
            ch = self.letters[tok]
            d = float(self.lm.logprobs_vocab(ctx)[ord(ch) - 96]) if self.lm is not None else 0.0
            nctx = (ctx + ch)[-self.order1:] if self.order1 else ""
            nword = (word + ch)[-40:]
        else:  # space-like: Space and the other printable non-letter keys
            collapse = (ctx == "" or ctx.endswith(" ")) if self.lm is not None else word == ""
            if collapse:
                d, nctx = 0.0, ctx
            else:
                d = (float(self.lm.logprobs_vocab(ctx)[27]) if self.lm is not None else 0.0) + self._close(word)
                nctx = (ctx + " ")[-self.order1:] if self.order1 else ""
            nword = ""
        self.i_par.append(n)
        self.i_cum.append(cum + d)
        self.i_ctx.append(nctx)
        self.i_word.append(nword)
        return len(self.i_par) - 1

    # --- search ----------------------------------------------------------------------------------------

    def push(self, log_probs: np.ndarray) -> None:
        lp = np.asarray(log_probs, np.float64)
        if lp.ndim != 2 or lp.shape[1] != self.V:
            raise ValueError(f"chunk must be (n, {self.V}), got {lp.shape}")
        allow = (lp >= self.prune) & self._allowed[None, :]
        active = allow.any(axis=1)
        blank, w, bonus, B = self.blank, self.w, self.bonus, self.B
        nodes, par, last, pb, pnb, lms, ln, L = (self.nodes, self.par, self.last, self.pb, self.pnb, self.lms,
                                                 self.ln, self.L)
        for t in range(lp.shape[0]):
            row = lp[t]
            ptot = np.logaddexp(pb, pnb)
            s_pb = ptot + row[blank]
            s_pnb = np.where(last >= 0, pnb + row[np.maximum(last, 0)], NEG_INF)
            if not active[t]:
                pb, pnb = s_pb, s_pnb
                continue
            C = np.nonzero(allow[t])[0]
            # acoustic score of each extension (b, c)
            same = last[:, None] == C[None, :]
            ext = np.where(same, pb[:, None], ptot[:, None]) + row[C][None, :]
            # merge: an extension that gives a prefix already in the beam joins that prefix
            if len(nodes) > 1:
                order = np.argsort(nodes, kind="stable")
                sn = nodes[order]
                pos = np.searchsorted(sn, par)
                pos = np.minimum(pos, len(sn) - 1)
                hit = (sn[pos] == par) & (par >= 0)
                if hit.any():
                    j = np.nonzero(hit)[0]
                    b = order[pos[j]]
                    cpos = np.searchsorted(C, last[j])
                    cpos = np.minimum(cpos, len(C) - 1)
                    okc = C[cpos] == last[j]
                    if okc.any():
                        j, b, cpos = j[okc], b[okc], cpos[okc]
                        s_pnb[j] = np.logaddexp(s_pnb[j], ext[b, cpos])
                        ext[b, cpos] = NEG_INF
            stay = np.logaddexp(s_pb, s_pnb) + w * lms + bonus * ln
            flat = (ext + w * (lms[:, None] + L[:, C]) + bonus * (ln[:, None] + 1.0)).ravel()
            ok = np.nonzero(flat > NEG_INF)[0]
            if ok.size > B:
                ok = ok[np.argpartition(-flat[ok], B - 1)[:B]]
            ss = np.nonzero(stay > NEG_INF)[0]
            scores = np.concatenate([stay[ss], flat[ok]])
            kind = np.concatenate([np.zeros(ss.size, np.int64), np.ones(ok.size, np.int64)])
            idx = np.concatenate([ss, ok])
            rank = np.lexsort((idx, kind, -scores))[:B]
            isx = kind[rank] == 1
            src = idx[rank]
            K = len(C)
            pb_i = np.where(isx, src // K, src)
            ci = np.where(isx, src % K, 0)
            tok = np.where(isx, C[ci], -1)
            n_pb = np.where(isx, NEG_INF, s_pb[pb_i])
            n_pnb = np.where(isx, ext[pb_i, ci], s_pnb[pb_i])
            n_nodes = nodes[pb_i].copy()
            n_par = par[pb_i].copy()
            n_last = last[pb_i].copy()
            n_lms = lms[pb_i].copy()
            n_ln = ln[pb_i] + isx
            n_L = L[pb_i].copy()
            for q in np.nonzero(isx)[0].tolist():
                parent = int(nodes[pb_i[q]])
                tk = int(tok[q])
                inode = self._push_intended(self.k_in[parent], tk)
                self.k_par.append(parent)
                self.k_tok.append(tk)
                self.k_fr.append(self.t + t)
                self.k_in.append(inode)
                nid = len(self.k_par) - 1
                n_nodes[q] = nid
                n_par[q] = parent
                n_last[q] = tk
                n_lms[q] = self.i_cum[inode]
                n_L[q] = self._row(inode)
            nodes, par, last, pb, pnb, lms, ln, L = n_nodes, n_par, n_last, n_pb, n_pnb, n_lms, n_ln, n_L
        self.nodes, self.par, self.last, self.pb, self.pnb, self.lms, self.ln, self.L = (nodes, par, last, pb, pnb,
                                                                                         lms, ln, L)
        self.t += lp.shape[0]

    # --- results ---------------------------------------------------------------------------------------

    def _end_lm(self, inode: int, eos: bool) -> float:
        word = self.i_word[inode]
        e = self._close(word)
        if eos and self.lm is not None:
            ctx = self.i_ctx[inode]
            e += float(self.lm.logprobs_vocab(ctx.rstrip(" ") if ctx.endswith(" ") else ctx)[0])
        return e

    def path(self, node: int) -> tuple[list[int], list[int]]:
        toks, frs = [], []
        while node > 0:
            toks.append(self.k_tok[node])
            frs.append(self.k_fr[node])
            node = self.k_par[node]
        return toks[::-1], frs[::-1]

    def nbest(self, n: int | None = None, eos: bool = True) -> list[Hyp]:
        """Final hypotheses, best first, with the end terms (open word, ``</s>``)."""
        out = []
        for j in range(len(self.nodes)):
            node = int(self.nodes[j])
            ac = float(np.logaddexp(self.pb[j], self.pnb[j]))
            if ac == NEG_INF:
                continue
            lml = float(self.lms[j]) + self._end_lm(self.k_in[node], eos)
            sc = ac + self.w * lml + self.bonus * float(self.ln[j])
            out.append((sc, j, node, ac, lml))
        out.sort(key=lambda x: (-x[0], x[1]))
        if n is not None:
            out = out[:n]
        res = []
        for sc, _, node, ac, lml in out:
            toks, frs = self.path(node)
            res.append(Hyp(toks, frs, sc, ac, lml))
        return res



# --- no-signal gate and readout (P14-48) -----------------------------------------------------------------

#: Decoder id of the gated LM readout in the manifests (``readouts.lm.decode``).
READOUT_ID = "ctc-lmbeam-ngram-gated-v1"


def greedy_tokens(lp: np.ndarray, blank: int = 0) -> list[int]:
    """Greedy CTC: per-frame argmax, runs of the same index joined, blank removed."""
    a = np.asarray(lp).argmax(1)
    if len(a) == 0:
        return []
    keep = np.concatenate([[True], a[1:] != a[:-1]])
    a = a[keep]
    return [int(x) for x in a[a != blank]]


def gate_features(lp: np.ndarray, frame_s: float, blank: int = 0) -> tuple[int, float]:
    """(n_keys, kps): greedy CTC emissions and emissions per second of the input."""
    T = int(np.asarray(lp).shape[0])
    n = len(greedy_tokens(lp, blank))
    return n, (n / (frame_s * T) if T > 0 else 0.0)


@dataclass(frozen=True)
class NoSignalGate:
    """Pass iff ``n_keys >= k_min`` and ``r_min <= kps <= r_max`` (P11-12 design)."""

    k_min: int
    r_min: float
    r_max: float
    frame_s: float
    blank: int = 0

    def features(self, lp: np.ndarray) -> tuple[int, float]:
        return gate_features(lp, self.frame_s, self.blank)

    def passes(self, lp: np.ndarray) -> bool:
        n, r = self.features(lp)
        return bool(n >= self.k_min and self.r_min <= r <= self.r_max)

    def to_dict(self) -> dict[str, Any]:
        return {"k_min": int(self.k_min), "r_min": float(self.r_min), "r_max": float(self.r_max),
                "frame_s": float(self.frame_s), "blank": int(self.blank)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "NoSignalGate":
        return cls(int(d["k_min"]), float(d["r_min"]), float(d["r_max"]), float(d["frame_s"]),
                   int(d.get("blank", 0)))

    @classmethod
    def fit(cls, fit_inputs: Sequence[np.ndarray], frame_s: float, blank: int = 0, tail: float = 0.01,
            r_max_factor: float = 2.0) -> "NoSignalGate":
        """The P11-12 fit rule, on real calibration inputs only.

        With ``m = floor(tail * n)``: ``k_min`` = the largest k with at most m inputs below it (the
        (m + 1)-th smallest ``n_keys``); ``r_min`` = the (m + 1)-th smallest ``kps``; ``r_max`` =
        ``r_max_factor`` x the largest ``kps``.
        """
        feats = [gate_features(x, frame_s, blank) for x in fit_inputs]
        if not feats:
            raise ValueError("the gate needs at least one fit input")
        m = int(math.floor(tail * len(feats) + 1e-9))
        ks = sorted(f[0] for f in feats)
        rs = sorted(f[1] for f in feats)
        return cls(int(ks[m]), float(rs[m]), float(r_max_factor * rs[-1]), float(frame_s), int(blank))


# --- score gates (P14-49) ----------------------------------------------------------------------------------

#: Features of :func:`posterior_features` that a :class:`ScoreGate` can read (higher = more like real input).
SCORE_FEATURES = ("nb_share", "peak", "neg_entropy", "lm_ratio", "logit")
#: Inputs of the learned score (``feature = "logit"``), in this order.
LOGIT_INPUTS = ("peak", "neg_entropy", "nb_share", "kps", "log_n_keys")


def posterior_features(lp: np.ndarray, frame_s: float, blank: int = 0) -> dict[str, float]:
    """Posterior features of one input (natural-log frame probabilities, T x V).

    - ``n_keys``, ``kps``: as :func:`gate_features`;
    - ``nb_share``: the share of frames whose argmax is not blank;
    - ``peak``: the mean, over the greedy emissions, of the largest probability of the emitted token in its run
      (0.0 when there is no emission);
    - ``neg_entropy``: minus the mean entropy (nats) of the frames whose argmax is not blank
      (``-log V`` when there is no such frame);
    - ``log_n_keys``: ``log(1 + n_keys)``.
    """
    x = np.asarray(lp, np.float64)
    T, V = x.shape
    a = x.argmax(1) if T else np.zeros(0, np.int64)
    nb = a != blank
    n_keys = 0
    peaks: list[float] = []
    if T:
        start = np.concatenate([[True], a[1:] != a[:-1]])
        idx = np.nonzero(start)[0]
        ends = np.concatenate([idx[1:], [T]])
        for s, e in zip(idx.tolist(), ends.tolist()):
            tok = int(a[s])
            if tok == blank:
                continue
            n_keys += 1
            peaks.append(float(np.exp(x[s:e, tok].max())))
    if nb.any():
        xn = x[nb]
        p = np.exp(xn)
        ent = float(np.mean(-(p * np.where(p > 0, xn, 0.0)).sum(1)))
    else:
        ent = math.log(V)
    return {"n_keys": float(n_keys), "kps": (n_keys / (frame_s * T) if T else 0.0),
            "nb_share": float(nb.mean()) if T else 0.0, "peak": float(np.mean(peaks)) if peaks else 0.0,
            "neg_entropy": -ent, "log_n_keys": math.log1p(n_keys)}


@dataclass(frozen=True)
class ScoreGate:
    """Pass iff ``n_keys >= k_min``, ``kps <= r_max`` and ``lo <= score <= hi`` (P14-49).

    ``feature``: one of :data:`SCORE_FEATURES`. ``lm_ratio`` = the number of tokens of the ungated LM top-1
    divided by ``max(1, n_keys)`` (it needs the LM search: :attr:`needs_lm`). ``logit`` = a logistic score
    ``intercept + coef . (z - mean) / scale`` over :data:`LOGIT_INPUTS`.
    """

    feature: str
    lo: float
    hi: float
    k_min: int
    r_max: float
    frame_s: float
    blank: int = 0
    mean: tuple[float, ...] = ()
    scale: tuple[float, ...] = ()
    coef: tuple[float, ...] = ()
    intercept: float = 0.0

    @property
    def needs_lm(self) -> bool:
        return self.feature == "lm_ratio"

    def score(self, lp: np.ndarray, lm_tokens: int | None = None) -> float:
        f = posterior_features(lp, self.frame_s, self.blank)
        if self.feature == "lm_ratio":
            if lm_tokens is None:
                raise ValueError("the lm_ratio gate needs the token count of the LM top-1 (lm_tokens=)")
            return float(lm_tokens) / max(1.0, f["n_keys"])
        if self.feature == "logit":
            z = np.array([f[k] for k in LOGIT_INPUTS])
            return float(self.intercept + np.dot(self.coef, (z - np.array(self.mean)) / np.array(self.scale)))
        return float(f[self.feature])

    def passes(self, lp: np.ndarray, lm_tokens: int | None = None) -> bool:
        n, r = gate_features(lp, self.frame_s, self.blank)
        if n < self.k_min or r > self.r_max:
            return False
        s = self.score(lp, lm_tokens)
        return bool(self.lo <= s <= self.hi)

    def with_lo(self, lo: float) -> "ScoreGate":
        """The same gate with another lower bound (for example from :func:`quantile_lo`, P14-58)."""
        from dataclasses import replace

        if not math.isfinite(float(lo)):
            raise ValueError("lo must be finite")
        return replace(self, lo=float(lo))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": "score", "feature": self.feature, "lo": float(self.lo),
                             "hi": (float(self.hi) if math.isfinite(self.hi) else None), "k_min": int(self.k_min),
                             "r_max": float(self.r_max), "frame_s": float(self.frame_s), "blank": int(self.blank)}
        if self.feature == "logit":
            d.update(inputs=list(LOGIT_INPUTS), mean=[float(v) for v in self.mean],
                     scale=[float(v) for v in self.scale], coef=[float(v) for v in self.coef],
                     intercept=float(self.intercept))
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ScoreGate":
        if d.get("feature") not in SCORE_FEATURES:
            raise ValueError(f"unknown gate feature {d.get('feature')!r} (known: {SCORE_FEATURES})")
        if d.get("feature") == "logit" and list(d.get("inputs", LOGIT_INPUTS)) != list(LOGIT_INPUTS):
            raise ValueError(f"logit gate inputs {d.get('inputs')} differ from {LOGIT_INPUTS}")
        hi = d.get("hi")
        return cls(str(d["feature"]), float(d["lo"]), math.inf if hi is None else float(hi), int(d["k_min"]),
                   float(d["r_max"]), float(d["frame_s"]), int(d.get("blank", 0)),
                   tuple(float(v) for v in d.get("mean", ())), tuple(float(v) for v in d.get("scale", ())),
                   tuple(float(v) for v in d.get("coef", ())), float(d.get("intercept", 0.0)))

    @classmethod
    def fit(cls, feature: str, real: Sequence[np.ndarray], frame_s: float, blank: int = 0,
            null: Sequence[np.ndarray] = (), real_lm_tokens: Sequence[int] | None = None, tail: float = 0.01,
            r_max_factor: float = 2.0, ridge: float = 1.0) -> "ScoreGate":
        """The P14-49 fit rule (real calibration inputs; ``null`` only for ``logit``).

        With ``m = floor(tail * n)``: ``k_min`` = 1; ``r_max`` = ``r_max_factor`` x the largest real ``kps``;
        ``lo`` = the (m + 1)-th smallest real score; ``hi`` = the (m + 1)-th largest real score for
        ``lm_ratio`` (a two-sided band), else no upper bound. ``logit``: an L2 logistic regression
        (``ridge`` on the coefficients, Newton steps) of real (1) against ``null`` (0) on the standardised
        :data:`LOGIT_INPUTS`, fitted before ``lo`` is set.
        """
        if feature not in SCORE_FEATURES:
            raise ValueError(f"unknown gate feature {feature!r}")
        if not real:
            raise ValueError("the gate needs at least one real fit input")
        fr = [posterior_features(x, frame_s, blank) for x in real]
        m = int(math.floor(tail * len(fr) + 1e-9))
        r_max = float(r_max_factor * max(f["kps"] for f in fr))
        mean: tuple[float, ...] = ()
        scale: tuple[float, ...] = ()
        coef: tuple[float, ...] = ()
        icpt = 0.0
        if feature == "logit":
            fn = [posterior_features(x, frame_s, blank) for x in null]
            if not fn:
                raise ValueError("the logit gate needs null fit inputs")
            Z = np.array([[f[k] for k in LOGIT_INPUTS] for f in fr + fn])
            y = np.concatenate([np.ones(len(fr)), np.zeros(len(fn))])
            mu, sd = Z.mean(0), Z.std(0)
            sd = np.where(sd > 1e-12, sd, 1.0)
            X = np.column_stack([np.ones(len(Z)), (Z - mu) / sd])
            w = np.zeros(X.shape[1])
            pen = np.full(X.shape[1], float(ridge))
            pen[0] = 0.0
            for _ in range(100):
                p = 1.0 / (1.0 + np.exp(-(X @ w)))
                g = X.T @ (p - y) + pen * w
                H = (X * (p * (1 - p))[:, None]).T @ X + np.diag(pen) + 1e-9 * np.eye(len(w))
                step = np.linalg.solve(H, g)
                w = w - step
                if float(np.abs(step).max()) < 1e-10:
                    break
            mean, scale, coef, icpt = tuple(mu.tolist()), tuple(sd.tolist()), tuple(w[1:].tolist()), float(w[0])
        g0 = cls(feature, -math.inf, math.inf, 1, r_max, float(frame_s), int(blank), mean, scale, coef, icpt)
        toks = list(real_lm_tokens) if real_lm_tokens is not None else [None] * len(real)
        sc = sorted(g0.score(x, t) for x, t in zip(real, toks))
        hi = sc[-1 - m] if feature == "lm_ratio" else math.inf
        return cls(feature, float(sc[m]), float(hi), 1, r_max, float(frame_s), int(blank), mean, scale, coef, icpt)


def hd_quantile(values: Sequence[float], q: float) -> float:
    """The Harrell-Davis estimate of the ``q`` quantile (P14-58): a weighted mean of all order statistics,
    with the weights of a Beta((n + 1) q, (n + 1)(1 - q)) distribution. Unlike one order statistic (for
    example the minimum), it moves little when one value changes."""
    from scipy.stats import beta

    x = np.sort(np.asarray([float(v) for v in values], np.float64))
    n = len(x)
    if n == 0:
        raise ValueError("hd_quantile needs at least one value")
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")
    if n == 1:
        return float(x[0])
    cdf = beta.cdf(np.arange(n + 1) / n, (n + 1) * q, (n + 1) * (1.0 - q))
    return float(np.dot(np.diff(cdf), x))


def quantile_lo(real_scores: Sequence[float], null_scores: Sequence[float] = (), q: float = 0.03,
                null_q: float = 0.99) -> tuple[float, dict[str, float]]:
    """The P14-58 threshold rule for the lower bound ``lo`` of a :class:`ScoreGate`.

    ``lo = max(hd_quantile(real_scores, q), the empirical null_q quantile of null_scores)`` (the null part
    only when ``null_scores`` is not empty; ``numpy.quantile``, linear). Returns ``(lo, parts)``.
    """
    lo_real = hd_quantile(real_scores, q)
    parts = {"lo_real_hd": lo_real}
    lo = lo_real
    if len(null_scores):
        lo_null = float(np.quantile(np.asarray([float(v) for v in null_scores], np.float64), null_q))
        parts["lo_null"] = lo_null
        lo = max(lo, lo_null)
    return float(lo), parts


def gate_from_dict(d: Mapping[str, Any]) -> "NoSignalGate | ScoreGate":
    """A gate of a manifest block: ``kind: "score"`` -> :class:`ScoreGate`; no kind or ``"count"`` -> :class:`NoSignalGate`."""
    kind = d.get("kind", "count")
    if kind == "score":
        return ScoreGate.from_dict(d)
    if kind == "count":
        return NoSignalGate.from_dict(d)
    raise ValueError(f"unknown gate kind {kind!r}")


class LmReadout:
    """Gated LM readout: the gate, then :class:`LMBeam` on the same log-probs.

    ``vocab``: the token of each column. ``lm``: a :class:`fidetype.lm.ngram.CharNgramLM` (or ``None``).
    ``settings``: ``lm_weight``, ``bonus``, ``beam``, ``prune_logp`` (optional ``n_best``; no lexicon).
    ``gate``: a :class:`NoSignalGate` or a :class:`ScoreGate`, or ``None`` for no gate. A gate with
    ``needs_lm`` (``lm_ratio``) reads the ungated search first.
    """

    def __init__(self, vocab: Sequence[str], lm: Any, settings: Mapping[str, Any], gate: NoSignalGate | None,
                 blank: int = 0) -> None:
        self.vocab = list(vocab)
        self.lm = lm
        self.settings = dict(settings)
        self.gate = gate
        self.blank = int(blank)

    def _beam(self) -> LMBeam:
        s = self.settings
        return LMBeam(self.vocab, self.blank, lm=self.lm, lm_weight=float(s.get("lm_weight", 0.0)),
                      bonus=float(s.get("bonus", 0.0)), beam=int(s.get("beam", 8)),
                      prune_logp=float(s.get("prune_logp", -8.0)), lexicon=None, lam=0.0)

    def _needs_lm(self) -> bool:
        return bool(getattr(self.gate, "needs_lm", False))

    def _search(self, lp: np.ndarray, n: int | None) -> list[Hyp]:
        d = self._beam()
        d.push(lp)
        return d.nbest(n)

    def gated(self, log_probs: np.ndarray) -> bool:
        """True when the gate stops this input (no text)."""
        if self.gate is None:
            return False
        lp = np.asarray(log_probs, np.float64)
        if self._needs_lm():
            hs = self._search(lp, 1)
            return not self.gate.passes(lp, lm_tokens=len(hs[0].tokens) if hs else 0)
        return not self.gate.passes(lp)

    def hyps(self, log_probs: np.ndarray, n: int | None = None, use_gate: bool = True) -> list[Hyp]:
        lp = np.asarray(log_probs, np.float64)
        if use_gate and self.gate is not None and self._needs_lm():
            hs = self._search(lp, n)
            top = len(hs[0].tokens) if hs else 0
            return hs if self.gate.passes(lp, lm_tokens=top) else []
        if use_gate and self.gated(lp):
            return []
        return self._search(lp, n)

    def tokens_text(self, tokens: Sequence[int]) -> str:
        return "".join(self.vocab[t] for t in tokens)

    def text(self, log_probs: np.ndarray, use_gate: bool = True) -> str:
        """The top-1 text; the empty text when the gate stops the input."""
        hs = self.hyps(log_probs, 1, use_gate)
        return self.tokens_text(hs[0].tokens) if hs else ""

    def nbest(self, log_probs: np.ndarray, n: int | None = None, use_gate: bool = True) -> list[dict[str, Any]]:
        """The n-best list as dicts (``text``, ``score``, ``logp_acoustic``, ``logp_lm``), best first."""
        n = int(self.settings.get("n_best", self.settings.get("beam", 8))) if n is None else n
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for h in self.hyps(log_probs, n, use_gate):
            t = self.tokens_text(h.tokens)
            if t in seen:
                continue
            seen.add(t)
            d: dict[str, Any] = {"text": t, "score": float(h.score)}
            for k, v in (("logp_acoustic", h.logp_acoustic), ("logp_lm", h.logp_lm)):
                if math.isfinite(v) and v <= 0:
                    d[k] = float(v)
            out.append(d)
        return out

    def decode_fn(self) -> Callable[[np.ndarray], list[dict[str, Any]]]:
        """The user decoder for :func:`fidetype.trust.calibrate` and :func:`fidetype.trust.load`."""

        def gated_lm_readout(log_probs: np.ndarray) -> list[dict[str, Any]]:
            return self.nbest(log_probs)

        return gated_lm_readout


def readout_for(model: Any, gate: Any = None) -> LmReadout:
    """The packaged LM readout of a pretrained character model (manifest block ``readouts.lm``).

    ``gate``: ``None`` = the gate of the manifest; a :class:`NoSignalGate` or :class:`ScoreGate` = this gate; ``False`` = no
    gate (research use only: the raw LM readout emits text on flat input). The LM file has the manifest
    role ``text`` and loads from the model folder or ``<cache>/text/`` (local, SHA-256 checked).
    """
    from fidetype.lm.ngram import CharNgramLM
    from fidetype.pretrained import PretrainedError, resolve_files

    cfg = (model.manifest.raw.get("readouts") or {}).get("lm")
    if not cfg:
        raise PretrainedError(f"{model.name}: no LM readout in the manifest (readouts.lm)")
    if cfg.get("decode") != READOUT_ID:
        raise PretrainedError(f"{model.name}: LM readout {cfg.get('decode')!r} is not packaged (known: {READOUT_ID})")
    files = resolve_files(model.manifest, weights=model._weights_arg, cache_dir=model._cache_dir, roles=("text",),
                          accept_research_only=True)
    by_name = {p.name: p for p in files.values()}
    lm = CharNgramLM.load(by_name[cfg["lm_file"]])
    if gate is None:
        if not cfg.get("gate"):
            raise PretrainedError(f"{model.name}: the no-signal gate of the LM readout is not fitted yet")
        gate = gate_from_dict(cfg["gate"])
    elif gate is False:
        gate = None
    from fidetype.pretrained import _xbody

    return LmReadout(list(_xbody.VOCAB), lm, cfg["settings"], gate, blank=0)
