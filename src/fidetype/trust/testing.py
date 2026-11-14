"""Reference n-best generators for tests and experiments.

The trust core must not depend on the LM agent's code (``fidetype.lm``).
This module gives small, self-contained stand-ins. The one exception is
the small LRU memo :class:`fidetype.lm.cache.LRUCache` (M4-10; no LM
code), which bounds the :class:`RefCharLM` memo (M6-14):

- :class:`RefCharLM`: a character n-gram LM with Witten-Bell smoothing.
- :class:`ReferenceDecoder`: a segment beam search. It finds the CTC
  peaks of a stream (runs of non-blank argmax frames), takes the top-m
  tokens of each peak (plus "drop the peak"), and rescores the
  combinations with the LM. It cannot recover a deleted character (a
  character with no peak), because it inserts no text where the neural
  evidence has no peak. It is a stand-in, not a full CTC prefix beam.
- :func:`greedy_nbest`: the CTC greedy decode as a 1-best list.
- :func:`synthetic_nbest`: n-best lists from the true text plus
  controlled noise, with an option where the LM pushes a wrong sentence.
- :func:`drifting_posteriors`: a synthetic stream of n-best posteriors
  whose over-confidence grows with time (for adaptive conformal tests).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import KEY_POS, LETTERS, key_distance
from fidetype.trust._align import hyp_correct_mask
from fidetype.trust._ctc import find_segments
from fidetype.trust.calibration import softmax
from fidetype.trust.types import Candidate, NBest

_BOS = "^"
_EOS = "$"
_LM_SYMBOLS = LETTERS + " " + _EOS


class RefCharLM:
    """Character n-gram LM, interpolated Witten-Bell smoothing.

    ``P(c | h) = (N(h, c) + W(h) * P(c | h')) / (N(h) + W(h))``, where
    ``W(h)`` is the number of different characters seen after ``h`` and
    ``h'`` is ``h`` without its first character. The base is uniform over
    the 26 letters, the space and the end symbol.
    """

    #: Default bound of the ``(context, char)`` memo. The M6-13 soak test saw
    #: about 20,000 entries after 6.5 h live (no bound then; about 1 MB).
    CACHE_SIZE = 32_768

    def __init__(self, order: int = 5, cache_size: int | None = CACHE_SIZE) -> None:
        from fidetype.lm.cache import LRUCache  # M4-10 memo; a bound changes the cost, never a value

        if order < 1:
            raise ValueError("order must be at least 1")
        self.order = order
        self._counts: list[dict[str, dict[str, int]]] = [defaultdict(lambda: defaultdict(int)) for _ in range(order)]
        self._cache: LRUCache = LRUCache(cache_size)

    def fit(self, sentences: Iterable[str]) -> "RefCharLM":
        pad = _BOS * (self.order - 1)
        for s in sentences:
            p = pad + s + _EOS
            for i in range(self.order - 1, len(p)):
                ch = p[i]
                for n in range(self.order):
                    self._counts[n][p[i - n : i]][ch] += 1
        # Freeze to plain dicts with totals.
        self._frozen = [
            {ctx: (dict(d), sum(d.values()), len(d)) for ctx, d in level.items()} for level in self._counts
        ]
        self._cache.clear()
        return self

    def logprob(self, context: str, ch: str) -> float:
        """Return ``log P(ch | context)``. ``ch`` can be ``"$"`` (end)."""
        ctx = (_BOS * (self.order - 1) + context)[-(self.order - 1) :] if self.order > 1 else ""
        key = (ctx, ch)
        v = self._cache.get(key)
        if v is not None:
            return v
        p = 1.0 / len(_LM_SYMBOLS)
        for n in range(self.order):
            h = ctx[len(ctx) - n :] if n else ""
            entry = self._frozen[n].get(h)
            if entry is None:
                continue
            counts, total, types = entry
            p = (counts.get(ch, 0) + types * p) / (total + types)
        v = math.log(p)
        self._cache[key] = v
        return v

    def score_sentence(self, text: str) -> float:
        """Return ``log P(text + end)``."""
        lp = 0.0
        for i, ch in enumerate(text):
            lp += self.logprob(text[:i], ch)
        return lp + self.logprob(text, _EOS)


class ReferenceDecoder:
    """Segment beam search with an optional character LM.

    Score of a candidate = ``logp_acoustic + lm_weight * logp_lm +
    insertion_bonus * len(text)``. ``logp_acoustic`` is the sum of the
    log-probabilities of the chosen token at each peak centre (blank for a
    dropped peak). ``char_confidences`` are the centre-frame probabilities
    of the chosen tokens.

    The defaults (``lm_weight=1.0``, ``insertion_bonus=4.0``, ``beam=16``,
    all 27 non-blank tokens per peak) were tuned by hand on 60 sentences
    of the ``median`` simulator preset. Without the bonus, the LM drops
    peaks to make the text shorter. With a small ``top_m``, the intended
    key is often out of reach: the simulator spreads the residual mass of
    a wrong peak around the *wrong* label, not around the intended key.
    Without an LM, ``lm_weight`` and ``insertion_bonus`` are set to 0.
    """

    def __init__(
        self,
        lm: RefCharLM | None = None,
        lm_weight: float = 1.0,
        insertion_bonus: float = 4.0,
        beam: int = 16,
        n_best: int = 10,
        top_m: int = 27,
        allow_drop: bool = True,
    ) -> None:
        self.lm = lm
        self.lm_weight = lm_weight if lm is not None else 0.0
        self.insertion_bonus = insertion_bonus if lm is not None else 0.0
        self.beam = beam
        self.n_best = n_best
        self.top_m = top_m
        self.allow_drop = allow_drop

    def __call__(self, stream: NeuralTextStream) -> NBest:
        beams = self.start()
        for s, e, c in find_segments(stream):
            beams = self.extend(beams, stream.log_probs[c], stream.vocab, stream.blank_id)
        return self.finish(beams, stream.meta)

    @staticmethod
    def start() -> dict[str, tuple[float, float, tuple[float, ...]]]:
        """The empty beam (text -> (logp_ac, logp_lm, confs))."""
        return {"": (0.0, 0.0, ())}

    def extend(self, beams: dict, centre_row: np.ndarray, vocab: Sequence[str], blank: int) -> dict:
        """Extend the beam by one peak (``centre_row``: the log-probs of its centre frame)."""
        lm = self.lm
        row = np.asarray(centre_row).astype(np.float64)
        order = [int(i) for i in np.argsort(-row) if i != blank][: self.top_m]
        options = [(vocab[i], float(row[i])) for i in order]
        if self.allow_drop:
            options.append(("", float(row[blank])))
        new: dict[str, tuple[float, float, tuple[float, ...]]] = {}
        for text, (ac, lml, conf) in beams.items():
            any_ok = False
            for ch, lp in options:
                if ch == " " and (not text or text.endswith(" ")):
                    continue  # no leading or double space
                any_ok = True
                t2 = text + ch
                ac2 = ac + lp
                lm2 = lml + (lm.logprob(text, ch) if (lm is not None and ch) else 0.0)
                conf2 = conf + ((math.exp(lp),) if ch else ())
                old = new.get(t2)
                if old is None:
                    new[t2] = (ac2, lm2, conf2)
                else:
                    # Merge paths with the same text (sum of acoustic probabilities).
                    best_conf = conf2 if ac2 > old[0] else old[2]
                    new[t2] = (float(np.logaddexp(old[0], ac2)), lm2, best_conf)
            if not any_ok:
                new.setdefault(text, (ac, lml, conf))
        return dict(sorted(new.items(), key=lambda kv: -self._score(kv[0], kv[1][0], kv[1][1]))[: self.beam])

    def finish(self, beams: dict, meta: dict) -> NBest:
        """The n-best list of a beam (end-of-sentence LM term added)."""
        lm = self.lm
        cands: dict[str, Candidate] = {}
        for text, (ac, lml, conf) in beams.items():
            t = text.rstrip(" ")
            conf = conf[: len(t)]
            if lm is not None:
                lml = lml + lm.logprob(t, _EOS)
            score = self._score(t, ac, lml)
            if t not in cands or score > cands[t].score:
                cands[t] = Candidate(t, score, ac, lml if lm is not None else 0.0, conf)
        nb = sorted(cands.values(), key=lambda c: -c.score)[: self.n_best]
        return NBest(nb, {"decoder": "ReferenceDecoder", **{k: v for k, v in meta.items() if k == "seed"}})

    def _score(self, text: str, ac: float, lml: float) -> float:
        return ac + self.lm_weight * lml + self.insertion_bonus * len(text)


def greedy_nbest(stream: NeuralTextStream) -> NBest:
    """The CTC greedy decode as a one-candidate list.

    The character confidence is the centre-frame probability of the peak.
    """
    segs = find_segments(stream)
    chars, conf = [], []
    for s, e, c in segs:
        i = int(np.argmax(stream.log_probs[c]))
        chars.append(stream.vocab[i])
        conf.append(float(np.exp(stream.log_probs[c, i])))
    return greedy_candidate(chars, conf)


def greedy_candidate(chars: Sequence[str], conf: Sequence[float]) -> NBest:
    """The greedy 1-best list from the peak characters and their confidences."""
    text = "".join(chars)
    # Same normalisation as the other decoders (no double or edge spaces).
    out_t, out_c = [], []
    for ch, cf in zip(text, conf):
        if ch == " " and (not out_t or out_t[-1] == " "):
            continue
        out_t.append(ch)
        out_c.append(cf)
    while out_t and out_t[-1] == " ":
        out_t.pop()
        out_c.pop()
    ac = float(np.sum(np.log(np.maximum(out_c, 1e-12)))) if out_c else 0.0
    return NBest([Candidate("".join(out_t), ac, ac, 0.0, tuple(out_c))], {"decoder": "greedy"})


# --- synthetic n-best lists ---------------------------------------------


def _neighbour(ch: str, rng: np.random.Generator) -> str:
    keys = [k for k in LETTERS if k != ch]
    w = np.array([math.exp(-key_distance(ch, k)) for k in keys])
    return keys[int(rng.choice(len(keys), p=w / w.sum()))]


def corrupt(text: str, n_sub: int, rng: np.random.Generator) -> str:
    """Substitute ``n_sub`` random letters with near QWERTY keys."""
    idx = [i for i, c in enumerate(text) if c in KEY_POS and c != " "]
    if not idx:
        return text
    chosen = rng.choice(idx, size=min(n_sub, len(idx)), replace=False)
    t = list(text)
    for i in chosen:
        t[i] = _neighbour(t[i], rng)
    return "".join(t)


def synthetic_nbest(
    truth: str,
    rng: np.random.Generator,
    n: int = 8,
    truth_in_list: bool = True,
    lm_push: bool = False,
    lexicon: Sequence[str] = (),
    good_beta: tuple[float, float] = (8.0, 1.5),
    bad_beta: tuple[float, float] = (1.5, 5.0),
) -> NBest:
    """Build an n-best list for ``truth`` with controlled noise.

    - Candidates are the truth (if ``truth_in_list``) and corruptions with
      1-3 substituted letters.
    - Characters that a Levenshtein alignment matches to the truth get an
      acoustic confidence from ``Beta(good_beta)``; other characters from
      ``Beta(bad_beta)``.
    - Scores: ``sum(log conf) + logp_lm``, with ``logp_lm = -0.5 * n_changed``.
    - If ``lm_push`` is true, the top candidate is a fluent wrong
      sentence: one word of the truth is replaced by a lexicon word, its
      new characters have low acoustic confidence, and its ``logp_lm`` is
      set so that it ranks first (1 nat above the next candidate).
    """
    texts: list[str] = []
    if truth_in_list:
        texts.append(truth)
    tries = 0
    while len(texts) < n and tries < 20 * n:
        tries += 1
        c = corrupt(truth, int(rng.integers(1, 4)), rng)
        if c not in texts and c != truth:
            texts.append(c)
    pushed = None
    if lm_push:
        words = truth.split()
        lex = [w for w in lexicon if w not in words] or ["something"]
        j = int(rng.integers(len(words)))
        words[j] = lex[int(rng.integers(len(lex)))]
        pushed = " ".join(words)
        if pushed in texts:
            texts.remove(pushed)
        texts.append(pushed)
    cands = []
    for t in texts:
        mask = hyp_correct_mask(truth, t)
        conf = [float(np.clip(rng.beta(*(good_beta if ok else bad_beta)), 1e-3, 1 - 1e-3)) for ok in mask]
        ac = float(np.sum(np.log(conf)))
        lm = -0.5 * (len(mask) - sum(mask))
        cands.append(Candidate(t, ac + lm, ac, lm, tuple(conf)))
    if pushed is not None:
        # The LM prefers the fluent wrong sentence so much that it ranks first.
        others = [c for c in cands if c.text != pushed]
        p = next(c for c in cands if c.text == pushed)
        top = max((c.score for c in others), default=0.0)
        lm = top + 1.0 - p.logp_acoustic
        cands = others + [Candidate(p.text, p.logp_acoustic + lm, p.logp_acoustic, lm, p.char_confidences)]
    return NBest(cands, {"synthetic": True, "lm_push": lm_push})


def drifting_posteriors(
    n_steps: int,
    rng: np.random.Generator,
    n_cand: int = 10,
    temp_start: float = 1.0,
    temp_end: float = 0.4,
    logit_scale: float = 2.0,
) -> list[tuple[np.ndarray, int]]:
    """Return (reported posteriors, true index) pairs for a drifting stream.

    At step t the true distribution is ``softmax(z)`` with
    ``z ~ N(0, logit_scale^2)``, and the truth is drawn from it. The
    reported posterior is ``softmax(z / tau_t)``. ``tau_t`` goes linearly
    from ``temp_start`` to ``temp_end``. A value below 1 means growing
    over-confidence, so the exchangeability assumption of split conformal
    fails.
    """
    out = []
    for t in range(n_steps):
        tau = temp_start + (temp_end - temp_start) * t / max(1, n_steps - 1)
        z = np.sort(rng.normal(0.0, logit_scale, n_cand))[::-1]
        y = int(rng.choice(n_cand, p=softmax(z)))
        out.append((softmax(z / tau), y))
    return out
