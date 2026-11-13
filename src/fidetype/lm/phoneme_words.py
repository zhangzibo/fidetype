"""Phoneme n-best -> word n-best, with a pronunciation lexicon and an LM.

This is a small, licence-clean route from a phoneme CTC decoder to words.
It is **not** a WFST decoder. It works on the n-best list of a phoneme CTC
beam (``fidetype.lm.ctc_prefix_beam_search`` on a one-character-per-token
stream, where a space is the word boundary):

1. Split each phoneme hypothesis into word segments at the spaces.
2. For each segment, find lexicon words whose pronunciation is within a
   small phoneme edit distance (:meth:`PronLexicon.candidates`, a
   SymSpell-style deletion index).
3. Combine the segment candidates into word sequences (a beam over the
   segments with an edit penalty and a word unigram prior).
4. Rescore each sentence: ``logp_acoustic + slot score +
   lm_weight * logp_charLM + word_bonus * n_words``.

Each output has per-character confidences for the trust core: every
character of a word gets the lowest frame posterior of its phonemes,
times ``0.5 ** edits``. So a word that needed edits to match the lexicon
gets less acoustic evidence.

The lexicon file format is the CMU Pronouncing Dictionary
(``word PH1 PH2 ...`` per line, stress digits allowed, ``word(2)`` for
variants, ``#`` comments). The CMUdict licence is BSD-2-Clause style; the
file itself is not in this repository.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from itertools import combinations
from os import PathLike
from typing import Callable, Iterable, Iterator, Sequence

import numpy as np

from fidetype.lm.cache import LRUCache

_VARIANT = re.compile(r"\(\d+\)$")


def edit_distance_str(a: str, b: str, max_d: int | None = None) -> int:
    """Levenshtein distance of two strings. Stops early above ``max_d``."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if max_d is not None and len(a) - len(b) > max_d:
        return max_d + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            best = min(best, v)
        if max_d is not None and best > max_d:
            return max_d + 1
        prev = cur
    return prev[-1]


def _levenshtein_many(q: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """Exact Levenshtein distances of the query ``q`` (code points) to each row of ``codes`` (``N x n``)."""
    N, n = codes.shape
    ar = np.arange(n + 1, dtype=np.int32)
    prev = np.broadcast_to(ar, (N, n + 1))
    tmp = np.empty((N, n + 1), dtype=np.int32)
    for i, c in enumerate(q.tolist(), 1):
        tmp[:, 0] = i
        np.minimum(prev[:, 1:] + 1, prev[:, :-1] + (codes != c), out=tmp[:, 1:])
        # Insertions: cur[j] = min over k <= j of tmp[k] + (j - k).
        prev = np.minimum.accumulate(tmp - ar, axis=1) + ar
    return np.asarray(prev[:, n])


def _deletes(s: str, d: int) -> set[str]:
    out = {s}
    for k in range(1, min(d, len(s)) + 1):
        for idx in combinations(range(len(s)), k):
            out.add("".join(c for i, c in enumerate(s) if i not in idx))
    return out


def default_max_edits(n: int) -> int:
    """Edits allowed for a segment of ``n`` phonemes: 1 (n <= 2), else 2."""
    return 1 if n <= 2 else 2


class PronLexicon:
    """Word pronunciations as symbol strings, with a fuzzy lookup.

    ``prons`` maps a word to its pronunciations. Each pronunciation is a
    string with one character per phoneme (see
    :func:`fidetype.adapters.b2t25.phonemes_to_symbols`).
    """

    def __init__(self, prons: dict[str, list[str]], max_index_edits: int = 2) -> None:
        self.prons = prons
        self.max_index_edits = max_index_edits
        self._by_pron: dict[str, list[str]] = {}
        for w, ps in prons.items():
            for p in ps:
                self._by_pron.setdefault(p, []).append(w)
        self._index: dict[str, list[str]] = {}
        for p in self._by_pron:
            for dl in _deletes(p, max_index_edits):
                self._index.setdefault(dl, []).append(p)
        self._fallback: dict[int, list[str]] = {}

    def set_fallback_words(self, words: Iterable[str]) -> None:
        """Words that :meth:`nearest` may return (for example, frequent words)."""
        self._fallback = {}
        for w in words:
            for p in self.prons.get(w, ()):
                self._fallback.setdefault(len(p), []).append(p)
        self._fb_index = None

    def _fallback_index(self) -> dict[int, tuple[list[str], np.ndarray]]:
        """Per length ``n``: the unique fallback pronunciations and their code points (``N x n``)."""
        idx = getattr(self, "_fb_index", None)
        if idx is None:
            idx = {}
            for n, ps in self._fallback.items():
                uniq = list(dict.fromkeys(ps))
                codes = np.array([[ord(c) for c in p] for p in uniq], dtype=np.int32).reshape(len(uniq), n)
                idx[n] = (uniq, codes)
            self._fb_index = idx
        return idx

    def nearest(self, seg: str, max_len_diff: int = 2) -> list[tuple[str, int]]:
        """Nearest fallback words, when :meth:`candidates` finds none.

        Searches only the pronunciations of the fallback words (see
        :meth:`set_fallback_words`) whose length is within ``max_len_diff``.
        Returns the words at the smallest distance, if it is at most
        ``max(3, len(seg) // 2)``, sorted by word.

        Exact and equal to :meth:`nearest_bruteforce` (same words, same
        distance, same order). It computes the full Levenshtein distance to
        all pronunciations of one length at once (NumPy, one row of the DP
        table per query symbol; the insertion chain of a row is a running
        minimum).
        """
        lim = max(3, len(seg) // 2)
        idx = self._fallback_index()
        q = np.array([ord(c) for c in seg], dtype=np.int32)
        best_d, hits = lim + 1, []
        for n in range(len(seg) - max_len_diff, len(seg) + max_len_diff + 1):
            got = idx.get(n)
            if got is None or abs(n - len(seg)) > best_d:
                continue
            prons, codes = got
            d = _levenshtein_many(q, codes)
            m = int(d.min())
            if m < best_d:
                best_d, hits = m, []
            if m == best_d:
                hits.extend(prons[i] for i in np.flatnonzero(d == m))
        if best_d > lim:
            return []
        return sorted({(w, best_d) for p in hits for w in self._by_pron[p]}, key=lambda x: x[0])

    def nearest_bruteforce(self, seg: str, max_len_diff: int = 2) -> list[tuple[str, int]]:
        """Reference for :meth:`nearest`: one Python edit distance per pronunciation (slow).

        Searches only the pronunciations of the fallback words (see
        :meth:`set_fallback_words`) whose length is within ``max_len_diff``.
        Returns the words at the smallest distance, if it is at most
        ``max(3, len(seg) // 2)``.
        """
        lim = max(3, len(seg) // 2)
        best_d, out = lim + 1, []
        for n in range(len(seg) - max_len_diff, len(seg) + max_len_diff + 1):
            for p in self._fallback.get(n, ()):
                d = edit_distance_str(seg, p, best_d)
                if d < best_d:
                    best_d, out = d, [p]
                elif d == best_d:
                    out.append(p)
        if best_d > lim:
            return []
        return sorted({(w, best_d) for p in out for w in self._by_pron[p]}, key=lambda x: x[0])

    @property
    def words(self) -> set[str]:
        return set(self.prons)

    def __len__(self) -> int:
        return len(self.prons)

    @classmethod
    def from_cmudict(
        cls,
        path: str | PathLike[str],
        to_symbols: Callable[[Sequence[str]], str],
        keep: Callable[[str], bool] | None = None,
        max_index_edits: int = 2,
    ) -> "PronLexicon":
        """Read a CMUdict file. Stress digits are removed.

        ``to_symbols`` turns a phoneme list into a symbol string. ``keep``
        filters the words (for example, words with letters and ``'`` only).
        """
        prons: dict[str, list[str]] = {}
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                word = _VARIANT.sub("", parts[0].lower())
                if keep is not None and not keep(word):
                    continue
                phs = [re.sub(r"\d", "", p) for p in parts[1:]]
                try:
                    sym = to_symbols(phs)
                except ValueError:
                    continue
                if sym and sym not in prons.setdefault(word, []):
                    prons[word].append(sym)
        return cls({w: p for w, p in prons.items() if p}, max_index_edits)

    def candidates(self, seg: str, max_edits: int | None = None) -> list[tuple[str, int]]:
        """Return ``(word, edits)`` for every word with a pronunciation within
        ``max_edits`` of ``seg`` (default :func:`default_max_edits`)."""
        d = default_max_edits(len(seg)) if max_edits is None else max_edits
        d = min(d, self.max_index_edits)
        found: dict[str, int] = {}
        seen: set[str] = set()
        for dl in _deletes(seg, d):
            for p in self._index.get(dl, ()):
                if p in seen:
                    continue
                seen.add(p)
                e = edit_distance_str(seg, p, d)
                if e <= d:
                    for w in self._by_pron[p]:
                        if e < found.get(w, d + 1):
                            found[w] = e
        return sorted(found.items(), key=lambda x: (x[1], x[0]))


#: Default entry bounds of the :class:`PhonemeWordDecoder` memos (M4-10).
DEFAULT_CAND_CACHE_SIZE = 5_000
DEFAULT_LM_CACHE_SIZE = 50_000


def _info(c) -> dict:
    if isinstance(c, LRUCache):
        return c.info()
    return {"size": len(c), "maxsize": None}


@dataclass
class WordHypothesis:
    """A word sentence from :class:`PhonemeWordDecoder` (duck-types ``Hypothesis``)."""

    text: str
    score: float
    logp_acoustic: float
    logp_lm: float
    char_confidences: tuple[float, ...] = ()
    edits: int = 0
    phonemes: str = ""
    words_conf: tuple[float, ...] = field(default=())


@dataclass
class PhonemeWordDecoder:
    """Turn a phoneme n-best into a word n-best (see the module docstring).

    ``unigram_logp`` maps a word to its log prior; words not in it get
    ``oov_logp``. ``sentence_lm`` returns the log-probability of a word
    sentence (for example ``CharNgramLM.score_sentence``), or is None.

    ``cand_cache_size`` bounds the memo segment -> lexicon candidates and
    ``lm_cache_size`` the memo word sentence -> sentence-LM score, in
    entries, with least-recently-used eviction
    (:class:`fidetype.lm.cache.LRUCache`). None: no bound. The memos hold
    pure function values, so a bound never changes a result, only the
    cost (M4-10). A candidate entry is large (B2T '25 with CMUdict: about
    17 KB, often hundreds of candidate words); a sentence-LM entry is about
    0.2 KB. The defaults bound the two memos to about 85 MB and 8 MB.
    """

    lexicon: PronLexicon
    unigram_logp: dict[str, float]
    sentence_lm: Callable[[str], float] | None = None
    lm_weight: float = 0.5
    edit_penalty: float = 4.0
    unigram_weight: float = 1.0
    word_bonus: float = 0.0
    oov_logp: float = -20.0
    drop_penalty: float = 15.0
    per_slot: int = 6
    per_hyp: int = 8
    n_best: int = 10
    cand_cache_size: int | None = DEFAULT_CAND_CACHE_SIZE
    lm_cache_size: int | None = DEFAULT_LM_CACHE_SIZE
    _lm_cache: LRUCache = field(init=False, repr=False)
    _cand_cache: LRUCache = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lm_cache = LRUCache(self.lm_cache_size)
        self._cand_cache = LRUCache(self.cand_cache_size)

    def set_cache_sizes(self, cand: int | None, lm: int | None) -> None:
        """Change the bounds of the two memos (the oldest entries go first)."""
        self._cand_cache.resize(cand)
        self._lm_cache.resize(lm)
        self.cand_cache_size, self.lm_cache_size = cand, lm

    def clear_caches(self) -> None:
        self._lm_cache.clear()
        self._cand_cache.clear()

    def cache_info(self) -> dict[str, dict]:
        """Size, bound and hit/miss/eviction counters of the two memos."""
        return {"candidates": _info(self._cand_cache), "sentence_lm": _info(self._lm_cache)}

    def _slot(self, seg: str) -> list[tuple[str, int]]:
        c = self._cand_cache.get(seg)
        if c is None:
            c = self.lexicon.candidates(seg) or self.lexicon.nearest(seg)
            self._cand_cache[seg] = c
        return c

    def _lm(self, text: str) -> float:
        if self.sentence_lm is None:
            return 0.0
        v = self._lm_cache.get(text)
        if v is None:
            v = float(self.sentence_lm(text))
            self._lm_cache[text] = v
        return v

    def warm(self, texts: Iterable[str]) -> Iterator[None]:
        """Fill the caches that :meth:`decode` of these phoneme texts would use, one small step per ``next()``.

        One step = the lexicon candidates of one new segment, its
        :meth:`PronLexicon.nearest` fallback (if it has no candidates), or the
        sentence-LM score of one new word sentence. The steps already in
        the caches are skipped. The caches hold values that :meth:`decode`
        would compute anyway, so a result never changes. Use it as a
        time-budgeted prewarm (``CTCBeamSpec(on_prewarm=wdec.warm, prewarm_budget_s=...)``).
        """
        for raw in texts:
            text = " ".join(str(raw).split())
            segs = text.split()
            for seg in segs:
                if seg not in self._cand_cache:
                    c = self.lexicon.candidates(seg)  # as _slot, in two steps
                    if not c:
                        yield
                        c = self.lexicon.nearest(seg)
                    self._cand_cache[seg] = c
                    yield
            if self.sentence_lm is None:
                continue
            for words, _, _, _ in self._combine(segs, [[0.0] * len(s) for s in segs]):
                wt = " ".join(words)
                if wt and wt not in self._lm_cache:
                    self._lm(wt)
                    yield

    def decode(self, phoneme_hyps: Iterable) -> list[WordHypothesis]:
        """Decode phoneme hypotheses (objects with ``text``, ``logp_acoustic``
        and per-symbol ``confidence_variants["frame"]`` or
        ``char_confidences``). Return up to ``n_best`` word hypotheses."""
        best: dict[str, WordHypothesis] = {}
        for h in phoneme_hyps:
            text = " ".join(str(h.text).split())
            conf = _frame_conf(h, len(str(h.text)))
            conf = _strip_conf(str(h.text), conf)
            segs, seg_conf = _segments(text, conf)
            for words, slot_score, edits, wconf in self._combine(segs, seg_conf):
                wt = " ".join(words)
                lp_lm = self._lm(wt) if wt else self.oov_logp
                lp_ac = float(getattr(h, "logp_acoustic", 0.0))
                score = lp_ac + slot_score + self.lm_weight * lp_lm + self.word_bonus * len(words)
                if wt in best and best[wt].score >= score:
                    continue
                cc: list[float] = []
                for i, (w, c) in enumerate(zip(words, wconf)):
                    if i:
                        cc.append(min(c, wconf[i - 1]))  # the space
                    cc.extend([c] * len(w))
                best[wt] = WordHypothesis(wt, score, lp_ac, lp_lm, tuple(cc), edits, text, tuple(wconf))
        out = sorted(best.values(), key=lambda x: -x.score)
        return out[: self.n_best]

    def _combine(self, segs: list[str], seg_conf: list[list[float]]):
        beams: list[tuple[float, tuple[str, ...], int, tuple[float, ...]]] = [(0.0, (), 0, ())]
        for seg, sc in zip(segs, seg_conf):
            cands = self._slot(seg)
            opts = []
            for w, e in cands:
                s = -self.edit_penalty * e + self.unigram_weight * self.unigram_logp.get(w, self.oov_logp)
                opts.append((s, w, e))
            opts.sort(key=lambda x: -x[0])
            opts = opts[: self.per_slot]
            base_c = min(sc) if sc else 0.0
            new = []
            for b_s, b_w, b_e, b_c in beams:
                if not opts:  # no lexicon word: drop the segment
                    new.append((b_s - self.drop_penalty, b_w, b_e + len(seg), b_c))
                    continue
                for s, w, e in opts:
                    new.append((b_s + s, b_w + (w,), b_e + e, b_c + (base_c * 0.5**e,)))
            new.sort(key=lambda x: -x[0])
            beams = new[: self.per_hyp]
        return [(w, s, e, c) for s, w, e, c in beams]


def _frame_conf(h, n: int) -> list[float]:
    cv = getattr(h, "confidence_variants", None)
    conf = None
    if isinstance(cv, dict) and "frame" in cv:
        conf = cv["frame"]
    if conf is None or len(conf) != n:
        conf = getattr(h, "char_confidences", None)
    if conf is None or len(conf) != n:
        return [0.0] * n
    return [0.0 if not math.isfinite(float(c)) else float(c) for c in conf]


def _strip_conf(raw: str, conf: list[float]) -> list[float]:
    """Confidences of the characters kept by ``" ".join(raw.split())``."""
    keep, prev_space = [], True
    for ch, c in zip(raw, conf):
        if ch == " ":
            if prev_space:
                continue
            prev_space = True
        else:
            prev_space = False
        keep.append(c)
    norm = " ".join(raw.split())
    return keep[: len(norm)]


def _segments(text: str, conf: list[float]) -> tuple[list[str], list[list[float]]]:
    segs, cs, cur, cc = [], [], [], []
    for ch, c in zip(text, conf):
        if ch == " ":
            if cur:
                segs.append("".join(cur))
                cs.append(cc)
            cur, cc = [], []
        else:
            cur.append(ch)
            cc.append(c)
    if cur:
        segs.append("".join(cur))
        cs.append(cc)
    return segs, cs


def unigram_logprobs(counts: dict[str, int], vocab: Iterable[str], alpha: float = 0.5) -> dict[str, float]:
    """Add-``alpha`` log unigram probabilities over ``vocab``."""
    vocab = list(vocab)
    total = sum(counts.get(w, 0) for w in vocab) + alpha * len(vocab)
    return {w: math.log((counts.get(w, 0) + alpha) / total) for w in vocab}
