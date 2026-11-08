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

Re-tuned search (``experiments/2026-11-08-beam-retune``)
--------------------------------------------------------
The defaults above lose the true sentence often. ``prune_topk=10`` cuts
a true character in most simulator sentences, and a beam of 16 is full
of variants of the last few characters. :data:`RETUNED` is the better
setting: ``search="vector"`` (the same search, with numpy over all
(prefix, token) pairs, so a beam of 256 is fast), no top-k cut,
``space_rules``, a larger LM weight and a smaller insertion bonus. The
old defaults stay, so old results do not change. LM-guided candidates
per prefix (``lm_candidates``), a score threshold (``beam_logp``) and a
diverse beam (``max_per_stem``) are options; they did not raise the
recall on the dev set.

:func:`word_alternatives` turns an n-best list into per-word choices.

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
from types import MappingProxyType
from typing import TYPE_CHECKING

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID, VOCAB

if TYPE_CHECKING:  # pragma: no cover
    from fidetype.lm.ngram import CharNgramLM

NEG_INF = -math.inf
#: Number of final texts that the n-best marginal confidence uses.
_MARGINAL_TEXTS = 64

#: The re-tuned search setting (experiments/2026-11-08-beam-retune):
#: no top-k cut, beam 256 with the vector search, space rules, and
#: ``lm_weight`` / ``insertion_bonus`` tuned for n-best recall on a dev
#: set (median simulator preset, 6-gram Tatoeba LM). Use
#: ``ctc_prefix_beam_search(stream, lm, **RETUNED)``. Re-tune the weight
#: and the bonus for a real decoder.
RETUNED = MappingProxyType(
    {
        "search": "vector",
        "beam": 256,
        "n_best": 20,
        "prune_topk": None,
        "prune_logp": -6.0,
        "space_rules": True,
        "lm_weight": 1.25,
        "insertion_bonus": 1.0,
    }
)


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
    *,
    lm_candidates: int = 0,
    lm_candidate_logp: float = -12.0,
    beam_logp: float | None = None,
    max_per_stem: int | None = None,
    stem_drop: int = 1,
    space_rules: bool = False,
    search: str = "loop",
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

    Keyword-only options (``experiments/2026-11-08-beam-retune``). Their
    defaults keep the old search exactly. :data:`RETUNED` holds the
    re-tuned setting (use ``**RETUNED``).

    - ``lm_candidates``: at each frame, each prefix also tries its
      ``lm_candidates`` most probable LM characters, if their frame
      log-probability is at least ``lm_candidate_logp``. This is pruning
      per prefix: a character with weak acoustic evidence survives if
      the LM expects it. It can also restore a deleted character (one
      without a peak) from the blank frames. It needs an LM.
    - ``beam_logp``: also drop the prefixes whose rank score is more than
      ``beam_logp`` below the best prefix of the frame.
    - ``max_per_stem``: keep at most this many prefixes that have the
      same text without their last ``stem_drop`` characters. This keeps
      older alternatives in the beam (a diverse beam).
    - ``space_rules``: no leading space and no double space. At the end,
      the search removes a trailing space and merges the prefixes that
      then have the same text (log-sum of the acoustic scores).
    - ``search``: ``"loop"`` (the original pure-Python loop) or
      ``"vector"`` (numpy over all (prefix, token) pairs of a frame; the
      same beam up to ties and rounding, and much faster for a large
      beam or no top-k cut).

    The ``"nbest"`` confidence uses the 64 best final texts only.
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
    if lm_candidates < 0 or stem_drop < 0 or (max_per_stem is not None and max_per_stem < 1):
        raise ValueError("lm_candidates and stem_drop must be >= 0; max_per_stem must be >= 1")
    if beam_logp is not None and beam_logp <= 0:
        raise ValueError("beam_logp must be positive")
    if search not in ("loop", "vector"):
        raise ValueError("search must be 'loop' or 'vector'")
    lp64 = np.asarray(lp_arr, dtype=np.float64)
    T, V = lp64.shape
    w = float(lm_weight) if lm is not None else 0.0
    if insertion_bonus is None:
        insertion_bonus = 2.0 if lm is not None else 0.0
    bonus = float(insertion_bonus)
    n_lmc = int(lm_candidates) if lm is not None else 0
    space_id = vocab.index(" ") if (space_rules and " " in vocab) else -1

    # Candidate characters per frame (most probable first).
    k = V if prune_topk is None else max(1, min(int(prune_topk), V))
    order = np.argsort(-lp64, axis=1, kind="stable")[:, :k]
    rows = lp64.tolist()
    cands: list[list[tuple[int, float]]] = []
    for t in range(T if search == "loop" else 0):
        row = rows[t]
        cands.append([(c, row[c]) for c in order[t].tolist() if c != blank and row[c] >= prune_logp])
    cand_sets = [{c for c, _ in ct} for ct in cands] if n_lmc else []

    # Prefix state: text -> [pb, pnb]. Side tables: LM score, last id.
    beams: dict[str, list[float]] = {"": [0.0, NEG_INF]}
    lm_score: dict[str, float] = {"": 0.0}
    last_id: dict[str, int] = {}
    lm_rows: dict[str, list[float]] = {}
    lm_tops: dict[str, list[int]] = {}

    def lm_row(prefix: str) -> list[float]:
        r = lm_rows.get(prefix)
        if r is None:
            r = lm.logprobs_vocab(prefix).tolist()  # type: ignore[union-attr]
            lm_rows[prefix] = r
        return r

    def lm_top(prefix: str) -> list[int]:
        r = lm_tops.get(prefix)
        if r is None:
            arr = lm.logprobs_vocab(prefix)  # type: ignore[union-attr]
            # Entry 0 is the end marker; entries 1.. are the characters.
            r = (np.argsort(-arr[1:], kind="stable")[:n_lmc] + 1).tolist()
            lm_tops[prefix] = r
        return r

    if search == "vector":
        beams = _vector_search(
            lp64, blank, vocab, lm, w, bonus, beam, k, prune_logp, n_lmc, lm_candidate_logp,
            beam_logp, max_per_stem, stem_drop, space_id, lm_score,
        )
    else:
        new_rules = beam_logp is not None or max_per_stem is not None
        for t in range(T):
            row = rows[t]
            lb = row[blank]
            ct = cands[t]
            cset = cand_sets[t] if n_lmc else None
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
                cl = ct
                if n_lmc:
                    extra = [(c, row[c]) for c in lm_top(prefix) if c not in cset and row[c] >= lm_candidate_logp]
                    if extra:
                        cl = ct + extra
                if not cl:
                    continue
                lmr = lm_row(prefix) if lm is not None else None
                no_space = space_id >= 0 and (not prefix or prefix[-1] == " ")
                for c, lpc in cl:
                    if no_space and c == space_id:
                        continue
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
            if not new_rules:
                # The original rule: keep the ``beam`` best prefixes.
                if len(nxt) > beam:
                    scored = sorted(
                        nxt.items(),
                        key=lambda kv: -(_lse(kv[1][0], kv[1][1]) + w * lm_score[kv[0]] + bonus * len(kv[0])),
                    )
                    beams = dict(scored[:beam])
                else:
                    beams = nxt
                continue
            sc = {p: _lse(v[0], v[1]) + w * lm_score[p] + bonus * len(p) for p, v in nxt.items()}
            ranked = sorted(nxt, key=lambda p: -sc[p])
            floor = sc[ranked[0]] - beam_logp if beam_logp is not None else NEG_INF
            kept: dict[str, list[float]] = {}
            stems: dict[str, int] = {}
            for p in ranked:
                if sc[p] < floor or len(kept) >= beam:
                    break
                if max_per_stem is not None:
                    key = p[: len(p) - stem_drop] if stem_drop else p
                    n_s = stems.get(key, 0)
                    if n_s >= max_per_stem:
                        continue
                    stems[key] = n_s + 1
                kept[p] = nxt[p]
            beams = kept

    # Final scores, with the end-of-sentence LM term.
    ends: dict[str, float] = {}
    for prefix, (pb, pnb) in beams.items():
        ac = _lse(pb, pnb)
        if space_id >= 0:
            prefix = prefix.rstrip(" ")
        ends[prefix] = _lse(ends[prefix], ac) if prefix in ends else ac
    final: list[tuple[float, str, float, float]] = []
    for prefix, ac in ends.items():
        lmt = lm_score[prefix] + (lm_row(prefix)[0] if lm is not None else 0.0)
        final.append((ac + w * lmt + bonus * len(prefix), prefix, ac, lmt))
    final.sort(key=lambda x: (-x[0], x[1]))
    texts = [f[1] for f in final]
    post = n_best_to_posteriors_scores([f[0] for f in final], confidence_temperature)
    # The n-best marginal uses the _MARGINAL_TEXTS best texts only (speed
    # for a large beam). The others have a negligible posterior.
    m_texts, m_post = texts[:_MARGINAL_TEXTS], post[:_MARGINAL_TEXTS]

    char_id = {ch: i for i, ch in enumerate(vocab)}
    out: list[Hypothesis] = []
    for score, text, ac, lmt in final[:n_best]:
        ids = tuple(char_id[ch] for ch in text) if all(len(v) == 1 for v in vocab[1:]) else ()
        conf = _nbest_marginal(text, m_texts, m_post)
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


def _vector_search(
    lp64: np.ndarray,
    blank: int,
    vocab: list[str],
    lm,
    w: float,
    bonus: float,
    beam: int,
    topk: int,
    prune_logp: float,
    n_lmc: int,
    lm_candidate_logp: float,
    beam_logp: float | None,
    max_per_stem: int | None,
    stem_drop: int,
    space_id: int,
    lm_score: dict[str, float],
) -> dict[str, list[float]]:
    """The prefix search of the loop, with numpy over (prefix, token).

    At each frame the function scores every allowed extension of every
    prefix in one (B, V) array. It makes Python objects only for the
    extensions that enter the beam. An extension that gives a prefix
    that is already in the beam is merged into that prefix, as in the
    loop. Without ``max_per_stem`` the result is the beam of the loop, up
    to ties and rounding. With ``max_per_stem`` the function looks at
    the ``4 * beam`` best new extensions only. A large beam stays fast.

    It returns the final beam (text -> [pb, pnb]) and fills ``lm_score``.
    """
    T, V = lp64.shape
    ninf = -np.inf
    # Acoustic candidates of each frame: top-k and log p >= prune_logp.
    allow_ac = lp64 >= prune_logp
    if topk < V:
        order = np.argsort(-lp64, axis=1, kind="stable")[:, :topk]
        top = np.zeros_like(allow_ac)
        np.put_along_axis(top, order, True, axis=1)
        allow_ac &= top
    allow_ac[:, blank] = False
    allow_lm = None
    if n_lmc:
        allow_lm = lp64 >= lm_candidate_logp
        allow_lm[:, blank] = False
    any_ac = allow_ac.any(axis=1)
    any_lm = allow_lm.any(axis=1) if allow_lm is not None else np.zeros(T, dtype=bool)

    zero_row = np.zeros(V)
    no_top = np.zeros(V, dtype=bool)
    lm_arr: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def lrow(text: str) -> tuple[np.ndarray, np.ndarray]:
        """LM row and LM top-``n_lmc`` mask of ``text``."""
        r = lm_arr.get(text)
        if r is None:
            if lm is None:
                r = (zero_row, no_top)
            else:
                row = np.asarray(lm.logprobs_vocab(text), dtype=np.float64)
                m = no_top
                if n_lmc:
                    m = np.zeros(V, dtype=bool)
                    m[np.argsort(-row[1:], kind="stable")[:n_lmc] + 1] = True
                    m[blank] = False
                r = (row, m)
            lm_arr[text] = r
        return r

    texts: list[str] = [""]
    pb = np.array([0.0])
    pnb = np.array([ninf])
    lms = np.array([0.0])
    ln = np.array([0], dtype=np.int64)
    last = np.array([-1], dtype=np.int64)
    r0, m0 = lrow("")
    L = r0[None, :].copy()
    LT = m0[None, :].copy()
    nosp = np.array([True])  # no space allowed next (empty or ends in space)
    cols = np.arange(V)
    n_ext = 4 * beam if max_per_stem is not None else beam

    for t in range(T):
        row = lp64[t]
        B = len(texts)
        ptot = np.logaddexp(pb, pnb)
        has_last = last >= 0
        s_pb = ptot + row[blank]
        s_pnb = np.where(has_last, pnb + row[np.maximum(last, 0)], ninf)
        if not (any_ac[t] or any_lm[t]):
            # No extension at this frame: the beam does not change.
            pb, pnb = s_pb, s_pnb
            continue
        mask = np.broadcast_to(allow_ac[t], (B, V))
        mask = mask | (LT & allow_lm[t]) if n_lmc else mask.copy()
        if space_id >= 0:
            mask[nosp, space_id] = False
        same = cols[None, :] == last[:, None]
        ext = np.where(same, pb[:, None], ptot[:, None]) + row[None, :]
        ext[~mask] = ninf
        # Extensions that give a prefix already in the beam: merge them.
        index = {x: i for i, x in enumerate(texts)}
        pidx = np.array([index.get(x[:-1], -1) if x else -1 for x in texts], dtype=np.int64)
        jm = np.nonzero(pidx >= 0)[0]
        if jm.size:
            pp, cc = pidx[jm], last[jm]
            s_pnb[jm] = np.logaddexp(s_pnb[jm], ext[pp, cc])
            ext[pp, cc] = ninf
        stay_score = np.logaddexp(s_pb, s_pnb) + w * lms + bonus * ln
        flat = (ext + w * (lms[:, None] + L) + bonus * (ln[:, None] + 1)).ravel()
        ok_e = np.nonzero(flat > ninf)[0]
        if ok_e.size > n_ext:
            sub = np.argpartition(-flat[ok_e], n_ext - 1)[:n_ext]
            ok_e = ok_e[sub]
        sel_s = np.nonzero(stay_score > ninf)[0]
        scores = np.concatenate([stay_score[sel_s], flat[ok_e]])
        kind = np.concatenate([np.zeros(sel_s.size, dtype=np.int64), np.ones(ok_e.size, dtype=np.int64)])
        idx = np.concatenate([sel_s, ok_e])
        # Rank stays and new extensions together (ties: stays first, then index).
        rank = np.lexsort((idx, kind, -scores))
        if beam_logp is not None and rank.size:
            rank = rank[scores[rank] >= scores[rank[0]] - beam_logp]
        if max_per_stem is None:
            kp = rank[:beam]
        else:
            keep: list[int] = []
            stems: dict[str, int] = {}
            for r in rank.tolist():
                if kind[r] == 0:
                    x = texts[int(idx[r])]
                else:
                    p, c = divmod(int(idx[r]), V)
                    x = texts[p] + vocab[c]
                key = x[: len(x) - stem_drop] if stem_drop else x
                n_s = stems.get(key, 0)
                if n_s >= max_per_stem:
                    continue
                stems[key] = n_s + 1
                keep.append(r)
                if len(keep) >= beam:
                    break
            kp = np.array(keep, dtype=np.int64)
        is_ext = kind[kp] == 1
        src = idx[kp]
        par = np.where(is_ext, src // V, src)
        tok = np.where(is_ext, src % V, 0)
        new_pb = np.where(is_ext, ninf, s_pb[par])
        new_pnb = np.where(is_ext, ext[par, tok], s_pnb[par])
        new_lms = np.where(is_ext, lms[par] + L[par, tok], lms[par])
        new_ln = ln[par] + is_ext
        new_last = np.where(is_ext, tok, last[par])
        new_L = L[par]
        new_LT = LT[par]
        new_nosp = nosp[par].copy()
        new_texts = [texts[p] for p in par.tolist()]
        for q in np.nonzero(is_ext)[0].tolist():
            x = new_texts[q] + vocab[int(tok[q])]
            new_texts[q] = x
            if x not in lm_score:
                lm_score[x] = float(new_lms[q])
            rr, mm = lrow(x)
            new_L[q] = rr
            new_LT[q] = mm
            new_nosp[q] = x[-1] == " "
        texts = new_texts
        pb, pnb, lms, ln, last, L, LT, nosp = new_pb, new_pnb, new_lms, new_ln, new_last, new_L, new_LT, new_nosp
    return {x: [float(a), float(b)] for x, a, b in zip(texts, pb, pnb)}


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


@dataclass
class WordSlot:
    """The alternatives for one word of the reference text."""

    #: Index of the word in ``reference.split()``.
    index: int
    #: The reference word.
    word: str
    #: (first, last + 1) character offsets of the word in the reference.
    span: tuple[int, int]
    #: (text, posterior mass), best first. A text can be "" (the word is
    #: absent in that hypothesis) or have two words (a split).
    alternatives: list[tuple[str, float]]

    @property
    def mass_of_reference(self) -> float:
        """Posterior mass of the reference word in this slot."""
        return next((m for a, m in self.alternatives if a == self.word), 0.0)


def word_alternatives(
    hyps,
    reference: str | None = None,
    temperature: float = 1.0,
    posteriors=None,
    max_alternatives: int = 5,
) -> list[WordSlot]:
    """Return the alternatives for each word of ``reference``.

    ``hyps`` is a list of objects with ``text`` and ``score`` (for
    example :class:`Hypothesis`), best first. ``reference`` defaults to
    the text of the first one. The posterior of each hypothesis is
    ``softmax(score / temperature)``, or ``posteriors`` if given (for
    example calibrated values from the trust layer).

    The function aligns the words of each hypothesis to the reference
    words (Levenshtein alignment over words). A hypothesis word that is
    aligned to reference word i is an alternative for slot i. An
    inserted word joins the slot before it (or the first slot). A
    deleted word gives the alternative "". The mass of an alternative is
    the sum of the posteriors of the hypotheses that have it. Each slot
    keeps the ``max_alternatives`` best ones (ties: alphabetical).

    Use it for an OFFER of per-word choices: a list of near-copy
    sentences becomes a short list of choices at the few words where
    the hypotheses differ.
    """
    hyps = list(hyps)
    if not hyps and reference is None:
        return []
    ref = hyps[0].text if reference is None else reference
    ref_words = ref.split()
    if posteriors is None:
        post = n_best_to_posteriors_scores([h.score for h in hyps], temperature)
    else:
        post = np.asarray(posteriors, dtype=np.float64)
        if post.shape != (len(hyps),):
            raise ValueError("posteriors must have one value per hypothesis")
    spans, pos = [], 0
    for wd in ref_words:
        s = ref.index(wd, pos)
        spans.append((s, s + len(wd)))
        pos = s + len(wd)
    mass: list[dict[str, float]] = [dict() for _ in ref_words]
    for h, p in zip(hyps, post.tolist()):
        hw = h.text.split()
        chunks: list[list[str]] = [[] for _ in ref_words]
        prev = None
        pending: list[str] = []
        for i, j in align_pairs(ref_words, hw):  # type: ignore[arg-type]
            if i is None:
                if prev is None:
                    pending.append(hw[j])  # before the first slot
                else:
                    chunks[prev].append(hw[j])
                continue
            if pending:
                chunks[i].extend(pending)
                pending = []
            if j is not None:
                chunks[i].append(hw[j])
            prev = i
        if pending and chunks:
            chunks[0].extend(pending)
        for i, ch in enumerate(chunks):
            key = " ".join(ch)
            mass[i][key] = mass[i].get(key, 0.0) + p
    out = []
    for i, wd in enumerate(ref_words):
        alts = sorted(mass[i].items(), key=lambda kv: (-kv[1], kv[0]))[:max_alternatives]
        out.append(WordSlot(i, wd, spans[i], alts))
    return out


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
