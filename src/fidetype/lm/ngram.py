"""Character n-gram language model with Kneser-Ney smoothing.

The model predicts the next character of a sentence. It is written in
pure Python and numpy, so it runs in CI and on every platform.

Symbols
-------
The model uses the token ids of :data:`fidetype.streams.vocab.VOCAB`:

- id 0: end of sentence (``</s>``). The CTC blank never reaches the
  model, so the model uses id 0 for the end marker.
- ids 1-26: the letters ``a`` to ``z``.
- id 27: the space.
- id 28: begin of sentence (``<s>``). It occurs only in contexts. The
  model never predicts it.

Thus a predicted distribution has 28 entries. Entry ``i`` (for
``i >= 1``) is the probability of vocab token ``i``. Entry 0 is the
probability of the end of the sentence. The beam search uses this
layout directly.

Each training sentence is padded with ``order - 1`` begin markers and
one end marker. A context at the start of a sentence is padded in the
same way.

Smoothing
---------
``smoothing="mkn"`` (default) is interpolated modified Kneser-Ney (Chen
and Goodman 1998, three discounts per order). ``"kn"`` is interpolated
Kneser-Ney with one discount per order. ``"mle"`` is the unsmoothed
maximum-likelihood model; it backs off only when a context is unseen.
It exists for comparison.

The lower orders of KN and MKN use continuation counts (the number of
different characters to the left). An n-gram that starts with ``<s>``
has no left extension, so it keeps its raw count (as in KenLM).

The model stores, for each order k and each seen context h:

- ``alpha(h, w) = max(c(h, w) - D, 0) / c(h)`` for each seen w,
- ``gamma(h) = 1 - sum_w alpha(h, w)`` (the back-off weight).

Then ``p_k(w | h) = alpha(h, w) + gamma(h) * p_{k-1}(w | h')``. Here
``h'`` is ``h`` without its first symbol. ``p_0`` is uniform over the
28 outcomes. If h is not seen, ``p_k = p_{k-1}``. Each distribution
sums to 1.

All log-probabilities are natural logs.

File format
-----------
:meth:`CharNgramLM.save` writes one ``.npz`` file (no pickle). It holds
the arrays of each order and a JSON string with the settings and the
provenance (``meta``).
"""

from __future__ import annotations

import json
import math
from os import PathLike
from typing import Any, Iterable

import numpy as np

from fidetype.lm.cache import LRUCache
from fidetype.streams.vocab import VOCAB, normalize_text

EOS_ID = 0
BOS_ID = 28
N_OUT = 28  # Predicted outcomes: EOS + 27 characters.
_BASE = 29  # Symbols: 0..27 outcomes + BOS.
EOS = "</s>"
BOS = "<s>"

# Byte -> symbol table for normalised text. "^" = BOS, "$" = EOS.
_LUT = np.full(256, -1, dtype=np.int64)
for _i, _c in enumerate(VOCAB):
    if _i > 0:
        _LUT[ord(_c)] = _i
_LUT[ord("^")] = BOS_ID
_LUT[ord("$")] = EOS_ID
_CHAR_ID = {c: i for i, c in enumerate(VOCAB) if i > 0}

FORMAT_VERSION = 1


def _discounts(counts: np.ndarray, smoothing: str) -> tuple[float, float, float]:
    """Return (D1, D2, D3+) from the count-of-counts of one order."""
    n = [int(np.sum(counts == r)) for r in (1, 2, 3, 4)]
    if smoothing == "mle":
        return 0.0, 0.0, 0.0
    if n[0] == 0 or n[1] == 0:
        return 0.5, 0.5, 0.5  # Tiny data: use a safe fixed discount.
    y = n[0] / (n[0] + 2.0 * n[1])
    if smoothing == "kn":
        return y, y, y
    d1 = 1.0 - 2.0 * y * n[1] / n[0]
    d2 = 2.0 - 3.0 * y * n[2] / n[1] if n[1] else 1.0
    d3 = 3.0 - 4.0 * y * n[3] / n[2] if n[2] else 1.5
    # Keep the discounts in a valid range (they can go wrong on tiny data).
    d1 = min(max(d1, 0.05), 0.95)
    d2 = min(max(d2, 0.05), 1.95)
    d3 = min(max(d3, 0.05), 2.95)
    return d1, d2, d3


def _unique_counts(codes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    u, c = np.unique(codes, return_counts=True)
    return u, c.astype(np.float64)


class CharNgramLM:
    """Character n-gram LM over the 27 characters plus ``<s>``/``</s>``.

    Use :meth:`train` or :meth:`load` before you query the model. See the
    module docstring for the symbols and the smoothing.
    """

    def __init__(self, order: int = 6, smoothing: str = "mkn", cache_size: int | None = 200_000) -> None:
        if order < 1:
            raise ValueError("order must be at least 1")
        if smoothing not in ("mkn", "kn", "mle"):
            raise ValueError("smoothing must be 'mkn', 'kn' or 'mle'")
        self.order = int(order)
        self.smoothing = smoothing
        # LRU bound of the next-symbol memo (M4-10; before: cleared when full). None: no bound.
        self.cache_size = None if cache_size is None else int(cache_size)
        self.meta: dict[str, Any] = {}
        self.discounts: list[tuple[float, float, float]] = []
        # Per order k (index k-1): sorted context codes, back-off weights,
        # offsets into the entry arrays, entry outcomes and alphas.
        self._ctx: list[np.ndarray] = []
        self._gamma: list[np.ndarray] = []
        self._off: list[np.ndarray] = []
        self._out: list[np.ndarray] = []
        self._alpha: list[np.ndarray] = []
        self._cache: LRUCache = LRUCache(self.cache_size)
        self._trained = False

    # --- training -------------------------------------------------------

    def train(self, texts: Iterable[str], normalize: bool = True) -> "CharNgramLM":
        """Train the model on ``texts`` (one sentence per item).

        Each text is normalised with :func:`normalize_text` (unless
        ``normalize`` is False; then it must already be in the character
        set). Empty texts are skipped. Returns ``self``.
        """
        n = self.order
        pad = "^" * (n - 1)
        parts: list[str] = []
        n_sent = n_chars = 0
        for t in texts:
            s = normalize_text(t) if normalize else t
            if not s:
                continue
            parts.append(pad + s + "$")
            n_sent += 1
            n_chars += len(s)
        if n_sent == 0:
            raise ValueError("no training text")
        buf = "".join(parts).encode("ascii")
        sym = _LUT[np.frombuffer(buf, dtype=np.uint8)]
        if np.any(sym < 0):
            raise ValueError("text contains characters outside the vocabulary")
        del buf, parts

        # Raw counts of the k-grams that end at a non-BOS position.
        # A window that ends at a predicted symbol never crosses a
        # sentence start, because each sentence has n-1 BOS in front.
        raw: list[tuple[np.ndarray, np.ndarray]] = []
        code = sym.copy()  # code[i] = k-gram that starts at i
        L = sym.shape[0]
        for k in range(1, n + 1):
            if k > 1:
                code = code[: L - k + 1] * _BASE + sym[k - 1 :]
            keep = sym[k - 1 :] != BOS_ID
            raw.append(_unique_counts(code[keep]))
        del code, sym

        self._ctx, self._gamma, self._off, self._out, self._alpha = [], [], [], [], []
        self.discounts = []
        for k in range(1, n + 1):
            grams, counts = raw[k - 1]
            if k < n and self.smoothing != "mle":
                # Continuation counts: distinct left extensions.
                hi_grams = raw[k][0]
                suffix = hi_grams % (_BASE**k)
                su, sc = _unique_counts(suffix)
                idx = np.searchsorted(su, grams)
                idx = np.minimum(idx, su.shape[0] - 1)
                cont = np.where(su[idx] == grams, sc[idx], 0.0)
                starts_bos = (grams // (_BASE ** (k - 1))) == BOS_ID
                counts = np.where(starts_bos | (cont == 0), counts, cont)
            d = _discounts(counts, self.smoothing)
            self.discounts.append(d)
            dvec = np.where(counts >= 3, d[2], np.where(counts >= 2, d[1], d[0]))
            dvec = np.minimum(dvec, counts)
            ctx = grams // _BASE
            out = (grams % _BASE).astype(np.int8)
            uctx, start, n_per = np.unique(ctx, return_index=True, return_counts=True)
            total = np.add.reduceat(counts, start)
            disc = np.add.reduceat(dvec, start)
            alpha = (counts - dvec) / np.repeat(total, n_per)
            self._ctx.append(uctx.astype(np.int64))
            self._gamma.append(disc / total)
            self._off.append(np.concatenate([start, [grams.shape[0]]]).astype(np.int64))
            self._out.append(out)
            self._alpha.append(alpha)
        self._cache = LRUCache(self.cache_size)
        self._trained = True
        self.meta.update(
            n_sentences=n_sent,
            n_chars=n_chars,
            n_grams_per_order=[int(c.shape[0]) for c in self._out],
        )
        return self

    # --- queries --------------------------------------------------------

    def _check(self) -> None:
        if not self._trained:
            raise RuntimeError("the model is not trained; call train() or load()")

    def _context_symbols(self, context: str, bos: bool) -> list[int]:
        m = self.order - 1
        if m == 0:
            return []
        tail = context[-m:] if context else ""
        try:
            ids = [_CHAR_ID[c] for c in tail]
        except KeyError as e:
            raise ValueError(f"context character {e.args[0]!r} is not in the vocabulary") from None
        if len(ids) < m and bos:
            ids = [BOS_ID] * (m - len(ids)) + ids
        return ids

    def _dist(self, syms: list[int]) -> np.ndarray:
        """Return the probability vector (28,) for a context of symbols."""
        p = np.full(N_OUT, 1.0 / N_OUT)
        code = 0
        mult = 1
        for k in range(1, self.order + 1):
            if k > 1:
                if k - 1 > len(syms):
                    break  # Context shorter than this order (bos=False).
                code += syms[-(k - 1)] * mult
                mult *= _BASE
            ctx = self._ctx[k - 1]
            i = int(np.searchsorted(ctx, code))
            if i >= ctx.shape[0] or ctx[i] != code:
                break  # Unseen context: longer ones are unseen too.
            s, e = self._off[k - 1][i], self._off[k - 1][i + 1]
            p *= self._gamma[k - 1][i]
            p[self._out[k - 1][s:e]] += self._alpha[k - 1][s:e]
        return p

    def logprobs_vocab(self, context: str, bos: bool = True) -> np.ndarray:
        """Return the natural-log distribution of the next symbol.

        The result has shape (28,). Entry ``i >= 1`` is vocab token ``i``.
        Entry 0 is the end of the sentence. ``context`` is the sentence
        text so far (only the last ``order - 1`` characters matter). With
        ``bos=True`` a short context is padded with ``<s>``.

        This is the fast path for the beam search. Results are cached.
        Do not change the returned array.
        """
        self._check()
        key = context[-(self.order - 1) :] if self.order > 1 else ""
        if not bos:
            key = "\x00" + key
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        p = self._dist(self._context_symbols(context, bos))
        with np.errstate(divide="ignore"):
            lp = np.log(p)
        lp.setflags(write=False)
        self._cache[key] = lp  # LRU: the least recently used entry goes when full
        return lp

    def logprob(self, next_char: str, context: str = "", bos: bool = True) -> float:
        """Return ``log p(next_char | context)`` (natural log).

        ``next_char`` is one character (``a``-``z`` or space) or
        :data:`EOS` (``"</s>"``).
        """
        if next_char == EOS:
            i = EOS_ID
        else:
            i = _CHAR_ID.get(next_char, -1)
            if i < 0:
                raise ValueError(f"next_char {next_char!r} is not in the vocabulary")
        return float(self.logprobs_vocab(context, bos)[i])

    def score_sentence(self, text: str, eos: bool = True, normalize: bool = True) -> float:
        """Return the natural-log probability of a whole sentence.

        The sum includes the end marker if ``eos`` is True.
        """
        s = normalize_text(text) if normalize else text
        total = 0.0
        for j, c in enumerate(s):
            total += self.logprobs_vocab(s[:j])[_CHAR_ID[c]]
        if eos:
            total += self.logprobs_vocab(s)[EOS_ID]
        return float(total)

    def perplexity(self, texts: Iterable[str], normalize: bool = True) -> float:
        """Return the per-symbol perplexity on ``texts``.

        Each sentence counts its characters plus one end marker. The
        value is ``exp(-sum log p / N)``. It is ``inf`` if a symbol has
        probability 0 (possible only with ``smoothing="mle"``).
        """
        tot = 0.0
        n = 0
        for t in texts:
            s = normalize_text(t) if normalize else t
            if not s:
                continue
            tot += self.score_sentence(s, eos=True, normalize=False)
            n += len(s) + 1
        if n == 0:
            raise ValueError("no text")
        return math.exp(-tot / n) if math.isfinite(tot) else math.inf

    # --- file I/O -------------------------------------------------------

    def save(self, path: str | PathLike[str]) -> None:
        """Save the model to one compressed ``.npz`` file (no pickle)."""
        self._check()
        arrays: dict[str, np.ndarray] = {}
        for k in range(self.order):
            arrays[f"ctx{k}"] = self._ctx[k]
            arrays[f"gamma{k}"] = self._gamma[k].astype(np.float32)
            arrays[f"off{k}"] = self._off[k]
            arrays[f"out{k}"] = self._out[k]
            arrays[f"alpha{k}"] = self._alpha[k].astype(np.float32)
        header = {
            "format": "fidetype-char-ngram",
            "format_version": FORMAT_VERSION,
            "order": self.order,
            "smoothing": self.smoothing,
            "discounts": [list(d) for d in self.discounts],
            "meta": self.meta,
        }
        np.savez_compressed(path, header_json=np.array(json.dumps(header)), **arrays)

    @classmethod
    def load(cls, path: str | PathLike[str]) -> "CharNgramLM":
        """Load a model that :meth:`save` wrote."""
        with np.load(path, allow_pickle=False) as z:
            header = json.loads(str(z["header_json"]))
            if header.get("format") != "fidetype-char-ngram":
                raise ValueError("not a fidetype char n-gram file")
            lm = cls(order=int(header["order"]), smoothing=str(header["smoothing"]))
            lm.discounts = [tuple(d) for d in header["discounts"]]
            lm.meta = dict(header.get("meta", {}))
            for k in range(lm.order):
                lm._ctx.append(z[f"ctx{k}"].astype(np.int64))
                lm._gamma.append(z[f"gamma{k}"].astype(np.float64))
                lm._off.append(z[f"off{k}"].astype(np.int64))
                lm._out.append(z[f"out{k}"].astype(np.int8))
                lm._alpha.append(z[f"alpha{k}"].astype(np.float64))
        lm._trained = True
        return lm


def exclude_sentences(corpus: Iterable[str], blocklist: Iterable[str]) -> list[str]:
    """Return the sentences of ``corpus`` that are not in ``blocklist``.

    Both sides are compared after :func:`normalize_text`. Use it to keep
    test sentences out of LM training data. The order of ``corpus`` is
    kept. Sentences that normalise to an empty string are dropped.
    """
    block = {normalize_text(b) for b in blocklist}
    block.discard("")
    out = []
    for s in corpus:
        ns = normalize_text(s)
        if ns and ns not in block:
            out.append(s)
    return out
