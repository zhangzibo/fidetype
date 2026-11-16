"""Run-time grounding check: does the neural evidence support a text? (P15-05, F2 / E3)

A language model (an n-gram LM or a large LM) can propose text that the
neural signal does not support. This module scores a candidate text by its
**CTC log-likelihood under the decoder's own log-probabilities** and
compares it with an anchor text (normally the decoder's top-1 for the same
input):

    deficit(c) = (log p_ctc(anchor | x) - log p_ctc(c | x)) / T

``T`` is the number of frames, so the deficit is in nats per frame and does
not grow with the utterance length. A text passes the check if its deficit
is at most ``tau``. A text that cannot be written in the label space (for
example a word with no pronunciation) gets an infinite deficit and fails.

``log p_ctc`` is the full CTC forward score (sum over all alignments), not
the Viterbi path. The label sequences come from a ``label_fn``: text ->
list of alternative label-id sequences (for example the CMUdict
pronunciations of each word, joined by the word-separator label). The score
of a text is the maximum over its alternatives.

:func:`fit_tau` sets ``tau`` from the deficits of the **true** texts on
calibration data (a split-conformal quantile): with exchangeable data, a
true text passes with probability at least ``coverage``. It is a coverage
statement about true texts, not a bound on hallucinated commits; that bound
is the job of the trust gate (P15-06).

The module does not import a language model or a decoder. It works on
plain n-best lists of dicts (``{"text", "score", ...}``) as used by
:func:`fidetype.trust.calibrate` (``decode_fn``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

NEG_INF = -np.inf

LabelFn = Callable[[str], "list[list[int]] | None"]


def log_softmax_rows(x: np.ndarray) -> np.ndarray:
    """Row-wise log-softmax (float64). Log-probabilities stay unchanged."""
    a = np.asarray(x, dtype=np.float64)
    m = a.max(axis=1, keepdims=True)
    return a - (m + np.log(np.exp(a - m).sum(axis=1, keepdims=True)))


def ctc_log_likelihood_many(log_probs: np.ndarray, label_seqs: Sequence[Sequence[int]],
                            blank: int = 0) -> np.ndarray:
    """CTC forward log-likelihood ``log p(labels | x)`` of each label sequence.

    All sequences run in one pass: their extended state lists (blank,
    label, blank, ...) sit side by side, and each frame updates all states
    at once. ``log_probs`` is ``(T, V)`` and must be log-probabilities. A
    sequence that needs more frames than ``T`` gets ``-inf``. An empty
    sequence gets the all-blank score.
    """
    lp = np.asarray(log_probs, dtype=np.float64)
    T = lp.shape[0]
    n = len(label_seqs)
    out = np.full(n, NEG_INF)
    if n == 0 or T == 0:
        return out
    exts, offs = [], []
    off = 0
    for ids in label_seqs:
        L = len(ids)
        ext = np.full(2 * L + 1, blank, dtype=np.int64)
        if L:
            ext[1::2] = np.asarray(ids, dtype=np.int64)
        exts.append(ext)
        offs.append(off)
        off += ext.shape[0]
    ext_all = np.concatenate(exts)
    S = ext_all.shape[0]
    offs_a = np.asarray(offs, dtype=np.int64)
    start = np.zeros(S, dtype=bool)
    start[offs_a] = True
    skip = np.zeros(S, dtype=bool)
    for o, ext in zip(offs, exts):
        Sk = ext.shape[0]
        if Sk > 3:
            skip[o + 3: o + Sk: 2] = ext[3::2] != ext[1:-2:2]
    emit = lp[:, ext_all]
    alpha = np.full(S, NEG_INF)
    alpha[offs_a] = emit[0, offs_a]
    has_label = np.array([e.shape[0] > 1 for e in exts])
    alpha[offs_a[has_label] + 1] = emit[0, offs_a[has_label] + 1]
    head1 = np.array([NEG_INF])
    head2 = np.array([NEG_INF, NEG_INF])
    for t in range(1, T):
        a1 = np.concatenate((head1, alpha[:-1]))
        a1[start] = NEG_INF
        a2 = np.concatenate((head2, alpha[:-2]))
        a2 = np.where(skip, a2, NEG_INF)
        alpha = np.logaddexp(np.logaddexp(alpha, a1), a2) + emit[t]
    for k, (o, ext) in enumerate(zip(offs, exts)):
        Sk = ext.shape[0]
        last = alpha[o + Sk - 1]
        out[k] = np.logaddexp(last, alpha[o + Sk - 2]) if Sk > 1 else last
    return out


def lexicon_label_fn(prons: Mapping[str, Sequence[str]], symbol_ids: Mapping[str, int], *,
                     word_sep: str | None = " ", max_variants: int = 16,
                     normalize: Callable[[str], str] | None = None) -> LabelFn:
    """Build a ``label_fn`` from a pronunciation lexicon.

    ``prons`` maps a word to its pronunciations; each pronunciation is a
    string of one-character symbols (as :class:`fidetype.lm.phoneme_words.PronLexicon`
    stores them). ``symbol_ids`` maps a symbol to its column in the
    log-probabilities. Words are joined by the ``word_sep`` symbol (None:
    no separator). Alternatives: the product of the word pronunciations,
    in lexicon order, cut at ``max_variants`` (the first pronunciation of
    each word is always in the first alternative). Returns None if a word
    has no pronunciation or a symbol has no column.
    """
    sep = None if word_sep is None else symbol_ids.get(word_sep)
    if word_sep is not None and sep is None:
        raise ValueError(f"word separator {word_sep!r} has no column")

    def fn(text: str) -> list[list[int]] | None:
        t = normalize(text) if normalize else " ".join(text.split())
        words = t.split()
        if not words:
            return [[]]
        per_word: list[list[list[int]]] = []
        for w in words:
            ps = prons.get(w)
            if not ps:
                return None
            alts = []
            for p in ps:
                ids = [symbol_ids.get(c) for c in p]
                if any(i is None for i in ids):
                    continue
                alts.append([int(i) for i in ids])
            if not alts:
                return None
            per_word.append(alts)
        seqs: list[list[int]] = [[]]
        for j, alts in enumerate(per_word):
            nxt = []
            for s in seqs:
                for a in alts:
                    nxt.append(s + ([sep] if (j and sep is not None) else []) + a)
                    if len(nxt) >= max_variants:
                        break
                if len(nxt) >= max_variants:
                    break
            seqs = nxt
        return seqs

    return fn


@dataclass
class GroundingCheck:
    """Score and gate candidate texts by their CTC evidence (see the module docstring).

    ``tau``: the largest allowed deficit (nats per frame). ``inf`` scores
    without gating. ``demote_margin``: how far below the best passing
    candidate a failing candidate is put (score units) by :meth:`apply`.
    """

    label_fn: LabelFn
    tau: float = math.inf
    blank: int = 0
    demote_margin: float = 1.0

    def __post_init__(self) -> None:
        self._cache: dict[tuple[bytes, str], float] = {}

    def log_likelihoods(self, log_probs: np.ndarray, texts: Sequence[str], *, key: bytes | None = None) -> np.ndarray:
        """``max_alt log p_ctc(text | x)`` per text (``-inf`` if the text has no label sequence).

        ``key`` (optional) names the input for a memo of the scores.
        """
        lp = log_softmax_rows(log_probs)
        out = np.full(len(texts), NEG_INF)
        todo: list[tuple[int, list[list[int]]]] = []
        for i, t in enumerate(texts):
            if key is not None and (key, t) in self._cache:
                out[i] = self._cache[(key, t)]
                continue
            seqs = self.label_fn(t)
            if seqs:
                todo.append((i, seqs))
        if todo:
            flat = [s for _, seqs in todo for s in seqs]
            ll = ctc_log_likelihood_many(lp, flat, self.blank)
            pos = 0
            for i, seqs in todo:
                out[i] = float(np.max(ll[pos: pos + len(seqs)]))
                pos += len(seqs)
                if key is not None:
                    self._cache[(key, texts[i])] = out[i]
        return out

    def deficits(self, log_probs: np.ndarray, texts: Sequence[str], anchor: str, *,
                 key: bytes | None = None) -> np.ndarray:
        """Deficit of each text against ``anchor`` in nats per frame (``inf``: no label sequence)."""
        T = max(1, int(np.asarray(log_probs).shape[0]))
        ll = self.log_likelihoods(log_probs, [anchor, *texts], key=key)
        a, rest = ll[0], ll[1:]
        d = np.full(len(texts), np.inf)
        if not np.isfinite(a):
            return d
        ok = np.isfinite(rest)
        d[ok] = (a - rest[ok]) / T
        return d

    def passes(self, deficits: np.ndarray) -> np.ndarray:
        return np.asarray(deficits) <= self.tau

    def apply(self, items: Sequence[Mapping], log_probs: np.ndarray, anchor: str, *,
              key: bytes | None = None, drop_if_none_pass: bool = True) -> tuple[list[dict], np.ndarray]:
        """Gate an n-best list of dicts. Return (new list, deficits in input order).

        A failing candidate keeps its place in the list (so the n-best
        still shows the decoder's doubt) but its score is lowered to
        ``best passing score - demote_margin * (1 + rank)``, so it can never
        be the top-1. If no candidate passes, the list is empty (the trust
        layer then withholds) when ``drop_if_none_pass``. Each output dict
        gets ``grounding_deficit`` and ``grounded`` fields.
        """
        texts = [str(it["text"]) for it in items]
        d = self.deficits(log_probs, texts, anchor, key=key)
        ok = self.passes(d)
        out = [dict(it, grounding_deficit=float(di), grounded=bool(oi)) for it, di, oi in zip(items, d, ok)]
        if not ok.any():
            return ([] if drop_if_none_pass else out), d
        best = max(float(o["score"]) for o, oi in zip(out, ok) if oi)
        r = 0
        for o, oi in zip(out, ok):
            if not oi:
                r += 1
                o["score"] = min(float(o["score"]), best - self.demote_margin * r)
        return out, d


def fit_tau(true_deficits: Iterable[float], coverage: float = 0.95) -> float:
    """Split-conformal ``tau``: the ``ceil((n + 1) * coverage)``-th smallest finite deficit.

    Non-finite values (true texts with no label sequence) count as
    failures: they stay in ``n`` and sort last. Returns ``inf`` if the
    rank is above ``n``.
    """
    d = np.sort(np.asarray([x if math.isfinite(x) else np.inf for x in true_deficits], dtype=np.float64))
    n = d.shape[0]
    if n == 0:
        return math.inf
    k = int(math.ceil((n + 1) * coverage))
    if k > n:
        return math.inf
    return float(d[k - 1])
