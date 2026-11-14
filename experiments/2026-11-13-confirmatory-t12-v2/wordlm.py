"""Word trigram LM (interpolated Kneser-Ney) on Tatoeba English, for M3-28. Our own code.

Corpus: Tatoeba English sentences (CC BY 2.0 FR), the same file as the B2T '25 word unigram
and char 6-gram (``experiments/2026-11-10-b2t25-trust/config.json``: ``tatoeba_eng``).
Text: ``normalize_words`` of ``fidetype.adapters.b2t25``. The model is a cache file outside the repo.

Used only as an extra term of the sentence LM of the word route:
    sentence_lm(text) = char6(text) + beta * word3(text)
``beta`` is chosen on decoder-validation data only (see results.md).
"""

from __future__ import annotations

import bz2
import math
import pickle
from collections import Counter, defaultdict
from pathlib import Path

BOS, EOS = "<s>", "</s>"


class WordKN3:
    """Interpolated Kneser-Ney trigram with one absolute discount D per order."""

    def __init__(self, D: float = 0.75, unk_logp: float = -18.0) -> None:
        self.D = D
        self.unk_logp = unk_logp

    def fit(self, sentences) -> "WordKN3":
        c3: Counter = Counter()
        c2: Counter = Counter()
        for s in sentences:
            w = [BOS, BOS] + s.split() + [EOS]
            if len(w) < 4:
                continue
            for i in range(2, len(w)):
                c3[(w[i - 2], w[i - 1], w[i])] += 1
                c2[(w[i - 1], w[i])] += 1
        # highest order: raw counts; lower orders: continuation counts
        self.c3 = c3
        self.c3_ctx = Counter()
        self.n3_ctx = Counter()  # distinct continuations of (a, b)
        for (a, b, c), n in c3.items():
            self.c3_ctx[(a, b)] += n
            self.n3_ctx[(a, b)] += 1
        cont2 = Counter()  # N1+(. b c)
        for (a, b, c) in c3:
            cont2[(b, c)] += 1
        self.cont2 = cont2
        self.cont2_ctx = Counter()
        self.n2_ctx = Counter()
        for (b, c), n in cont2.items():
            self.cont2_ctx[b] += n
            self.n2_ctx[b] += 1
        cont1 = Counter()  # N1+(. c)
        for (b, c) in cont2:
            cont1[c] += 1
        tot = sum(cont1.values())
        self.p1 = {c: n / tot for c, n in cont1.items()}
        return self

    def _p2(self, b: str, c: str) -> float:
        p1 = self.p1.get(c, 0.0)
        den = self.cont2_ctx.get(b, 0)
        if den == 0:
            return p1
        num = max(self.cont2.get((b, c), 0) - self.D, 0.0)
        lam = self.D * self.n2_ctx[b] / den
        return num / den + lam * p1

    def _p3(self, a: str, b: str, c: str) -> float:
        p2 = self._p2(b, c)
        den = self.c3_ctx.get((a, b), 0)
        if den == 0:
            return p2
        num = max(self.c3.get((a, b, c), 0) - self.D, 0.0)
        lam = self.D * self.n3_ctx[(a, b)] / den
        return num / den + lam * p2

    def score_sentence(self, text: str) -> float:
        w = [BOS, BOS] + text.split() + [EOS]
        tot = 0.0
        for i in range(2, len(w)):
            p = self._p3(w[i - 2], w[i - 1], w[i])
            tot += math.log(p) if p > 0 else self.unk_logp
        return tot


def load_or_build(corpus: str, cache: Path, normalize) -> WordKN3:
    if cache.exists():
        with open(cache, "rb") as f:
            return pickle.load(f)
    sents = []
    with bz2.open(corpus, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                s = normalize(parts[-1])
                if s:
                    sents.append(s)
    m = WordKN3().fit(sents)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with open(cache, "wb") as f:
        pickle.dump(m, f, protocol=pickle.HIGHEST_PROTOCOL)
    return m
