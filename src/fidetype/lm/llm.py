"""Large-language-model (LLM) n-best rescoring and lattice-limited rewrite (P15-05, F2 / E3).

The LLM is optional. This module defines two small interfaces and the
logic that uses them; a backend is needed only to run a real model:

- :class:`SentenceScorer`: ``score(texts) -> log p(text)`` for each text.
- :class:`SentenceRewriter`: ``rewrite(nbest_texts, constrained) -> text``.
- :class:`LlamaCppLLM`: a backend for both, on ``llama-cpp-python``
  (extra ``fidetype[llm]``). It imports ``llama_cpp`` only when it is
  built, so the rest of the module (and its tests) work without it.

Functions (no model needed):

- :func:`rescore` adds ``weight * log p_llm(text)`` to each n-best score.
- :func:`lattice_words` / :func:`within_lattice`: the word bag of the
  decoder's n-best, and the check that a rewrite uses only those words.
- :func:`add_rewrite` puts a rewrite on top of an n-best list, with
  character confidences copied from the decoder candidates.

All n-best lists are lists of dicts ``{"text", "score", ...}``, the form
that :func:`fidetype.trust.calibrate` accepts from a ``decode_fn``.
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable, Mapping, Protocol, Sequence, runtime_checkable

import numpy as np

REWRITE_PROMPT_CONSTRAINED = (
    "A speech decoder heard one English sentence. These are its best guesses, best first:\n{guesses}\n"
    "Write the sentence that the speaker most likely said. Use only words that appear in the guesses. "
    "Write only the sentence, in lower case, with no punctuation."
)
REWRITE_PROMPT_FREE = (
    "A speech decoder heard one English sentence. These are its best guesses, best first:\n{guesses}\n"
    "Write the sentence that the speaker most likely said. Correct any wrong words. "
    "Write only the sentence, in lower case, with no punctuation."
)


@runtime_checkable
class SentenceScorer(Protocol):
    def score(self, texts: Sequence[str]) -> list[float]:
        """Natural-log probability of each text under the LLM."""
        ...


@runtime_checkable
class SentenceRewriter(Protocol):
    def rewrite(self, nbest_texts: Sequence[str], constrained: bool = True) -> str:
        """One sentence written from the n-best texts (best first)."""
        ...


def normalize_text(text: str) -> str:
    """Lower case; keep a-z, the apostrophe and single spaces (the B2T word convention)."""
    t = "".join(c if ("a" <= c <= "z" or c == "'") else " " for c in text.lower())
    return " ".join(t.split())


def rescore(items: Sequence[Mapping], scorer: SentenceScorer, weight: float) -> list[dict]:
    """Return copies of the n-best dicts with ``score += weight * logp_llm`` (sorted, best first).

    Each dict gets ``logp_llm_large``. ``weight`` 0 keeps the order (and
    does not call the scorer).
    """
    items = [dict(it) for it in items]
    if not items or weight == 0:
        return items
    lps = scorer.score([str(it["text"]) for it in items])
    for it, lp in zip(items, lps):
        it["logp_llm_large"] = float(lp)
        it["score"] = float(it["score"]) + weight * float(lp)
    items.sort(key=lambda d: -float(d["score"]))
    return items


def lattice_words(texts: Iterable[str]) -> frozenset[str]:
    """The word bag of an n-best list (every word of every candidate)."""
    return frozenset(w for t in texts for w in t.split())


def within_lattice(text: str, texts: Iterable[str]) -> bool:
    """True if every word of ``text`` is in the word bag of ``texts`` (and ``text`` is not empty)."""
    bag = lattice_words(texts)
    ws = text.split()
    return bool(ws) and all(w in bag for w in ws)


def _word_confidences(text: str, conf: Sequence[float]) -> list[float]:
    out, pos = [], 0
    cc = list(conf) or [0.0] * len(text)
    for w in text.split(" "):
        out.append(min(cc[pos: pos + len(w)]) if w else 0.0)
        pos += len(w) + 1
    return out


def rewrite_confidences(rewrite: str, items: Sequence[Mapping]) -> list[float]:
    """Character confidences for a rewrite, from the decoder candidates.

    A rewrite word at word position ``k`` gets the largest word confidence
    (min over its characters) among the candidates that have the same word
    at position ``k``; else the largest among the candidates that have the
    word anywhere; else 0. A space gets the min of its two neighbours.
    """
    words = rewrite.split()
    pos_conf: dict[tuple[int, str], float] = {}
    any_conf: dict[str, float] = {}
    for it in items:
        t = str(it["text"])
        cc = it.get("char_confidences") or []
        if not t or (cc and len(cc) != len(t)):
            continue
        wc = _word_confidences(t, cc)
        for k, (w, c) in enumerate(zip(t.split(" "), wc)):
            pos_conf[(k, w)] = max(pos_conf.get((k, w), 0.0), c)
            any_conf[w] = max(any_conf.get(w, 0.0), c)
    wconf = [pos_conf.get((k, w), any_conf.get(w, 0.0)) for k, w in enumerate(words)]
    out: list[float] = []
    for k, w in enumerate(words):
        if k:
            out.append(min(wconf[k], wconf[k - 1]))
        out.extend([wconf[k]] * len(w))
    return out


def add_rewrite(items: Sequence[Mapping], rewrite: str, margin: float = 2.0) -> list[dict]:
    """Put ``rewrite`` on top of the n-best list (score = best score + ``margin``).

    If the rewrite is already a candidate, that candidate moves to the top
    and keeps its fields. Otherwise a new candidate is added with
    :func:`rewrite_confidences` and ``rewrite: True``. An empty rewrite
    returns the list unchanged.
    """
    items = [dict(it) for it in items]
    if not rewrite or not items:
        return items
    best = max(float(it["score"]) for it in items)
    for it in items:
        if it["text"] == rewrite:
            it["score"] = best + margin
            it["rewrite"] = True
            break
    else:
        d = {"text": rewrite, "score": best + margin, "rewrite": True}
        if any(it.get("char_confidences") for it in items):
            d["char_confidences"] = rewrite_confidences(rewrite, items)
        items.append(d)
    items.sort(key=lambda d: -float(d["score"]))
    return items


class CachedScorer:
    """Memo around any :class:`SentenceScorer` (text -> log-prob). ``store`` may be a persistent dict."""

    def __init__(self, inner: SentenceScorer, store: dict | None = None) -> None:
        self.inner = inner
        self.store = {} if store is None else store
        self.calls = 0

    def score(self, texts: Sequence[str]) -> list[float]:
        todo = [t for t in dict.fromkeys(texts) if t not in self.store]
        if todo:
            self.calls += len(todo)
            for t, v in zip(todo, self.inner.score(todo)):
                self.store[t] = float(v)
        return [self.store[t] for t in texts]


class LlamaCppLLM:
    """:class:`SentenceScorer` and :class:`SentenceRewriter` on a local GGUF model (``llama-cpp-python``).

    ``score``: the log-probability of ``text`` + end-of-text after a fixed
    chat prefix (the model's chat template with a short instruction), one
    forward pass per text; the prefix is evaluated once and kept in the KV
    cache. ``rewrite``: greedy decoding (temperature 0) of a short answer.
    CPU only unless ``n_gpu_layers`` is set.
    """

    def __init__(self, model_path: str, *, n_threads: int = 4, n_ctx: int = 1024, seed: int = 0,
                 n_gpu_layers: int = 0, max_tokens: int = 48,
                 score_prefix: str = "<|im_start|>user\nWrite one English sentence.<|im_end|>\n"
                                     "<|im_start|>assistant\n") -> None:
        try:
            from llama_cpp import Llama  # noqa: PLC0415 (optional dependency)
        except ImportError as e:  # pragma: no cover - depends on the environment
            raise ImportError("LlamaCppLLM needs llama-cpp-python (pip install 'fidetype[llm]'; on Windows use "
                              "the CPU wheel index, see docs)") from e
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.seed = seed
        self._llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, n_threads_batch=n_threads,
                          n_gpu_layers=n_gpu_layers, logits_all=True, verbose=False, seed=seed)
        self._prefix = self._llm.tokenize(score_prefix.encode("utf-8"), add_bos=False, special=True)
        self._eos = self._llm.token_eos()
        self._prefix_ready = False

    def _eval_prefix(self) -> None:
        self._llm.reset()
        self._llm.eval(self._prefix)
        self._prefix_ready = True

    def score(self, texts: Sequence[str]) -> list[float]:
        llm, P = self._llm, len(self._prefix)
        out = []
        for t in texts:
            if not self._prefix_ready:
                self._eval_prefix()
            toks = llm.tokenize(t.encode("utf-8"), add_bos=False, special=False) + [self._eos]
            if P + len(toks) > llm.n_ctx():
                out.append(-math.inf)
                continue
            llm.n_tokens = P  # keep the prefix in the KV cache; eval() drops the rest
            llm.eval(toks)
            sc = np.asarray(llm.scores[P - 1: P - 1 + len(toks)], dtype=np.float64)
            m = sc.max(axis=1, keepdims=True)
            lse = m[:, 0] + np.log(np.exp(sc - m).sum(axis=1))
            out.append(float(sum(sc[i, tok] - lse[i] for i, tok in enumerate(toks))))
        return out

    def rewrite(self, nbest_texts: Sequence[str], constrained: bool = True) -> str:
        guesses = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(nbest_texts))
        prompt = (REWRITE_PROMPT_CONSTRAINED if constrained else REWRITE_PROMPT_FREE).format(guesses=guesses)
        self._prefix_ready = False  # generation reuses the context
        r = self._llm.create_chat_completion([{"role": "user", "content": prompt}], temperature=0.0,
                                             max_tokens=self.max_tokens, seed=self.seed)
        text = r["choices"][0]["message"]["content"] or ""
        return normalize_text(text.strip().split("\n")[0])


def prompt_key(nbest_texts: Sequence[str], constrained: bool) -> str:
    """A stable key for a rewrite request (for a persistent memo)."""
    h = hashlib.sha1(("C" if constrained else "F").encode() + "\n".join(nbest_texts).encode("utf-8"))
    return h.hexdigest()


class CachedRewriter:
    """Memo around any :class:`SentenceRewriter`. ``store`` may be a persistent dict."""

    def __init__(self, inner: SentenceRewriter, store: dict | None = None) -> None:
        self.inner = inner
        self.store = {} if store is None else store
        self.calls = 0

    def rewrite(self, nbest_texts: Sequence[str], constrained: bool = True) -> str:
        k = prompt_key(nbest_texts, constrained)
        if k not in self.store:
            self.calls += 1
            self.store[k] = self.inner.rewrite(list(nbest_texts), constrained)
        return self.store[k]


def is_fluent_by_llm(logp: float, n_tokens_or_words: int, threshold_per_unit: float) -> bool:
    """True if ``logp / n`` is at least ``threshold_per_unit`` (the "fluent" test of the fluent-wrong metric)."""
    if n_tokens_or_words <= 0 or not math.isfinite(logp):
        return False
    return logp / n_tokens_or_words >= threshold_per_unit

