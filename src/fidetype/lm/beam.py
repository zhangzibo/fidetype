"""CTC prefix beam search with shallow LM fusion and n-best output.

The search follows the CTC prefix beam search of Graves (2012) and
Hannun et al. (2014). Each prefix keeps two acoustic log-probabilities:

- ``pb``: the sum over all paths that give the prefix and end in blank,
- ``pnb``: the sum over all paths that give the prefix and end in its
  last character.

Their log-sum is the CTC prefix probability (``logp_acoustic``). A
repeated character needs a blank between the two copies ("aa" needs
"a, blank, a"). Without the blank, the frames collapse to one "a".

Shallow fusion
--------------
When a prefix gets a new character ``c``, the search adds
``log p_LM(c | prefix)`` to the LM score of the new prefix. At the end,
it adds ``log p_LM(</s> | text)``. The LM score depends only on the
text, so the search keeps it apart from the acoustic score. The rank
score is::

    score = logp_acoustic + lm_weight * logp_lm + insertion_bonus * len(text)

Pruning
-------
At each frame the search tries only the characters with
``log p >= prune_logp``, and at most ``prune_topk`` of them (the most
probable first). The blank and the repeat of the last character are
always tried. Then it keeps the ``beam`` best prefixes.

The search is deterministic: ties keep a fixed order.

Character confidences
---------------------
Each :class:`Hypothesis` has three per-character confidence variants:

- ``"nbest"``: an n-best marginal. The search
  turns the scores of all prefixes in the final beam into posteriors
  (softmax of ``score / confidence_temperature``). Each final prefix is
  aligned to the hypothesis (Levenshtein alignment). The confidence of
  character i is the posterior mass of the prefixes that have the same
  character at the aligned position. It includes the LM, so it can
  rise for a character that the LM supports.
- ``"frame"`` (also in ``char_frame_posteriors``): the acoustic view. A CTC Viterbi forced
  alignment of the text gives the frames of each character
  (``frame_spans``). The value is the maximum frame posterior
  ``p(c | frame)`` over those frames.

- ``"fused"``: a local fused posterior. At the frame where the character
  has its maximum posterior (from the forced alignment), the search
  combines the acoustic log-probability of each non-blank token with
  ``lm_weight`` times its LM log-probability in the hypothesis context,
  and normalises over the 27 characters. The value is the share of the
  chosen character. It sees both the acoustics and the LM, and it does
  not depend on how many alternatives survived in the beam.

The ``confidence`` argument selects the variant that goes into
``char_confidences``. All variants are in ``confidence_variants``. See
``experiments/2026-11-08-lm-beam/results.md`` for their calibration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID, VOCAB

if TYPE_CHECKING:  # pragma: no cover
    from fidetype.lm.ngram import CharNgramLM

NEG_INF = -math.inf


@dataclass
class Hypothesis:
    """One decoded text with its scores and per-character data."""

    #: The decoded text.
    text: str
    #: CTC prefix log-probability (log-sum over blank/non-blank paths).
    logp_acoustic: float
    #: LM log-probability of the text, with the end marker (0.0 if no LM).
    logp_lm: float
    #: ``logp_acoustic + lm_weight * logp_lm + insertion_bonus * len(text)``.
    score: float
    #: n-best marginal confidence of each character, shape (len(text),).
    char_confidences: np.ndarray = field(default_factory=lambda: np.zeros(0))
    #: (first frame, last frame) of each character, inclusive, from a CTC
    #: Viterbi forced alignment. Empty if the alignment was not run.
    frame_spans: list[tuple[int, int]] = field(default_factory=list)
    #: Max frame posterior of each character over its span (NaN if no span).
    char_frame_posteriors: np.ndarray = field(default_factory=lambda: np.zeros(0))
    #: Token ids of the text.
    ids: tuple[int, ...] = ()
    #: All confidence variants: ``"fused"``, ``"nbest"``, ``"frame"``.
    confidence_variants: dict[str, np.ndarray] = field(default_factory=dict)


def _lse(a: float, b: float) -> float:
    """Return log(exp(a) + exp(b)), safe for -inf."""
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    if a > b:
        return a + math.log1p(math.exp(b - a))
    return b + math.log1p(math.exp(a - b))


def _unpack(stream_or_logprobs, blank_id):
    if isinstance(stream_or_logprobs, NeuralTextStream):
        s = stream_or_logprobs
        return s.log_probs, list(s.vocab), s.blank_id if blank_id is None else blank_id
    lp = np.asarray(stream_or_logprobs)
    if lp.ndim != 2:
        raise ValueError(f"log_probs must be 2-D (T, V), got shape {lp.shape}")
    vocab = list(VOCAB) if lp.shape[1] == len(VOCAB) else [str(i) for i in range(lp.shape[1])]
    return lp, vocab, BLANK_ID if blank_id is None else blank_id


def ctc_prefix_beam_search(
    stream_or_logprobs: NeuralTextStream | np.ndarray,
    lm: "CharNgramLM | None" = None,
    lm_weight: float = 1.0,
    insertion_bonus: float | None = None,
    beam: int = 16,
    n_best: int = 10,
    prune_logp: float = -6.0,
    prune_topk: int | None = 10,
    blank_id: int | None = None,
    align: bool = True,
    confidence_temperature: float = 1.0,
    confidence: str = "fused",
) -> list[Hypothesis]:
    """Decode a CTC stream. Return up to ``n_best`` hypotheses, best first.

    ``stream_or_logprobs`` is a :class:`NeuralTextStream` or a (T, V)
    array of natural-log probabilities. With an LM, the vocabulary must
    be :data:`fidetype.streams.vocab.VOCAB`. ``lm_weight`` and
    ``insertion_bonus`` are used only in the rank score (see the module
    docstring). ``insertion_bonus=None`` means 2.0 with an LM and 0.0
    without one. The defaults (``lm_weight=1.0``, bonus 2.0, beam 16)
    were tuned on simulator streams with the 6-gram Tatoeba LM
    (``experiments/2026-11-08-lm-beam``). Re-tune them for a real
    decoder: an over-confident decoder needs a larger ``lm_weight``. With ``align=False`` the search skips the forced
    alignment: ``frame_spans`` is empty and ``char_frame_posteriors`` is
    NaN, and the ``"fused"`` variant falls back to ``"nbest"``.

    ``confidence`` selects the variant in ``char_confidences``:
    ``"fused"`` (default), ``"nbest"`` or ``"frame"``.
    ``confidence_temperature`` is the softmax temperature of the n-best
    posteriors that the ``"nbest"`` variant uses.
    """
    if confidence not in ("fused", "nbest", "frame"):
        raise ValueError("confidence must be 'fused', 'nbest' or 'frame'")
    lp_arr, vocab, blank = _unpack(stream_or_logprobs, blank_id)
    if beam < 1 or n_best < 1:
        raise ValueError("beam and n_best must be at least 1")
    if confidence_temperature <= 0:
        raise ValueError("confidence_temperature must be positive")
    if lm is not None and tuple(vocab) != VOCAB:
        raise ValueError("an LM needs the default VOCAB (blank, a-z, space)")
    lp64 = np.asarray(lp_arr, dtype=np.float64)
    T, V = lp64.shape
    w = float(lm_weight) if lm is not None else 0.0
    if insertion_bonus is None:
        insertion_bonus = 2.0 if lm is not None else 0.0
    bonus = float(insertion_bonus)

    # Candidate characters per frame (most probable first).
    k = V if prune_topk is None else max(1, min(int(prune_topk), V))
    order = np.argsort(-lp64, axis=1, kind="stable")[:, :k]
    rows = lp64.tolist()
    cands: list[list[tuple[int, float]]] = []
    for t in range(T):
        row = rows[t]
        cands.append([(c, row[c]) for c in order[t].tolist() if c != blank and row[c] >= prune_logp])

    # Prefix state: text -> [pb, pnb]. Side tables: LM score, last id.
    beams: dict[str, list[float]] = {"": [0.0, NEG_INF]}
    lm_score: dict[str, float] = {"": 0.0}
    last_id: dict[str, int] = {}
    lm_rows: dict[str, list[float]] = {}

    def lm_row(prefix: str) -> list[float]:
        r = lm_rows.get(prefix)
        if r is None:
            r = lm.logprobs_vocab(prefix).tolist()  # type: ignore[union-attr]
            lm_rows[prefix] = r
        return r

    for t in range(T):
        row = rows[t]
        lb = row[blank]
        ct = cands[t]
        nxt: dict[str, list[float]] = {}
        for prefix, (pb, pnb) in beams.items():
            ptot = _lse(pb, pnb)
            e = nxt.get(prefix)
            if e is None:
                e = nxt[prefix] = [NEG_INF, NEG_INF]
            e[0] = _lse(e[0], ptot + lb)
            last = last_id.get(prefix, -1)
            if last >= 0:
                e[1] = _lse(e[1], pnb + row[last])
            if not ct:
                continue
            lmr = lm_row(prefix) if lm is not None else None
            for c, lpc in ct:
                new = prefix + vocab[c]
                add = (pb if c == last else ptot) + lpc
                if add == NEG_INF:
                    continue
                en = nxt.get(new)
                if en is None:
                    en = nxt[new] = [NEG_INF, NEG_INF]
                    if new not in lm_score:
                        lm_score[new] = lm_score[prefix] + (lmr[c] if lmr is not None else 0.0)
                        last_id[new] = c
                en[1] = _lse(en[1], add)
        if len(nxt) > beam:
            scored = sorted(
                nxt.items(),
                key=lambda kv: -(_lse(kv[1][0], kv[1][1]) + w * lm_score[kv[0]] + bonus * len(kv[0])),
            )
            beams = dict(scored[:beam])
        else:
            beams = nxt

    # Final scores, with the end-of-sentence LM term.
    final: list[tuple[float, str, float, float]] = []
    for prefix, (pb, pnb) in beams.items():
        ac = _lse(pb, pnb)
        lmt = lm_score[prefix] + (lm_row(prefix)[0] if lm is not None else 0.0)
        final.append((ac + w * lmt + bonus * len(prefix), prefix, ac, lmt))
    final.sort(key=lambda x: (-x[0], x[1]))
    texts = [f[1] for f in final]
    post = n_best_to_posteriors_scores([f[0] for f in final], confidence_temperature)

    char_id = {ch: i for i, ch in enumerate(vocab)}
    out: list[Hypothesis] = []
    for score, text, ac, lmt in final[:n_best]:
        ids = tuple(char_id[ch] for ch in text) if all(len(v) == 1 for v in vocab[1:]) else ()
        conf = _nbest_marginal(text, texts, post)
        spans: list[tuple[int, int]] = []
        fpost = np.full(len(text), np.nan)
        fused = conf
        if align and ids:
            got = ctc_forced_align(lp64, ids, blank)
            if got is not None:
                spans = got
                peak = [max(range(s, e + 1), key=lambda t, i=i: (rows[t][i], -t)) for (s, e), i in zip(spans, ids)]
                fpost = np.array([math.exp(rows[t][i]) for t, i in zip(peak, ids)])
                fused = _fused(rows, peak, ids, text, lm if w else None, w, blank)
        variants = {"nbest": conf, "frame": fpost, "fused": fused}
        out.append(
            Hypothesis(
                text=text,
                logp_acoustic=float(ac),
                logp_lm=float(lmt) if lm is not None else 0.0,
                score=float(score),
                char_confidences=variants[confidence],
                frame_spans=spans,
                char_frame_posteriors=fpost,
                ids=ids,
                confidence_variants=variants,
            )
        )
    return out


def n_best_to_posteriors_scores(scores, temperature: float = 1.0) -> np.ndarray:
    """Return ``softmax(scores / temperature)`` as a float64 array."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    s = np.asarray(scores, dtype=np.float64) / temperature
    if s.size == 0:
        return s
    s = s - np.max(s)
    p = np.exp(s)
    return p / p.sum()


def n_best_to_posteriors(hyps: list[Hypothesis], temperature: float = 1.0) -> np.ndarray:
    """Return a posterior over the hypotheses: softmax of score / temperature.

    The values sum to 1. A higher ``temperature`` gives a flatter
    distribution. The list covers only these hypotheses, so the values
    are relative to the n-best list, not to all texts.
    """
    return n_best_to_posteriors_scores([h.score for h in hyps], temperature)


def align_pairs(a: str, b: str) -> list[tuple[int | None, int | None]]:
    """Return a minimum-cost Levenshtein alignment of ``a`` and ``b``.

    Each pair is ``(i, j)``: a match or substitution of ``a[i]`` and
    ``b[j]``; ``(i, None)``: ``a[i]`` is deleted; ``(None, j)``: ``b[j]``
    is inserted. The common prefix and suffix are matched first (this
    keeps the cost minimal and the function fast). Ties are broken in a
    fixed order (match/substitution, then deletion, then insertion).
    """
    n, m = len(a), len(b)
    p = 0
    while p < n and p < m and a[p] == b[p]:
        p += 1
    s = 0
    while s < n - p and s < m - p and a[n - 1 - s] == b[m - 1 - s]:
        s += 1
    pairs: list[tuple[int | None, int | None]] = [(i, i) for i in range(p)]
    am, bm = a[p : n - s], b[p : m - s]
    na, nb = len(am), len(bm)
    if na or nb:
        d = [[0] * (nb + 1) for _ in range(na + 1)]
        for i in range(na + 1):
            d[i][0] = i
        for j in range(nb + 1):
            d[0][j] = j
        for i in range(1, na + 1):
            di, dp = d[i], d[i - 1]
            ai = am[i - 1]
            for j in range(1, nb + 1):
                di[j] = min(dp[j - 1] + (ai != bm[j - 1]), dp[j] + 1, di[j - 1] + 1)
        i, j = na, nb
        mid: list[tuple[int | None, int | None]] = []
        while i > 0 or j > 0:
            if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (am[i - 1] != bm[j - 1]):
                mid.append((p + i - 1, p + j - 1))
                i, j = i - 1, j - 1
            elif i > 0 and d[i][j] == d[i - 1][j] + 1:
                mid.append((p + i - 1, None))
                i -= 1
            else:
                mid.append((None, p + j - 1))
                j -= 1
        pairs.extend(reversed(mid))
    pairs.extend((n - s + q, m - s + q) for q in range(s))
    return pairs


def _nbest_marginal(text: str, texts: list[str], post: np.ndarray) -> np.ndarray:
    conf = np.zeros(len(text))
    for other, wgt in zip(texts, post.tolist()):
        if other == text:
            conf += wgt
            continue
        for i, j in align_pairs(text, other):
            if i is not None and j is not None and text[i] == other[j]:
                conf[i] += wgt
    return np.clip(conf, 0.0, 1.0)


def _fused(rows, peak, ids, text, lm, w, blank) -> np.ndarray:
    """Local fused posterior of each character (see the module docstring)."""
    V = len(rows[0])
    nb = [c for c in range(V) if c != blank]
    out = np.empty(len(ids))
    for j, (t, i) in enumerate(zip(peak, ids)):
        ac = np.array([rows[t][c] for c in nb])
        if lm is not None:
            ac = ac + w * lm.logprobs_vocab(text[:j])[nb]
        ac -= ac.max()
        p = np.exp(ac)
        out[j] = p[nb.index(i)] / p.sum()
    return out


def ctc_forced_align(log_probs: np.ndarray, ids, blank: int = BLANK_ID) -> list[tuple[int, int]] | None:
    """Return the (first, last) frame of each label on the CTC Viterbi path.

    ``ids`` are the label ids (no blanks). The spans are inclusive. The
    result is ``None`` if the stream is too short for the labels.
    """
    lp = np.asarray(log_probs, dtype=np.float64)
    T = lp.shape[0]
    L = len(ids)
    if L == 0:
        return []
    ext = np.full(2 * L + 1, blank, dtype=np.int64)
    ext[1::2] = ids
    S = ext.shape[0]
    # A skip from s-2 to s is allowed for a label that differs from the
    # label two states back.
    skip = np.zeros(S, dtype=bool)
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    emit = lp[:, ext]  # (T, S)
    delta = np.full(S, NEG_INF)
    delta[0] = emit[0, 0]
    if S > 1:
        delta[1] = emit[0, 1]
    bp = np.zeros((T, S), dtype=np.int8)
    for t in range(1, T):
        c0 = delta
        c1 = np.concatenate(([NEG_INF], delta[:-1]))
        c2 = np.concatenate(([NEG_INF, NEG_INF], delta[:-2]))
        c2 = np.where(skip, c2, NEG_INF)
        stack = np.stack([c0, c1, c2])
        arg = np.argmax(stack, axis=0)
        bp[t] = arg
        delta = stack[arg, np.arange(S)] + emit[t]
    ends = [S - 1, S - 2] if S > 1 else [S - 1]
    s = max(ends, key=lambda q: (delta[q], -q))
    if delta[s] == NEG_INF:
        return None
    states = np.empty(T, dtype=np.int64)
    for t in range(T - 1, -1, -1):
        states[t] = s
        s -= int(bp[t, s])
    spans: list[tuple[int, int]] = []
    for j in range(L):
        fr = np.nonzero(states == 2 * j + 1)[0]
        if fr.size == 0:
            return None
        spans.append((int(fr[0]), int(fr[-1])))
    return spans
